from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import Lock
from time import time
from typing import Any, Callable, Mapping

from fastapi import Request

from app.security.cloudflare_access import (
    CloudflareAccessVerifierConfig,
    normalize_cloudflare_team_domain,
    verify_cloudflare_access_request,
)
from app.security.cloudflare_control_room import (
    CloudflareIndependentMfaAssurancePolicy,
    build_attested_independent_mfa_assurance_resolver,
)
from app.security.cloudflare_policy_audit import (
    CloudflarePolicyAuditConfig,
    CloudflarePolicyAuditResult,
    audit_cloudflare_control_room_policy,
)
from app.security.control_room import (
    ControlRoomPrincipal,
    ControlRoomSecurityMisconfigured,
    ControlRoomSecurityPolicy,
    authorize_control_room_identity,
    normalize_email_allowlist,
)
from app.security.control_room_origin import (
    protect_control_room_guard_with_origin_provenance,
)


CONTROL_ROOM_RUNTIME_VERSION = "sportabase-control-room-runtime-v1"


@dataclass(frozen=True)
class ControlRoomRuntimeConfig:
    enabled: bool
    team_domain: str
    account_id: str
    application_id: str
    application_audience: str
    identity_provider_id: str
    allowed_emails: tuple[str, ...]
    policy_audit_api_token: str = field(repr=False)
    policy_cache_ttl_seconds: int = 240
    request_timeout_seconds: int = 10
    max_session_duration_seconds: int = 900
    max_policy_pages: int = 10
    clock_skew_seconds: int = 60


def validate_control_room_runtime_config(
    config: ControlRoomRuntimeConfig,
) -> None:
    if not isinstance(config, ControlRoomRuntimeConfig):
        raise ControlRoomSecurityMisconfigured(
            "Control Room runtime configuration is invalid."
        )

    if not config.enabled:
        raise ControlRoomSecurityMisconfigured(
            "Control Room is disabled."
        )

    normalize_cloudflare_team_domain(config.team_domain)

    required_identifiers = {
        "Cloudflare account id": config.account_id,
        "Cloudflare application id": config.application_id,
        "Cloudflare application audience": config.application_audience,
        "Google identity provider id": config.identity_provider_id,
    }
    for label, value in required_identifiers.items():
        if not str(value or "").strip():
            raise ControlRoomSecurityMisconfigured(
                f"Control Room {label} is not configured."
            )

    if not normalize_email_allowlist(config.allowed_emails):
        raise ControlRoomSecurityMisconfigured(
            "Control Room exact email allowlist is not configured."
        )

    if not str(config.policy_audit_api_token or "").strip():
        raise ControlRoomSecurityMisconfigured(
            "Control Room Cloudflare policy audit API token is not configured."
        )

    cache_ttl = int(config.policy_cache_ttl_seconds)
    if cache_ttl <= 0 or cache_ttl > 300:
        raise ControlRoomSecurityMisconfigured(
            "Control Room policy cache TTL must be between 1 and 300 seconds."
        )

    request_timeout = int(config.request_timeout_seconds)
    if request_timeout <= 0 or request_timeout > 30:
        raise ControlRoomSecurityMisconfigured(
            "Control Room Cloudflare request timeout must be between 1 and 30 seconds."
        )

    max_session = int(config.max_session_duration_seconds)
    if max_session <= 0 or max_session > 900:
        raise ControlRoomSecurityMisconfigured(
            "Control Room maximum session duration must be between 1 and 900 seconds."
        )

    if int(config.max_policy_pages) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Control Room policy page limit must be positive."
        )

    if int(config.clock_skew_seconds) < 0:
        raise ControlRoomSecurityMisconfigured(
            "Control Room clock skew cannot be negative."
        )


class ControlRoomPolicyAttestationCache:
    """Short-lived, fail-closed cache of independently audited Access policy."""

    def __init__(
        self,
        *,
        config: ControlRoomRuntimeConfig,
        get_json: Callable[
            [str, str, int],
            Mapping[str, Any],
        ] | None = None,
        now_epoch_resolver: Callable[[], int] | None = None,
    ) -> None:
        self._config = config
        self._get_json = get_json
        self._clock = now_epoch_resolver or (lambda: int(time()))
        self._lock = Lock()
        self._cached_result: CloudflarePolicyAuditResult | None = None

    def _audit(self, now_epoch: int) -> CloudflarePolicyAuditResult:
        config = self._config
        audit_config = CloudflarePolicyAuditConfig(
            account_id=str(config.account_id).strip(),
            application_id=str(config.application_id).strip(),
            application_audience=str(config.application_audience).strip(),
            expected_identity_provider_id=(
                str(config.identity_provider_id).strip()
            ),
            allowed_emails=normalize_email_allowlist(
                config.allowed_emails
            ),
            request_timeout_seconds=int(
                config.request_timeout_seconds
            ),
            max_application_session_duration_seconds=int(
                config.max_session_duration_seconds
            ),
            max_policy_pages=int(config.max_policy_pages),
        )

        kwargs: dict[str, Any] = {
            "config": audit_config,
            "api_token": config.policy_audit_api_token,
            "now_epoch": now_epoch,
        }
        if self._get_json is not None:
            kwargs["get_json"] = self._get_json

        result = audit_cloudflare_control_room_policy(**kwargs)
        if not isinstance(result, CloudflarePolicyAuditResult):
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare policy audit returned an invalid result."
            )

        if not result.attestation.verified:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare policy audit did not produce a verified attestation."
            )

        return result

    def get_result(self) -> CloudflarePolicyAuditResult:
        validate_control_room_runtime_config(self._config)
        now_epoch = int(self._clock())

        with self._lock:
            cached = self._cached_result
            if cached is not None:
                verified_at = int(
                    cached.attestation.verified_at_epoch
                )
                age = now_epoch - verified_at
                if (
                    0 <= age
                    <= int(self._config.policy_cache_ttl_seconds)
                ):
                    return cached

            # Never fall back to stale policy state when refresh fails.
            refreshed = self._audit(now_epoch)
            self._cached_result = refreshed
            return refreshed

    def clear(self) -> None:
        with self._lock:
            self._cached_result = None


def build_control_room_runtime_guard(
    *,
    config: ControlRoomRuntimeConfig,
    policy_audit_get_json: Callable[
        [str, str, int],
        Mapping[str, Any],
    ] | None = None,
    jwks_client_factory: Callable[[str], Any] | None = None,
    now_epoch_resolver: Callable[[], int] | None = None,
) -> Callable[[Request], ControlRoomPrincipal]:
    clock = now_epoch_resolver or (lambda: int(time()))
    cache = ControlRoomPolicyAttestationCache(
        config=config,
        get_json=policy_audit_get_json,
        now_epoch_resolver=clock,
    )

    def guard(request: Request) -> ControlRoomPrincipal:
        validate_control_room_runtime_config(config)
        team_domain = normalize_cloudflare_team_domain(
            config.team_domain
        )
        audience = str(config.application_audience).strip()
        skew = int(config.clock_skew_seconds)
        max_session = int(config.max_session_duration_seconds)

        verifier_config = CloudflareAccessVerifierConfig(
            team_domain=team_domain,
            audience=audience,
            clock_skew_seconds=skew,
        )

        # Verify the caller's Cloudflare-signed token before touching the
        # privileged policy-audit API token. Random or forged requests can never
        # trigger the authenticated Cloudflare configuration audit.
        verify_kwargs: dict[str, Any] = {
            "config": verifier_config,
        }
        if jwks_client_factory is not None:
            verify_kwargs["jwks_client_factory"] = jwks_client_factory

        identity = verify_cloudflare_access_request(
            request,
            **verify_kwargs,
        )

        audited = cache.get_result()
        assurance_policy = CloudflareIndependentMfaAssurancePolicy(
            max_attestation_age_seconds=300,
            max_application_token_lifetime_seconds=max_session,
            clock_skew_seconds=skew,
            require_every_login=True,
        )
        assurance_resolver = (
            build_attested_independent_mfa_assurance_resolver(
                attestation=audited.attestation,
                expected_audience=audience,
                policy=assurance_policy,
                now_epoch_resolver=clock,
            )
        )
        assurance = assurance_resolver(
            {
                "iat": identity.issued_at_epoch,
                "exp": identity.expires_at_epoch,
                "auth_time": identity.authenticated_at_epoch,
                "amr": identity.auth_methods,
            }
        )
        strong_identity = replace(
            identity,
            authenticated_at_epoch=(
                assurance.authenticated_at_epoch
            ),
            auth_strength=assurance.auth_strength,
            auth_methods=assurance.auth_methods,
        )

        authorization_policy = ControlRoomSecurityPolicy(
            enabled=True,
            allowed_emails=normalize_email_allowlist(
                config.allowed_emails
            ),
            expected_issuer=team_domain,
            expected_audience=audience,
            minimum_auth_strength="phishing_resistant",
            max_session_age_seconds=max_session,
            clock_skew_seconds=skew,
        )
        return authorize_control_room_identity(
            strong_identity,
            policy=authorization_policy,
            now_epoch=int(clock()),
        )

    # Expose only non-secret operational hooks for deterministic tests.
    setattr(guard, "clear_policy_cache", cache.clear)
    setattr(guard, "runtime_version", CONTROL_ROOM_RUNTIME_VERSION)
    return guard


def runtime_config_from_application_config() -> ControlRoomRuntimeConfig:
    from app.application import config as application_config

    return ControlRoomRuntimeConfig(
        enabled=bool(application_config.CONTROL_ROOM_ENABLED),
        team_domain=(
            application_config.CONTROL_ROOM_CLOUDFLARE_TEAM_DOMAIN
        ),
        account_id=(
            application_config.CONTROL_ROOM_CLOUDFLARE_ACCOUNT_ID
        ),
        application_id=(
            application_config.CONTROL_ROOM_CLOUDFLARE_APPLICATION_ID
        ),
        application_audience=(
            application_config.CONTROL_ROOM_CLOUDFLARE_APPLICATION_AUDIENCE
        ),
        identity_provider_id=(
            application_config.CONTROL_ROOM_GOOGLE_IDP_ID
        ),
        allowed_emails=(
            application_config.CONTROL_ROOM_ALLOWED_EMAILS
        ),
        policy_audit_api_token=(
            application_config.CONTROL_ROOM_CLOUDFLARE_POLICY_AUDIT_API_TOKEN
        ),
        policy_cache_ttl_seconds=int(
            application_config.CONTROL_ROOM_POLICY_CACHE_TTL_SECONDS
        ),
        request_timeout_seconds=int(
            application_config.CONTROL_ROOM_CLOUDFLARE_REQUEST_TIMEOUT_SECONDS
        ),
        max_session_duration_seconds=int(
            application_config.CONTROL_ROOM_MAX_SESSION_DURATION_SECONDS
        ),
        max_policy_pages=int(
            application_config.CONTROL_ROOM_MAX_POLICY_PAGES
        ),
        clock_skew_seconds=int(
            application_config.CONTROL_ROOM_CLOCK_SKEW_SECONDS
        ),
    )


def build_default_control_room_guard() -> Callable[
    [Request],
    ControlRoomPrincipal,
]:
    """Build the production guard without performing network I/O.

    Cloudflare policy and JWKS requests remain lazy and occur only when a
    Control Room request reaches the protected route. The outer provenance
    check runs first so direct-origin traffic cannot reach JWT or policy-audit
    work without the Worker-held shared secret.
    """
    from app.application import config as application_config

    inner_guard = build_control_room_runtime_guard(
        config=runtime_config_from_application_config(),
    )
    return protect_control_room_guard_with_origin_provenance(
        inner_guard=inner_guard,
        expected_secret=(
            application_config.CONTROL_ROOM_ORIGIN_PROVENANCE_SECRET
        ),
    )


__all__ = [
    "CONTROL_ROOM_RUNTIME_VERSION",
    "ControlRoomRuntimeConfig",
    "ControlRoomPolicyAttestationCache",
    "validate_control_room_runtime_config",
    "build_control_room_runtime_guard",
    "runtime_config_from_application_config",
    "build_default_control_room_guard",
]
