"""Organization-scoped connector credential lifecycle helpers."""

import hashlib
import hmac
import secrets

from vaultify.extensions import db
from vaultify.models import ConnectorCredential, Organization, utc_now


CONNECTOR_TOKEN_PREFIX = "vlt_mcp_"
CONNECTOR_RANDOM_BYTES = 32
DEFAULT_CONNECTOR_NAME = "Claude MCP Connector"


def generate_connector_token():
    return CONNECTOR_TOKEN_PREFIX + secrets.token_urlsafe(CONNECTOR_RANDOM_BYTES)


def hash_connector_token(raw_token):
    cleaned_token = str(raw_token or "").strip()
    if not cleaned_token:
        raise ValueError("Connector token cannot be empty.")
    return hashlib.sha256(cleaned_token.encode("utf-8")).hexdigest()


def connector_token_display_prefix(raw_token):
    cleaned_token = str(raw_token or "").strip()
    if not cleaned_token.startswith(CONNECTOR_TOKEN_PREFIX):
        raise ValueError("Invalid Vaultify MCP token format.")
    return cleaned_token[:18]


def create_connector_credential(organization, name=DEFAULT_CONNECTOR_NAME):
    if organization is None:
        raise ValueError("Organization is required.")

    raw_token = generate_connector_token()
    credential = ConnectorCredential(
        organization_id=organization.id,
        name=str(name or DEFAULT_CONNECTOR_NAME).strip(),
        token_hash=hash_connector_token(raw_token),
        token_prefix=connector_token_display_prefix(raw_token),
        is_active=True,
    )
    db.session.add(credential)
    db.session.commit()
    return credential, raw_token


def resolve_connector_credential(raw_token, *, mark_used=False):
    cleaned_token = str(raw_token or "").strip()
    if not cleaned_token.startswith(CONNECTOR_TOKEN_PREFIX):
        return None

    token_hash = hash_connector_token(cleaned_token)
    credential = ConnectorCredential.query.filter_by(
        token_hash=token_hash,
        is_active=True,
    ).first()

    if credential is None:
        return None

    if not hmac.compare_digest(credential.token_hash, token_hash):
        return None

    if mark_used:
        credential.last_used_at = utc_now()
        db.session.commit()

    return credential


def revoke_connector_credential(credential):
    if credential is None:
        raise ValueError("Credential is required.")

    if not credential.is_active:
        return credential

    credential.is_active = False
    credential.revoked_at = utc_now()
    db.session.commit()
    return credential


def rotate_connector_credential(credential):
    if credential is None:
        raise ValueError("Credential is required.")

    organization = db.session.get(Organization, credential.organization_id)
    if organization is None:
        raise RuntimeError("Credential organization no longer exists.")

    credential_name = credential.name
    revoke_connector_credential(credential)
    return create_connector_credential(
        organization=organization,
        name=credential_name,
    )


def connector_credential_to_tenant_id(credential):
    if credential is None:
        raise PermissionError("A valid connector credential is required.")
    if not credential.is_active:
        raise PermissionError("The connector credential has been revoked.")

    organization = db.session.get(Organization, credential.organization_id)
    if organization is None:
        raise PermissionError("The connector organization does not exist.")

    return organization.tenant_id
