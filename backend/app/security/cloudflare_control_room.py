from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any, Callable, Mapping

from fastapi import Request

from app.security.cloudflare_access import (
    CloudflareAccessAssurance,
    CloudflareAccessVerifierConfig,
    default_cloudflare_claim_assurance,
    verify_cloudflare_access_request,
)
from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomPrincipal,
    ControlRoomSecurityMisconfigured,
    ControlRoomSecurityPolicy,
    authorize_control_room_identity,
)


CLOUDFLARE_CONTROL_ROOM_ASSURANCE_VERSION = (
    "sportabase-cloudflare-control-room-assurance-v1"
)

_PHISHING_RESISTANT_AUTHENTICATORS = frozenset(
    {
        "security_key",
        "biometrics",
    }
)


@dataclass(frozen=True)
class CloudflareIndependentMfaAttestation:
    """Verified snapshot of the Access MFA policy protecting Control Room.

    ``verified`` is intentionally separate from the configuration values.
    Production code must obtain this object from an independent Cloudflare
    configuration verifier rather than assuming that dashboard settings are
    correct.
    """

    verified: bool
    verified_at_epoch: int
    application_audience: str
    allowed_authenticators: tuple[str, ...]
    mfa_disabled: bool
    mfa_session_duration_seconds: int
    source: str = "cloudflare_access_policy_api"


@dataclass(frozen=True)
class CloudflareIndependentMfaAssurancePolicy:
    max_attestation_age_seconds: int = 300
    max_application_token_lifetime_seconds: int = 900
    clock_skew_seconds: int = 60
    require_every_login: bool = True


def normalize_cloudflare_authenticators(
    values: object,
) -> tuple[str, ...]:
    if isinstance(values, str):
        candidates = (values,)
    elif isinstance(values, (list, tuple, set, frozenset)):
        candidates = tuple(values)
    else:
        candidates = ()

    normalized: list[str] = []
    for candidate in candidates:
        value = str(candidate or "").strip().casefold()
        if value and value not in normalized:
            normalized.append(value)

    return tuple(normalized)


def validate_independent_mfa_assurance_policy(
    policy: CloudflareIndependentMfaAssurancePolicy,
) -> None:
    if int(policy.max_attestation_age_seconds) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare MFA attestation age limit must be positive."
        )

    if int(policy.max_application_token_lifetime_seconds) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare application token lifetime limit must be positive."
        )

    if int(policy.clock_skew_seconds) < 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare assurance clock skew cannot be negative."
        )

    if not policy.require_every_login:
        raise ControlRoomSecurityMisconfigured(
            "Control Room requires Cloudflare independent MFA on every login."
        )


def validate_independent_mfa_attestation(
    attestation: CloudflareIndependentMfaAttestation,
    *,
    expected_audience: str,
    policy: CloudflareIndependentMfaAssurancePolicy,
    now_epoch: int | None = None,
) -> tuple[str, ...]:
    validate_independent_mfa_assurance_policy(policy)

    if not isinstance(attestation, CloudflareIndependentMfaAttestation):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare independent MFA attestation is invalid."
        )

    if not attestation.verified:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare independent MFA policy has not been verified."
        )

    audience = str(attestation.application_audience or "").strip()
    required_audience = str(expected_audience or "").strip()

    if not required_audience or audience != required_audience:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare independent MFA attestation audience is invalid."
        )

    if attestation.mfa_disabled:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare independent MFA is disabled for Control Room."
        )

    authenticators = normalize_cloudflare_authenticators(
        attestation.allowed_authenticators
    )

    if not authenticators:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare independent MFA has no allowed authenticators."
        )

    unsupported = tuple(
        value
        for value in authenticators
        if value not in _PHISHING_RESISTANT_AUTHENTICATORS
    )

    if unsupported:
        raise ControlRoomSecurityMisconfigured(
            "Control Room Cloudflare MFA allows a non-phishing-resistant "
            "authenticator."
        )

    if (
        policy.require_every_login
        and int(attestation.mfa_session_duration_seconds) != 0
    ):
        raise ControlRoomSecurityMisconfigured(
            "Control Room Cloudflare MFA must require every login."
        )

    verified_at = int(attestation.verified_at_epoch)
    if verified_at <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare MFA attestation verification time is missing."
        )

    current = int(time()) if now_epoch is None else int(now_epoch)
    skew = int(policy.clock_skew_seconds)

    if verified_at > current + skew:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare MFA attestation verification time is in the future."
        )

    if (
        current - verified_at
        > int(policy.max_attestation_age_seconds) + skew
    ):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare MFA attestation is stale."
        )

    return authenticators


def build_attested_independent_mfa_assurance_resolver(
    *,
    attestation: CloudflareIndependentMfaAttestation,
    expected_audience: str,
    policy: CloudflareIndependentMfaAssurancePolicy | None = None,
    now_epoch_resolver: Callable[[], int] | None = None,
) -> Callable[[Mapping[str, Any]], CloudflareAccessAssurance]:
    assurance_policy = (
        policy
        if policy is not None
        else CloudflareIndependentMfaAssurancePolicy()
    )
    clock = now_epoch_resolver or (lambda: int(time()))

    def resolve(
        claims: Mapping[str, Any],
    ) -> CloudflareAccessAssurance:
        now_epoch = int(clock())

        authenticators = validate_independent_mfa_attestation(
            attestation,
            expected_audience=expected_audience,
            policy=assurance_policy,
            now_epoch=now_epoch,
        )

        try:
            issued_at = int(claims.get("iat") or 0)
            expires_at = int(claims.get("exp") or 0)
        except Exception as error:
            raise ControlRoomAccessDenied(
                "Cloudflare Access token lifetime is invalid."
            ) from error

        if issued_at <= 0 or expires_at <= issued_at:
            raise ControlRoomAccessDenied(
                "Cloudflare Access token lifetime is invalid."
            )

        token_lifetime = expires_at - issued_at
        if (
            token_lifetime
            > int(
                assurance_policy.max_application_token_lifetime_seconds
            )
        ):
            raise ControlRoomAccessDenied(
                "Cloudflare Access application token lifetime exceeds "
                "the Control Room limit."
            )

        # Preserve stronger signed IdP evidence when it is available, but never
        # depend on it. Independent MFA is guaranteed by the separately verified
        # Access policy attestation. The application-token iat is therefore used
        # as the bounded policy-evaluation/authentication freshness anchor.
        signed = default_cloudflare_claim_assurance(claims)
        methods: list[str] = [
            "cloudflare_independent_mfa",
        ]

        for value in authenticators:
            if value not in methods:
                methods.append(value)

        for value in signed.auth_methods:
            if value not in methods:
                methods.append(value)

        return CloudflareAccessAssurance(
            authenticated_at_epoch=issued_at,
            auth_strength="phishing_resistant",
            auth_methods=tuple(methods),
        )

    return resolve


def build_cloudflare_control_room_guard(
    *,
    verifier_config: CloudflareAccessVerifierConfig,
    authorization_policy: ControlRoomSecurityPolicy,
    mfa_attestation: CloudflareIndependentMfaAttestation,
    assurance_policy: CloudflareIndependentMfaAssurancePolicy | None = None,
    jwks_client_factory: Callable[[str], Any] | None = None,
    now_epoch_resolver: Callable[[], int] | None = None,
) -> Callable[[Request], ControlRoomPrincipal]:
    clock = now_epoch_resolver or (lambda: int(time()))

    assurance_resolver = (
        build_attested_independent_mfa_assurance_resolver(
            attestation=mfa_attestation,
            expected_audience=verifier_config.audience,
            policy=assurance_policy,
            now_epoch_resolver=clock,
        )
    )

    def guard(request: Request) -> ControlRoomPrincipal:
        kwargs: dict[str, Any] = {
            "config": verifier_config,
            "assurance_resolver": assurance_resolver,
        }
        if jwks_client_factory is not None:
            kwargs["jwks_client_factory"] = jwks_client_factory

        identity = verify_cloudflare_access_request(
            request,
            **kwargs,
        )

        return authorize_control_room_identity(
            identity,
            policy=authorization_policy,
            now_epoch=int(clock()),
        )

    return guard


__all__ = [
    "CLOUDFLARE_CONTROL_ROOM_ASSURANCE_VERSION",
    "CloudflareIndependentMfaAttestation",
    "CloudflareIndependentMfaAssurancePolicy",
    "normalize_cloudflare_authenticators",
    "validate_independent_mfa_assurance_policy",
    "validate_independent_mfa_attestation",
    "build_attested_independent_mfa_assurance_resolver",
    "build_cloudflare_control_room_guard",
]
