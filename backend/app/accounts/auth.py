"""Clerk session JWT verification; no client identity or test-mode fallback."""
from dataclasses import dataclass
from functools import lru_cache
import os
import threading
import time
from urllib.parse import urlparse

import jwt
import requests
from fastapi import HTTPException


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    audience: str | None = None
    authorized_parties: tuple[str, ...] = ()


class ClerkVerifier:
    def __init__(self, config: AuthConfig, *, fetch_keys=None, clock=time.monotonic):
        self.config = config
        self.fetch_keys = fetch_keys or self._fetch_keys
        self.clock = clock
        self.keys = {}
        self.loaded_at = None
        self.lock = threading.Lock()

    def _fetch_keys(self):
        # URL comes exclusively from trusted server configuration, never JWT jku/iss.
        response = requests.get(self.config.issuer + "/.well-known/jwks.json", timeout=5, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200 or len(response.content) > 65536:
            raise ValueError("Invalid key response")
        return response.json()

    def verify(self, token: str) -> dict:
        try:
            parsed = urlparse(self.config.issuer)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                    parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
                raise ValueError("Invalid configuration")
            if len(token) > 16384:
                raise ValueError("Token too long")
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
                raise ValueError("Invalid header")
            now = self.clock()
            with self.lock:
                # Cache has a finite lifetime; unknown IDs can trigger at most one
                # refresh every 30 seconds, preventing random-kid network floods.
                age = float("inf") if self.loaded_at is None else now - self.loaded_at
                if age >= 300 or (header["kid"] not in self.keys and age >= 30):
                    payload = self.fetch_keys()
                    candidates = payload.get("keys", [])
                    if not isinstance(candidates, list) or len(candidates) > 32:
                        raise ValueError("Invalid keys")
                    keys = {}
                    for value in candidates:
                        if value.get("kty") == "RSA" and value.get("use", "sig") == "sig" and value.get("alg", "RS256") == "RS256":
                            kid = value.get("kid")
                            if not isinstance(kid, str) or kid in keys:
                                raise ValueError("Ambiguous key")
                            key = jwt.PyJWK.from_dict(value, algorithm="RS256").key
                            if key.key_size < 2048:
                                raise ValueError("Weak key")
                            keys[kid] = key
                    self.keys, self.loaded_at = keys, now
                key = self.keys.get(header["kid"])
                if key is None or now - self.loaded_at >= 300:
                    raise ValueError("Unknown key")
            claims = jwt.decode(token, key, algorithms=["RS256"], issuer=self.config.issuer,
                                audience=self.config.audience,
                                options={"require": ["exp", "nbf", "iat", "iss", "sub", "sid"],
                                         "verify_aud": self.config.audience is not None})
            if (not isinstance(claims["sub"], str) or not claims["sub"].startswith("user_") or
                    not isinstance(claims["sid"], str) or not claims["sid"].strip() or
                    len(claims["sid"]) > 256):
                raise ValueError("Invalid session")
            if claims.get("sts") not in (None, "active"):
                raise ValueError("Session tasks incomplete")
            # Clerk defines azp as the Origin present when the session token was
            # minted. Native clients may legitimately omit it; any supplied value
            # must be a non-empty string and, when configured, match the allowlist.
            authorized_party = claims.get("azp")
            if authorized_party is not None:
                if (not isinstance(authorized_party, str) or not authorized_party.strip() or
                        (self.config.authorized_parties and authorized_party not in self.config.authorized_parties)):
                    raise ValueError("Unauthorized party")
            return claims
        except Exception as exc:
            raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"}) from exc


@lru_cache(maxsize=1)
def configured_verifier():
    authorized_parties = tuple(v.strip() for v in os.getenv("CLERK_AUTHORIZED_PARTIES", "").split(",") if v.strip())
    if os.getenv("SPORTABASE_ENV", "development").strip().lower() == "production" and not authorized_parties:
        raise RuntimeError("Production requires CLERK_AUTHORIZED_PARTIES for browser-origin tokens.")
    return ClerkVerifier(AuthConfig(
        issuer=os.getenv("CLERK_ISSUER", "").rstrip("/"),
        audience=os.getenv("CLERK_AUDIENCE") or None,
        authorized_parties=authorized_parties,
    ))


def recent_intent(claims):
    ages = claims.get("fva")
    if not isinstance(ages, list) or not ages or type(ages[0]) is not int or not 0 <= ages[0] <= 5:
        raise HTTPException(403, "Verify your account again before deleting data.")
