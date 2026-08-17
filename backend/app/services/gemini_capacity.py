from __future__ import annotations

import json
import math
import os
import re

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


GEMINI_CAPACITY_POLICY_VERSION = "gemini-capacity-policy-v2"

DEFAULT_PROVIDER_RPM = 5
DEFAULT_DISPATCH_RPM = 4
DEFAULT_PROVIDER_TPM = 250_000
DEFAULT_USABLE_TPM = 200_000
DEFAULT_PROVIDER_RPD = 20
DEFAULT_RPD_RESERVE = 4
DEFAULT_MAX_ESTIMATED_INPUT_TOKENS = 50_000
DEFAULT_MAX_PACING_WAIT_SECONDS = 75.0
DEFAULT_GLOBAL_DAILY_CALL_CAP = 16
DEFAULT_CLIENT_DAILY_CALL_CAP = 8

PROVIDER_TIMEZONE_NAME = "America/Los_Angeles"
_PROVIDER_TIMEZONE = ZoneInfo(PROVIDER_TIMEZONE_NAME)


class GeminiCapacityError(RuntimeError):
    pass


class GeminiCapacityConfigurationError(GeminiCapacityError):
    pass


class GeminiCapacityPacingRequired(GeminiCapacityError):
    def __init__(
        self,
        *,
        wait_seconds: float,
        reason: str,
    ) -> None:
        self.wait_seconds = max(0.0, float(wait_seconds))
        self.reason = str(reason or "capacity").strip().lower() or "capacity"
        super().__init__(
            "Gemini capacity pacing required "
            f"for {self.wait_seconds:.3f}s ({self.reason})."
        )


@dataclass(frozen=True)
class GeminiCapacityPolicy:
    version: str
    model: str
    provider_rpm: int
    dispatch_rpm: int
    provider_tpm: int
    usable_tpm: int
    provider_rpd: int
    rpd_reserve: int
    max_estimated_input_tokens: int
    max_pacing_wait_seconds: float

    @property
    def usable_rpd(self) -> int:
        return max(
            1,
            self.provider_rpd - self.rpd_reserve,
        )

    @property
    def minimum_dispatch_interval_seconds(self) -> float:
        return 60.0 / float(self.dispatch_rpm)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "model": self.model,
            "provider_rpm": self.provider_rpm,
            "dispatch_rpm": self.dispatch_rpm,
            "provider_tpm": self.provider_tpm,
            "usable_tpm": self.usable_tpm,
            "provider_rpd": self.provider_rpd,
            "rpd_reserve": self.rpd_reserve,
            "usable_rpd": self.usable_rpd,
            "max_estimated_input_tokens": self.max_estimated_input_tokens,
            "max_pacing_wait_seconds": self.max_pacing_wait_seconds,
            "provider_timezone": PROVIDER_TIMEZONE_NAME,
            "minimum_dispatch_interval_seconds": (
                self.minimum_dispatch_interval_seconds
            ),
        }


def normalized_model_name(model: Any) -> str:
    value = re.sub(
        r"\s+",
        " ",
        str(model or ""),
    ).strip().lower()
    return value or "unknown-model"


def _model_env_suffix(model: Any) -> str:
    normalized = normalized_model_name(model)
    if normalized == "unknown-model":
        return ""
    return re.sub(
        r"[^A-Z0-9]+",
        "_",
        normalized.upper(),
    ).strip("_")


def _env_value(
    *,
    model: Any,
    key: str,
) -> str:
    suffix = _model_env_suffix(model)
    if suffix:
        model_key = (
            "SPORTABASE_GEMINI_MODEL_"
            + suffix
            + "_"
            + key
        )
        if model_key in os.environ:
            return str(os.environ[model_key]).strip()
    return str(
        os.getenv(
            "SPORTABASE_GEMINI_" + key,
            "",
        )
    ).strip()


def _positive_int(
    *,
    model: Any,
    key: str,
    default: int,
    allow_zero: bool = False,
) -> int:
    raw = _env_value(
        model=model,
        key=key,
    )
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise GeminiCapacityConfigurationError(
            f"{key} must be an integer."
        ) from error
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise GeminiCapacityConfigurationError(
            f"{key} must be >= {minimum}."
        )
    return value


def _positive_float(
    *,
    model: Any,
    key: str,
    default: float,
) -> float:
    raw = _env_value(
        model=model,
        key=key,
    )
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise GeminiCapacityConfigurationError(
            f"{key} must be numeric."
        ) from error
    if not math.isfinite(value) or value <= 0.0:
        raise GeminiCapacityConfigurationError(
            f"{key} must be finite and > 0."
        )
    return value


def capacity_policy_for_model(
    model: Any,
) -> GeminiCapacityPolicy:
    normalized_model = normalized_model_name(model)

    provider_rpm = _positive_int(
        model=model,
        key="PROVIDER_RPM",
        default=DEFAULT_PROVIDER_RPM,
    )
    dispatch_rpm = _positive_int(
        model=model,
        key="DISPATCH_RPM",
        default=DEFAULT_DISPATCH_RPM,
    )
    provider_tpm = _positive_int(
        model=model,
        key="PROVIDER_TPM",
        default=DEFAULT_PROVIDER_TPM,
    )
    usable_tpm = _positive_int(
        model=model,
        key="USABLE_TPM",
        default=DEFAULT_USABLE_TPM,
    )
    provider_rpd = _positive_int(
        model=model,
        key="PROVIDER_RPD",
        default=DEFAULT_PROVIDER_RPD,
    )
    rpd_reserve = _positive_int(
        model=model,
        key="RPD_RESERVE",
        default=DEFAULT_RPD_RESERVE,
        allow_zero=True,
    )
    max_estimated = _positive_int(
        model=model,
        key="MAX_ESTIMATED_INPUT_TOKENS",
        default=DEFAULT_MAX_ESTIMATED_INPUT_TOKENS,
    )
    max_wait = _positive_float(
        model=model,
        key="MAX_PACING_WAIT_SECONDS",
        default=DEFAULT_MAX_PACING_WAIT_SECONDS,
    )

    if dispatch_rpm > provider_rpm:
        raise GeminiCapacityConfigurationError(
            "DISPATCH_RPM cannot exceed PROVIDER_RPM."
        )
    if usable_tpm > provider_tpm:
        raise GeminiCapacityConfigurationError(
            "USABLE_TPM cannot exceed PROVIDER_TPM."
        )
    if rpd_reserve >= provider_rpd:
        raise GeminiCapacityConfigurationError(
            "RPD_RESERVE must leave at least one usable request per day."
        )
    if max_estimated > usable_tpm:
        raise GeminiCapacityConfigurationError(
            "MAX_ESTIMATED_INPUT_TOKENS cannot exceed USABLE_TPM."
        )

    return GeminiCapacityPolicy(
        version=GEMINI_CAPACITY_POLICY_VERSION,
        model=normalized_model,
        provider_rpm=provider_rpm,
        dispatch_rpm=dispatch_rpm,
        provider_tpm=provider_tpm,
        usable_tpm=usable_tpm,
        provider_rpd=provider_rpd,
        rpd_reserve=rpd_reserve,
        max_estimated_input_tokens=max_estimated,
        max_pacing_wait_seconds=max_wait,
    )


def _configured_cap(
    *,
    new_name: str,
    legacy_name: str,
    default: int,
    ceiling: int,
) -> int:
    effective = int(default)

    raw_new = str(
        os.getenv(new_name, "")
    ).strip()
    if raw_new:
        try:
            requested = int(raw_new)
        except (TypeError, ValueError) as error:
            raise GeminiCapacityConfigurationError(
                f"{new_name} must be an integer."
            ) from error
        if requested < 1:
            raise GeminiCapacityConfigurationError(
                f"{new_name} must be >= 1."
            )
        effective = min(
            requested,
            int(ceiling),
        )

    raw_legacy = str(
        os.getenv(legacy_name, "")
    ).strip()
    if raw_legacy:
        try:
            legacy = int(raw_legacy)
        except (TypeError, ValueError) as error:
            raise GeminiCapacityConfigurationError(
                f"{legacy_name} must be an integer."
            ) from error
        if legacy < 1:
            raise GeminiCapacityConfigurationError(
                f"{legacy_name} must be >= 1."
            )
        effective = min(
            effective,
            legacy,
        )

    return max(
        1,
        min(
            int(effective),
            int(ceiling),
        ),
    )


def sportabase_daily_caps(
    policy: GeminiCapacityPolicy,
) -> tuple[int, int]:
    provider_ceiling = int(policy.usable_rpd)

    global_cap = _configured_cap(
        new_name="SPORTABASE_GEMINI_GLOBAL_DAILY_CALL_CAP",
        legacy_name="SPORTABASE_GLOBAL_DAILY_GEMINI_CALL_CAP",
        default=min(
            DEFAULT_GLOBAL_DAILY_CALL_CAP,
            provider_ceiling,
        ),
        ceiling=provider_ceiling,
    )

    client_cap = _configured_cap(
        new_name="SPORTABASE_GEMINI_CLIENT_DAILY_CALL_CAP",
        legacy_name="SPORTABASE_CLIENT_DAILY_GEMINI_CALL_CAP",
        default=min(
            DEFAULT_CLIENT_DAILY_CALL_CAP,
            global_cap,
        ),
        ceiling=global_cap,
    )

    return (
        global_cap,
        client_cap,
    )


def provider_usage_day(
    now: datetime | None = None,
) -> str:
    current = (
        now
        if now is not None
        else datetime.now(timezone.utc)
    )
    if current.tzinfo is None:
        current = current.replace(
            tzinfo=timezone.utc,
        )
    return (
        current
        .astimezone(_PROVIDER_TIMEZONE)
        .date()
        .isoformat()
    )


def estimate_prompt_tokens(
    contents: Any,
) -> int:
    if isinstance(contents, str):
        serialized = contents
    else:
        try:
            serialized = json.dumps(
                contents,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            serialized = repr(contents)

    byte_count = len(
        serialized.encode(
            "utf-8",
            errors="replace",
        )
    )
    return max(
        1,
        int(
            math.ceil(
                byte_count / 3.0
            )
        ),
    )


__all__ = [
    "GEMINI_CAPACITY_POLICY_VERSION",
    "DEFAULT_PROVIDER_RPM",
    "DEFAULT_DISPATCH_RPM",
    "DEFAULT_PROVIDER_TPM",
    "DEFAULT_USABLE_TPM",
    "DEFAULT_PROVIDER_RPD",
    "DEFAULT_RPD_RESERVE",
    "DEFAULT_MAX_ESTIMATED_INPUT_TOKENS",
    "DEFAULT_MAX_PACING_WAIT_SECONDS",
    "DEFAULT_GLOBAL_DAILY_CALL_CAP",
    "DEFAULT_CLIENT_DAILY_CALL_CAP",
    "PROVIDER_TIMEZONE_NAME",
    "GeminiCapacityError",
    "GeminiCapacityConfigurationError",
    "GeminiCapacityPacingRequired",
    "GeminiCapacityPolicy",
    "normalized_model_name",
    "capacity_policy_for_model",
    "sportabase_daily_caps",
    "provider_usage_day",
    "estimate_prompt_tokens",
]
