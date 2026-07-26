"""Vaultify MCP resource-server integration."""

from vaultify.mcp.server import (
    VaultifyConnectorTokenVerifier,
    create_authenticated_mcp_server,
    serialize_mcp_sources,
)

__all__ = [
    "VaultifyConnectorTokenVerifier",
    "create_authenticated_mcp_server",
    "serialize_mcp_sources",
]
