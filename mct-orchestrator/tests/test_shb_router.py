import json

import pytest

import server
from shb_router import SHBRoute, SHBRouteError, SHBRouter


def test_router_prefers_priority_then_stability_then_id():
    router = SHBRouter([
        SHBRoute("b", "node-b", frozenset({"connector"}), frozenset({"fetch"}), priority=10, stability=0.9),
        SHBRoute("a", "node-a", frozenset({"connector"}), frozenset({"fetch"}), priority=10, stability=0.9),
        SHBRoute("c", "node-c", frozenset({"connector"}), frozenset({"fetch"}), priority=20, stability=0.8),
    ])
    assert router.resolve(capability="connector", operation="fetch").route_id == "c"


def test_router_fails_closed_for_disallowed_operation():
    router = SHBRouter([
        SHBRoute("read", "connector", frozenset({"connector"}), frozenset({"fetch"}))
    ])
    with pytest.raises(SHBRouteError):
        router.resolve(capability="connector", operation="execute")


def test_router_honors_health_and_stability():
    router = SHBRouter([
        SHBRoute("down", "node-a", frozenset({"automaton"}), frozenset({"sync"}), healthy=False),
        SHBRoute("weak", "node-b", frozenset({"automaton"}), frozenset({"sync"}), stability=0.4),
    ])
    with pytest.raises(SHBRouteError):
        router.resolve(capability="automaton", operation="sync", min_stability=0.8)


def test_mcp_route_tool_resolves_known_route():
    result = json.loads(server.route_shb_request(json.dumps({
        "capability": "connector",
        "operation": "fetch",
        "min_stability": 0.9,
    })))
    assert result["status"] == "routed"
    assert result["route_id"] == "connector-readonly"


def test_mcp_route_tool_rejects_unknown_fields():
    result = json.loads(server.route_shb_request(json.dumps({
        "capability": "connector",
        "operation": "fetch",
        "surprise": True,
    })))
    assert result["status"] == "rejected"
    assert result["error"] == "unknown_route_fields"
