"""Deterministic real-Flask integration regression for the clean V2 answer engine."""

import numpy as np

from vaultify.extensions import db
from vaultify.models import Membership, Organization, QueryLog, User
from vaultify.services.answer_service import answer_question_v2
from vaultify.services.document_catalog import build_document_catalog
from vaultify.services.entity_routing import prepare_entity_retrieval_indexes
from vaultify.web.answer_adapter import create_answer_question_v2_web_adapter
from vaultify.web.app import create_app


ENTITY_RULES = {
    "Apple": {
        "filename_terms": {"apple", "aapl"},
        "content_terms": {"apple inc"},
        "aliases": {"apple", "apple inc", "aapl"},
    },
    "Tesla": {
        "filename_terms": {"tesla", "tsla"},
        "content_terms": {"tesla inc"},
        "aliases": {"tesla", "tesla inc", "tsla"},
    },
}


class FakeEmbeddingService:
    @staticmethod
    def _vector(text):
        normalized = str(text or "").lower()
        vector = np.array(
            [
                1.0 if "sales" in normalized else 0.0,
                1.0 if "revenue" in normalized else 0.0,
                1.0 if "2025" in normalized else 0.0,
            ],
            dtype=np.float32,
        )
        norm = np.linalg.norm(vector)
        if norm == 0:
            return np.array([0.0, 0.0, 1.0], dtype=np.float32)
        return vector / norm

    def encode_documents(self, texts, *, batch_size=32, show_progress_bar=False):
        return np.vstack([self._vector(text) for text in texts])

    def encode_query(self, question):
        return self._vector(question)


def make_chunk(*, point_id, tenant_id, filename, document_hash, text, section):
    return {
        "point_id": point_id,
        "tenant_id": tenant_id,
        "filename": filename,
        "document_hash": document_hash,
        "chunk_index": 0,
        "chunk_type": "text",
        "section": section,
        "text": text,
        "payload": {},
    }


def test_real_flask_route_uses_clean_v2_answer_engine():
    tenant_id = "tenant_flask_v2"
    chunks = [
        make_chunk(
            point_id="apple-1",
            tenant_id=tenant_id,
            filename="apple_fy2025_10k.pdf",
            document_hash="apple_hash",
            section="Note 2 - Revenue",
            text=(
                "Apple Inc. Dollars in millions. Fiscal year 2025 total net sales "
                "were 416,161."
            ),
        ),
        make_chunk(
            point_id="tesla-1",
            tenant_id=tenant_id,
            filename="tesla_q4_2025_update.pdf",
            document_hash="tesla_hash",
            section="Financial Statements",
            text=(
                "Tesla Inc. Dollars in millions. Q4 2025 total revenue was 24,901."
            ),
        ),
    ]

    catalog, registry = build_document_catalog(
        chunks,
        tenant_id,
        entity_rules=ENTITY_RULES,
    )
    embeddings = FakeEmbeddingService()
    indexes = prepare_entity_retrieval_indexes(catalog, registry, embeddings)

    runtime_provider_calls = []

    def runtime_provider(trusted_tenant_id):
        runtime_provider_calls.append(trusted_tenant_id)
        if trusted_tenant_id != tenant_id:
            raise PermissionError("No prepared runtime exists for this tenant.")
        return {
            "runtime_tenant_id": tenant_id,
            "entity_registry": registry,
            "retrieval_indexes": indexes,
            "embedding_service": embeddings,
            "top_k_per_entity": 6,
        }

    adapter = create_answer_question_v2_web_adapter(
        answer_service=answer_question_v2,
        runtime_provider=runtime_provider,
        use_llm=False,
    )

    app = create_app(
        services={"answer_tenant_question": adapter},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "r1-flask-v2-integration-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        },
    )

    with app.app_context():
        db.create_all()

        user = User(
            email="flask-v2@example.com",
            display_name="Flask V2 User",
        )
        user.set_password("Vaultify123")

        trusted_org = Organization(
            name="Flask V2 Organization",
            slug="flask-v2-organization",
            tenant_id=tenant_id,
        )
        attacker_org = Organization(
            name="Untrusted Organization",
            slug="untrusted-flask-v2-organization",
            tenant_id="tenant_untrusted_flask_v2",
        )
        db.session.add_all([user, trusted_org, attacker_org])
        db.session.flush()

        db.session.add(
            Membership(
                user_id=user.id,
                organization_id=trusted_org.id,
                role="owner",
            )
        )
        db.session.commit()

        trusted_user_id = user.id
        trusted_org_id = trusted_org.id
        attacker_org_id = attacker_org.id

    client = app.test_client()

    unauthenticated = client.post(
        "/ask",
        data={"question": "What were Apple's total net sales in fiscal year 2025?"},
        follow_redirects=False,
    )
    assert unauthenticated.status_code == 302
    assert runtime_provider_calls == []

    login = client.post(
        "/login",
        data={"email": "flask-v2@example.com", "password": "Vaultify123"},
        follow_redirects=True,
    )
    assert login.status_code == 200
    assert b"Flask V2 Organization" in login.data

    # Tamper with both session and form tenant/org values. The membership resolver
    # must restore the trusted organization before the V2 runtime is selected.
    with client.session_transaction() as browser_session:
        browser_session["organization_id"] = attacker_org_id
        browser_session["tenant_id"] = "tenant_untrusted_flask_v2"

    apple = client.post(
        "/ask",
        data={
            "question": "What were Apple's total net sales in fiscal year 2025?",
            "tenant_id": "tenant_untrusted_flask_v2",
            "organization_id": str(attacker_org_id),
        },
        follow_redirects=True,
    )
    assert apple.status_code == 200
    assert b"416,161" in apple.data
    assert b"million" in apple.data
    assert b"apple_fy2025_10k.pdf" in apple.data
    assert runtime_provider_calls[-1] == tenant_id

    with client.session_transaction() as browser_session:
        assert browser_session["organization_id"] == trusted_org_id

    tesla = client.post(
        "/ask",
        data={"question": "What was Tesla's total revenue in Q4 2025?"},
        follow_redirects=True,
    )
    assert tesla.status_code == 200
    assert b"24,901" in tesla.data
    assert b"million" in tesla.data
    assert b"tesla_q4_2025_update.pdf" in tesla.data

    comparison = client.post(
        "/ask",
        data={
            "question": (
                "Compare Apple's fiscal 2025 net sales with Tesla's Q4 2025 revenue."
            )
        },
        follow_redirects=True,
    )
    assert comparison.status_code == 200
    assert b"416,161" in comparison.data
    assert b"24,901" in comparison.data
    assert b"apple_fy2025_10k.pdf" in comparison.data
    assert b"tesla_q4_2025_update.pdf" in comparison.data

    ambiguous = client.post(
        "/ask",
        data={"question": "What was the total revenue in 2025?"},
        follow_redirects=True,
    )
    assert ambiguous.status_code == 200
    assert b"Which company do you mean" in ambiguous.data

    outside = client.post(
        "/ask",
        data={"question": "Who wrote Pride and Prejudice?"},
        follow_redirects=True,
    )
    assert outside.status_code == 200
    assert b"could not identify relevant evidence" in outside.data

    with app.app_context():
        logs = QueryLog.query.order_by(QueryLog.id.asc()).all()
        assert len(logs) == 5
        assert all(log.user_id == trusted_user_id for log in logs)
        assert all(log.organization_id == trusted_org_id for log in logs)
        assert logs[0].source_count == 1
        assert logs[1].source_count == 1
        assert logs[2].source_count == 2
        assert logs[3].source_count == 0
        assert logs[4].source_count == 0
        assert "416,161" in logs[0].answer
        assert "24,901" in logs[1].answer

    assert runtime_provider_calls == [tenant_id] * 5
