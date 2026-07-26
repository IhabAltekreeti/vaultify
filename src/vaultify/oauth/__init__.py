"""Vaultify OAuth authorization-server components."""

from vaultify.oauth.server import (
    OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS,
    OAUTH_AUTH_CODE_LIFETIME_SECONDS,
    OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS,
    VAULTIFY_OAUTH_SCOPE,
    create_oauth_authorization_server,
    resolve_oauth_access_token,
)

__all__ = [
    "VAULTIFY_OAUTH_SCOPE",
    "OAUTH_AUTH_CODE_LIFETIME_SECONDS",
    "OAUTH_ACCESS_TOKEN_LIFETIME_SECONDS",
    "OAUTH_REFRESH_TOKEN_LIFETIME_SECONDS",
    "create_oauth_authorization_server",
    "resolve_oauth_access_token",
]
