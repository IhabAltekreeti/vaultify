"""R1 Step 25 regression: OAuth access token -> protected MCP -> trusted V2 tenant."""

import inspect
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

from vaultify.extensions import db
from vaultify.mcp.oauth_server import create_oauth_protected_mcp_server
from vaultify.models import ConnectorCredential, Organization
from vaultify.oauth.server import (
    VAULTIFY_OAUTH_SCOPE,
    create_oauth_authorization_server,
    oauth_base64url_sha256,
)
from vaultify.services.connector_credentials import (
    create_connector_credential,
    revoke_connector_credential,
)
from vaultify.web.app import create_app


class MemoryOAuthStateStore:
    """Regression-only OAuth state. R2 will provide persistence."""

    def __init__(self):
        self.clients = {}
        self.authorization_codes = {}
        self.access_tokens = {}
        self.refresh_tokens = {}

    def put_client(self, client_id, value):
        self.clients[client_id] = dict(value)

    def get_client(self, client_id):
        value = self.clients.get(client_id)
        return dict(value) if value is not None else None

    def put_authorization_code(self, secret_hash, value):
        self.authorization_codes[secret_hash] = dict(value)

    def pop_authorization_code(self, secret_hash):
        return self.authorization_codes.pop(secret_hash, None)

    def put_access_token(self, secret_hash, value):
        self.access_tokens[secret_hash] = dict(value)

    def get_access_token(self, secret_hash):
        value = self.access_tokens.get(secret_hash)
        return dict(value) if value is not None else None

    def pop_access_token(self, secret_hash):
        return self.access_tokens.pop(secret_hash, None)

    def put_refresh_token(self, secret_hash, value):
        self.refresh_tokens[secret_hash] = dict(value)

    def pop_refresh_token(self, secret_hash):
        return self.refresh_tokens.pop(secret_hash, None)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def parse_tool_payload(tool_result):
    assert not tool_result.isError
    structured = tool_result.structuredContent
    if isinstance(structured, dict) and isinstance(structured.get("result"), dict):
        return structured["result"]
    if isinstance(structured, dict):
        return structured
    raise AssertionError("MCP tool result did not contain structured content.")


async def call_mcp(http_app, raw_token, question):
    headers = {}
    if raw_token is not None:
        headers["Authorization"] = f"Bearer {raw_token}"

    transport = httpx.ASGITransport(app=http_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=headers,
        timeout=10.0,
    ) as http_client:
        async with streamable_http_client(
            "http://testserver/mcp",
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool(
                    "ask_documents",
                    {"question": question},
                )
                return tools.tools, result


async def request_is_rejected(http_app, raw_token):
    try:
        await call_mcp(http_app, raw_token, "What was total revenue?")
    except BaseException:
        return True
    return False


def issue_oauth_tokens(
    oauth_client,
    client_identity_map,
    identity,
    *,
    resource,
    label,
):
    registration = oauth_client.post(
        "/register",
        json={
            "client_name": f"{label} OAuth Client",
            "redirect_uris": [f"https://client.example/{label}/callback"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert registration.status_code == 201
    client_id = registration.json()["client_id"]
    client_identity_map[client_id] = dict(identity)

    verifier = f"{label}-vaultify-pkce-verifier-abcdefghijklmnopqrstuvwxyz0123456789"
    challenge = oauth_base64url_sha256(verifier)
    redirect_uri = f"https://client.example/{label}/callback"

    approval = oauth_client.post(
        "/authorize",
        data={
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": VAULTIFY_OAUTH_SCOPE,
            "state": f"state-{label}",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
        },
        follow_redirects=False,
    )
    assert approval.status_code == 303
    code = parse_qs(urlparse(approval.headers["location"]).query)["code"][0]

    token_response = oauth_client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    assert token_response.status_code == 200
    return token_response.json()


@pytest.mark.anyio
async def test_oauth_access_token_protects_mcp_and_preserves_trusted_tenant_identity(tmp_path):
    flask_app = create_app(
        services={"answer_tenant_question": lambda **_: None},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "r1-oauth-mcp-test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        },
    )

    with flask_app.app_context():
        db.create_all()
        apple_org = Organization(
            name="Apple OAuth MCP Organization",
            slug="apple-oauth-mcp-organization",
            tenant_id="tenant_oauth_mcp_apple",
        )
        tesla_org = Organization(
            name="Tesla OAuth MCP Organization",
            slug="tesla-oauth-mcp-organization",
            tenant_id="tenant_oauth_mcp_tesla",
        )
        db.session.add_all([apple_org, tesla_org])
        db.session.commit()

        apple_credential, apple_connector_token = create_connector_credential(
            apple_org,
            name="Apple OAuth MCP Test",
        )
        tesla_credential, _ = create_connector_credential(
            tesla_org,
            name="Tesla OAuth MCP Test",
        )

        apple_identity = {
            "credential_id": apple_credential.id,
            "organization_id": apple_org.id,
            "tenant_id": apple_org.tenant_id,
        }
        tesla_identity = {
            "credential_id": tesla_credential.id,
            "organization_id": tesla_org.id,
            "tenant_id": tesla_org.tenant_id,
        }
        tesla_credential_id = tesla_credential.id

    state_store = MemoryOAuthStateStore()
    client_identity_map = {}

    async def authorization_identity_resolver(request, normalized):
        identity = client_identity_map.get(normalized["client_id"])
        if identity is None:
            raise PermissionError("No trusted connector identity is assigned.")
        return dict(identity)

    def connector_identity_is_active(credential_id, organization_id, tenant_id):
        with flask_app.app_context():
            credential = db.session.get(ConnectorCredential, credential_id)
            organization = db.session.get(Organization, organization_id)
            return bool(
                credential is not None
                and credential.is_active
                and credential.organization_id == organization_id
                and organization is not None
                and organization.tenant_id == tenant_id
            )

    issuer_url = "https://oauth.vaultify.example"
    resource_url = "http://testserver/mcp"
    fixed_now = 1_800_000_000

    oauth_app = create_oauth_authorization_server(
        issuer_url=issuer_url,
        state_store=state_store,
        authorization_identity_resolver=authorization_identity_resolver,
        connector_identity_is_active=connector_identity_is_active,
        now_provider=lambda: fixed_now,
    )
    oauth_client = TestClient(oauth_app)

    apple_tokens = issue_oauth_tokens(
        oauth_client,
        client_identity_map,
        apple_identity,
        resource=resource_url,
        label="apple",
    )
    tesla_tokens = issue_oauth_tokens(
        oauth_client,
        client_identity_map,
        tesla_identity,
        resource=resource_url,
        label="tesla",
    )
    wrong_resource_tokens = issue_oauth_tokens(
        oauth_client,
        client_identity_map,
        apple_identity,
        resource="http://other-resource.example/mcp",
        label="wrong-resource",
    )

    runtimes = {
        "tenant_oauth_mcp_apple": {
            "runtime_tenant_id": "tenant_oauth_mcp_apple",
            "entity_registry": {},
            "retrieval_indexes": {},
            "embedding_service": object(),
        },
        "tenant_oauth_mcp_tesla": {
            "runtime_tenant_id": "tenant_oauth_mcp_tesla",
            "entity_registry": {},
            "retrieval_indexes": {},
            "embedding_service": object(),
        },
    }
    answer_calls = []

    def tenant_runtime_resolver(tenant_id):
        return runtimes.get(tenant_id)

    def answer_service_spy(tenant_id, question, **kwargs):
        assert kwargs["runtime_tenant_id"] == tenant_id
        answer_calls.append(
            {
                "tenant_id": tenant_id,
                "question": question,
                "use_llm": kwargs["use_llm"],
            }
        )
        is_apple = tenant_id == "tenant_oauth_mcp_apple"
        return {
            "status": "answered",
            "answer": "APPLE_OAUTH_MCP_OK" if is_apple else "TESLA_OAUTH_MCP_OK",
            "sources": [
                {
                    "filename": "apple.pdf" if is_apple else "tesla.pdf",
                    "section": "Revenue",
                    "entity": "Apple" if is_apple else "Tesla",
                    "chunk_type": "table",
                    "chunk_index": 3,
                    "text": "RAW_CHUNK_TEXT_MUST_NOT_LEAK",
                    "tenant_id": tenant_id,
                    "organization_id": 999,
                }
            ],
        }

    mcp, ask_documents = create_oauth_protected_mcp_server(
        flask_app=flask_app,
        state_store=state_store,
        connector_identity_is_active=connector_identity_is_active,
        tenant_runtime_resolver=tenant_runtime_resolver,
        resource_server_url=resource_url,
        issuer_url=issuer_url,
        use_llm=False,
        answer_service=answer_service_spy,
        now_provider=lambda: fixed_now + 1,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    parameters = set(inspect.signature(ask_documents).parameters)
    assert parameters == {"question"}
    assert "tenant_id" not in parameters
    assert "organization_id" not in parameters

    http_app = mcp.streamable_http_app()

    async with mcp.session_manager.run():
        transport = httpx.ASGITransport(app=http_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as metadata_client:
            metadata = await metadata_client.get(
                "/.well-known/oauth-protected-resource/mcp"
            )
        assert metadata.status_code == 200
        metadata_payload = metadata.json()
        assert metadata_payload["resource"].rstrip("/") == resource_url.rstrip("/")
        assert [value.rstrip("/") for value in metadata_payload["authorization_servers"]] == [
            issuer_url.rstrip("/")
        ]

        assert await request_is_rejected(http_app, None)
        assert await request_is_rejected(http_app, apple_connector_token)
        assert await request_is_rejected(http_app, "vlt_oauth_at_unknown-token")
        assert await request_is_rejected(
            http_app,
            wrong_resource_tokens["access_token"],
        )
        assert answer_calls == []

        apple_tools, apple_result = await call_mcp(
            http_app,
            apple_tokens["access_token"],
            "Apple question",
        )
        apple_payload = parse_tool_payload(apple_result)
        assert [tool.name for tool in apple_tools] == ["ask_documents"]
        assert set(apple_tools[0].inputSchema.get("properties", {})) == {"question"}
        assert apple_payload == {
            "status": "answered",
            "answer": "APPLE_OAUTH_MCP_OK",
            "sources": [
                {
                    "filename": "apple.pdf",
                    "section": "Revenue",
                    "entity": "Apple",
                    "chunk_type": "table",
                    "chunk_index": 3,
                }
            ],
        }

        _, tesla_result = await call_mcp(
            http_app,
            tesla_tokens["access_token"],
            "Tesla question",
        )
        tesla_payload = parse_tool_payload(tesla_result)
        assert tesla_payload["answer"] == "TESLA_OAUTH_MCP_OK"
        assert tesla_payload["sources"][0]["filename"] == "tesla.pdf"
        assert [call["tenant_id"] for call in answer_calls] == [
            "tenant_oauth_mcp_apple",
            "tenant_oauth_mcp_tesla",
        ]

        with flask_app.app_context():
            tesla_credential = db.session.get(
                ConnectorCredential,
                tesla_credential_id,
            )
            revoke_connector_credential(tesla_credential)

        calls_before_connector_revoke = len(answer_calls)
        assert await request_is_rejected(http_app, tesla_tokens["access_token"])
        assert len(answer_calls) == calls_before_connector_revoke

        _, apple_again = await call_mcp(
            http_app,
            apple_tokens["access_token"],
            "Apple remains valid",
        )
        assert parse_tool_payload(apple_again)["answer"] == "APPLE_OAUTH_MCP_OK"

        revoke = oauth_client.post(
            "/revoke",
            data={"token": apple_tokens["access_token"]},
        )
        assert revoke.status_code == 200

        calls_before_oauth_revoke = len(answer_calls)
        assert await request_is_rejected(http_app, apple_tokens["access_token"])
        assert len(answer_calls) == calls_before_oauth_revoke

    assert all(call["use_llm"] is False for call in answer_calls)
