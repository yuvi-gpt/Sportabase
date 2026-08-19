from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import jwt
from fastapi import Request
from jwt import PyJWKClient
from jwt.exceptions import (
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
)

from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomAuthStrength,
    ControlRoomSecurityMisconfigured,
    VerifiedControlRoomIdentity,
)


CLOUDFLARE_ACCESS_JWT_VERSION = (
    "sportabase-cloudflare-access-jwt-v1"
)
CLOUDFLARE_ACCESS_JWT_HEADER = "cf-access-jwt-assertion"
CLOUDFLARE_ACCESS_JWT_ALGORITHM = "RS256"

_PHISHING_RESISTANT_AMR = frozenset(
    {
        "hwk",
        "swk",
        "face",
        "fpt",
        "iris",
        "retina",
        "vbm",
    }
)
_MFA_AMR = frozenset(
    {
        "mfa",
        "otp",
    }
) | _PHISHING_RESISTANT_AMR
_SINGLE_FACTOR_AMR = frozenset(
    {
        "pwd",
        "pin",
        "kba",
        "sms",
        "tel",
    }
)


@dataclass(frozen=True)
class CloudflareAccessVerifierConfig:
    team_domain: str
    audience: str
    clock_skew_seconds: int = 60


@dataclass(frozen=True)
class CloudflareAccessAssurance:
    authenticated_at_epoch: int
    auth_strength: ControlRoomAuthStrength
    auth_methods: tuple[str, ...]


def normalize_cloudflare_team_domain(value: object) -> str:
    domain = str(value or "").strip().rstrip("/")
    if not domain:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access team domain is not configured."
        )

    parsed = urlparse(domain)
    hostname = str(parsed.hostname or "").casefold()

    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or not hostname.endswith(".cloudflareaccess.com")
    ):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access team domain must be an HTTPS "
            "*.cloudflareaccess.com origin."
        )

    return "https://" + hostname


def validate_cloudflare_access_config(
    config: CloudflareAccessVerifierConfig,
) -> None:
    normalize_cloudflare_team_domain(config.team_domain)

    if not str(config.audience or "").strip():
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access application audience is not configured."
        )

    if int(config.clock_skew_seconds) < 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access clock skew cannot be negative."
        )


def cloudflare_access_certs_url(
    team_domain: object,
) -> str:
    return (
        normalize_cloudflare_team_domain(team_domain)
        + "/cdn-cgi/access/certs"
    )


def normalize_auth_methods(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = tuple(value)
    else:
        candidates = ()

    normalized: list[str] = []
    for candidate in candidates:
        method = str(candidate or "").strip().casefold()
        if method and method not in normalized:
            normalized.append(method)

    return tuple(normalized)


def auth_strength_from_amr(
    methods: tuple[str, ...],
) -> ControlRoomAuthStrength:
    method_set = frozenset(methods)

    if method_set & _PHISHING_RESISTANT_AMR:
        return "phishing_resistant"

    if method_set & _MFA_AMR:
        return "mfa"

    if method_set & _SINGLE_FACTOR_AMR:
        return "single_factor"

    return "unknown"


def _claim_audiences(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        candidates = (value,)
    elif isinstance(value, (list, tuple)):
        candidates = tuple(value)
    else:
        candidates = ()

    return tuple(
        str(candidate or "").strip()
        for candidate in candidates
        if str(candidate or "").strip()
    )


def default_cloudflare_claim_assurance(
    claims: Mapping[str, Any],
) -> CloudflareAccessAssurance:
    """Derive only assurance explicitly present in signed JWT claims.

    Cloudflare Access application tokens do not universally expose a fresh
    authentication timestamp or an AMR value. Missing evidence deliberately
    remains zero/unknown so the Sportabase authorization contract fails closed.
    A later provider-policy adapter may supply stronger assurance only after it
    can prove that assurance independently.
    """

    auth_methods = normalize_auth_methods(
        claims.get("amr")
    )

    try:
        authenticated_at = int(
            claims.get("auth_time") or 0
        )
    except Exception:
        authenticated_at = 0

    return CloudflareAccessAssurance(
        authenticated_at_epoch=max(0, authenticated_at),
        auth_strength=auth_strength_from_amr(auth_methods),
        auth_methods=auth_methods,
    )


def _default_jwks_client_factory(url: str):
    return PyJWKClient(url)


def verify_cloudflare_access_token(
    token: object,
    *,
    config: CloudflareAccessVerifierConfig,
    jwks_client_factory: Callable[[str], Any] = (
        _default_jwks_client_factory
    ),
    assurance_resolver: Callable[
        [Mapping[str, Any]],
        CloudflareAccessAssurance,
    ] = default_cloudflare_claim_assurance,
) -> VerifiedControlRoomIdentity:
    validate_cloudflare_access_config(config)

    encoded = str(token or "").strip()
    if not encoded:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT is missing."
        )

    try:
        header = jwt.get_unverified_header(encoded)
    except InvalidTokenError as error:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT header is invalid."
        ) from error

    if str(header.get("alg") or "") != CLOUDFLARE_ACCESS_JWT_ALGORITHM:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT algorithm is invalid."
        )

    if not str(header.get("kid") or "").strip():
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT signing key id is missing."
        )

    team_domain = normalize_cloudflare_team_domain(
        config.team_domain
    )
    certs_url = cloudflare_access_certs_url(team_domain)

    try:
        jwks_client = jwks_client_factory(certs_url)
        signing_key = jwks_client.get_signing_key_from_jwt(
            encoded
        )
    except PyJWKClientConnectionError as error:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access signing keys are unavailable."
        ) from error
    except PyJWKClientError as error:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT signing key is invalid."
        ) from error
    except ControlRoomSecurityMisconfigured:
        raise
    except Exception as error:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT signing key could not be resolved."
        ) from error

    key = getattr(signing_key, "key", signing_key)

    try:
        claims = jwt.decode(
            encoded,
            key,
            algorithms=[CLOUDFLARE_ACCESS_JWT_ALGORITHM],
            audience=str(config.audience).strip(),
            issuer=team_domain,
            leeway=int(config.clock_skew_seconds),
            options={
                "require": [
                    "exp",
                    "iat",
                    "nbf",
                    "iss",
                    "aud",
                    "sub",
                    "email",
                ],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except InvalidTokenError as error:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT verification failed."
        ) from error

    if str(claims.get("type") or "").strip() != "app":
        raise ControlRoomAccessDenied(
            "Cloudflare Access token type is invalid."
        )

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip()

    # Cloudflare service-token application JWTs have an empty subject and no
    # user email. Control Room is user-only and therefore rejects them.
    if not subject or not email:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT does not represent a user identity."
        )

    audiences = _claim_audiences(
        claims.get("aud")
    )

    try:
        issued_at = int(claims.get("iat") or 0)
        expires_at = int(claims.get("exp") or 0)
    except Exception as error:
        raise ControlRoomAccessDenied(
            "Cloudflare Access JWT timestamps are invalid."
        ) from error

    assurance = assurance_resolver(claims)
    if not isinstance(assurance, CloudflareAccessAssurance):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Access assurance resolver returned an invalid result."
        )

    return VerifiedControlRoomIdentity(
        token_verified=True,
        subject=subject,
        email=email,
        # Cloudflare documents the identity-token email as verified by the IdP.
        email_verified=True,
        issuer=str(claims.get("iss") or "").strip(),
        audiences=audiences,
        issued_at_epoch=issued_at,
        authenticated_at_epoch=(
            assurance.authenticated_at_epoch
        ),
        expires_at_epoch=expires_at,
        auth_strength=assurance.auth_strength,
        auth_methods=assurance.auth_methods,
    )


def verify_cloudflare_access_request(
    request: Request,
    *,
    config: CloudflareAccessVerifierConfig,
    jwks_client_factory: Callable[[str], Any] = (
        _default_jwks_client_factory
    ),
    assurance_resolver: Callable[
        [Mapping[str, Any]],
        CloudflareAccessAssurance,
    ] = default_cloudflare_claim_assurance,
) -> VerifiedControlRoomIdentity:
    token = request.headers.get(
        CLOUDFLARE_ACCESS_JWT_HEADER,
        "",
    )

    return verify_cloudflare_access_token(
        token,
        config=config,
        jwks_client_factory=jwks_client_factory,
        assurance_resolver=assurance_resolver,
    )


__all__ = [
    "CLOUDFLARE_ACCESS_JWT_VERSION",
    "CLOUDFLARE_ACCESS_JWT_HEADER",
    "CLOUDFLARE_ACCESS_JWT_ALGORITHM",
    "CloudflareAccessVerifierConfig",
    "CloudflareAccessAssurance",
    "normalize_cloudflare_team_domain",
    "validate_cloudflare_access_config",
    "cloudflare_access_certs_url",
    "normalize_auth_methods",
    "auth_strength_from_amr",
    "default_cloudflare_claim_assurance",
    "verify_cloudflare_access_token",
    "verify_cloudflare_access_request",
]
