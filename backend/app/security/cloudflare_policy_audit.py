from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from time import time
from typing import Any, Callable, Mapping

import requests

from app.security.cloudflare_control_room import (
    CloudflareIndependentMfaAttestation,
    normalize_cloudflare_authenticators,
)
from app.security.control_room import (
    ControlRoomSecurityMisconfigured,
    normalize_email_allowlist,
)


CLOUDFLARE_POLICY_AUDIT_VERSION = (
    "sportabase-cloudflare-policy-audit-v1"
)
CLOUDFLARE_API_ORIGIN = "https://api.cloudflare.com/client/v4"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_DURATION_TOKEN_RE = re.compile(
    r"(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<unit>ns|us|µs|ms|s|m|h)"
)
_DURATION_FACTORS = {
    "ns": Decimal("0.000000001"),
    "us": Decimal("0.000001"),
    "µs": Decimal("0.000001"),
    "ms": Decimal("0.001"),
    "s": Decimal("1"),
    "m": Decimal("60"),
    "h": Decimal("3600"),
}
_PHISHING_RESISTANT_AUTHENTICATORS = frozenset(
    {
        "security_key",
        "biometrics",
    }
)
_GOOGLE_IDP_TYPES = frozenset(
    {
        "google",
        "google-apps",
    }
)


@dataclass(frozen=True)
class CloudflarePolicyAuditConfig:
    account_id: str
    application_id: str
    application_audience: str
    expected_identity_provider_id: str
    allowed_emails: tuple[str, ...]
    request_timeout_seconds: int = 10
    max_application_session_duration_seconds: int = 900
    max_policy_pages: int = 10


@dataclass(frozen=True)
class CloudflarePolicyAuditResult:
    version: str
    application_id: str
    application_name: str
    application_audience: str
    identity_provider_id: str
    identity_provider_type: str
    allow_policy_ids: tuple[str, ...]
    audited_policy_count: int
    attestation: CloudflareIndependentMfaAttestation

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "application_id": self.application_id,
            "application_name": self.application_name,
            "application_audience": self.application_audience,
            "identity_provider_id": self.identity_provider_id,
            "identity_provider_type": self.identity_provider_type,
            "allow_policy_ids": list(self.allow_policy_ids),
            "audited_policy_count": self.audited_policy_count,
            "attestation": {
                "verified": self.attestation.verified,
                "verified_at_epoch": self.attestation.verified_at_epoch,
                "application_audience": self.attestation.application_audience,
                "allowed_authenticators": list(
                    self.attestation.allowed_authenticators
                ),
                "mfa_disabled": self.attestation.mfa_disabled,
                "mfa_session_duration_seconds": (
                    self.attestation.mfa_session_duration_seconds
                ),
                "source": self.attestation.source,
            },
        }


def _normalize_identifier(value: object, label: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} is invalid."
        )
    return normalized


def validate_cloudflare_policy_audit_config(
    config: CloudflarePolicyAuditConfig,
) -> None:
    _normalize_identifier(config.account_id, "account id")
    _normalize_identifier(config.application_id, "application id")
    _normalize_identifier(
        config.expected_identity_provider_id,
        "identity provider id",
    )

    if not str(config.application_audience or "").strip():
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room application audience is missing."
        )

    if not normalize_email_allowlist(config.allowed_emails):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room audit requires an exact email allowlist."
        )

    if int(config.request_timeout_seconds) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy audit timeout must be positive."
        )

    if int(config.max_application_session_duration_seconds) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare application session limit must be positive."
        )

    if int(config.max_policy_pages) <= 0:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy page limit must be positive."
        )


def parse_cloudflare_duration_seconds(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare duration is missing."
        )

    position = 0
    total = Decimal("0")
    matched = False

    while position < len(text):
        match = _DURATION_TOKEN_RE.match(text, position)
        if match is None:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare duration is invalid."
            )

        matched = True
        try:
            quantity = Decimal(match.group("value"))
        except InvalidOperation as error:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare duration is invalid."
            ) from error

        total += quantity * _DURATION_FACTORS[match.group("unit")]
        position = match.end()

    if not matched or total < 0 or total != total.to_integral_value():
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare duration must resolve to whole seconds."
        )

    return int(total)


def _default_get_json(
    url: str,
    api_token: str,
    timeout_seconds: int,
) -> Mapping[str, Any]:
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": "Bearer " + api_token,
                "Accept": "application/json",
            },
            timeout=timeout_seconds,
        )
    except requests.RequestException as error:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification API is unavailable."
        ) from error

    if response.status_code != 200:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification API request failed."
        )

    try:
        payload = response.json()
    except ValueError as error:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification API returned invalid JSON."
        ) from error

    if not isinstance(payload, Mapping):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification API returned an invalid payload."
        )

    return payload


def _unwrap_result(
    payload: Mapping[str, Any],
    *,
    expect_list: bool,
) -> Any:
    if payload.get("success") is not True:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification API reported failure."
        )

    result = payload.get("result")
    if expect_list:
        if not isinstance(result, list):
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare policy verification list result is invalid."
            )
    elif not isinstance(result, Mapping):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare policy verification object result is invalid."
        )

    return result


def _safe_mfa_config(
    value: object,
    *,
    label: str,
) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} independent MFA configuration is missing."
        )

    if value.get("mfa_disabled") is True:
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} independent MFA is disabled."
        )

    authenticators = normalize_cloudflare_authenticators(
        value.get("allowed_authenticators")
    )
    if not authenticators:
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} has no MFA authenticators."
        )

    if any(
        method not in _PHISHING_RESISTANT_AUTHENTICATORS
        for method in authenticators
    ):
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} allows a non-phishing-resistant MFA method."
        )

    duration = parse_cloudflare_duration_seconds(
        value.get("session_duration")
    )
    if duration != 0:
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} MFA must be required on every login."
        )

    return authenticators


def _validate_session_duration(
    value: object,
    *,
    limit_seconds: int,
    label: str,
) -> int:
    duration = parse_cloudflare_duration_seconds(value)
    if duration <= 0 or duration > int(limit_seconds):
        raise ControlRoomSecurityMisconfigured(
            f"Cloudflare {label} session duration exceeds the Control Room limit."
        )
    return duration


def _exact_allow_policy_emails(
    policy: Mapping[str, Any],
    *,
    allowed_emails: tuple[str, ...],
) -> tuple[str, ...]:
    include = policy.get("include")
    if not isinstance(include, list) or not include:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room allow policy has no exact include rules."
        )

    approved = frozenset(normalize_email_allowlist(allowed_emails))
    observed: list[str] = []

    for rule in include:
        if not isinstance(rule, Mapping) or set(rule.keys()) != {"email"}:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare Control Room allow policy contains a broad selector."
            )

        email_rule = rule.get("email")
        if not isinstance(email_rule, Mapping):
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare Control Room email selector is invalid."
            )

        email = normalize_email_allowlist(
            (email_rule.get("email"),)
        )
        if len(email) != 1 or email[0] not in approved:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare Control Room allow policy grants an unapproved email."
            )

        if email[0] not in observed:
            observed.append(email[0])

    if not observed:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room allow policy has no approved email."
        )

    return tuple(observed)


def _list_application_policies(
    *,
    base_url: str,
    api_token: str,
    timeout_seconds: int,
    max_pages: int,
    get_json: Callable[[str, str, int], Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    policies: list[Mapping[str, Any]] = []
    page = 1

    while page <= max_pages:
        payload = get_json(
            f"{base_url}/policies?per_page=100&page={page}",
            api_token,
            timeout_seconds,
        )
        result = _unwrap_result(payload, expect_list=True)

        for item in result:
            if not isinstance(item, Mapping):
                raise ControlRoomSecurityMisconfigured(
                    "Cloudflare Access policy result is invalid."
                )
            policies.append(item)

        result_info = payload.get("result_info")
        if isinstance(result_info, Mapping):
            try:
                total_pages = int(result_info.get("total_pages") or 1)
            except Exception as error:
                raise ControlRoomSecurityMisconfigured(
                    "Cloudflare policy pagination metadata is invalid."
                ) from error

            if total_pages < 1 or total_pages > max_pages:
                raise ControlRoomSecurityMisconfigured(
                    "Cloudflare policy audit cannot prove all policies were inspected."
                )
            if page >= total_pages:
                return policies
        elif len(result) < 100:
            return policies
        else:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare policy audit cannot prove pagination completeness."
            )

        page += 1

    raise ControlRoomSecurityMisconfigured(
        "Cloudflare policy audit exceeded its page limit."
    )


def audit_cloudflare_control_room_policy(
    *,
    config: CloudflarePolicyAuditConfig,
    api_token: object,
    get_json: Callable[[str, str, int], Mapping[str, Any]] = (
        _default_get_json
    ),
    now_epoch: int | None = None,
) -> CloudflarePolicyAuditResult:
    validate_cloudflare_policy_audit_config(config)

    token = str(api_token or "").strip()
    if not token:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare read-only policy audit API token is not configured."
        )

    account_id = _normalize_identifier(config.account_id, "account id")
    app_id = _normalize_identifier(config.application_id, "application id")
    idp_id = _normalize_identifier(
        config.expected_identity_provider_id,
        "identity provider id",
    )
    audience = str(config.application_audience).strip()
    timeout_seconds = int(config.request_timeout_seconds)
    app_url = (
        f"{CLOUDFLARE_API_ORIGIN}/accounts/{account_id}/access/apps/{app_id}"
    )

    app_payload = get_json(app_url, token, timeout_seconds)
    application = _unwrap_result(app_payload, expect_list=False)

    if str(application.get("id") or "").strip() != app_id:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room application id does not match."
        )

    if str(application.get("aud") or "").strip() != audience:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room application audience does not match."
        )

    allowed_idps = tuple(
        str(value or "").strip()
        for value in (application.get("allowed_idps") or ())
        if str(value or "").strip()
    )
    if frozenset(allowed_idps) != frozenset({idp_id}):
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room application must allow only the approved Google IdP."
        )

    _validate_session_duration(
        application.get("session_duration"),
        limit_seconds=config.max_application_session_duration_seconds,
        label="Control Room application",
    )

    effective_authenticators = list(
        _safe_mfa_config(
            application.get("mfa_config"),
            label="Control Room application",
        )
    )

    idp_url = (
        f"{CLOUDFLARE_API_ORIGIN}/accounts/{account_id}"
        f"/access/identity_providers/{idp_id}"
    )
    idp_payload = get_json(idp_url, token, timeout_seconds)
    identity_provider = _unwrap_result(idp_payload, expect_list=False)

    if str(identity_provider.get("id") or "").strip() != idp_id:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room identity provider id does not match."
        )

    idp_type = str(identity_provider.get("type") or "").strip()
    if idp_type not in _GOOGLE_IDP_TYPES:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room identity provider is not Google."
        )

    policies = _list_application_policies(
        base_url=app_url,
        api_token=token,
        timeout_seconds=timeout_seconds,
        max_pages=int(config.max_policy_pages),
        get_json=get_json,
    )
    if not policies:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room application has no Access policies."
        )

    allow_policy_ids: list[str] = []
    for policy in policies:
        decision = str(policy.get("decision") or "").strip().casefold()
        if decision == "block":
            continue
        if decision != "allow":
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare Control Room contains a bypass or non-user policy."
            )

        policy_id = str(policy.get("id") or "").strip()
        if not policy_id:
            raise ControlRoomSecurityMisconfigured(
                "Cloudflare Control Room allow policy id is missing."
            )

        _exact_allow_policy_emails(
            policy,
            allowed_emails=config.allowed_emails,
        )

        _validate_session_duration(
            policy.get("session_duration"),
            limit_seconds=config.max_application_session_duration_seconds,
            label="Control Room allow policy",
        )

        policy_mfa = policy.get("mfa_config")
        if policy_mfa is not None:
            for method in _safe_mfa_config(
                policy_mfa,
                label="Control Room allow policy",
            ):
                if method not in effective_authenticators:
                    effective_authenticators.append(method)

        allow_policy_ids.append(policy_id)

    if not allow_policy_ids:
        raise ControlRoomSecurityMisconfigured(
            "Cloudflare Control Room has no exact-email allow policy."
        )

    attestation = CloudflareIndependentMfaAttestation(
        verified=True,
        verified_at_epoch=(
            int(time()) if now_epoch is None else int(now_epoch)
        ),
        application_audience=audience,
        allowed_authenticators=tuple(effective_authenticators),
        mfa_disabled=False,
        mfa_session_duration_seconds=0,
        source="cloudflare_access_policy_api",
    )

    return CloudflarePolicyAuditResult(
        version=CLOUDFLARE_POLICY_AUDIT_VERSION,
        application_id=app_id,
        application_name=str(application.get("name") or "").strip(),
        application_audience=audience,
        identity_provider_id=idp_id,
        identity_provider_type=idp_type,
        allow_policy_ids=tuple(allow_policy_ids),
        audited_policy_count=len(policies),
        attestation=attestation,
    )


__all__ = [
    "CLOUDFLARE_POLICY_AUDIT_VERSION",
    "CLOUDFLARE_API_ORIGIN",
    "CloudflarePolicyAuditConfig",
    "CloudflarePolicyAuditResult",
    "validate_cloudflare_policy_audit_config",
    "parse_cloudflare_duration_seconds",
    "audit_cloudflare_control_room_policy",
]
