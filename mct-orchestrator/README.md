# MCT-1700021 System Orchestrator

A fail-closed Python MCP server for validated automaton dispatch, deterministic SHB routing, and a hotspot-to-backoffice trust boundary.

## Architecture

```text
Hotspot / Mobile WAN
        |
        v
Authenticated tunnel
        |
        v
Hotspot Gateway
- client identity
- tunnel state
- session validity
- permission allowlist
        |
        v
SHB Router
- capability/operation allowlist
- health + stability gates
- deterministic target selection
        |
        +--> SHB Backoffice
        |     - read
        |     - write
        |     - sync
        |     - admin
        |
        +--> MCP connectors
        |
        +--> Mesh controller
              - initialize
              - sync
              - execute
              - halt
```

The hotspot itself is treated only as transport. A request does not receive a backoffice route unless the tunnel is authenticated, the session is valid, and the client has the exact `backoffice:<operation>` permission.

## Security properties

- Strict Draft-07 validation for automaton commands.
- Unknown fields and unsupported operations fail closed.
- `MESH_AUTH_TOKEN` is required for external automaton dispatch.
- Mesh controller URL must use HTTPS.
- Bounded HTTP timeouts and explicit transport-failure handling.
- SHB routing filters by health, stability, capability, and allowed operation.
- Backoffice permissions are split into `read`, `write`, `sync`, and `admin`.
- Gateway authorization and routing do not execute a backoffice operation; they return an authorized route only.
- Audit events are generated for accepted and rejected backoffice authorization decisions.
- No unverified ZeroTier, PQC, Cloudflare, or other security property is claimed.

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

Do not commit real tokens.

## Run

```bash
python server.py
```

## MCP tools

### `route_shb_request`

Read-only route resolution. Selection is deterministic: highest priority, then highest stability, then lexicographically smallest route ID.

```json
{
  "capability": "connector",
  "operation": "fetch",
  "min_stability": 0.9
}
```

### `authorize_hotspot_backoffice`

Validates the trust boundary and returns an authorized SHB backoffice route without performing the external action.

```json
{
  "client_id": "hotspot-client-01",
  "tunnel_authenticated": true,
  "session_valid": true,
  "permissions": ["backoffice:read"],
  "backoffice": {
    "operation": "read",
    "resource": "jobs",
    "payload": {}
  }
}
```

### `dispatch_automaton_command`

Mutating external dispatch to the configured mesh controller.

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

## Default SHB routes

- `mesh-controller-primary`: `initialize`, `sync`, `execute`, `halt`
- `backoffice-primary`: `read`, `write`, `sync`, `admin`
- `connector-readonly`: `search`, `fetch`, `status`

## Test

```bash
pytest -q
```

## Production hardening still recommended

Before real infrastructure use, source tunnel/session assertions from a trusted identity provider or VPN controller rather than caller-supplied booleans. Add controller-side authorization, replay/idempotency protection, durable or immutable audit storage, rate limiting, authenticated health telemetry, certificate validation/pinning where appropriate, and an independent approval boundary for high-impact `admin`, `execute`, and `halt` operations.
