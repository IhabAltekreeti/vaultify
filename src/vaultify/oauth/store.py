"""Persistence boundary for Vaultify OAuth state.

R1 deliberately defines only the interface. Regression tests may supply an
in-memory implementation. R2 will provide persistent database-backed state.
"""

from typing import Protocol


class OAuthStateStore(Protocol):
    def put_client(self, client_id: str, value: dict) -> None: ...

    def get_client(self, client_id: str) -> dict | None: ...

    def put_authorization_code(self, secret_hash: str, value: dict) -> None: ...

    def pop_authorization_code(self, secret_hash: str) -> dict | None: ...

    def put_access_token(self, secret_hash: str, value: dict) -> None: ...

    def get_access_token(self, secret_hash: str) -> dict | None: ...

    def pop_access_token(self, secret_hash: str) -> dict | None: ...

    def put_refresh_token(self, secret_hash: str, value: dict) -> None: ...

    def pop_refresh_token(self, secret_hash: str) -> dict | None: ...


__all__ = ["OAuthStateStore"]
