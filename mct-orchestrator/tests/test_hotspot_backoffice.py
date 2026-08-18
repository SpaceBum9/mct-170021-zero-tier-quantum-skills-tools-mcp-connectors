import json
import time
import uuid

from attestation import sign_attestation
import server


SECRET = "test-secret-that-is-at-least-thirty-two-characters"


def _token(*, permissions=None, tunnel=True, session=True, exp_offset=120, audience="mct-backoffice"):
    now = int(time.time())
    claims = {
        "iss": "shb-hotspot-gateway",
        "aud": audience,
        "sub": "hotspot-client-01",
        "exp": now + exp_offset,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "permissions": ["backoffice:read"] if permissions is None else permissions,
        "tunnel_authenticated": tunnel,
        "session_valid": session,
    }
    return sign_attestation(claims, SECRET)


def _payload(token=None, **overrides):
    data = {
        "attestation": token or _token(),
        "backoffice": {
            "operation": "read",
            "resource": "jobs",
            "payload": {},
        },
    }
    data.update(overrides)
    return data


def _configure(monkeypatch):
    monkeypatch.setenv("SHB_ATTESTATION_SECRET", SECRET)
    monkeypatch.setenv("SHB_ATTESTATION_AUDIENCE", "mct-backoffice")
    monkeypatch.setenv("SHB_ATTESTATION_ISSUER", "shb-hotspot-gateway")


def test_authorizes_signed_attestation(monkeypatch):
    _configure(monkeypatch)
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload())))
    assert result["status"] == "authorized"
    assert result["target"] == "shb-backoffice"
    assert result["operation"] == "read"
    assert result["client_id"] == "hotspot-client-01"
    assert result["audit"]["outcome"] == "authorized"


def test_rejects_tampered_attestation(monkeypatch):
    _configure(monkeypatch)
    token = _token()
    encoded, signature = token.split(".", 1)
    tampered = f"{encoded[:-1]}A.{signature}"
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(tampered))))
    assert result["status"] == "rejected"
    assert result["error"] == "backoffice_access_denied"


def test_rejects_without_authenticated_tunnel_claim(monkeypatch):
    _configure(monkeypatch)
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(_token(tunnel=False)))))
    assert result["status"] == "rejected"
    assert "authenticated tunnel required" in result["detail"]


def test_rejects_missing_permission(monkeypatch):
    _configure(monkeypatch)
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(_token(permissions=[])))))
    assert result["status"] == "rejected"
    assert "permission denied" in result["detail"]


def test_admin_requires_admin_permission(monkeypatch):
    _configure(monkeypatch)
    payload = _payload(_token(permissions=["backoffice:read"]))
    payload["backoffice"] = {"operation": "admin", "resource": "system", "payload": {}}
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(payload)))
    assert result["status"] == "rejected"


def test_replay_is_rejected(monkeypatch):
    _configure(monkeypatch)
    token = _token()
    first = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(token))))
    second = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(token))))
    assert first["status"] == "authorized"
    assert second["status"] == "rejected"
    assert "replay" in second["detail"]


def test_wrong_audience_is_rejected(monkeypatch):
    _configure(monkeypatch)
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(_payload(_token(audience="other-service")))))
    assert result["status"] == "rejected"
    assert "audience" in result["detail"]


def test_unknown_gateway_fields_fail_closed(monkeypatch):
    _configure(monkeypatch)
    payload = _payload(extra="no")
    result = json.loads(server.authorize_hotspot_backoffice(json.dumps(payload)))
    assert result["status"] == "rejected"
    assert result["error"] == "unknown_gateway_fields"
