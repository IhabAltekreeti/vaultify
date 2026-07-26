"""R1 Step 24 regression for the extracted golden Cell 23H OAuth semantics."""

from urllib.parse import parse_qs, urlparse

from starlette.testclient import TestClient

from vaultify.oauth.server import (
    OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
    VAULTIFY_OAUTH_SCOPE,
    create_oauth_authorization_server,
    oauth_base64url_sha256,
    oauth_hash_secret,
    resolve_oauth_access_token,
)


class MemoryOAuthStateStore:
    """Regression-only store. Product code never owns this memory state."""

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


def test_oauth_authorization_server_preserves_pkce_dcr_rotation_and_revocation():
    store = MemoryOAuthStateStore()
    active_credentials = {101: True}
    identity_calls = []

    async def authorization_identity_resolver(request, normalized):
        identity_calls.append(normalized["client_id"])
        return {
            "credential_id": 101,
            "organization_id": 201,
            "tenant_id": "tenant_oauth_regression",
        }

    def connector_identity_is_active(credential_id, organization_id, tenant_id):
        return (
            active_credentials.get(credential_id, False)
            and organization_id == 201
            and tenant_id == "tenant_oauth_regression"
        )

    app = create_oauth_authorization_server(
        issuer_url="https://oauth.vaultify.example",
        state_store=store,
        authorization_identity_resolver=authorization_identity_resolver,
        connector_identity_is_active=connector_identity_is_active,
        now_provider=lambda: 1_800_000_000,
    )
    client = TestClient(app)

    metadata = client.get("/.well-known/oauth-authorization-server")
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["issuer"] == "https://oauth.vaultify.example"
    assert payload["authorization_endpoint"].endswith("/authorize")
    assert payload["token_endpoint"].endswith("/token")
    assert payload["registration_endpoint"].endswith("/register")
    assert payload["revocation_endpoint"].endswith("/revoke")
    assert payload["code_challenge_methods_supported"] == ["S256"]
    assert payload["token_endpoint_auth_methods_supported"] == ["none"]

    bad_registration = client.post(
        "/register",
        json={
            "redirect_uris": ["https://client.example/callback"],
            "token_endpoint_auth_method": "client_secret_basic",
        },
    )
    assert bad_registration.status_code == 400

    registration = client.post(
        "/register",
        json={
            "client_name": "Vaultify Regression Client",
            "redirect_uris": ["https://client.example/callback"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert registration.status_code == 201
    client_id = registration.json()["client_id"]
    assert registration.json()["scope"] == VAULTIFY_OAUTH_SCOPE

    verifier = "vaultify-regression-pkce-verifier"
    challenge = oauth_base64url_sha256(verifier)
    auth_params = {
        "client_id": client_id,
        "redirect_uri": "https://client.example/callback",
        "response_type": "code",
        "scope": VAULTIFY_OAUTH_SCOPE,
        "state": "state-123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "resource": "https://mcp.vaultify.example/mcp",
    }

    missing_pkce = dict(auth_params)
    missing_pkce.pop("code_challenge_method")
    assert client.get("/authorize", params=missing_pkce).status_code == 400

    consent_page = client.get("/authorize", params=auth_params)
    assert consent_page.status_code == 200
    assert "Vaultify Regression Client" in consent_page.text

    approval = client.post(
        "/authorize",
        data=auth_params,
        follow_redirects=False,
    )
    assert approval.status_code == 303
    callback = urlparse(approval.headers["location"])
    callback_params = parse_qs(callback.query)
    authorization_code = callback_params["code"][0]
    assert callback_params["state"] == ["state-123"]
    assert identity_calls == [client_id]
    assert authorization_code not in store.authorization_codes
    assert oauth_hash_secret(authorization_code) in store.authorization_codes

    token_response = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_verifier": verifier,
        },
    )
    assert token_response.status_code == 200
    tokens = token_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS
    assert token_response.headers["cache-control"] == "no-store"
    assert access_token not in store.access_tokens
    assert refresh_token not in store.refresh_tokens
    assert oauth_hash_secret(access_token) in store.access_tokens
    assert oauth_hash_secret(refresh_token) in store.refresh_tokens

    resolved = resolve_oauth_access_token(
        store,
        access_token,
        connector_identity_is_active=connector_identity_is_active,
        now=1_800_000_001,
    )
    assert resolved["tenant_id"] == "tenant_oauth_regression"
    assert resolved["resource"] == "https://mcp.vaultify.example/mcp"

    reused_code = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": client_id,
            "redirect_uri": "https://client.example/callback",
            "code_verifier": verifier,
        },
    )
    assert reused_code.status_code == 400
    assert reused_code.json()["error"] == "invalid_grant"

    refreshed = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    assert refreshed.status_code == 200
    rotated = refreshed.json()
    assert rotated["refresh_token"] != refresh_token
    assert oauth_hash_secret(refresh_token) not in store.refresh_tokens
    assert oauth_hash_secret(rotated["refresh_token"]) in store.refresh_tokens

    reused_refresh = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        },
    )
    assert reused_refresh.status_code == 400
    assert reused_refresh.json()["error"] == "invalid_grant"

    rotated_access = rotated["access_token"]
    revoke = client.post("/revoke", data={"token": rotated_access})
    assert revoke.status_code == 200
    assert resolve_oauth_access_token(
        store,
        rotated_access,
        connector_identity_is_active=connector_identity_is_active,
        now=1_800_000_002,
    ) is None

    active_credentials[101] = False
    assert resolve_oauth_access_token(
        store,
        access_token,
        connector_identity_is_active=connector_identity_is_active,
        now=1_800_000_002,
    ) is None

    for secret_store in (
        store.authorization_codes,
        store.access_tokens,
        store.refresh_tokens,
    ):
        assert all(not key.startswith("vlt_oauth_") for key in secret_store)
