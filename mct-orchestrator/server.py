from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

import requests
from jsonschema import Draft7Validator
from mcp.server.fastmcp import FastMCP


orchestrator_mcp = FastMCP("MCT-1700021-System-Orchestrator")

MESH_API_URL = os.environ.get(
    "MESH_CONTROLLER_URL",
    "https://mesh.local/api/v1",
).rstrip("/")
SECURITY_TOKEN = os.environ.get("MESH_AUTH_TOKEN")
REQUEST_TIMEOUT = float(os.environ.get("MESH_REQUEST_TIMEOUT", "10"))

AUTOMATON_COMMAND_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "AutomatonCommand",
    "type": "object",
    "properties": {
        "automaton_id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
            "pattern": r"^[A-Za-z0-9._:-]+$",
        },
        "action": {
            "type": "string",
            "enum": ["initialize", "sync", "execute", "halt"],
        },
        "parameters": {
            "type": "object",
            "properties": {
                "target_node": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128,
                    "pattern": r"^[A-Za-z0-9._:-]+$",
                },
                "stability_threshold": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["target_node"],
            "additionalProperties": False,
        },
    },
    "required": ["automaton_id", "action", "parameters"],
    "additionalProperties": False,
}

validator = Draft7Validator(AUTOMATON_COMMAND_SCHEMA)
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _result(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _runtime_config() -> tuple[str, str, float]:
    mesh_api_url = os.environ.get("MESH_CONTROLLER_URL", MESH_API_URL).rstrip("/")
    security_token = os.environ.get("MESH_AUTH_TOKEN", SECURITY_TOKEN or "")
    timeout = float(os.environ.get("MESH_REQUEST_TIMEOUT", str(REQUEST_TIMEOUT)))

    if not security_token:
        raise RuntimeError("MESH_AUTH_TOKEN ist nicht gesetzt.")
    if not mesh_api_url.startswith("https://"):
        raise RuntimeError("MESH_CONTROLLER_URL muss HTTPS verwenden.")
    if timeout <= 0 or timeout > 120:
        raise RuntimeError("MESH_REQUEST_TIMEOUT muss zwischen 0 und 120 Sekunden liegen.")

    return mesh_api_url, security_token, timeout


def _validate_identifier(value: str, field: str) -> None:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Ungültiger Wert für {field}.")


def _dispatch(command: dict[str, Any]) -> str:
    errors = sorted(validator.iter_errors(command), key=lambda e: list(e.path))
    if errors:
        return _result(
            status="rejected",
            error="schema_validation_failed",
            details=[
                {
                    "path": ".".join(map(str, error.path)),
                    "message": error.message,
                }
                for error in errors
            ],
        )

    automaton_id = command["automaton_id"]
    action = command["action"]
    parameters = command["parameters"]
    target_node = parameters["target_node"]

    try:
        mesh_api_url, security_token, timeout = _runtime_config()
        _validate_identifier(automaton_id, "automaton_id")
        _validate_identifier(target_node, "target_node")
    except (RuntimeError, ValueError) as exc:
        return _result(status="rejected", error="security_policy_failed", detail=str(exc))

    endpoint = (
        f"{mesh_api_url}/nodes/{quote(target_node, safe='')}/"
        f"automata/{quote(automaton_id, safe='')}/commands"
    )

    headers = {
        "Authorization": f"Bearer {security_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "MCT-1700021-Orchestrator/1.0",
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"action": action, "parameters": parameters},
            timeout=timeout,
        )
    except requests.Timeout:
        return _result(status="failed", error="mesh_timeout", target_node=target_node)
    except requests.ConnectionError as exc:
        return _result(
            status="failed",
            error="mesh_connection_failed",
            target_node=target_node,
            detail=str(exc),
        )
    except requests.RequestException as exc:
        return _result(status="failed", error="mesh_transport_error", detail=str(exc))

    try:
        remote_result: Any = response.json()
    except ValueError:
        remote_result = {"raw_response": response.text[:2048]}

    if not response.ok:
        return _result(
            status="failed",
            error="mesh_rejected_command",
            http_status=response.status_code,
            automaton_id=automaton_id,
            action=action,
            target_node=target_node,
            remote_result=remote_result,
        )

    return _result(
        status="orchestrated",
        automaton_id=automaton_id,
        action_executed=action,
        target_node=target_node,
        http_status=response.status_code,
        dispatch_result=remote_result,
    )


@orchestrator_mcp.tool()
def dispatch_automaton_command(command_payload_json: str) -> str:
    """Use this when a validated command must be dispatched to a known automaton node.

    The tool mutates an external system. Input must be one JSON object matching the
    AutomatonCommand schema; unknown fields and unknown actions are rejected.
    """
    try:
        command = json.loads(command_payload_json)
    except json.JSONDecodeError as exc:
        return _result(status="rejected", error="invalid_json", detail=str(exc))

    if not isinstance(command, dict):
        return _result(status="rejected", error="schema_validation_failed", detail="Payload muss ein JSON-Objekt sein.")

    return _dispatch(command)


if __name__ == "__main__":
    orchestrator_mcp.run()
