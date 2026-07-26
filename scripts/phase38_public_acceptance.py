"""Temporary Colab acceptance harness for the extracted Phase 3.8 release path.

This file is intentionally outside ``src/vaultify``. It may launch Uvicorn threads
and Cloudflare Quick Tunnels for short-lived acceptance tests, but application
modules must never own this orchestration. The harness performs read-only Qdrant
access and uses an acceptance-only in-memory OAuth state store.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

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
from vaultify.services.document_catalog import build_document_catalog
from vaultify.services.embeddings import EmbeddingService
from vaultify.services.entity_routing import prepare_entity_retrieval_indexes
from vaultify.services.llm import create_groq_client
from vaultify.services.qdrant import create_qdrant_client
from vaultify.services.retrieval import load_tenant_chunks
from vaultify.web.app import create_app


APPLE_TENANT_ID = "demo_apple_tenant"
APPLE_QUESTION = "What were Apple's total net sales in fiscal year 2025?"
APPLE_EXPECTED_VALUE = "416,161"

APPLE_ENTITY_RULES = {
    "Apple": {
        "filename_terms": {"apple"},
        "content_terms": {"apple inc", "apple inc."},
        "aliases": {"apple", "apple inc", "apple inc.", "aapl"},
    }
}


class MemoryOAuthStateStore:
    """Acceptance-only OAuth state. R2 must replace this with persistence."""

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


class UvicornThread:
    def __init__(self, app, port):
        self.port = int(port)
        self.config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(
            target=self.server.run,
            name=f"vaultify-acceptance-{self.port}",
            daemon=True,
        )

    def start(self, timeout=20):
        self.thread.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _port_open(self.port):
                return
            if not self.thread.is_alive():
                break
            time.sleep(0.1)
        raise RuntimeError(f"Uvicorn did not start on port {self.port}.")

    def stop(self):
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=8)


class CloudflareTunnel:
    def __init__(self, port):
        self.port = int(port)
        self.process = None
        self.logs = []
        self.public_url = None
        self._reader_thread = None

    def _read_logs(self):
        if self.process is None or self.process.stderr is None:
            return
        for line in iter(self.process.stderr.readline, ""):
            cleaned = line.strip()
            if cleaned:
                self.logs.append(cleaned)
            if self.process.poll() is not None:
                break

    def start(self, timeout=75):
        _install_cloudflared_if_missing()
        self.process = subprocess.Popen(
            [
                "cloudflared",
                "tunnel",
                "--url",
                f"http://127.0.0.1:{self.port}",
                "--no-autoupdate",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._reader_thread = threading.Thread(
            target=self._read_logs,
            name=f"cloudflared-reader-{self.port}",
            daemon=True,
        )
        self._reader_thread.start()

        pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    "cloudflared exited early. Recent logs: " + " | ".join(self.logs[-8:])
                )
            for line in self.logs:
                match = pattern.search(line)
                if match:
                    self.public_url = match.group(0).rstrip("/")
                    return self.public_url
            time.sleep(0.15)
        raise RuntimeError("Cloudflare did not provide a Quick Tunnel URL in time.")

    def stop(self):
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


@dataclass
class Phase38PublicRuntime:
    flask_app: object
    credential_id: int
    state_store: MemoryOAuthStateStore
    tenant_runtime: dict
    oauth_public_url: str
    mcp_public_url: str
    oauth_server: UvicornThread
    mcp_server: UvicornThread
    oauth_tunnel: CloudflareTunnel
    mcp_tunnel: CloudflareTunnel
    authorization_budget: dict

    def tenant_runtime_resolver(self, tenant_id):
        if tenant_id == APPLE_TENANT_ID:
            return self.tenant_runtime
        return None

    def connector_identity_is_active(self, credential_id, organization_id, tenant_id):
        with self.flask_app.app_context():
            credential = db.session.get(ConnectorCredential, int(credential_id))
            if credential is None or not credential.is_active:
                return False
            if credential.organization_id != int(organization_id):
                return False
            organization = db.session.get(Organization, credential.organization_id)
            return (
                organization is not None
                and organization.id == int(organization_id)
                and organization.tenant_id == str(tenant_id)
            )

    async def authorization_identity_resolver(self, request, normalized):
        if self.authorization_budget["remaining"] <= 0:
            raise PermissionError("The temporary acceptance authorization window is closed.")

        with self.flask_app.app_context():
            credential = db.session.get(ConnectorCredential, self.credential_id)
            if credential is None or not credential.is_active:
                raise PermissionError("The temporary connector credential is unavailable.")
            organization = db.session.get(Organization, credential.organization_id)
            if organization is None:
                raise PermissionError("The temporary connector organization is unavailable.")
            identity = {
                "credential_id": credential.id,
                "organization_id": organization.id,
                "tenant_id": organization.tenant_id,
            }

        self.authorization_budget["remaining"] -= 1
        return identity

    def revoke_connector(self):
        with self.flask_app.app_context():
            credential = db.session.get(ConnectorCredential, self.credential_id)
            if credential is not None and credential.is_active:
                revoke_connector_credential(credential)

    def stop(self, *, revoke=True):
        if revoke:
            try:
                self.revoke_connector()
            except Exception:
                pass
        for component in (
            self.oauth_server,
            self.mcp_server,
            self.oauth_tunnel,
            self.mcp_tunnel,
        ):
            try:
                component.stop()
            except Exception:
                pass


def _port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _install_cloudflared_if_missing():
    if shutil.which("cloudflared"):
        return
    subprocess.run(
        [
            "bash",
            "-lc",
            "set -e; wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cloudflared.deb; dpkg -i /tmp/cloudflared.deb >/dev/null; rm -f /tmp/cloudflared.deb",
        ],
        check=True,
    )


def _placeholder_app():
    async def health(request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/health", health)])


def _reserve_public_url(port):
    placeholder = UvicornThread(_placeholder_app(), port)
    placeholder.start()
    tunnel = CloudflareTunnel(port)
    try:
        public_url = tunnel.start()
    finally:
        placeholder.stop()
    return tunnel, public_url


def _wait_public_http(url, *, expected_status=200, timeout=150):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=15, follow_redirects=False)
            if response.status_code == expected_status:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code} from {url}")
        except Exception as error:
            last_error = error
        time.sleep(2)
    raise RuntimeError(f"Public endpoint did not become ready: {url}") from last_error


def _create_live_apple_runtime(*, qdrant_url, qdrant_api_key, groq_api_key):
    print("🔧 Loading real Vaultify runtime services...")
    qdrant = create_qdrant_client(url=qdrant_url, api_key=qdrant_api_key)
    embedding_service = EmbeddingService()
    groq_client = create_groq_client(api_key=groq_api_key)

    print("📚 Loading Apple tenant chunks from Qdrant (read-only)...")
    chunks = load_tenant_chunks(qdrant, APPLE_TENANT_ID)
    print(f"✅ Apple tenant chunks loaded: {len(chunks)}")

    document_catalog, entity_registry = build_document_catalog(
        chunks,
        APPLE_TENANT_ID,
        entity_rules=APPLE_ENTITY_RULES,
    )
    if "Apple" not in entity_registry:
        raise RuntimeError(f"Apple entity was not registered: {sorted(entity_registry)}")

    print("🧠 Building the real Apple hybrid retrieval index...")
    retrieval_indexes = prepare_entity_retrieval_indexes(
        document_catalog,
        entity_registry,
        embedding_service,
        show_progress_bar=False,
    )

    return {
        "runtime_tenant_id": APPLE_TENANT_ID,
        "entity_registry": entity_registry,
        "retrieval_indexes": retrieval_indexes,
        "embedding_service": embedding_service,
        "groq_client": groq_client,
    }


def start_phase38_public_runtime(
    *,
    qdrant_url,
    qdrant_api_key,
    groq_api_key,
    workspace="/content/vaultify-phase38-acceptance",
):
    """Start temporary public OAuth + MCP runtime and return a live handle."""
    workspace_path = Path(workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)
    sqlite_path = workspace_path / "acceptance.sqlite"
    if sqlite_path.exists():
        sqlite_path.unlink()

    tenant_runtime = _create_live_apple_runtime(
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        groq_api_key=groq_api_key,
    )

    flask_app = create_app(
        services={"answer_tenant_question": lambda **_: None},
        config={
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": secrets.token_urlsafe(32),
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{sqlite_path}",
            "UPLOAD_FOLDER": str(workspace_path / "uploads"),
        },
    )

    with flask_app.app_context():
        db.create_all()
        organization = Organization(
            name="Vaultify Phase 3.8 Acceptance",
            slug="vaultify-phase38-acceptance",
            tenant_id=APPLE_TENANT_ID,
        )
        db.session.add(organization)
        db.session.commit()
        credential, _raw_connector_token = create_connector_credential(
            organization,
            name="Temporary Phase 3.8 Acceptance Connector",
        )
        credential_id = credential.id

    oauth_port = _free_port()
    mcp_port = _free_port()
    while mcp_port == oauth_port:
        mcp_port = _free_port()

    print("🌐 Reserving temporary Cloudflare URLs...")
    oauth_tunnel, oauth_public_url = _reserve_public_url(oauth_port)
    mcp_tunnel, mcp_public_base = _reserve_public_url(mcp_port)
    mcp_public_url = mcp_public_base.rstrip("/") + "/mcp"

    state_store = MemoryOAuthStateStore()
    authorization_budget = {"remaining": 4}

    runtime = Phase38PublicRuntime(
        flask_app=flask_app,
        credential_id=credential_id,
        state_store=state_store,
        tenant_runtime=tenant_runtime,
        oauth_public_url=oauth_public_url,
        mcp_public_url=mcp_public_url,
        oauth_server=None,
        mcp_server=None,
        oauth_tunnel=oauth_tunnel,
        mcp_tunnel=mcp_tunnel,
        authorization_budget=authorization_budget,
    )

    oauth_app = create_oauth_authorization_server(
        issuer_url=oauth_public_url,
        state_store=state_store,
        authorization_identity_resolver=runtime.authorization_identity_resolver,
        connector_identity_is_active=runtime.connector_identity_is_active,
    )

    mcp, _ = create_oauth_protected_mcp_server(
        flask_app=flask_app,
        state_store=state_store,
        connector_identity_is_active=runtime.connector_identity_is_active,
        tenant_runtime_resolver=runtime.tenant_runtime_resolver,
        resource_server_url=mcp_public_url,
        issuer_url=oauth_public_url,
        use_llm=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    oauth_server = UvicornThread(oauth_app, oauth_port)
    mcp_server = UvicornThread(mcp.streamable_http_app(), mcp_port)
    runtime.oauth_server = oauth_server
    runtime.mcp_server = mcp_server

    try:
        oauth_server.start()
        mcp_server.start()
        _wait_public_http(oauth_public_url + "/.well-known/oauth-authorization-server")
    except Exception:
        runtime.stop(revoke=True)
        raise

    print("✅ Temporary public OAuth server is reachable.")
    print(f"🔐 OAuth issuer: {oauth_public_url}")
    print(f"🔗 Public MCP: {mcp_public_url}")
    return runtime


def issue_public_oauth_token(runtime: Phase38PublicRuntime):
    """Exercise public DCR + Authorization Code + PKCE and return access token."""
    callback_url = "http://127.0.0.1:8765/vaultify-acceptance-callback"
    verifier = secrets.token_urlsafe(48)
    challenge = oauth_base64url_sha256(verifier)

    with httpx.Client(timeout=30, follow_redirects=False) as client:
        registration = client.post(
            runtime.oauth_public_url + "/register",
            json={
                "client_name": "Vaultify Phase 3.8 Public Acceptance",
                "redirect_uris": [callback_url],
                "token_endpoint_auth_method": "none",
            },
        )
        registration.raise_for_status()
        client_id = registration.json()["client_id"]

        auth_params = {
            "client_id": client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": VAULTIFY_OAUTH_SCOPE,
            "state": secrets.token_urlsafe(12),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": runtime.mcp_public_url,
        }

        consent = client.get(runtime.oauth_public_url + "/authorize", params=auth_params)
        consent.raise_for_status()
        if "Authorize Vaultify" not in consent.text:
            raise RuntimeError("The public OAuth consent page did not render.")

        approval = client.post(
            runtime.oauth_public_url + "/authorize",
            data=auth_params,
        )
        if approval.status_code != 303:
            raise RuntimeError(
                f"Public OAuth authorization failed with HTTP {approval.status_code}: {approval.text[:500]}"
            )

        callback = urlparse(approval.headers["location"])
        code = parse_qs(callback.query)["code"][0]

        token_response = client.post(
            runtime.oauth_public_url + "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "redirect_uri": callback_url,
                "code_verifier": verifier,
            },
        )
        token_response.raise_for_status()
        return token_response.json()["access_token"]


async def call_public_mcp(runtime: Phase38PublicRuntime, access_token, question=APPLE_QUESTION):
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60.0) as http_client:
        async with streamable_http_client(
            runtime.mcp_public_url,
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_result = await session.call_tool(
                    "ask_documents",
                    {"question": question},
                )

    if tool_result.isError:
        raise RuntimeError("The public MCP tool returned an error.")

    payload = tool_result.structuredContent
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        payload = payload["result"]
    if not isinstance(payload, dict):
        raise RuntimeError("Public MCP returned no structured payload.")

    return [tool.name for tool in tools.tools], payload


async def run_public_acceptance(runtime: Phase38PublicRuntime):
    """Run the complete public OAuth + real Apple V2 + MCP acceptance flow."""
    access_token = issue_public_oauth_token(runtime)
    tools, payload = await call_public_mcp(runtime, access_token)

    if tools != ["ask_documents"]:
        raise RuntimeError(f"Unexpected public MCP tools: {tools}")

    answer = str(payload.get("answer", ""))
    if APPLE_EXPECTED_VALUE not in answer:
        raise RuntimeError(
            "The public real-V2 answer did not contain Apple FY2025 net sales: "
            + answer[:800]
        )

    sources = payload.get("sources") or []
    apple_sources = [
        source
        for source in sources
        if isinstance(source, dict)
        and "apple" in str(source.get("filename", "")).lower()
    ]
    if not apple_sources:
        raise RuntimeError(f"No Apple source was returned publicly: {sources}")

    if "tenant_id" in payload or "organization_id" in payload:
        raise RuntimeError("Sensitive tenant/organization metadata leaked in MCP output.")

    return {
        "answer": answer,
        "sources": sources,
        "tools": tools,
        "oauth_public_url": runtime.oauth_public_url,
        "mcp_public_url": runtime.mcp_public_url,
        "authorization_uses_remaining": runtime.authorization_budget["remaining"],
    }


__all__ = [
    "APPLE_QUESTION",
    "Phase38PublicRuntime",
    "call_public_mcp",
    "issue_public_oauth_token",
    "run_public_acceptance",
    "start_phase38_public_runtime",
]
