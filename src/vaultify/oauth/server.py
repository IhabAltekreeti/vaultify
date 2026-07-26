"""OAuth Authorization Server protocol core extracted from golden Cell 23H.

This module intentionally does not launch Uvicorn, create Cloudflare tunnels, or
own an in-memory global token database. OAuth state is injected through the
OAuthStateStore boundary so R2 can replace test memory state with persistence.
"""

import base64
import hashlib
import html
import inspect
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from vaultify.oauth.store import OAuthStateStore


VAULTIFY_OAUTH_SCOPE = "vaultify:mcp"
OAUTH_AUTH_CODE_LIFETIME_SECONDS = 300
OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS = 3600
OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS = 30 * 24 * 60 * 60


def oauth_hash_secret(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def oauth_generate_secret(prefix):
    return prefix + secrets.token_urlsafe(32)


def oauth_base64url_sha256(value):
    digest = hashlib.sha256(str(value).encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def oauth_valid_redirect_uri(uri):
    try:
        parsed = urlparse(str(uri))
    except Exception:
        return False

    if parsed.scheme == "https":
        return bool(parsed.netloc)

    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    )


def oauth_scope_is_valid(scope):
    requested = {item for item in str(scope or "").split() if item}
    return not requested or requested <= {VAULTIFY_OAUTH_SCOPE}


def _identity_record(identity, normalized, now):
    required = {"credential_id", "organization_id", "tenant_id"}
    if not isinstance(identity, dict) or required - set(identity):
        raise PermissionError("Authorization identity is incomplete.")

    return {
        "credential_id": identity["credential_id"],
        "organization_id": identity["organization_id"],
        "tenant_id": identity["tenant_id"],
        "client_id": normalized["client_id"],
        "redirect_uri": normalized.get("redirect_uri"),
        "scope": normalized["scope"],
        "resource": normalized.get("resource", ""),
        "code_challenge": normalized.get("code_challenge"),
        "created_at": now,
    }


def _token_record(authorization, *, now, expires_at):
    return {
        "credential_id": authorization["credential_id"],
        "organization_id": authorization["organization_id"],
        "tenant_id": authorization["tenant_id"],
        "client_id": authorization["client_id"],
        "scope": authorization["scope"],
        "resource": authorization.get("resource", ""),
        "created_at": now,
        "expires_at": expires_at,
    }


def resolve_oauth_access_token(
    state_store: OAuthStateStore,
    raw_token,
    *,
    connector_identity_is_active,
    now=None,
):
    """Resolve one OAuth access token and re-check its connector identity."""
    cleaned = str(raw_token or "").strip()
    if not cleaned:
        return None

    record = state_store.get_access_token(oauth_hash_secret(cleaned))
    if record is None:
        return None

    current_time = int(time.time() if now is None else now)
    if record["expires_at"] < current_time:
        state_store.pop_access_token(oauth_hash_secret(cleaned))
        return None

    if not connector_identity_is_active(
        record["credential_id"],
        record["organization_id"],
        record["tenant_id"],
    ):
        return None

    return dict(record)


def create_oauth_authorization_server(
    *,
    issuer_url,
    state_store: OAuthStateStore,
    authorization_identity_resolver,
    connector_identity_is_active,
    now_provider=None,
):
    """Create the Vaultify OAuth ASGI app without launching a server.

    authorization_identity_resolver is the consent boundary. It receives the
    Starlette request plus the validated OAuth request and returns only trusted
    identity scalars: credential_id, organization_id, tenant_id. It may be sync
    or async. The release module never asks the browser for tenant_id.
    """
    issuer = str(issuer_url or "").strip().rstrip("/")
    if not issuer:
        raise ValueError("issuer_url is required.")
    if state_store is None:
        raise ValueError("state_store is required.")
    if not callable(authorization_identity_resolver):
        raise TypeError("authorization_identity_resolver must be callable.")
    if not callable(connector_identity_is_active):
        raise TypeError("connector_identity_is_active must be callable.")

    def now():
        return int(now_provider() if now_provider is not None else time.time())

    def validate_authorization_request(params):
        client_id = str(params.get("client_id", ""))
        client = state_store.get_client(client_id)
        if client is None:
            return None, "invalid_client"

        if str(params.get("response_type", "")) != "code":
            return None, "unsupported_response_type"

        redirect_uri = str(params.get("redirect_uri", ""))
        if redirect_uri not in client["redirect_uris"]:
            return None, "invalid_redirect_uri"

        code_challenge = str(params.get("code_challenge", ""))
        if not code_challenge or str(params.get("code_challenge_method", "")) != "S256":
            return None, "invalid_request"

        scope = str(params.get("scope", VAULTIFY_OAUTH_SCOPE))
        if not oauth_scope_is_valid(scope):
            return None, "invalid_scope"

        return {
            "client_id": client_id,
            "client_name": client["client_name"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope or VAULTIFY_OAUTH_SCOPE,
            "state": str(params.get("state", "")),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "resource": str(params.get("resource", "")),
        }, None

    def issue_access_token(authorization):
        raw = oauth_generate_secret("vlt_oauth_at_")
        created = now()
        state_store.put_access_token(
            oauth_hash_secret(raw),
            _token_record(
                authorization,
                now=created,
                expires_at=created + OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
            ),
        )
        return raw

    def issue_refresh_token(authorization):
        raw = oauth_generate_secret("vlt_oauth_rt_")
        created = now()
        state_store.put_refresh_token(
            oauth_hash_secret(raw),
            _token_record(
                authorization,
                now=created,
                expires_at=created + OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS,
            ),
        )
        return raw

    async def metadata_endpoint(request):
        return JSONResponse(
            {
                "issuer": issuer,
                "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token",
                "registration_endpoint": issuer + "/register",
                "revocation_endpoint": issuer + "/revoke",
                "scopes_supported": [VAULTIFY_OAUTH_SCOPE],
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
                "client_id_metadata_document_supported": False,
            }
        )

    async def register_endpoint(request):
        try:
            metadata = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_client_metadata"}, status_code=400)

        redirect_uris = metadata.get("redirect_uris") or []
        if not isinstance(redirect_uris, list) or not redirect_uris:
            return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)
        if not all(oauth_valid_redirect_uri(uri) for uri in redirect_uris):
            return JSONResponse({"error": "invalid_redirect_uri"}, status_code=400)

        if metadata.get("token_endpoint_auth_method", "none") != "none":
            return JSONResponse(
                {
                    "error": "invalid_client_metadata",
                    "error_description": "Vaultify currently supports public OAuth clients only.",
                },
                status_code=400,
            )

        client_id = oauth_generate_secret("vlt_oauth_client_")
        client = {
            "client_id": client_id,
            "client_name": str(metadata.get("client_name", "Remote MCP Client"))[:200],
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": VAULTIFY_OAUTH_SCOPE,
            "created_at": now(),
        }
        state_store.put_client(client_id, client)
        return JSONResponse(client, status_code=201)

    async def authorize_get(request):
        normalized, error = validate_authorization_request(dict(request.query_params))
        if error:
            return JSONResponse({"error": error}, status_code=400)

        fields = "".join(
            '<input type="hidden" name="{}" value="{}">'.format(
                html.escape(name), html.escape(str(value))
            )
            for name, value in normalized.items()
        )
        page = (
            "<!doctype html><html><body><h1>Authorize Vaultify</h1>"
            f"<p>{html.escape(normalized['client_name'])}</p>"
            f"<p>{html.escape(normalized['scope'])}</p>"
            f'<form method="post" action="/authorize">{fields}'
            '<button type="submit">Authorize</button></form></body></html>'
        )
        return HTMLResponse(page)

    async def authorize_post(request):
        raw_body = (await request.body()).decode("utf-8")
        params = {key: values[-1] for key, values in parse_qs(raw_body, keep_blank_values=True).items()}
        normalized, error = validate_authorization_request(params)
        if error:
            return JSONResponse({"error": error}, status_code=400)

        try:
            identity = authorization_identity_resolver(request, normalized)
            if inspect.isawaitable(identity):
                identity = await identity
            authorization = _identity_record(identity, normalized, now())
        except PermissionError as exc:
            return JSONResponse(
                {"error": "access_denied", "error_description": str(exc)},
                status_code=403,
            )

        raw_code = oauth_generate_secret("vlt_oauth_code_")
        authorization["expires_at"] = now() + OAUTH_AUTH_CODE_LIFETIME_SECONDS
        state_store.put_authorization_code(oauth_hash_secret(raw_code), authorization)

        values = {"code": raw_code}
        if normalized["state"]:
            values["state"] = normalized["state"]
        separator = "&" if "?" in normalized["redirect_uri"] else "?"
        return RedirectResponse(
            normalized["redirect_uri"] + separator + urlencode(values),
            status_code=303,
        )

    async def token_endpoint(request):
        raw_body = (await request.body()).decode("utf-8")
        params = {key: values[-1] for key, values in parse_qs(raw_body, keep_blank_values=True).items()}
        grant_type = str(params.get("grant_type", ""))

        if grant_type == "authorization_code":
            code = str(params.get("code", ""))
            client_id = str(params.get("client_id", ""))
            redirect_uri = str(params.get("redirect_uri", ""))
            code_verifier = str(params.get("code_verifier", ""))
            if not code or not client_id or not redirect_uri or not code_verifier:
                return JSONResponse({"error": "invalid_request"}, status_code=400)

            authorization = state_store.pop_authorization_code(oauth_hash_secret(code))
            if authorization is None:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if authorization["expires_at"] < now():
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if authorization["client_id"] != client_id or authorization["redirect_uri"] != redirect_uri:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if not secrets.compare_digest(
                oauth_base64url_sha256(code_verifier), authorization["code_challenge"]
            ):
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "PKCE verification failed."},
                    status_code=400,
                )
            if not connector_identity_is_active(
                authorization["credential_id"],
                authorization["organization_id"],
                authorization["tenant_id"],
            ):
                return JSONResponse({"error": "invalid_grant"}, status_code=400)

            access_token = issue_access_token(authorization)
            refresh_token = issue_refresh_token(authorization)
            return JSONResponse(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
                    "refresh_token": refresh_token,
                    "scope": authorization["scope"],
                },
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )

        if grant_type == "refresh_token":
            raw_refresh_token = str(params.get("refresh_token", ""))
            client_id = str(params.get("client_id", ""))
            if not raw_refresh_token or not client_id:
                return JSONResponse({"error": "invalid_request"}, status_code=400)

            authorization = state_store.pop_refresh_token(oauth_hash_secret(raw_refresh_token))
            if authorization is None:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if authorization["expires_at"] < now() or authorization["client_id"] != client_id:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if not connector_identity_is_active(
                authorization["credential_id"],
                authorization["organization_id"],
                authorization["tenant_id"],
            ):
                return JSONResponse({"error": "invalid_grant"}, status_code=400)

            access_token = issue_access_token(authorization)
            rotated_refresh = issue_refresh_token(authorization)
            return JSONResponse(
                {
                    "access_token": access_token,
                    "token_type": "Bearer",
                    "expires_in": OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
                    "refresh_token": rotated_refresh,
                    "scope": authorization["scope"],
                },
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )

        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    async def revoke_endpoint(request):
        raw_body = (await request.body()).decode("utf-8")
        parsed = parse_qs(raw_body, keep_blank_values=True)
        raw_token = parsed.get("token", [""])[-1]
        if raw_token:
            secret_hash = oauth_hash_secret(raw_token)
            state_store.pop_access_token(secret_hash)
            state_store.pop_refresh_token(secret_hash)
        return Response(status_code=200)

    async def health_endpoint(request):
        return JSONResponse({"status": "ok", "service": "vaultify-oauth", "issuer": issuer})

    return Starlette(
        routes=[
            Route("/.well-known/oauth-authorization-server", metadata_endpoint, methods=["GET"]),
            Route("/.well-known/openid-configuration", metadata_endpoint, methods=["GET"]),
            Route("/register", register_endpoint, methods=["POST"]),
            Route("/authorize", authorize_get, methods=["GET"]),
            Route("/authorize", authorize_post, methods=["POST"]),
            Route("/token", token_endpoint, methods=["POST"]),
            Route("/revoke", revoke_endpoint, methods=["POST"]),
            Route("/health", health_endpoint, methods=["GET"]),
        ]
    )


__all__ = [
    "VAULTIFY_OAUTH_SCOPE",
    "OAUTH_AUTH_CODE_LIFETIME_SECONDS",
    "OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS",
    "OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS",
    "oauth_hash_secret",
    "oauth_base64url_sha256",
    "create_oauth_authorization_server",
    "resolve_oauth_access_token",
]
