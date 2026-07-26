from flask import Flask

from vaultify.extensions import db
from vaultify.models import Organization
from vaultify.services.connector_answer import answer_question_for_connector
from vaultify.services.connector_credentials import (
    create_connector_credential,
    revoke_connector_credential,
)


def build_test_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="connector-answer-test",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    return app


def test_connector_token_binds_trusted_tenant_before_v2():
    app = build_test_app()
    runtime_calls = []
    answer_calls = []

    with app.app_context():
        db.create_all()

        apple = Organization(
            name="Apple Connector Org",
            slug="apple-connector-org",
            tenant_id="tenant_apple_connector",
        )
        tesla = Organization(
            name="Tesla Connector Org",
            slug="tesla-connector-org",
            tenant_id="tenant_tesla_connector",
        )
        db.session.add_all([apple, tesla])
        db.session.commit()

        apple_credential, apple_token = create_connector_credential(apple)
        tesla_credential, tesla_token = create_connector_credential(tesla)

        def tenant_runtime_resolver(tenant_id):
            runtime_calls.append(tenant_id)
            return {
                "runtime_tenant_id": tenant_id,
                "entity_registry": {"tenant": tenant_id},
                "retrieval_indexes": {"tenant": tenant_id},
                "embedding_service": object(),
            }

        def answer_service_spy(tenant_id, question, **kwargs):
            answer_calls.append(
                {
                    "tenant_id": tenant_id,
                    "question": question,
                    "runtime_tenant_id": kwargs["runtime_tenant_id"],
                }
            )
            return {
                "tenant_id": tenant_id,
                "question": question,
                "status": "answered",
                "answer": f"answer for {tenant_id}",
                "sources": [],
                "facts": [],
                "generation_method": "test",
                "llm_called": False,
                "generation_validation": None,
                "verification": {},
            }

        apple_result = answer_question_for_connector(
            apple_token,
            "What were total net sales?",
            tenant_runtime_resolver=tenant_runtime_resolver,
            answer_service=answer_service_spy,
            use_llm=False,
        )
        tesla_result = answer_question_for_connector(
            tesla_token,
            "What was total revenue?",
            tenant_runtime_resolver=tenant_runtime_resolver,
            answer_service=answer_service_spy,
            use_llm=False,
        )

        assert apple_result["tenant_id"] == "tenant_apple_connector"
        assert tesla_result["tenant_id"] == "tenant_tesla_connector"
        assert runtime_calls == [
            "tenant_apple_connector",
            "tenant_tesla_connector",
        ]
        assert [call["tenant_id"] for call in answer_calls] == runtime_calls
        assert all(
            call["tenant_id"] == call["runtime_tenant_id"]
            for call in answer_calls
        )

        runtime_call_count = len(runtime_calls)
        answer_call_count = len(answer_calls)

        for invalid_token in ("unknown-token", "vlt_mcp_unknown"):
            try:
                answer_question_for_connector(
                    invalid_token,
                    "blocked",
                    tenant_runtime_resolver=tenant_runtime_resolver,
                    answer_service=answer_service_spy,
                    use_llm=False,
                )
            except PermissionError:
                pass
            else:
                raise AssertionError("Unknown connector token was accepted.")

        revoke_connector_credential(apple_credential)
        try:
            answer_question_for_connector(
                apple_token,
                "blocked after revoke",
                tenant_runtime_resolver=tenant_runtime_resolver,
                answer_service=answer_service_spy,
                use_llm=False,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("Revoked connector token was accepted.")

        assert len(runtime_calls) == runtime_call_count
        assert len(answer_calls) == answer_call_count

        def mismatched_runtime_resolver(_tenant_id):
            return {
                "runtime_tenant_id": "tenant_attacker",
                "entity_registry": {},
                "retrieval_indexes": {},
                "embedding_service": object(),
            }

        try:
            answer_question_for_connector(
                tesla_token,
                "attempt runtime mismatch",
                tenant_runtime_resolver=mismatched_runtime_resolver,
                answer_service=answer_service_spy,
                use_llm=False,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("Mismatched tenant runtime was accepted.")

        assert len(answer_calls) == answer_call_count
        assert tesla_credential.last_used_at is not None
