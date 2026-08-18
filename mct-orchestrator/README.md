# MCT-1700021 System Orchestrator

A small, fail-closed Python MCP server that validates an automaton command and dispatches it to a configured HTTPS mesh-controller API.

## Security properties

- Rejects malformed JSON and commands outside a strict Draft-07 JSON Schema.
- Rejects unknown fields and unknown actions.
- Requires `MESH_AUTH_TOKEN`; there is no production placeholder fallback.
- Requires an HTTPS controller URL.
- Restricts identifiers before they are interpolated into the request path.
- Uses bounded HTTP timeouts.
- Does not claim ZeroTier, PQC, Cloudflare, or other transport properties it has not verified.
- Treats transport failure, timeout, and remote rejection as failure rather than success.

## Install

```bash
cd mct-orchestrator
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Configure

```bash
export MESH_CONTROLLER_URL='https://mesh.example.internal/api/v1'
export MESH_AUTH_TOKEN='replace-with-real-secret'
export MESH_REQUEST_TIMEOUT='10'
```

Do not commit the real token.

## Run

```bash
python server.py
```

`FastMCP.run()` uses the SDK's default transport. For ChatGPT deployment, expose the MCP server through an HTTPS-reachable endpoint using a transport/configuration supported by the current MCP SDK and follow the current ChatGPT MCP connection instructions.

## Command shape

```json
{
  "automaton_id": "automaton-01",
  "action": "sync",
  "parameters": {
    "target_node": "node-01",
    "stability_threshold": 0.9
  }
}
```

Allowed actions: `initialize`, `sync`, `execute`, `halt`.

The mesh controller is expected to accept:

```text
POST /api/v1/nodes/{target_node}/automata/{automaton_id}/commands
Authorization: Bearer ...
Content-Type: application/json
```

with the JSON body:

```json
{
  "action": "sync",
  "parameters": {
    "target_node": "node-01",
    "stability_threshold": 0.9
  }
}
```

## Test

```bash
pytest -q
```

## Production hardening still recommended

Before controlling real equipment or infrastructure, add controller-side authorization per automaton/action, replay or idempotency keys, immutable audit logging, rate limiting, certificate validation/pinning as appropriate, and a separate approval boundary for high-impact actions such as `halt` or `execute`.
