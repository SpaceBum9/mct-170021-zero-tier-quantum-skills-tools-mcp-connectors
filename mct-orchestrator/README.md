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
Trusted Hotspot Gateway
- client identity
- tunnel/session state
- permission allowlist
- short-lived signed attestation
        |
        v
MCP Attestation Verifier
- HMAC-SHA256 signature
- issuer + audience checks
- expiry/lifetime checks
- nonce replay protection
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

The hotspot itself is transport only. Backoffice access is based on a signed gateway attestation, not caller-controlled `tunnel_authenticated`, `session_valid`, or permission fields.

## Security properties

- Strict Draft-07 validation for automaton commands.
- Unknown fields and unsupported operations fail closed.
- `MESH_AUTH_TOKEN` is required for external automaton dispatch.
- Mesh controller URL must use HTTPS.
- Bounded HTTP timeouts and explicit transport-failure handling.
- SHB routing filters by health, stability, capability, and allowed operation.
- Backoffice permissions are split into `read`, `write`, `sync`, and `admin`.
- Hotspot gateway attestations use HMAC-SHA256 and are checked for issuer, audience, expiry, maximum lifetime, authenticated tunnel/session claims, and nonce replay.
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

export SHB_ATTESTATION_SECRET='replace-with-a-random-secret-at-least-32-chars'
export SHB_ATTESTATION_AUDIENCE='mct-backoffice'
export SHB_ATTESTATION_ISSUER='shb-hotspot-gateway'
```

Do not commit real tokens or attestation secrets.

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

Verifies a signed gateway attestation and returns an authorized SHB backoffice route without performing the external action.

```json
{
  "attestation": "<signed-gateway-attestation>",
  "backoffice": {
    "operation": "read",
    "resource": "jobs",
    "payload": {}
  }
}
```

The trusted gateway signs claims with this exact shape:

```json
{
  "iss": "shb-hotspot-gateway",
  "aud": "mct-backoffice",
  "sub": "hotspot-client-01",
  "exp": 1787082000,
  "iat": 1787081880,
  "jti": "unique-request-nonce",
  "permissions": ["backoffice:read"],
  "tunnel_authenticated": true,
  "session_valid": true
}
```

Attestations are intentionally short-lived. The verifier defaults to a maximum lifetime of 300 seconds.

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

Tests cover signed authorization, tampered tokens, tunnel claim denial, missing permission, admin denial, wrong audience, and replay rejection.

## Production hardening still recommended

The process-local replay cache is sufficient only for a single-process prototype. Production should use a shared durable replay store (for example Redis with TTL or an equivalent transactional store), durable/immutable audit storage, key rotation with key IDs, rate limiting, authenticated health telemetry, controller-side authorization, certificate pinning where appropriate, and an independent approval boundary for high-impact `admin`, `execute`, and `halt` operations.
