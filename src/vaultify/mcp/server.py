"""Authenticated Vaultify MCP resource-server construction."""

from typing import Any, Callable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import AnyHttpUrl

from vaultify.services.connector_answer import answer_question_for_connector
from vaultify.services.connector_credentials import (
    connector_credential_to_tenant_id,
    resolve_connector_credential,
)


MCP_SCOPE = "vaultify:mcp"


class VaultifyConnectorTokenVerifier(TokenVerifier):
    """Fail closed unless a connector token resolves to an active organization."""

    def __init__(self, flask_app):
        self.flask_app = flask_app

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            with self.flask_app.app_context():
                credential = resolve_connector_credential(
                    token,
                    mark_used=False,
                )
                if credential is None:
                    return None

                # This also proves that the owning organization still exists and
                # that tenant identity is derived only from that organization.
                connector_credential_to_tenant_id(credential)

                credential_id = credential.id
        except Exception:
            return None

        return AccessToken(
            token=token,
            client_id=f"vaultify-connector-{credential_id}",
            scopes=[MCP_SCOPE],
        )


def serialize_mcp_sources(sources):
    """Return non-sensitive source metadata for the public MCP response."""
    serialized = []

    for source in sources or []:
        if not isinstance(source, dict):
            continue

        serialized.append(
            {
                "filename": source.get("filename"),
                "section": source.get("section"),
                "entity": source.get("entity"),
                "chunk_type": source.get("chunk_type"),
                "chunk_index": source.get("chunk_index"),
            }
        )

    return serialized


def create_authenticated_mcp_server(
    *,
    flask_app,
    tenant_runtime_resolver: Callable[[str], dict],
    resource_server_url: str,
    issuer_url: str,
    use_llm: bool = True,
    connector_answer_service=answer_question_for_connector,
    transport_security=None,
):
    """Create the authenticated Streamable HTTP Vaultify MCP server.

    The public tool contract exposes only ``question``. Tenant and organization
    identity come from the HTTP bearer token and are never accepted as tool
    arguments or returned as public MCP metadata.
    """
    if flask_app is None:
        raise ValueError("flask_app is required.")
    if not callable(tenant_runtime_resolver):
        raise TypeError("tenant_runtime_resolver must be callable.")

    resource_server_url = str(resource_server_url or "").strip()
    issuer_url = str(issuer_url or "").strip()

    if not resource_server_url:
        raise ValueError("resource_server_url is required.")
    if not issuer_url:
        raise ValueError("issuer_url is required.")

    mcp_kwargs = {
        "name": "Vaultify",
        "stateless_http": True,
        "json_response": True,
        "token_verifier": VaultifyConnectorTokenVerifier(flask_app),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl(issuer_url),
            resource_server_url=AnyHttpUrl(resource_server_url),
            required_scopes=[MCP_SCOPE],
        ),
    }

    if transport_security is not None:
        mcp_kwargs["transport_security"] = transport_security

    mcp = FastMCP(**mcp_kwargs)

    @mcp.tool()
    def ask_documents(question: str) -> dict[str, Any]:
        """Answer from documents owned by the bearer-authenticated organization."""
        cleaned_question = str(question or "").strip()
        if not cleaned_question:
            raise ToolError("The question cannot be empty.")

        verified_access_token = get_access_token()
        if verified_access_token is None:
            raise ToolError("Connector authentication is required.")

        try:
            with flask_app.app_context():
                result = connector_answer_service(
                    verified_access_token.token,
                    cleaned_question,
                    tenant_runtime_resolver=tenant_runtime_resolver,
                    use_llm=use_llm,
                )
        except PermissionError as error:
            raise ToolError(
                "The connector credential is invalid or has been revoked."
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
