from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Iterable, Literal


CONTROL_ROOM_SECURITY_VERSION = "sportabase-control-room-security-v1"

ControlRoomAuthStrength = Literal[
    "unknown",
    "single_factor",
    "mfa",
    "phishing_resistant",
]

_AUTH_STRENGTH_RANK = {
    "unknown": 0,
    "single_factor": 1,
    "mfa": 2,
    "phishing_resistant": 3,
}


class ControlRoomSecurityError(RuntimeError):
    """Base error for Control Room authorization failures."""


class ControlRoomSecurityMisconfigured(ControlRoomSecurityError):
    """Raised when the server-side Control Room policy is incomplete."""


class ControlRoomAccessDenied(ControlRoomSecurityError):
    """Raised when a verified identity does not satisfy Control Room policy."""


@dataclass(frozen=True)
class ControlRoomSecurityPolicy:
    enabled: bool
    allowed_emails: tuple[str, ...]
    expected_issuer: str
    expected_audience: str
    minimum_auth_strength: ControlRoomAuthStrength = "phishing_resistant"
    max_session_age_seconds: int = 3600
    clock_skew_seconds: int = 60


@dataclass(frozen=True)
class VerifiedControlRoomIdentity:
    """Normalized identity produced only after cryptographic token verification.

    The provider adapter is responsible for verifying the token signature and
    mapping provider-specific authentication evidence into ``auth_strength``.
    This module remains the Sportabase authorization authority.
    """

    token_verified: bool
    subject: str
    email: str
    issuer: str
    audiences: tuple[str, ...]
    issued_at_epoch: int
    authenticated_at_epoch: int
    expires_at_epoch: int
    auth_strength: ControlRoomAuthStrength
    auth_methods: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlRoomPrincipal:
    version: str
    subject: str
    email: str
    issuer: str
    audience: str
    auth_strength: ControlRoomAuthStrength
    auth_methods: tuple[str, ...]
    authenticated_at_epoch: int
    expires_at_epoch: int

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "subject": self.subject,
            "email": self.email,
            "issuer": self.issuer,
            "audience": self.audience,
            "auth_strength": self.auth_strength,
            "auth_methods": list(self.auth_methods),
            "authenticated_at_epoch": self.authenticated_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
        }


def normalize_email(value: object) -> str:
    return str(value or "").strip().casefold()


def normalize_email_allowlist(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []

    for value in values:
        email = normalize_email(value)
        if email and email not in normalized:
            normalized.append(email)

    return tuple(normalized)


def validate_control_room_policy(policy: ControlRoomSecurityPolicy) -> None:
    if not policy.enabled:
        return

    allowed = normalize_email_allowlist(policy.allowed_emails)
    if not allowed:
        raise ControlRoomSecurityMisconfigured(
            "Control Room requires at least one exact allowlisted email."
        )

    if not str(policy.expected_issuer or "").strip():
        raise ControlRoomSecurityMisconfigured(
            "Control Room token issuer is not configured."
        )

    if not str(policy.expected_audience or "").strip():
        raise ControlRoomSecurityMisconfigured(
            "Control Room token audience is not configured."
        )

    if policy.minimum_auth_strength not in _AUTH_STRENGTH_RANK:
        raise ControlRoomSecurityMisconfigured(
            "Control Room minimum authentication strength is invalid."
        )

    if int(policy.max_session_age_seconds) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Control Room maximum session age must be positive."
        )

    if int(policy.clock_skew_seconds) < 0:
        raise ControlRoomSecurityMisconfigured(
            "Control Room clock skew cannot be negative."
        )


def authorize_control_room_identity(
    identity: VerifiedControlRoomIdentity,
    *,
    policy: ControlRoomSecurityPolicy,
    now_epoch: int | None = None,
    max_auth_age_seconds: int | None = None,
) -> ControlRoomPrincipal:
    """Authorize one already-verified identity using fail-closed policy checks."""

    validate_control_room_policy(policy)

    if not policy.enabled:
        raise ControlRoomAccessDenied("Control Room is disabled.")

    if not identity.token_verified:
        raise ControlRoomAccessDenied(
            "Control Room token has not been cryptographically verified."
        )

    subject = str(identity.subject or "").strip()
    email = normalize_email(identity.email)
    issuer = str(identity.issuer or "").strip()
    audiences = tuple(
        str(value or "").strip()
        for value in identity.audiences
        if str(value or "").strip()
    )

    if not subject:
        raise ControlRoomAccessDenied("Control Room identity subject is missing.")

    if not email:
        raise ControlRoomAccessDenied("Control Room identity email is missing.")

    if email not in normalize_email_allowlist(policy.allowed_emails):
        raise ControlRoomAccessDenied(
            "Control Room identity is not allowlisted."
        )

    if issuer != str(policy.expected_issuer).strip():
        raise ControlRoomAccessDenied("Control Room token issuer is invalid.")

    expected_audience = str(policy.expected_audience).strip()
    if expected_audience not in audiences:
        raise ControlRoomAccessDenied("Control Room token audience is invalid.")

    current = int(time()) if now_epoch is None else int(now_epoch)
    skew = int(policy.clock_skew_seconds)

    issued_at = int(identity.issued_at_epoch)
    authenticated_at = int(identity.authenticated_at_epoch)
    expires_at = int(identity.expires_at_epoch)

    if issued_at <= 0 or authenticated_at <= 0 or expires_at <= 0:
        raise ControlRoomAccessDenied(
            "Control Room token timestamps are incomplete."
        )

    if issued_at > current + skew:
        raise ControlRoomAccessDenied("Control Room token was issued in the future.")

    if authenticated_at > current + skew:
        raise ControlRoomAccessDenied(
            "Control Room authentication time is in the future."
        )

    if expires_at <= current - skew:
        raise ControlRoomAccessDenied("Control Room token has expired.")

    if expires_at <= issued_at:
        raise ControlRoomAccessDenied(
            "Control Room token lifetime is invalid."
        )

    auth_age_limit = (
        int(policy.max_session_age_seconds)
        if max_auth_age_seconds is None
        else int(max_auth_age_seconds)
    )

    if auth_age_limit <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Control Room authentication age limit must be positive."
        )

    if current - authenticated_at > auth_age_limit + skew:
        raise ControlRoomAccessDenied(
            "Control Room authentication is too old; fresh authentication is required."
        )

    actual_strength = _AUTH_STRENGTH_RANK.get(identity.auth_strength, 0)
    required_strength = _AUTH_STRENGTH_RANK[policy.minimum_auth_strength]

    if actual_strength < required_strength:
        raise ControlRoomAccessDenied(
            "Control Room requires stronger authentication assurance."
        )

    return ControlRoomPrincipal(
        version=CONTROL_ROOM_SECURITY_VERSION,
        subject=subject,
        email=email,
        issuer=issuer,
        audience=expected_audience,
        auth_strength=identity.auth_strength,
        auth_methods=tuple(
            str(value or "").strip()
            for value in identity.auth_methods
            if str(value or "").strip()
        ),
        authenticated_at_epoch=authenticated_at,
        expires_at_epoch=expires_at,
    )


__all__ = [
    "CONTROL_ROOM_SECURITY_VERSION",
    "ControlRoomAuthStrength",
    "ControlRoomSecurityError",
    "ControlRoomSecurityMisconfigured",
    "ControlRoomAccessDenied",
    "ControlRoomSecurityPolicy",
    "VerifiedControlRoomIdentity",
    "ControlRoomPrincipal",
    "normalize_email",
    "normalize_email_allowlist",
    "validate_control_room_policy",
    "authorize_control_room_identity",
]
