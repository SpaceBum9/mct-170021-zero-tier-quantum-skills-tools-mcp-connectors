from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    client_id: str
    action: str
    resource: str
    outcome: str
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(*, client_id: str, action: str, resource: str, outcome: str, metadata: dict[str, Any] | None = None) -> AuditEvent:
    return AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        client_id=client_id,
        action=action,
        resource=resource,
        outcome=outcome,
        metadata=metadata or {},
    )
