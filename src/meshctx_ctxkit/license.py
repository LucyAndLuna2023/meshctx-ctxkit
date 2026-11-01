"""License checking for ctxkit's paid tier.

Design constraint that drives everything here: **the license must verify
offline.** A user who paid should not be locked out because our licence
server is down, and we should not be running a phone-home endpoint that
sees every user's usage.

So licenses are Ed25519-signed tokens (JWT, ``EdDSA``):
  - private key lives only on the server (never shipped)
  - public key is baked into the package
  - the client verifies the signature locally, against the expiry

This module is intentionally dependency-light: it uses ``PyJWT[crypto]``
when available, and falls back to a clear error when it is not. Memory and
verification (the free tier) never touch this module at all.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal

Tier = Literal["free", "pro", "team"]

# Public key shipped with the client. Replace with the real one when the
# Stripe setup is live (see billing/README.md). The placeholder is refused
# explicitly rather than silently trusting anything.
PUBLIC_KEY_PEM = os.environ.get("CTXKIT_LICENSE_PUBKEY") or """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAsnFCGUPdXj1osPhWOsdxNj8ngmaMciTksQP2h86hmw8=
-----END PUBLIC KEY-----"""

_PLACEHOLDER = "PLACEHOLDER_REPLACE_ME"

# Free tier never expires and needs no token.
FREE = "free"

QUOTAS: dict[Tier, dict[str, Any]] = {
    "free":  {"consensus_per_month": 0,    "email_support": False, "managed_keys": False, "seats": 1},
    "pro":   {"consensus_per_month": 300,  "email_support": True,  "managed_keys": False, "seats": 1},
    "team":  {"consensus_per_month": 3000, "email_support": True,  "managed_keys": True,  "seats": 5},
}


@dataclass
class License:
    tier: Tier = "free"
    email: str = ""
    exp: int = 0                       # unix ts; 0 = never (free)
    seats: int = 1
    managed_keys: bool = False
    claims: dict[str, Any] = field(default_factory=dict)
    reason: str = ""                   # why the license isn't active, if so

    @property
    def active(self) -> bool:
        return self.tier != "free" and (self.exp == 0 or self.exp > time.time())

    @property
    def consensus_quota(self) -> int:
        return QUOTAS[self.tier]["consensus_per_month"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "active": self.active,
            "email": self.email,
            "expires": self.exp,
            "expires_human": (time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(self.exp))
                              if self.exp else "never"),
            "seats": self.seats,
            "managed_keys": self.managed_keys,
            "consensus_quota": self.consensus_quota,
            "reason": self.reason,
        }


def _jwt():
    try:
        import jwt  # type: ignore
        return jwt
    except ImportError:  # pragma: no cover - optional dependency path
        return None


def verify_license(token: str | None, public_key: str | None = None,
                   *, now: float | None = None) -> License:
    """Verify a license token locally. Never raises; returns a License with
    ``reason`` set if anything is off."""
    if not token:
        return License(tier="free", reason="no token (free tier)")
    jwt = _jwt()
    if jwt is None:
        return License(tier="free", reason=(
                "licence verification needs PyJWT: "
                "pip install 'meshctx-ctxkit[license]'"))
    key = public_key or PUBLIC_KEY_PEM
    if _PLACEHOLDER in key:
        return License(tier="free",
                       reason="license public key not configured in this build")
    try:
        # EdDSA only. Rejecting HS256/RS256 prevents the classic
        # "alg: none" and public-key-as-HMAC-secret downgrade attacks.
        claims = jwt.decode(token, key, algorithms=["EdDSA"],
                            options={"require": ["tier", "exp"]})
    except Exception as e:
        return License(tier="free", reason=f"invalid license: {type(e).__name__}: {e}")

    tier = claims.get("tier", "free")
    if tier not in QUOTAS:
        return License(tier="free", reason=f"unknown tier: {tier}")
    exp = int(claims.get("exp") or 0)
    lic = License(
        tier=tier,
        email=claims.get("email", ""),
        exp=exp,
        seats=int(claims.get("seats") or QUOTAS[tier]["seats"]),
        managed_keys=bool(claims.get("managed_keys",
                                     QUOTAS[tier]["managed_keys"])),
        claims=claims,
    )
    if now is not None and exp and exp <= now:
        lic.tier = "free"
        lic.reason = f"license expired on {time.strftime('%Y-%m-%d', time.gmtime(exp))}"
    return lic


def load_license_from_env(public_key: str | None = None) -> License:
    """Read CTXKIT_LICENSE, or ~/.ctxkit/license.key if the env var is unset."""
    token = os.environ.get("CTXKIT_LICENSE", "").strip()
    if not token:
        path = os.path.join(os.environ.get("CTXKIT_HOME") or 
                            os.path.join(os.path.expanduser("~"), ".ctxkit"),
                            "license.key")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                token = fh.read().strip()
        except OSError:
            token = ""
    return verify_license(token, public_key)


def sign_license(private_key_pem: str, *, tier: Tier, email: str,
                 days: int = 30, seats: int | None = None,
                 managed_keys: bool | None = None) -> str:
    """Server-side only. Produces the token we email to a paying customer."""
    jwt = _jwt()
    if jwt is None:
        raise RuntimeError("PyJWT required on the signing side: pip install pyjwt[crypto]")
    now = int(time.time())
    claims: dict[str, Any] = {
        "tier": tier,
        "email": email,
        "iat": now,
        "exp": now + days * 86400,
        "iss": "ctxkit-billing",
    }
    if seats is not None:
        claims["seats"] = seats
    if managed_keys is not None:
        claims["managed_keys"] = managed_keys
    return jwt.encode(claims, private_key_pem, algorithm="EdDSA")
