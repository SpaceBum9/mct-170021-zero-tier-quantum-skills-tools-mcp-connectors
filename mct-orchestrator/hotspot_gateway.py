from __future__ import annotations

from dataclasses import dataclass


class GatewayAccessError(ValueError):
    pass


@dataclass(frozen=True)
class GatewaySession:
    client_id: str
    tunnel_authenticated: bool
    session_valid: bool
    permissions: frozenset[str]

    def authorize(self, permission: str) -> None:
        if not self.tunnel_authenticated:
            raise GatewayAccessError("authenticated tunnel required")
        if not self.session_valid:
            raise GatewayAccessError("valid session required")
        if permission not in self.permissions:
            raise GatewayAccessError(f"permission denied: {permission}")


def build_session(*, client_id: str, tunnel_authenticated: bool, session_valid: bool, permissions: list[str]) -> GatewaySession:
    if not client_id or len(client_id) > 128:
        raise GatewayAccessError("invalid client_id")
    if not all(isinstance(item, str) and item for item in permissions):
        raise GatewayAccessError("invalid permissions")
    return GatewaySession(
        client_id=client_id,
        tunnel_authenticated=tunnel_authenticated,
        session_valid=session_valid,
        permissions=frozenset(permissions),
    )
