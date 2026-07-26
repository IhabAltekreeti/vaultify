"""OAuth-protected Vaultify MCP resource-server construction.

This module binds the extracted OAuth protocol core to the existing clean V2
runtime without accepting tenant or organization identity from the MCP client.
It does not launch a server or create a public tunnel.
"""

from typing import Any, Callable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import AnyHttpUrl

from vaultify.mcp.server import serialize_mcp_sources
from vaultify.oauth.server import VAULTIFY_OAUTH_SCOPE, resolve_oauth_access_token
from vaultify.services.answer_service import answer_question_v2


def _normalize_resource_url(value):
    return str(value or "").strip().rstrip("/")


def _scope_contains_mcp(scope):
    return VAULTIFY_OAUTH_SCOPE in {
        item for item in str(scope or "").split() if item
    }


def resolve_oauth_mcp_identity(
    *,
    state_store,
    raw_access_token,
    connector_identity_is_active,
    resource_server_url,
    now=None,
):
    """Resolve a valid OAuth access token for exactly one MCP resource."""
    record = resolve_oauth_access_token(
        state_store,
        raw_access_token,
        connector_identity_is_active=connector_identity_is_active,
        now=now,
    )
    if record is None:
        return None

    expected_resource = _normalize_resource_url(resource_server_url)
    token_resource = _normalize_resource_url(record.get("resource"))

    if not expected_resource or token_resource != expected_resource:
        return None
    if not _scope_contains_mcp(record.get("scope")):
        return None

    return record


class VaultifyOAuthAccessTokenVerifier(TokenVerifier):
    """Validate resource-bound OAuth tokens and re-check connector identity."""

    def __init__(
        self,
        *,
        flask_app,
        state_store,
        connector_identity_is_active,
        resource_server_url,
        now_provider=None,
    ):
        self.flask_app = flask_app
        self.state_store = state_store
        self.connector_identity_is_active = connector_identity_is_active
        self.resource_server_url = resource_server_url
        self.now_provider = now_provider

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            now = self.now_provider() if self.now_provider is not None else None
            with self.flask_app.app_context():
                record = resolve_oauth_mcp_identity(
                    state_store=self.state_store,
                    raw_access_token=token,
                    connector_identity_is_active=self.connector_identity_is_active,
                    resource_server_url=self.resource_server_url,
                    now=now,
                )
        except Exception:
            return None

        if record is None:
            return None

        return AccessToken(
            token=token,
            client_id=str(record["client_id"]),
            scopes=[VAULTIFY_OAUTH_SCOPE],
        )


def answer_question_for_oauth_access_token(
    raw_access_token,
    question,
    *,
    state_store,
    connector_identity_is_active,
    tenant_runtime_resolver,
    resource_server_url,
    answer_service=answer_question_v2,
    now=None,
    use_llm=True,
):
    """Resolve OAuth identity to one trusted tenant and execute clean V2."""
    record = resolve_oauth_mcp_identity(
        state_store=state_store,
        raw_access_token=raw_access_token,
        connector_identity_is_active=connector_identity_is_active,
        resource_server_url=resource_server_url,
        now=now,
    )
    if record is None:
        raise PermissionError("Invalid, revoked, expired, or wrong-resource OAuth token.")

    tenant_id = str(record.get("tenant_id") or "").strip()
    if not tenant_id:
        raise PermissionError("OAuth identity has no trusted tenant.")

    runtime = tenant_runtime_resolver(tenant_id)
    if runtime is None:
        raise RuntimeError("No Vaultify V2 runtime is available for this tenant.")
    if not isinstance(runtime, dict):
        raise TypeError("The tenant runtime resolver must return a dictionary.")

    required_runtime_keys = {
        "runtime_tenant_id",
        "entity_registry",
        "retrieval_indexes",
        "embedding_service",
    }
    missing_keys = sorted(required_runtime_keys - set(runtime))
    if missing_keys:
        raise RuntimeError(
            "The tenant runtime is incomplete: " + ", ".join(missing_keys)
        )

    runtime_tenant_id = str(runtime["runtime_tenant_id"] or "").strip()
    if runtime_tenant_id != tenant_id:
        raise PermissionError(
            "The resolved V2 runtime belongs to a different tenant."
        )

    answer_kwargs = {
        "runtime_tenant_id": runtime_tenant_id,
        "entity_registry": runtime["entity_registry"],
        "retrieval_indexes": runtime["retrieval_indexes"],
        "embedding_service": runtime["embedding_service"],
        "use_llm": use_llm,
    }

    for optional_key in (
        "groq_client",
        "model",
        "top_k_per_entity",
        "metric_expansions",
    ):
        if optional_key in runtime:
            answer_kwargs[optional_key] = runtime[optional_key]

    return answer_service(
        tenant_id,
        question,
        **answer_kwargs,
    )


def create_oauth_protected_mcp_server(
    *,
    flask_app,
    state_store,
    connector_identity_is_active,
    tenant_runtime_resolver: Callable[[str], dict],
    resource_server_url: str,
    issuer_url: str,
    use_llm: bool = True,
    answer_service=answer_question_v2,
    now_provider=None,
    transport_security=None,
):
    """Create the OAuth-protected Streamable HTTP Vaultify MCP server."""
    if flask_app is None:
        raise ValueError("flask_app is required.")
    if state_store is None:
        raise ValueError("state_store is required.")
    if not callable(connector_identity_is_active):
        raise TypeError("connector_identity_is_active must be callable.")
    if not callable(tenant_runtime_resolver):
        raise TypeError("tenant_runtime_resolver must be callable.")

    resource_server_url = str(resource_server_url or "").strip()
    issuer_url = str(issuer_url or "").strip()
    if not resource_server_url:
        raise ValueError("resource_server_url is required.")
    if not issuer_url:
        raise ValueError("issuer_url is required.")

    token_verifier = VaultifyOAuthAccessTokenVerifier(
        flask_app=flask_app,
        state_store=state_store,
        connector_identity_is_active=connector_identity_is_active,
        resource_server_url=resource_server_url,
        now_provider=now_provider,
    )

    mcp_kwargs = {
        "name": "Vaultify",
        "stateless_http": True,
        "json_response": True,
        "token_verifier": token_verifier,
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url),
            resource_server_url=AnyHttpUrl(resource_server_url),
            required_scopes=[VAULTIFY_OAUTH_SCOPE],
        ),
    }
    if transport_security is not None:
        mcp_kwargs["transport_security"] = transport_security

    mcp = FastMCP(**mcp_kwargs)

    @mcp.tool()
    def ask_documents(question: str) -> dict[str, Any]:
        """Answer from the OAuth-authorized organization's documents."""
        cleaned_question = str(question or "").strip()
        if not cleaned_question:
            raise ToolError("The question cannot be empty.")

        verified_access_token = get_access_token()
        if verified_access_token is None:
            raise ToolError("OAuth authentication is required.")

        try:
            now = now_provider() if now_provider is not None else None
            with flask_app.app_context():
                result = answer_question_for_oauth_access_token(
                    verified_access_token.token,
                    cleaned_question,
                    state_store=state_store,
                    connector_identity_is_active=connector_identity_is_active,
                    tenant_runtime_resolver=tenant_runtime_resolver,
                    resource_server_url=resource_server_url,
                    answer_service=answer_service,
                    now=now,
                    use_llm=use_llm,
                )
        except PermissionError as error:
            raise ToolError(
                "The OAuth credential is invalid, revoked, expired, or not valid for this resource."
            ) from error
        except Exception as error:
            raise ToolError(
                "Vaultify could not process the document question."
            ) from error

        return {
            "status": result.get("status"),
            "answer": result.get("answer", ""),
            "sources": serialize_mcp_sources(result.get("sources", [])),
        }

    return mcp, ask_documents


__all__ = [
    "VaultifyOAuthAccessTokenVerifier",
    "answer_question_for_oauth_access_token",
    "create_oauth_protected_mcp_server",
    "resolve_oauth_mcp_identity",
]
