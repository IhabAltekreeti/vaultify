"""Early R1 Flask request-flow security regression.

This test intentionally uses a deterministic answer-service spy so it proves the
web/auth/tenant boundary without requiring Qdrant, Groq, retrieval, OAuth, or MCP.
"""

from vaultify.extensions import db
from vaultify.models import Membership, Organization, QueryLog, User
from vaultify.web.app import create_app


def test_flask_request_flow_security_gate():
    service_calls = []

    responses = {
        "answered question": {
            "status": "answered",
            "answer": "ANSWERED_RENDERED",
            "results": [],
        },
        "clarification question": {
            "status": "clarification_required",
            "answer": "CLARIFICATION_RENDERED",
            "results": [],
        },
        "no answer question": {
            "status": "no_answer",
            "answer": "NO_ANSWER_RENDERED",
            "results": [],
        },
    }

    def answer_service_spy(*, question, tenant_id):
        service_calls.append(
            {
                "question": question,
                "tenant_id": tenant_id,
            }
        )
        return responses[question]

    app = create_app(
        services={"answer_tenant_question": answer_service_spy},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "r1-security-gate-test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        },
    )

    with app.app_context():
        db.create_all()

        user = User(
            email="security-gate@example.com",
            display_name="Security Gate User",
        )
        user.set_password("Vaultify123")

        trusted_org = Organization(
            name="Trusted Organization",
            slug="trusted-organization-security-gate",
            tenant_id="tenant_trusted_security_gate",
        )

        attacker_org = Organization(
            name="Attacker Organization",
            slug="attacker-organization-security-gate",
            tenant_id="tenant_attacker_security_gate",
        )

        db.session.add_all([user, trusted_org, attacker_org])
        db.session.flush()

        membership = Membership(
            user_id=user.id,
            organization_id=trusted_org.id,
            role="owner",
        )
        db.session.add(membership)
        db.session.commit()

        trusted_user_id = user.id
        trusted_org_id = trusted_org.id
        attacker_org_id = attacker_org.id

    client = app.test_client()

    # 1. Unauthenticated /ask must redirect to login.
    response = client.post(
        "/ask",
        data={"question": "answered question"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert service_calls == []

    # 2. Valid login creates an authenticated session.
    response = client.post(
        "/login",
        data={
            "email": "security-gate@example.com",
            "password": "Vaultify123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Trusted Organization" in response.data

    # 3. Empty questions are rejected before the answer service is called.
    response = client.post(
        "/ask",
        data={"question": "   "},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert service_calls == []

    # Simulate a tampered organization selection in the browser session. The
    # resolver must ignore it because the authenticated user has no membership
    # in attacker_org.
    with client.session_transaction() as session:
        session["organization_id"] = attacker_org_id
        session["tenant_id"] = "tenant_attacker_security_gate"

    # 4. Answered rendering + explicit browser-controlled tenant/org fields.
    response = client.post(
        "/ask",
        data={
            "question": "answered question",
            "tenant_id": "tenant_attacker_security_gate",
            "organization_id": str(attacker_org_id),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"ANSWERED_RENDERED" in response.data

    # Critical tenant-isolation assertion: neither form fields nor the tampered
    # session organization may override the authenticated membership tenant.
    assert service_calls[-1]["tenant_id"] == "tenant_trusted_security_gate"
    assert service_calls[-1]["tenant_id"] != "tenant_attacker_security_gate"

    with client.session_transaction() as session:
        assert session["organization_id"] == trusted_org_id

    # 5. Clarification-required output renders through the real Flask route.
    response = client.post(
        "/ask",
        data={"question": "clarification question"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"CLARIFICATION_RENDERED" in response.data
    assert service_calls[-1]["tenant_id"] == "tenant_trusted_security_gate"

    # 6. No-answer output renders through the real Flask route.
    response = client.post(
        "/ask",
        data={"question": "no answer question"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"NO_ANSWER_RENDERED" in response.data
    assert service_calls[-1]["tenant_id"] == "tenant_trusted_security_gate"

    # 7. Every accepted question is logged against the authenticated user/org.
    with app.app_context():
        logs = QueryLog.query.order_by(QueryLog.id.asc()).all()
        assert len(logs) == 3
        assert [log.question for log in logs] == [
            "answered question",
            "clarification question",
            "no answer question",
        ]
        assert all(log.user_id == trusted_user_id for log in logs)
        assert all(log.organization_id == trusted_org_id for log in logs)

    # Empty question must not have reached the service; only three valid asks did.
    assert len(service_calls) == 3

    # 8. Logout clears authentication; protected routes must redirect again.
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Vaultify sign in" in response.data

    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
