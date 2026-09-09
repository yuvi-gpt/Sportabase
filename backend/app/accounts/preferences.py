from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    appearance: Literal["system", "light", "dark"] = "system"
    contrast: Literal["standard", "high"] = "standard"
    text_size: Literal["system", "small", "large"] = "system"
    density: Literal["compact", "comfortable"] = "comfortable"
    motion: Literal["system", "reduce", "full"] = "system"
    language: Literal["system", "en"] = "system"
    date_format: Literal["system", "iso"] = "system"
    analysis_detail: Literal["essential", "full"] = "full"
    notifications_enabled: bool = True
    entity_alerts: bool = True
    story_alerts: bool = True
    claim_alerts: bool = True
    media_alerts: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = Field(default="22:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="UTC", min_length=1, max_length=80)
    analytics_enabled: bool = False
    activity_enabled: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose an IANA timezone.") from exc
        return value

    @model_validator(mode="after")
    def quiet_window(self):
        if self.quiet_hours_enabled and self.quiet_hours_start == self.quiet_hours_end:
            raise ValueError("Quiet hours must have different start and end times.")
        return self


def validate_patch(patch: dict, base: dict | None = None) -> dict:
    validated = Preferences.model_validate({**(base or {}), **patch}).model_dump()
    return {key: validated[key] for key in patch}


def effective_preferences(defaults: dict, overrides: dict, follows: bool) -> dict:
    return Preferences.model_validate({**defaults, **({} if follows else overrides)}).model_dump()


def delivery_time(preferences: dict, kind: str, now_epoch: int) -> int | None:
    """None suppresses push only; future epoch postpones without consuming a retry.

    Walk real UTC minutes through the local window. This handles nonexistent and
    repeated local times without manufacturing an invalid wall-clock instant.
    The finite 26-hour bound includes daylight-saving fall-back windows.
    """
    if not preferences["notifications_enabled"] or not preferences.get(f"{kind}_alerts", False):
        return None
    if not preferences["quiet_hours_enabled"]:
        return now_epoch
    zone = ZoneInfo(preferences["timezone"])
    start, end = preferences["quiet_hours_start"], preferences["quiet_hours_end"]

    def quiet(epoch):
        wall = datetime.fromtimestamp(epoch, timezone.utc).astimezone(zone).strftime("%H:%M")
        return start <= wall < end if start < end else wall >= start or wall < end

    if not quiet(now_epoch):
        return now_epoch
    candidate = now_epoch - now_epoch % 60 + 60
    for _ in range(26 * 60):
        if not quiet(candidate):
            return candidate
        candidate += 60
    return now_epoch + int(timedelta(hours=26).total_seconds())
