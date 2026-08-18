from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class BackofficePolicyError(ValueError):
    pass


ALLOWED_OPERATIONS = {"read", "write", "sync", "admin"}


@dataclass(frozen=True)
class BackofficeRequest:
    operation: str
    resource: str
    payload: dict[str, Any]

    def required_permission(self) -> str:
        if self.operation not in ALLOWED_OPERATIONS:
            raise BackofficePolicyError("unsupported backoffice operation")
        return f"backoffice:{self.operation}"


def parse_backoffice_request(data: dict[str, Any]) -> BackofficeRequest:
    allowed = {"operation", "resource", "payload"}
    if set(data) - allowed:
        raise BackofficePolicyError("unknown backoffice fields")
    operation = data.get("operation")
    resource = data.get("resource")
    payload = data.get("payload", {})
    if not isinstance(operation, str) or operation not in ALLOWED_OPERATIONS:
        raise BackofficePolicyError("invalid operation")
    if not isinstance(resource, str) or not resource or len(resource) > 128:
        raise BackofficePolicyError("invalid resource")
    if not isinstance(payload, dict):
        raise BackofficePolicyError("payload must be an object")
    return BackofficeRequest(operation=operation, resource=resource, payload=payload)
