import io
import re

import numpy as np

from vaultify.extensions import db
from vaultify.models import Document, Membership, Organization, User
from vaultify.web.app import create_app


class FakeTokenizer:
    def __init__(self):
        self._token_to_id = {}
        self._id_to_token = {}
        self._next_id = 1000

    def _tokens(self, text):
        return re.findall(r"\S+", str(text or ""))

    def _id(self, token):
        if token not in self._token_to_id:
            token_id = self._next_id
            self._next_id += 1
            self._token_to_id[token] = token_id
            self._id_to_token[token_id] = token
        return self._token_to_id[token]

    def __call__(self, text, *, add_special_tokens, **_kwargs):
        ids = [self._id(token) for token in self._tokens(text)]
        if add_special_tokens:
            ids = [101] + ids + [102]
        return {"input_ids": ids}

    def decode(self, token_ids, **_kwargs):
        return " ".join(
            self._id_to_token[token_id]
            for token_id in token_ids
            if token_id in self._id_to_token
        )


class FakeModel:
    max_seq_length = 256

    def __init__(self):
        self.tokenizer = FakeTokenizer()


class FakeEmbeddingService:
    def __init__(self):
        self.model = FakeModel()

    def encode_documents(self, texts, *, batch_size=32, show_progress_bar=False):
        assert batch_size == 64
        return np.vstack(
            [np.full(384, index + 1, dtype=np.float32) for index, _ in enumerate(texts)]
        )


class FakeConvertedDocument:
    def export_to_markdown(self):
        return (
            "# Revenue\n\n"
            "Dollars in millions.\n\n"
            "| Metric | 2025 | 2024 |\n"
            "|---|---|---|\n"
            "| Total net sales | 416,161 | 391,035 |"
        )


class FakeConversionResult:
    document = FakeConvertedDocument()


class FakeConverter:
    def convert(self, _path):
        return FakeConversionResult()


class FakeQdrant:
    def __init__(self):
        self.delete_calls = []
        self.upsert_calls = []

    def delete(self, *, collection_name, points_selector, wait):
        self.delete_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
                "wait": wait,
            }
        )

    def upsert(self, *, collection_name, points, wait):
        self.upsert_calls.append(
            {
                "collection_name": collection_name,
                "points": list(points),
                "wait": wait,
            }
        )


def _filter_values(delete_call):
    conditions = delete_call["points_selector"].filter.must
    return {condition.key: condition.match.value for condition in conditions}


def test_trusted_document_upload_retry_delete_flow(tmp_path):
    qdrant = FakeQdrant()
    embedding_service = FakeEmbeddingService()

    app = create_app(
        services={
            "answer_tenant_question": lambda **_kwargs: {"answer": "unused", "results": []},
            "embedding_service": embedding_service,
            "qdrant": qdrant,
            "converter": FakeConverter(),
            "collection_name": "vaultify_test_documents",
        },
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "document-management-regression",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        },
    )

    with app.app_context():
        db.create_all()

        user = User(email="documents@example.com", display_name="Documents User")
        user.set_password("Vaultify123")
        trusted_org = Organization(
            name="Trusted Documents Org",
            slug="trusted-documents-org",
            tenant_id="tenant_trusted_documents",
        )
        attacker_org = Organization(
            name="Attacker Documents Org",
            slug="attacker-documents-org",
            tenant_id="tenant_attacker_documents",
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

        trusted_org_id = trusted_org.id
        attacker_org_id = attacker_org.id

    client = app.test_client()
    login = client.post(
        "/login",
        data={"email": "documents@example.com", "password": "Vaultify123"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    listing = client.get("/documents")
    assert listing.status_code == 200
    assert b"No documents yet" in listing.data

    pdf_bytes = b"%PDF-1.7\nVaultify document route regression"
    upload = client.post(
        "/documents/upload",
        data={
            "file": (io.BytesIO(pdf_bytes), "Quarterly Report.pdf"),
            "organization_id": str(attacker_org_id),
            "tenant_id": "tenant_attacker_documents",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert upload.status_code == 200
    assert b"Quarterly Report.pdf" in upload.data

    with app.app_context():
        documents = Document.query.order_by(Document.id.asc()).all()
        assert len(documents) == 1
        trusted_document = documents[0]
        assert trusted_document.organization_id == trusted_org_id
        assert trusted_document.status == "ready"
        assert trusted_document.chunk_count > 0
        trusted_document_id = trusted_document.id
        trusted_hash = trusted_document.document_hash
        trusted_path = trusted_document.storage_path

    assert qdrant.upsert_calls
    uploaded_points = [
        point
        for call in qdrant.upsert_calls
        for point in call["points"]
    ]
    assert uploaded_points
    assert all(
        point.payload["tenant_id"] == "tenant_trusted_documents"
        for point in uploaded_points
    )

    duplicate = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(pdf_bytes), "Different Name.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert duplicate.status_code == 200
    assert b"already exists" in duplicate.data

    with app.app_context():
        assert Document.query.filter_by(organization_id=trusted_org_id).count() == 1

        attacker_path = tmp_path / "attacker.pdf"
        attacker_path.write_bytes(b"%PDF-1.7\nattacker")
        attacker_document = Document(
            organization_id=attacker_org_id,
            original_filename="attacker.pdf",
            stored_filename="attacker-unique.pdf",
            storage_path=str(attacker_path),
            mime_type="application/pdf",
            size_bytes=20,
            document_hash="b" * 64,
            status="ready",
            chunk_count=1,
        )
        db.session.add(attacker_document)
        db.session.commit()
        attacker_document_id = attacker_document.id

        trusted_document = db.session.get(Document, trusted_document_id)
        trusted_document.status = "failed"
        trusted_document.chunk_count = 0
        db.session.commit()

    cross_retry = client.post(
        f"/documents/{attacker_document_id}/retry",
        follow_redirects=False,
    )
    assert cross_retry.status_code == 404

    cross_delete = client.post(
        f"/documents/{attacker_document_id}/delete",
        follow_redirects=False,
    )
    assert cross_delete.status_code == 404

    retry = client.post(
        f"/documents/{trusted_document_id}/retry",
        follow_redirects=True,
    )
    assert retry.status_code == 200
    assert b"indexed with" in retry.data

    with app.app_context():
        trusted_document = db.session.get(Document, trusted_document_id)
        assert trusted_document.status == "ready"
        assert trusted_document.chunk_count > 0
        assert db.session.get(Document, attacker_document_id) is not None

    delete = client.post(
        f"/documents/{trusted_document_id}/delete",
        follow_redirects=True,
    )
    assert delete.status_code == 200
    assert b"deleted from storage and Qdrant" in delete.data

    with app.app_context():
        assert db.session.get(Document, trusted_document_id) is None
        assert db.session.get(Document, attacker_document_id) is not None

    assert not (tmp_path / "uploads" / trusted_path.split("/")[-1]).exists()

    trusted_deletes = [
        call
        for call in qdrant.delete_calls
        if _filter_values(call).get("document_hash") == trusted_hash
    ]
    assert trusted_deletes
    assert all(
        _filter_values(call)["tenant_id"] == "tenant_trusted_documents"
        for call in trusted_deletes
    )
    assert all(
        _filter_values(call)["tenant_id"] != "tenant_attacker_documents"
        for call in trusted_deletes
    )
