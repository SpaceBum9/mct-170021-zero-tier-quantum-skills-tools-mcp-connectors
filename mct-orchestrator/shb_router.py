from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class SHBRouteError(ValueError):
    """Raised when no safe SHB route can be resolved."""


@dataclass(frozen=True)
class SHBRoute:
    route_id: str
    target: str
    capabilities: frozenset[str]
    allowed_operations: frozenset[str]
    priority: int = 0
    stability: float = 1.0
    healthy: bool = True

    def __post_init__(self) -> None:
        if not self.route_id or not self.target:
            raise ValueError("route_id and target are required")
        if not 0.0 <= self.stability <= 1.0:
            raise ValueError("stability must be between 0 and 1")


class SHBRouter:
    """Deterministic, fail-closed router for MCP connectors and mesh nodes."""

    def __init__(self, routes: Iterable[SHBRoute] = ()) -> None:
        self._routes: dict[str, SHBRoute] = {}
        for route in routes:
            self.register(route)

    def register(self, route: SHBRoute) -> None:
        if route.route_id in self._routes:
            raise ValueError(f"duplicate route_id: {route.route_id}")
        self._routes[route.route_id] = route

    def resolve(self, *, capability: str, operation: str, min_stability: float = 0.0) -> SHBRoute:
        if not capability or not operation:
            raise SHBRouteError("capability and operation are required")
        if not 0.0 <= min_stability <= 1.0:
            raise SHBRouteError("min_stability must be between 0 and 1")
        candidates = [
            route for route in self._routes.values()
            if route.healthy
            and route.stability >= min_stability
            and capability in route.capabilities
            and operation in route.allowed_operations
        ]
        if not candidates:
            raise SHBRouteError("no eligible SHB route")
        candidates.sort(key=lambda route: (-route.priority, -route.stability, route.route_id))
        return candidates[0]

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "route_id": route.route_id,
                "target": route.target,
                "capabilities": sorted(route.capabilities),
                "allowed_operations": sorted(route.allowed_operations),
                "priority": route.priority,
                "stability": route.stability,
                "healthy": route.healthy,
            }
            for route in sorted(self._routes.values(), key=lambda r: r.route_id)
        ]


DEFAULT_ROUTER = SHBRouter(
    [
        SHBRoute(
            route_id="mesh-controller-primary",
            target="mesh-controller",
            capabilities=frozenset({"automaton"}),
            allowed_operations=frozenset({"initialize", "sync", "execute", "halt"}),
            priority=100,
            stability=1.0,
        ),
        SHBRoute(
            route_id="backoffice-primary",
            target="shb-backoffice",
            capabilities=frozenset({"backoffice"}),
            allowed_operations=frozenset({"read", "write", "sync", "admin"}),
            priority=80,
            stability=1.0,
        ),
        SHBRoute(
            route_id="connector-readonly",
            target="mcp-connectors",
            capabilities=frozenset({"connector"}),
            allowed_operations=frozenset({"search", "fetch", "status"}),
            priority=50,
            stability=1.0,
        ),
    ]
)
