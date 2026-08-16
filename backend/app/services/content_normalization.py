from __future__ import annotations

import hashlib
import json
import re

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
)

from app.models import content


CONTENT_NORMALIZATION_VERSION = (
    "content-normalization-v1"
)


PLATFORM_ALIASES = {
    "twitter": "x",
    "x.com": "x",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "reddit.com": "reddit",
    "facebook.com": "facebook",
    "fb": "facebook",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
}


SURFACE_ALIASES = {
    "reels": "reel",
    "shorts": "short",
    "tweet": "post",
    "tweets": "post",
    "submission": "post",
    "community post": "community_post",
    "community-post": "community_post",
}


TEXT_ROLE_ALIASES = {
    "post_text": "body",
    "text": "body",
    "ocr": "on_screen_text",
    "on-screen-text": "on_screen_text",
    "onscreen_text": "on_screen_text",
    "subtitle": "transcript",
    "subtitles": "transcript",
    "speech": "transcript",
}


MEDIA_KIND_ALIASES = {
    "photo": "image",
    "picture": "image",
    "still": "image",
    "movie": "video",
    "clip": "video",
    "sound": "audio",
}


FORBIDDEN_SEMANTIC_FIELDS = {
    "truth_status",
    "authority_class",
    "authority_score",
    "merit_score",
    "badge",
    "corroboration_status",
    "independence_status",
    "affects_merit_score",
    "score_effect_applied",
}


ALLOWED_TOP_LEVEL_FIELDS = {
    "item_id",
    "id",
    "platform",
    "source_platform",
    "platform_surface",
    "surface",
    "format",
    "container_kind",
    "container_type",
    "canonical_url",
    "url",
    "platform_content_id",
    "content_id",
    "post_id",
    "actor",
    "author",
    "published_at",
    "created_at",
    "observed_at",
    "captured_at",
    "ephemeral",
    "expires_at",
    "title",
    "body",
    "text",
    "caption",
    "description",
    "transcript",
    "on_screen_text",
    "text_components",
    "media",
    "media_components",
    "engagement",
    "engagement_snapshots",
    "provenance",
    "metadata",
}


ALLOWED_ACTOR_FIELDS = {
    "platform_actor_id",
    "id",
    "handle",
    "username",
    "display_name",
    "name",
    "profile_url",
    "url",
    "canonical_entity_id",
    "metadata",
}


def _clean_string(
    value: Any,
) -> str:
    if value is None:
        return ""

    text = str(
        value
    ).replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    lines = []

    for line in text.split("\n"):
        clean_line = re.sub(
            r"[ \t\f\v]+",
            " ",
            line,
        ).strip()

        if clean_line:
            lines.append(
                clean_line
            )

    return "\n".join(
        lines
    ).strip()


def _normalized_token(
    value: Any,
) -> str:
    token = _clean_string(
        value
    ).lower()

    token = token.replace(
        "-",
        "_",
    ).replace(
        " ",
        "_",
    )

    return re.sub(
        r"_+",
        "_",
        token,
    ).strip(
        "_"
    )


def normalize_platform(
    value: Any,
) -> str:
    platform = _normalized_token(
        value
    )

    platform = PLATFORM_ALIASES.get(
        platform,
        platform,
    )

    if not platform:
        raise ValueError(
            "Platform is required."
        )

    return platform


def normalize_surface(
    value: Any,
) -> str:
    surface = _normalized_token(
        value
    )

    return SURFACE_ALIASES.get(
        surface,
        surface,
    )


def normalize_text_role(
    value: Any,
) -> str:
    role = _normalized_token(
        value
    )

    role = TEXT_ROLE_ALIASES.get(
        role,
        role,
    )

    return role


def normalize_media_kind(
    value: Any,
) -> str:
    kind = _normalized_token(
        value
    )

    kind = MEDIA_KIND_ALIASES.get(
        kind,
        kind,
    )

    if kind not in {
        "image",
        "video",
        "audio",
    }:
        raise ValueError(
            "Unsupported media kind: "
            + str(
                value
            )
        )

    return kind


def _optional_float(
    value: Any,
    *,
    field_name: str,
) -> Optional[float]:
    if (
        value is None
        or value == ""
    ):
        return None

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            field_name
            + " must be numeric."
        )

    try:
        number = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            field_name
            + " must be numeric."
        ) from error

    if number < 0:
        raise ValueError(
            field_name
            + " cannot be negative."
        )

    return number


def _optional_int(
    value: Any,
    *,
    field_name: str,
) -> Optional[int]:
    number = _optional_float(
        value,
        field_name=field_name,
    )

    if number is None:
        return None

    if not number.is_integer():
        raise ValueError(
            field_name
            + " must be an integer."
        )

    return int(
        number
    )


def _optional_bool(
    value: Any,
) -> Optional[bool]:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return value

    token = _normalized_token(
        value
    )

    if token in {
        "true",
        "yes",
        "1",
    }:
        return True

    if token in {
        "false",
        "no",
        "0",
    }:
        return False

    raise ValueError(
        "Boolean value could not "
        "be normalized."
    )


def normalize_metric_value(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Engagement metric must "
            "be numeric."
        )

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        number = float(
            value
        )

    else:
        raw = _clean_string(
            value
        ).replace(
            ",",
            "",
        ).lower()

        match = re.fullmatch(
            (
                r"([0-9]+"
                r"(?:\.[0-9]+)?)"
                r"\s*([kmb])?"
            ),
            raw,
        )

        if not match:
            raise ValueError(
                "Engagement metric could "
                "not be normalized: "
                + str(
                    value
                )
            )

        number = float(
            match.group(1)
        )

        multiplier = {
            "": 1.0,
            "k": 1_000.0,
            "m": 1_000_000.0,
            "b": 1_000_000_000.0,
        }[
            match.group(2) or ""
        ]

        number *= multiplier

    if number < 0:
        raise ValueError(
            "Engagement metric cannot "
            "be negative."
        )

    return number


def _ensure_dict(
    value: Any,
    *,
    field_name: str,
) -> Dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            field_name
            + " must be an object."
        )

    return dict(
        value
    )


def _ensure_list(
    value: Any,
    *,
    field_name: str,
) -> List[Any]:
    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return list(
            value
        )

    raise ValueError(
        field_name
        + " must be a list."
    )


def _reject_semantic_fields(
    payload: Dict[str, Any],
) -> None:
    forbidden = (
        set(
            payload.keys()
        )
        & FORBIDDEN_SEMANTIC_FIELDS
    )

    if forbidden:
        raise ValueError(
            "Ingestion cannot establish "
            "semantic intelligence fields: "
            + ", ".join(
                sorted(
                    forbidden
                )
            )
        )


def _validate_top_level_fields(
    payload: Dict[str, Any],
) -> None:
    _reject_semantic_fields(
        payload
    )

    unknown = (
        set(
            payload.keys()
        )
        - ALLOWED_TOP_LEVEL_FIELDS
    )

    if unknown:
        raise ValueError(
            "Unsupported normalization "
            "fields: "
            + ", ".join(
                sorted(
                    unknown
                )
            )
        )


def _first_nonempty(
    payload: Dict[str, Any],
    names: Iterable[str],
) -> str:
    for name in names:
        value = _clean_string(
            payload.get(
                name
            )
        )

        if value:
            return value

    return ""


def _normalize_metadata(
    value: Any,
) -> Dict[str, Any]:
    metadata = _ensure_dict(
        value,
        field_name="metadata",
    )

    _reject_semantic_fields(
        metadata
    )

    return metadata


def _normalize_provenance(
    value: Any,
    *,
    source_url: str,
    observed_at: str,
) -> content.ProvenanceRecord:
    raw = _ensure_dict(
        value,
        field_name="provenance",
    )

    _reject_semantic_fields(
        raw
    )

    confidence = raw.get(
        "extraction_confidence",
        0.0,
    )

    if confidence in {
        None,
        "",
    }:
        confidence = 0.0

    confidence = float(
        confidence
    )

    if not (
        0.0
        <= confidence
        <= 1.0
    ):
        raise ValueError(
            "Extraction confidence must "
            "be between 0 and 1."
        )

    return content.ProvenanceRecord(
        source_url=(
            _clean_string(
                raw.get(
                    "source_url"
                )
            )
            or source_url
        ),
        observed_at=(
            _clean_string(
                raw.get(
                    "observed_at"
                )
            )
            or observed_at
        ),
        extraction_method=(
            _clean_string(
                raw.get(
                    "extraction_method"
                )
            )
            or "adapter"
        ),
        content_hash=_clean_string(
            raw.get(
                "content_hash"
            )
        ),
        extraction_confidence=(
            confidence
        ),
        metadata=_normalize_metadata(
            raw.get(
                "metadata"
            )
        ),
    )


def _normalize_actor(
    value: Any,
) -> content.ActorReference:
    if value is None:
        return content.ActorReference()

    if isinstance(
        value,
        str,
    ):
        clean = _clean_string(
            value
        )

        if clean.startswith(
            "@"
        ):
            return content.ActorReference(
                handle=clean[1:]
            )

        return content.ActorReference(
            display_name=clean
        )

    raw = _ensure_dict(
        value,
        field_name="actor",
    )

    _reject_semantic_fields(
        raw
    )

    unknown = (
        set(
            raw.keys()
        )
        - ALLOWED_ACTOR_FIELDS
    )

    if unknown:
        raise ValueError(
            "Unsupported actor fields: "
            + ", ".join(
                sorted(
                    unknown
                )
            )
        )

    handle = _first_nonempty(
        raw,
        (
            "handle",
            "username",
        ),
    ).lstrip(
        "@"
    )

    return content.ActorReference(
        platform_actor_id=(
            _first_nonempty(
                raw,
                (
                    "platform_actor_id",
                    "id",
                ),
            )
        ),
        handle=handle,
        display_name=(
            _first_nonempty(
                raw,
                (
                    "display_name",
                    "name",
                ),
            )
        ),
        profile_url=(
            _first_nonempty(
                raw,
                (
                    "profile_url",
                    "url",
                ),
            )
        ),
        canonical_entity_id=(
            _clean_string(
                raw.get(
                    "canonical_entity_id"
                )
            )
        ),
        metadata=_normalize_metadata(
            raw.get(
                "metadata"
            )
        ),
    )


def _component_provenance(
    raw: Dict[str, Any],
    *,
    fallback: content.ProvenanceRecord,
) -> content.ProvenanceRecord:
    if not raw.get(
        "provenance"
    ):
        return fallback

    return _normalize_provenance(
        raw.get(
            "provenance"
        ),
        source_url=(
            fallback.source_url
        ),
        observed_at=(
            fallback.observed_at
        ),
    )


def _normalize_explicit_text_component(
    raw_value: Any,
    *,
    fallback_provenance: (
        content.ProvenanceRecord
    ),
) -> content.TextComponent:
    raw = _ensure_dict(
        raw_value,
        field_name="text component",
    )

    _reject_semantic_fields(
        raw
    )

    component_id = _first_nonempty(
        raw,
        (
            "component_id",
            "id",
        ),
    )

    if not component_id:
        raise ValueError(
            "Text component requires "
            "component_id."
        )

    role = normalize_text_role(
        raw.get(
            "role",
            "other",
        )
    )

    text_value = _clean_string(
        raw.get(
            "text"
        )
    )

    if not text_value:
        raise ValueError(
            "Text component cannot "
            "be empty."
        )

    return content.TextComponent(
        component_id=component_id,
        role=role,
        text=text_value,
        language=_clean_string(
            raw.get(
                "language"
            )
        ),
        sequence_index=(
            _optional_int(
                raw.get(
                    "sequence_index"
                ),
                field_name=(
                    "sequence_index"
                ),
            )
        ),
        start_seconds=(
            _optional_float(
                raw.get(
                    "start_seconds"
                ),
                field_name=(
                    "start_seconds"
                ),
            )
        ),
        end_seconds=(
            _optional_float(
                raw.get(
                    "end_seconds"
                ),
                field_name=(
                    "end_seconds"
                ),
            )
        ),
        provenance=(
            _component_provenance(
                raw,
                fallback=(
                    fallback_provenance
                ),
            )
        ),
        metadata=_normalize_metadata(
            raw.get(
                "metadata"
            )
        ),
    )


def _normalize_text_components(
    payload: Dict[str, Any],
    *,
    fallback_provenance: (
        content.ProvenanceRecord
    ),
) -> List[content.TextComponent]:
    components = []

    top_level_roles = (
        (
            "title",
            "title",
        ),
        (
            "body",
            "body",
        ),
        (
            "text",
            "body",
        ),
        (
            "caption",
            "caption",
        ),
        (
            "description",
            "description",
        ),
        (
            "transcript",
            "transcript",
        ),
    )

    used_top_level_roles = set()

    for field_name, role in (
        top_level_roles
    ):
        text_value = _clean_string(
            payload.get(
                field_name
            )
        )

        if not text_value:
            continue

        if (
            role == "body"
            and role
            in used_top_level_roles
        ):
            continue

        used_top_level_roles.add(
            role
        )

        components.append(
            content.TextComponent(
                component_id=role,
                role=role,
                text=text_value,
                provenance=(
                    fallback_provenance
                ),
            )
        )

    on_screen = payload.get(
        "on_screen_text"
    )

    if isinstance(
        on_screen,
        list,
    ):
        for index, value in enumerate(
            on_screen
        ):
            text_value = _clean_string(
                value
            )

            if not text_value:
                continue

            components.append(
                content.TextComponent(
                    component_id=(
                        "on_screen_text:"
                        + str(
                            index
                        )
                    ),
                    role=(
                        "on_screen_text"
                    ),
                    text=text_value,
                    sequence_index=index,
                    provenance=(
                        fallback_provenance
                    ),
                )
            )

    else:
        text_value = _clean_string(
            on_screen
        )

        if text_value:
            components.append(
                content.TextComponent(
                    component_id=(
                        "on_screen_text"
                    ),
                    role=(
                        "on_screen_text"
                    ),
                    text=text_value,
                    provenance=(
                        fallback_provenance
                    ),
                )
            )

    explicit = _ensure_list(
        payload.get(
            "text_components"
        ),
        field_name="text_components",
    )

    for raw in explicit:
        components.append(
            _normalize_explicit_text_component(
                raw,
                fallback_provenance=(
                    fallback_provenance
                ),
            )
        )

    return components


def _normalize_media_component(
    raw_value: Any,
    *,
    index: int,
    fallback_provenance: (
        content.ProvenanceRecord
    ),
) -> content.MediaComponent:
    raw = _ensure_dict(
        raw_value,
        field_name="media component",
    )

    _reject_semantic_fields(
        raw
    )

    kind = normalize_media_kind(
        raw.get(
            "media_kind",
            raw.get(
                "type",
                raw.get(
                    "kind"
                ),
            ),
        )
    )

    component_id = _first_nonempty(
        raw,
        (
            "component_id",
            "id",
        ),
    )

    if not component_id:
        component_id = (
            kind
            + ":"
            + str(
                index
            )
        )

    media_url = _first_nonempty(
        raw,
        (
            "media_url",
            "url",
            "src",
        ),
    )

    return content.MediaComponent(
        component_id=component_id,
        media_kind=kind,
        media_url=media_url,
        sequence_index=(
            _optional_int(
                raw.get(
                    "sequence_index",
                    index,
                ),
                field_name=(
                    "sequence_index"
                ),
            )
        ),
        duration_seconds=(
            _optional_float(
                raw.get(
                    "duration_seconds",
                    raw.get(
                        "duration"
                    ),
                ),
                field_name=(
                    "duration_seconds"
                ),
            )
        ),
        width=(
            _optional_int(
                raw.get(
                    "width"
                ),
                field_name="width",
            )
        ),
        height=(
            _optional_int(
                raw.get(
                    "height"
                ),
                field_name="height",
            )
        ),
        has_audio=(
            _optional_bool(
                raw.get(
                    "has_audio"
                )
            )
        ),
        provenance=(
            _component_provenance(
                raw,
                fallback=(
                    fallback_provenance
                ),
            )
        ),
        metadata=_normalize_metadata(
            raw.get(
                "metadata"
            )
        ),
    )


def _normalize_media_components(
    payload: Dict[str, Any],
    *,
    fallback_provenance: (
        content.ProvenanceRecord
    ),
) -> List[content.MediaComponent]:
    values = payload.get(
        "media_components"
    )

    if values is None:
        values = payload.get(
            "media"
        )

    raw_media = _ensure_list(
        values,
        field_name="media",
    )

    return [
        _normalize_media_component(
            raw,
            index=index,
            fallback_provenance=(
                fallback_provenance
            ),
        )
        for index, raw in enumerate(
            raw_media
        )
    ]


def _normalize_engagement_snapshot(
    raw_value: Any,
    *,
    observed_at: str,
) -> content.EngagementSnapshot:
    raw = _ensure_dict(
        raw_value,
        field_name=(
            "engagement snapshot"
        ),
    )

    _reject_semantic_fields(
        raw
    )

    if "metrics" in raw:
        raw_metrics = _ensure_dict(
            raw.get(
                "metrics"
            ),
            field_name=(
                "engagement metrics"
            ),
        )

        snapshot_observed_at = (
            _clean_string(
                raw.get(
                    "observed_at"
                )
            )
            or observed_at
        )

        metadata = _normalize_metadata(
            raw.get(
                "metadata"
            )
        )

    else:
        raw_metrics = {
            key: value
            for key, value
            in raw.items()
            if key not in {
                "observed_at",
                "metadata",
            }
        }

        snapshot_observed_at = (
            _clean_string(
                raw.get(
                    "observed_at"
                )
            )
            or observed_at
        )

        metadata = _normalize_metadata(
            raw.get(
                "metadata"
            )
        )

    metrics = {}

    for key, value in (
        raw_metrics.items()
    ):
        metric_name = _normalized_token(
            key
        )

        if not metric_name:
            raise ValueError(
                "Engagement metric name "
                "cannot be empty."
            )

        metrics[
            metric_name
        ] = normalize_metric_value(
            value
        )

    return content.EngagementSnapshot(
        observed_at=(
            snapshot_observed_at
        ),
        metrics=metrics,
        metadata=metadata,
    )


def _normalize_engagement(
    payload: Dict[str, Any],
    *,
    observed_at: str,
) -> List[
    content.EngagementSnapshot
]:
    snapshots = payload.get(
        "engagement_snapshots"
    )

    if snapshots is not None:
        raw_snapshots = _ensure_list(
            snapshots,
            field_name=(
                "engagement_snapshots"
            ),
        )

        return [
            _normalize_engagement_snapshot(
                raw,
                observed_at=observed_at,
            )
            for raw in raw_snapshots
        ]

    raw_engagement = payload.get(
        "engagement"
    )

    if raw_engagement is None:
        return []

    return [
        _normalize_engagement_snapshot(
            raw_engagement,
            observed_at=observed_at,
        )
    ]


def _infer_container_kind(
    payload: Dict[str, Any],
    *,
    surface: str,
) -> str:
    raw = _first_nonempty(
        payload,
        (
            "container_kind",
            "container_type",
        ),
    )

    if raw:
        return _normalized_token(
            raw
        )

    if surface == "story":
        return "story"

    if surface == "thread":
        return "thread"

    if surface == "comment":
        return "comment"

    if surface == "reply":
        return "reply"

    if surface == "article":
        return "article"

    return "post"


def _deterministic_item_id(
    *,
    platform: str,
    platform_content_id: str,
    canonical_url: str,
) -> str:
    if platform_content_id:
        return (
            platform
            + ":"
            + platform_content_id
        )

    if canonical_url:
        digest = hashlib.sha256(
            canonical_url.encode(
                "utf-8"
            )
        ).hexdigest()[
            :20
        ]

        return (
            platform
            + ":url:"
            + digest
        )

    raise ValueError(
        "Normalization requires item_id, "
        "platform_content_id, or "
        "canonical_url."
    )


def normalize_content_item(
    raw_payload: Dict[str, Any],
) -> content.UnifiedContentItem:
    if not isinstance(
        raw_payload,
        dict,
    ):
        raise ValueError(
            "Content payload must "
            "be an object."
        )

    payload = dict(
        raw_payload
    )

    _validate_top_level_fields(
        payload
    )

    platform = normalize_platform(
        _first_nonempty(
            payload,
            (
                "platform",
                "source_platform",
            ),
        )
    )

    surface = normalize_surface(
        _first_nonempty(
            payload,
            (
                "platform_surface",
                "surface",
                "format",
            ),
        )
    )

    canonical_url = _first_nonempty(
        payload,
        (
            "canonical_url",
            "url",
        ),
    )

    platform_content_id = (
        _first_nonempty(
            payload,
            (
                "platform_content_id",
                "content_id",
                "post_id",
            ),
        )
    )

    item_id = _first_nonempty(
        payload,
        (
            "item_id",
            "id",
        ),
    )

    if not item_id:
        item_id = (
            _deterministic_item_id(
                platform=platform,
                platform_content_id=(
                    platform_content_id
                ),
                canonical_url=(
                    canonical_url
                ),
            )
        )

    published_at = _first_nonempty(
        payload,
        (
            "published_at",
            "created_at",
        ),
    )

    observed_at = _first_nonempty(
        payload,
        (
            "observed_at",
            "captured_at",
        ),
    )

    fallback_provenance = (
        _normalize_provenance(
            payload.get(
                "provenance"
            ),
            source_url=canonical_url,
            observed_at=observed_at,
        )
    )

    text_components = (
        _normalize_text_components(
            payload,
            fallback_provenance=(
                fallback_provenance
            ),
        )
    )

    media_components = (
        _normalize_media_components(
            payload,
            fallback_provenance=(
                fallback_provenance
            ),
        )
    )

    item = content.UnifiedContentItem(
        item_id=item_id,
        platform=platform,
        platform_surface=surface,
        container_kind=(
            _infer_container_kind(
                payload,
                surface=surface,
            )
        ),
        canonical_url=canonical_url,
        platform_content_id=(
            platform_content_id
        ),
        actor=_normalize_actor(
            payload.get(
                "actor",
                payload.get(
                    "author"
                ),
            )
        ),
        published_at=published_at,
        observed_at=observed_at,
        ephemeral=bool(
            _optional_bool(
                payload.get(
                    "ephemeral",
                    False,
                )
            )
        ),
        expires_at=_clean_string(
            payload.get(
                "expires_at"
            )
        ),
        text_components=(
            text_components
        ),
        media_components=(
            media_components
        ),
        claim_candidates=[],
        alignments=[],
        engagement_snapshots=(
            _normalize_engagement(
                payload,
                observed_at=(
                    observed_at
                ),
            )
        ),
        metadata={
            **_normalize_metadata(
                payload.get(
                    "metadata"
                )
            ),
            (
                "normalization_version"
            ): (
                CONTENT_NORMALIZATION_VERSION
            ),
        },
    )

    content.validate_unified_content_item(
        item
    )

    return item


def normalized_item_fingerprint(
    item: content.UnifiedContentItem,
) -> str:
    if hasattr(
        item,
        "model_dump",
    ):
        payload = item.model_dump(
            mode="json"
        )
    else:  # pragma: no cover
        payload = item.dict()

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()

CONTENT_BUNDLE_NORMALIZATION_VERSION = (
    "content-bundle-normalization-v1"
)


RELATIONSHIP_TYPE_ALIASES = {
    "reply": "reply_to",
    "reply_to": "reply_to",
    "quote": "quote_of",
    "quote_post": "quote_of",
    "quote_of": "quote_of",
    "repost": "repost_of",
    "retweet": "repost_of",
    "repost_of": "repost_of",
    "crosspost": "crosspost_of",
    "cross_post": "crosspost_of",
    "crosspost_of": "crosspost_of",
    "derived_from": "derives_from",
    "derive_from": "derives_from",
    "derives_from": "derives_from",
    "link": "links_to",
    "links_to": "links_to",
    "part_of": "part_of",
}


ALLOWED_BUNDLE_FIELDS = {
    "bundle_id",
    "id",
    "root_item_ids",
    "roots",
    "items",
    "relationships",
    "metadata",
}


ALLOWED_RELATIONSHIP_FIELDS = {
    "relationship_id",
    "id",
    "source_item_id",
    "source_item",
    "source",
    "from_item_id",
    "from",
    "target_item_id",
    "target_item",
    "target",
    "to_item_id",
    "to",
    "relationship_type",
    "relation",
    "type",
    "kind",
    "provenance",
    "metadata",
}


def normalize_relationship_type(
    value: Any,
) -> str:
    relationship_type = _normalized_token(
        value
    )

    relationship_type = (
        RELATIONSHIP_TYPE_ALIASES.get(
            relationship_type,
            relationship_type,
        )
    )

    allowed = {
        "reply_to",
        "quote_of",
        "repost_of",
        "crosspost_of",
        "derives_from",
        "links_to",
        "part_of",
    }

    if relationship_type not in allowed:
        raise ValueError(
            "Unsupported content relationship type: "
            + str(value)
        )

    return relationship_type


def _item_reference_aliases(
    raw_item: Dict[str, Any],
    item: content.UnifiedContentItem,
) -> List[str]:
    aliases = {
        item.item_id,
    }

    for field_name in (
        "item_id",
        "id",
        "platform_content_id",
        "content_id",
        "post_id",
        "canonical_url",
        "url",
    ):
        value = _clean_string(
            raw_item.get(field_name)
        )

        if value:
            aliases.add(value)

    if item.platform_content_id:
        aliases.add(
            item.platform_content_id
        )

    if item.canonical_url:
        aliases.add(
            item.canonical_url
        )

    return sorted(aliases)


def _build_reference_map(
    raw_items: List[Dict[str, Any]],
    items: List[
        content.UnifiedContentItem
    ],
) -> Dict[str, str]:
    reference_map = {}

    for raw_item, item in zip(
        raw_items,
        items,
    ):
        for alias in _item_reference_aliases(
            raw_item,
            item,
        ):
            existing = reference_map.get(
                alias
            )

            if (
                existing
                and existing != item.item_id
            ):
                raise ValueError(
                    "Ambiguous bundle item reference: "
                    + alias
                )

            reference_map[
                alias
            ] = item.item_id

    return reference_map


def _resolve_item_reference(
    value: Any,
    *,
    reference_map: Dict[str, str],
) -> str:
    reference = _clean_string(
        value
    )

    if not reference:
        raise ValueError(
            "Content relationship endpoint cannot be empty."
        )

    resolved = reference_map.get(
        reference
    )

    if not resolved:
        raise ValueError(
            "Unknown content item reference: "
            + reference
        )

    return resolved


def _deterministic_relationship_id(
    *,
    source_item_id: str,
    target_item_id: str,
    relationship_type: str,
) -> str:
    raw = (
        relationship_type
        + "|"
        + source_item_id
        + "|"
        + target_item_id
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:20]

    return "rel:" + digest


def _normalize_relationship(
    raw_value: Any,
    *,
    reference_map: Dict[str, str],
    item_map: Dict[
        str,
        content.UnifiedContentItem,
    ],
) -> content.ContentRelationship:
    raw = _ensure_dict(
        raw_value,
        field_name="content relationship",
    )

    _reject_semantic_fields(raw)

    unknown = (
        set(raw.keys())
        - ALLOWED_RELATIONSHIP_FIELDS
    )

    if unknown:
        raise ValueError(
            "Unsupported relationship fields: "
            + ", ".join(sorted(unknown))
        )

    source_reference = _first_nonempty(
        raw,
        (
            "source_item_id",
            "source_item",
            "source",
            "from_item_id",
            "from",
        ),
    )

    target_reference = _first_nonempty(
        raw,
        (
            "target_item_id",
            "target_item",
            "target",
            "to_item_id",
            "to",
        ),
    )

    source_item_id = _resolve_item_reference(
        source_reference,
        reference_map=reference_map,
    )

    target_item_id = _resolve_item_reference(
        target_reference,
        reference_map=reference_map,
    )

    relationship_type = (
        normalize_relationship_type(
            _first_nonempty(
                raw,
                (
                    "relationship_type",
                    "relation",
                    "type",
                    "kind",
                ),
            )
        )
    )

    relationship_id = _first_nonempty(
        raw,
        (
            "relationship_id",
            "id",
        ),
    )

    if not relationship_id:
        relationship_id = (
            _deterministic_relationship_id(
                source_item_id=source_item_id,
                target_item_id=target_item_id,
                relationship_type=relationship_type,
            )
        )

    source_item = item_map[
        source_item_id
    ]

    provenance = _normalize_provenance(
        raw.get("provenance"),
        source_url=source_item.canonical_url,
        observed_at=source_item.observed_at,
    )

    return content.ContentRelationship(
        relationship_id=relationship_id,
        source_item_id=source_item_id,
        target_item_id=target_item_id,
        relationship_type=relationship_type,
        provenance=provenance,
        metadata=_normalize_metadata(
            raw.get("metadata")
        ),
    )


def _normalize_bundle_roots(
    value: Any,
    *,
    reference_map: Dict[str, str],
) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_roots = [value]

    elif isinstance(value, list):
        raw_roots = value

    else:
        raise ValueError(
            "Bundle roots must be a string or list."
        )

    roots = []

    for raw_root in raw_roots:
        resolved = _resolve_item_reference(
            raw_root,
            reference_map=reference_map,
        )

        if resolved not in roots:
            roots.append(resolved)

    return roots


def _deterministic_bundle_id(
    *,
    item_ids: List[str],
    relationships: List[
        content.ContentRelationship
    ],
) -> str:
    relationship_keys = [
        (
            relationship.relationship_type
            + "|"
            + relationship.source_item_id
            + "|"
            + relationship.target_item_id
        )
        for relationship
        in relationships
    ]

    payload = {
        "items": sorted(item_ids),
        "relationships": sorted(
            relationship_keys
        ),
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    digest = hashlib.sha256(
        encoded
    ).hexdigest()[:20]

    return "bundle:" + digest


def normalize_content_bundle(
    raw_payload: Dict[str, Any],
) -> content.UnifiedContentBundle:
    if not isinstance(
        raw_payload,
        dict,
    ):
        raise ValueError(
            "Content bundle payload must be an object."
        )

    payload = dict(raw_payload)

    _reject_semantic_fields(payload)

    unknown = (
        set(payload.keys())
        - ALLOWED_BUNDLE_FIELDS
    )

    if unknown:
        raise ValueError(
            "Unsupported bundle fields: "
            + ", ".join(sorted(unknown))
        )

    raw_items = _ensure_list(
        payload.get("items"),
        field_name="items",
    )

    if not raw_items:
        raise ValueError(
            "Content bundle must contain at least one item."
        )

    clean_raw_items = [
        _ensure_dict(
            raw_item,
            field_name="bundle item",
        )
        for raw_item
        in raw_items
    ]

    items = [
        normalize_content_item(
            raw_item
        )
        for raw_item
        in clean_raw_items
    ]

    reference_map = _build_reference_map(
        clean_raw_items,
        items,
    )

    item_map = {
        item.item_id: item
        for item
        in items
    }

    raw_relationships = _ensure_list(
        payload.get("relationships"),
        field_name="relationships",
    )

    relationships = [
        _normalize_relationship(
            raw_relationship,
            reference_map=reference_map,
            item_map=item_map,
        )
        for raw_relationship
        in raw_relationships
    ]

    raw_roots = payload.get(
        "root_item_ids"
    )

    if raw_roots is None:
        raw_roots = payload.get(
            "roots"
        )

    root_item_ids = _normalize_bundle_roots(
        raw_roots,
        reference_map=reference_map,
    )

    if not root_item_ids:
        if len(items) == 1:
            root_item_ids = [
                items[0].item_id
            ]

        else:
            raise ValueError(
                "Multi-item bundle requires an explicit root."
            )

    bundle_id = _first_nonempty(
        payload,
        (
            "bundle_id",
            "id",
        ),
    )

    if not bundle_id:
        bundle_id = _deterministic_bundle_id(
            item_ids=[
                item.item_id
                for item
                in items
            ],
            relationships=relationships,
        )

    bundle = content.UnifiedContentBundle(
        bundle_id=bundle_id,
        root_item_ids=root_item_ids,
        items=items,
        relationships=relationships,
        metadata={
            **_normalize_metadata(
                payload.get("metadata")
            ),
            "normalization_version": (
                CONTENT_BUNDLE_NORMALIZATION_VERSION
            ),
        },
    )

    content.validate_unified_content_bundle(
        bundle
    )

    return bundle


def normalized_bundle_fingerprint(
    bundle: content.UnifiedContentBundle,
) -> str:
    if hasattr(
        bundle,
        "model_dump",
    ):
        payload = bundle.model_dump(
            mode="json"
        )

    else:
        payload = bundle.dict()

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()