import json

import requests

import server


VALID = {
    "automaton_id": "automaton-01",
    "action": "sync",
    "parameters": {
        "target_node": "node-01",
        "stability_threshold": 0.9,
    },
}


def test_rejects_unknown_action():
    payload = dict(VALID)
    payload["action"] = "destroy"
    result = json.loads(server.dispatch_automaton_command(json.dumps(payload)))
    assert result["status"] == "rejected"
    assert result["error"] == "schema_validation_failed"


def test_rejects_missing_token(monkeypatch):
    monkeypatch.delenv("MESH_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(server, "SECURITY_TOKEN", None)
    result = json.loads(server.dispatch_automaton_command(json.dumps(VALID)))
    assert result["status"] == "rejected"
    assert result["error"] == "security_policy_failed"


def test_dispatches_to_expected_endpoint(monkeypatch):
    monkeypatch.setenv("MESH_AUTH_TOKEN", "secret")
    monkeypatch.setenv("MESH_CONTROLLER_URL", "https://mesh.test/api/v1")

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"accepted": True, "command_id": "cmd-123"}

    called = {}

    def fake_post(url, headers, json, timeout):
        called.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    result = json.loads(server.dispatch_automaton_command(json.dumps(VALID)))

    assert result["status"] == "orchestrated"
    assert called["url"] == "https://mesh.test/api/v1/nodes/node-01/automata/automaton-01/commands"
    assert called["headers"]["Authorization"] == "Bearer secret"
    assert called["json"]["action"] == "sync"


def test_timeout_is_fail_closed(monkeypatch):
    monkeypatch.setenv("MESH_AUTH_TOKEN", "secret")

    def fake_post(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr(requests, "post", fake_post)
    result = json.loads(server.dispatch_automaton_command(json.dumps(VALID)))
    assert result["status"] == "failed"
    assert result["error"] == "mesh_timeout"
