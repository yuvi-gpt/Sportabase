from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict


class GoldenCaptureError(RuntimeError):
    pass


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def iso(base: datetime, hours: float = 0.0) -> str:
    return (base + timedelta(hours=hours)).astimezone(
        timezone.utc
    ).isoformat().replace("+00:00", "Z")


def platform_url(platform: str, slug: str, index: int) -> str:
    clean_slug = "".join(
        ch if ch.isalnum() else "-"
        for ch in slug.lower()
    ).strip("-")

    if platform == "web":
        return f"https://eval.sportabase.test/{clean_slug}/{index}"
    if platform == "x":
        return "https://x.com/golden_eval/status/" + str(
            900000000000000000 + index
        )
    if platform == "instagram":
        return f"https://instagram.com/p/{clean_slug[:8]}{index:03d}"
    if platform == "tiktok":
        return "https://www.tiktok.com/@golden_eval/video/" + str(
            7000000000000000000 + index
        )
    if platform == "reddit":
        return (
            "https://reddit.com/r/sports/comments/"
            + f"g{index:x}/{clean_slug}"
        )
    if platform == "facebook":
        return "https://facebook.com/golden_eval/posts/" + str(
            800000000000000000 + index
        )
    if platform == "youtube":
        token = "".join(ch for ch in clean_slug if ch.isalnum())
        video_id = ((token + "goldeneval00")[:7] + f"{index:04d}")[:11]
        return "https://youtube.com/watch?v=" + video_id

    raise GoldenCaptureError("Unsupported golden capture platform: " + platform)


def capture(
    *,
    platform: str,
    text: str,
    observed_at: str,
    url: str,
    title: str = "",
    actor_handle: str = "golden_eval",
) -> Dict[str, Any]:
    surface = {
        "web": "article",
        "x": "post",
        "instagram": "post",
        "tiktok": "video",
        "reddit": "post",
        "facebook": "post",
        "youtube": "video",
    }[platform]

    payload = {
        "platform": platform,
        "surface": surface,
        "container_kind": (
            "article"
            if platform == "web"
            else "media"
            if platform in {"youtube", "tiktok"}
            else "post"
        ),
        "canonical_url": url,
        "title": clean(title),
        "body": clean(text),
    }

    actor: Dict[str, Any] = {}
    if platform != "web":
        actor = {
            "handle": actor_handle,
            "display_name": actor_handle.replace("_", " ").title(),
            "profile_url": {
                "x": f"https://x.com/{actor_handle}",
                "instagram": f"https://instagram.com/{actor_handle}",
                "tiktok": f"https://www.tiktok.com/@{actor_handle}",
                "reddit": f"https://reddit.com/user/{actor_handle}",
                "facebook": f"https://facebook.com/{actor_handle}",
                "youtube": f"https://youtube.com/@{actor_handle}",
            }[platform],
        }

    return {
        "version": "browser-capture-v1",
        "source_url": url,
        "observed_at": observed_at,
        "extraction_method": (
            "browser_dom+article_extractor"
            if platform == "web"
            else "browser_dom"
        ),
        "payload": payload,
        "actor": actor,
    }


def capture_entry(
    *,
    platform: str,
    text: str,
    observed_at: str,
    slug: str,
    index: int,
    role: str,
    url: str = "",
) -> Dict[str, Any]:
    final_url = url or platform_url(platform, slug, index)
    return {
        "role": role,
        "capture": capture(
            platform=platform,
            text=text,
            observed_at=observed_at,
            url=final_url,
            title=text.split(".", 1)[0],
            actor_handle=f"golden_eval_{index}",
        ),
    }


def entity_payload(value, *, sport: str) -> Dict[str, Any]:
    if not isinstance(value, (tuple, list)) or len(value) != 5:
        raise GoldenCaptureError("Golden entity spec must contain five values.")

    entity_id, entity_key, entity_type, canonical_name, aliases = value
    result = {
        "id": clean(entity_id),
        "entity_key": clean(entity_key),
        "entity_type": clean(entity_type),
        "sport_key": clean(sport),
        "canonical_name": clean(canonical_name),
        "aliases": [clean(item) for item in aliases if clean(item)],
    }

    if not all(
        result[field]
        for field in (
            "id",
            "entity_key",
            "entity_type",
            "sport_key",
            "canonical_name",
        )
    ):
        raise GoldenCaptureError("Golden entity identity is incomplete.")

    return result
