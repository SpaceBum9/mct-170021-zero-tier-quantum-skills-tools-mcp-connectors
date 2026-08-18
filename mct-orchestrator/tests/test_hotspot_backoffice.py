import json

import server


def _payload(**overrides):
    data = {
        "client_id": "hotspot-client-01",
        "tunnel_authenticated": True,
        "session_valid": True,
        "permissions": ["backoffice:read"],
        "backoffice": {
            "operation": "read",
            "resource": "jobs",
            "payload": {},
        },
    }
    data.update(overrides)
    return data


def test_authorizes_read_over_authenticated_tunnel():
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload())))
    assert result["status"] == "authorized"
    assert result["target"] == "shb-backoffice"
    assert result["operation"] == "read"
    assert result["audit"]["outcome"] == "authorized"


def test_rejects_without_tunnel():
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(tunnel_authenticated=False))))
    assert result["status"] == "rejected"
    assert result["error"] == "backoffice_access_denied"
    assert result["audit"]["outcome"] == "rejected"


def test_rejects_missing_permission():
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(permissions=[]))))
    assert result["status"] == "rejected"
    assert "permission denied" in result["detail"]


def test_admin_requires_admin_permission():
    payload = _payload()
    payload["backoffice"] = {"operation": "admin", "resource": "system", "payload": {}}
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(payload)))
    assert result["status"] == "rejected"


def test_unknown_gateway_fields_fail_closed():
    payload = _payload(extra="no")
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(payload)))
    assert result["status"] == "rejected"
    assert result["error"] == "unknown_gateway_fields"
