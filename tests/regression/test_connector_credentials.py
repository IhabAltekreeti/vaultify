from vaultify.extensions import db
from vaultify.models import ConnectorCredential, Organization
from vaultify.services.connector_credentials import (
    CONNECTOR_TOKEN_PREFIX,
    connector_credential_to_tenant_id,
    create_connector_credential,
    hash_connector_token,
    resolve_connector_credential,
    revoke_connector_credential,
    rotate_connector_credential,
)
from vaultify.web.app import create_app


def _make_app():
    return create_app(
        services={
            "answer_tenant_question": lambda **_kwargs: {
                "answer": "unused",
                "results": [],
            }
        },
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "connector-credential-regression-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        },
    )


def test_connector_credential_lifecycle_matches_golden_behavior():
    app = _make_app()

    with app.app_context():
        db.create_all()

        organization = Organization(
            name="Connector Test Organization",
            slug="connector-test-organization",
            tenant_id="tenant_connector_test",
        )
        db.session.add(organization)
        db.session.commit()

        credential, raw_token = create_connector_credential(
            organization,
            name="Phase 3.8 Runtime Test",
        )

        assert raw_token.startswith(CONNECTOR_TOKEN_PREFIX)
        assert credential.organization_id == organization.id
        assert credential.name == "Phase 3.8 Runtime Test"
        assert credential.is_active is True
        assert credential.revoked_at is None
        assert credential.last_used_at is None
        assert credential.token_hash == hash_connector_token(raw_token)
        assert credential.token_hash != raw_token
        assert credential.token_prefix == raw_token[:18]

        # Plaintext connector secrets must have no persistence column and must not
        # appear in any stored string value for the credential row.
        column_names = {column.name for column in ConnectorCredential.__table__.columns}
        assert "token" not in column_names
        assert "raw_token" not in column_names
        stored_values = [
            getattr(credential, column_name)
            for column_name in column_names
        ]
        assert raw_token not in {value for value in stored_values if isinstance(value, str)}

        resolved = resolve_connector_credential(raw_token)
        assert resolved is not None
        assert resolved.id == credential.id
        assert connector_credential_to_tenant_id(resolved) == "tenant_connector_test"

        assert resolve_connector_credential("vlt_mcp_unknown-token") is None
        assert resolve_connector_credential("not-a-vaultify-token") is None

        used = resolve_connector_credential(raw_token, mark_used=True)
        assert used is not None
        assert used.last_used_at is not None

        old_credential_id = credential.id
        old_raw_token = raw_token
        old_name = credential.name
        old_org_id = credential.organization_id

        replacement, replacement_token = rotate_connector_credential(credential)

        old_credential = db.session.get(ConnectorCredential, old_credential_id)
        assert old_credential is not None
        assert old_credential.is_active is False
        assert old_credential.revoked_at is not None
        assert resolve_connector_credential(old_raw_token) is None

        assert replacement.id != old_credential_id
        assert replacement.organization_id == old_org_id
        assert replacement.name == old_name
        assert replacement.is_active is True
        assert replacement_token != old_raw_token
        assert resolve_connector_credential(replacement_token).id == replacement.id
        assert connector_credential_to_tenant_id(replacement) == "tenant_connector_test"

        revoke_connector_credential(replacement)
        assert replacement.is_active is False
        assert replacement.revoked_at is not None
        assert resolve_connector_credential(replacement_token) is None

        # Revoke remains idempotent.
        revoke_connector_credential(replacement)
        assert replacement.is_active is False
