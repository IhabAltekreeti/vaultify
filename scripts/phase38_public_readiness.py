"""Small readiness helper for the temporary Phase 3.8 public acceptance harness.

This file stays outside ``src/vaultify`` because it is Colab acceptance
orchestration, not product runtime code. It prevents the first MCP client
session from racing a freshly-created Cloudflare Quick Tunnel.
"""

import time

import httpx


def wait_for_phase38_public_runtime(runtime, *, timeout=150):
    """Wait until both OAuth metadata and MCP protected-resource metadata are public."""
    oauth_url = (
        runtime.oauth_public_url.rstrip("/")
        + "/.well-known/oauth-authorization-server"
    )
    mcp_metadata_url = runtime.mcp_public_url.replace(
        "/mcp",
        "/.well-known/oauth-protected-resource/mcp",
    )

    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            oauth_response = httpx.get(
                oauth_url,
                timeout=15,
                follow_redirects=False,
            )
            mcp_response = httpx.get(
                mcp_metadata_url,
                timeout=15,
                follow_redirects=False,
            )

            if oauth_response.status_code == 200 and mcp_response.status_code == 200:
                payload = mcp_response.json()
                if payload.get("resource") == runtime.mcp_public_url:
                    return {
                        "oauth_metadata_url": oauth_url,
                        "mcp_metadata_url": mcp_metadata_url,
                    }

            last_error = RuntimeError(
                "Public acceptance surfaces are not ready yet: "
                f"oauth={oauth_response.status_code}, mcp={mcp_response.status_code}."
            )
        except Exception as error:
            last_error = error

        time.sleep(2)

    raise RuntimeError(
        "Phase 3.8 public OAuth/MCP runtime did not become ready in time."
    ) from last_error


__all__ = ["wait_for_phase38_public_runtime"]
