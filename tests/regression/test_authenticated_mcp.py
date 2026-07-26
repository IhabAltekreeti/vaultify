import inspect

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings

from vaultify.extensions import db
from vaultify.mcp.server import create_authenticated_mcp_server
from vaultify.models import ConnectorCredential, Organization
from vaultify.services.connector_credentials import (
    connector_credential_to_tenant_id,
    create_connector_credential,
    resolve_connector_credential,
    revoke_connector_credential,
)
from vaultify.web.app import create_app


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
                tool_result = await session.call_tool(
                    "ask_documents",
                    {"question": question},
                )
                return tools.tools, tool_result


async def request_is_rejected(http_app, raw_token):
    try:
        await call_mcp(
            http_app,
            raw_token,
            "What was total revenue?",
        )
    except BaseException:
        return True
    return False


@pytest.mark.anyio
async def test_authenticated_mcp_request_layer_is_fail_closed_and_tenant_hidden(tmp_path):
    app = create_app(
        services={"answer_tenant_question": lambda **_: None},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "r1-authenticated-mcp-test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        },
    )

    with app.app_context():
        db.create_all()

        apple_org = Organization(
            name="Apple MCP Organization",
            slug="apple-mcp-organization",
            tenant_id="tenant_mcp_apple",
        )
        tesla_org = Organization(
            name="Tesla MCP Organization",
            slug="tesla-mcp-organization",
            tenant_id="tenant_mcp_tesla",
        )
        db.session.add_all([apple_org, tesla_org])
        db.session.commit()

        _, apple_token = create_connector_credential(
            apple_org,
            name="Apple MCP Test",
        )
        tesla_credential, tesla_token = create_connector_credential(
            tesla_org,
            name="Tesla MCP Test",
        )
        tesla_credential_id = tesla_credential.id

    runtimes = {
        "tenant_mcp_apple": {"runtime_tenant_id": "tenant_mcp_apple"},
        "tenant_mcp_tesla": {"runtime_tenant_id": "tenant_mcp_tesla"},
    }
    service_calls = []

    def tenant_runtime_resolver(tenant_id):
        return runtimes.get(tenant_id)

    def connector_answer_spy(
        raw_token,
        question,
        *,
        tenant_runtime_resolver,
        use_llm,
    ):
        credential = resolve_connector_credential(raw_token, mark_used=True)
        if credential is None:
            raise PermissionError("Invalid connector credential.")

        tenant_id = connector_credential_to_tenant_id(credential)
        runtime = tenant_runtime_resolver(tenant_id)
        assert runtime["runtime_tenant_id"] == tenant_id

        service_calls.append(
            {
                "tenant_id": tenant_id,
                "question": question,
                "use_llm": use_llm,
            }
        )

        answer = "APPLE_MCP_OK" if tenant_id == "tenant_mcp_apple" else "TESLA_MCP_OK"
        filename = "apple.pdf" if tenant_id == "tenant_mcp_apple" else "tesla.pdf"

        return {
            "status": "answered",
            "answer": answer,
            "sources": [
                {
                    "filename": filename,
                    "section": "Revenue",
                    "entity": "Apple" if tenant_id == "tenant_mcp_apple" else "Tesla",
                    "chunk_type": "table",
                    "chunk_index": 7,
                    "text": "RAW_CHUNK_TEXT_MUST_NOT_LEAK",
                    "tenant_id": tenant_id,
                }
            ],
        }

    mcp, ask_documents = create_authenticated_mcp_server(
        flask_app=app,
        tenant_runtime_resolver=tenant_runtime_resolver,
        resource_server_url="http://testserver/mcp",
        issuer_url="https://vaultify.local",
        use_llm=False,
        connector_answer_service=connector_answer_spy,
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
        assert await request_is_rejected(http_app, None)
        assert await request_is_rejected(http_app, "vlt_mcp_unknown-token")
        assert service_calls == []

        apple_tools, apple_result = await call_mcp(
            http_app,
            apple_token,
            "Apple question",
        )
        apple_payload = parse_tool_payload(apple_result)

        assert [tool.name for tool in apple_tools] == ["ask_documents"]
        tool_schema = apple_tools[0].inputSchema
        assert set(tool_schema.get("properties", {})) == {"question"}
        assert "tenant_id" not in tool_schema.get("properties", {})
        assert "organization_id" not in tool_schema.get("properties", {})

        assert apple_payload["status"] == "answered"
        assert apple_payload["answer"] == "APPLE_MCP_OK"
        assert "tenant_id" not in apple_payload
        assert "organization" not in apple_payload
        assert apple_payload["sources"] == [
            {
                "filename": "apple.pdf",
                "section": "Revenue",
                "entity": "Apple",
                "chunk_type": "table",
                "chunk_index": 7,
            }
        ]

        _, tesla_result = await call_mcp(
            http_app,
            tesla_token,
            "Tesla question",
        )
        tesla_payload = parse_tool_payload(tesla_result)

        assert tesla_payload["answer"] == "TESLA_MCP_OK"
        assert [call["tenant_id"] for call in service_calls] == [
            "tenant_mcp_apple",
            "tenant_mcp_tesla",
        ]

        with app.app_context():
            tesla_credential = db.session.get(
                ConnectorCredential,
                tesla_credential_id,
            )
            revoke_connector_credential(tesla_credential)

        calls_before_revoked_retry = len(service_calls)
        assert await request_is_rejected(http_app, tesla_token)
        assert len(service_calls) == calls_before_revoked_retry

        _, apple_again_result = await call_mcp(
            http_app,
            apple_token,
            "Apple still valid",
        )
        assert parse_tool_payload(apple_again_result)["answer"] == "APPLE_MCP_OK"

    assert all(call["use_llm"] is False for call in service_calls)
