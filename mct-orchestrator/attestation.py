from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any


class AttestationError(ValueError):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise AttestationError("invalid base64url attestation") from exc


@dataclass(frozen=True)
class GatewayAttestation:
    issuer: str
    audience: str
    client_id: str
    expires_at: int
    issued_at: int
    nonce: str
    permissions: frozenset[str]


class ReplayCache:
    """Process-local replay cache. Replace with durable shared storage in production."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def consume(self, nonce: str, expires_at: int, now: int) -> None:
        self._seen = {key: exp for key, exp in self._seen.items() if exp >= now}
        if nonce in self._seen:
            raise AttestationError("attestation replay detected")
        self._seen[nonce] = expires_at


DEFAULT_REPLAY_CACHE = ReplayCache()


def sign_attestation(claims: dict[str, Any], secret: str) -> str:
    """Create a compact HMAC-SHA256 attestation for a trusted gateway service."""
    if not secret:
        raise AttestationError("attestation secret is required")
    payload = json.dumps(claims, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = _b64url_encode(payload)
    signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_b64url_encode(signature)}"


def verify_attestation(
    token: str,
    *,
    secret: str,
    expected_audience: str,
    expected_issuer: str = "shb-hotspot-gateway",
    now: int | None = None,
    max_lifetime_seconds: int = 300,
    replay_cache: ReplayCache | None = DEFAULT_REPLAY_CACHE,
) -> GatewayAttestation:
    if not isinstance(token, str) or token.count(".") != 1:
        raise AttestationError("invalid attestation format")
    if not secret:
        raise AttestationError("attestation verifier is not configured")

    encoded, signature_text = token.split(".", 1)
    supplied_signature = _b64url_decode(signature_text)
    expected_signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise AttestationError("invalid attestation signature")

    try:
        claims = json.loads(_b64url_decode(encoded))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AttestationError("invalid attestation payload") from exc
    if not isinstance(claims, dict):
        raise AttestationError("invalid attestation claims")

    required = {"iss", "aud", "sub", "exp", "iat", "jti", "permissions", "tunnel_authenticated", "session_valid"}
    if set(claims) != required:
        raise AttestationError("unexpected attestation claims")

    issuer = claims["iss"]
    audience = claims["aud"]
    client_id = claims["sub"]
    expires_at = claims["exp"]
    issued_at = claims["iat"]
    nonce = claims["jti"]
    permissions = claims["permissions"]

    if issuer != expected_issuer:
        raise AttestationError("unexpected attestation issuer")
    if audience != expected_audience:
        raise AttestationError("unexpected attestation audience")
    if not isinstance(client_id, str) or not client_id or len(client_id) > 128:
        raise AttestationError("invalid attestation subject")
    if isinstance(expires_at, bool) or not isinstance(expires_at, int):
        raise AttestationError("invalid attestation expiry")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise AttestationError("invalid attestation issued-at")
    if not isinstance(nonce, str) or not nonce or len(nonce) > 128:
        raise AttestationError("invalid attestation nonce")
    if not isinstance(permissions, list) or not all(isinstance(item, str) and item for item in permissions):
        raise AttestationError("invalid attestation permissions")
    if claims["tunnel_authenticated"] is not True:
        raise AttestationError("authenticated tunnel required")
    if claims["session_valid"] is not True:
        raise AttestationError("valid session required")

    current = int(time.time()) if now is None else now
    if issued_at > current + 30:
        raise AttestationError("attestation issued in the future")
    if expires_at < current:
        raise AttestationError("attestation expired")
    if expires_at <= issued_at or expires_at - issued_at > max_lifetime_seconds:
        raise AttestationError("attestation lifetime exceeds policy")

    if replay_cache is not None:
        replay_cache.consume(nonce, expires_at, current)

    return GatewayAttestation(
        issuer=issuer,
        audience=audience,
        client_id=client_id,
        expires_at=expires_at,
        issued_at=issued_at,
        nonce=nonce,
        permissions=frozenset(permissions),
    )
