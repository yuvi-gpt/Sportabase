from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from urllib.parse import (
    parse_qs,
    urlparse,
)

from app.models import content
from app.services import content_normalization
from app.services import content_resolution


MULTIMODAL_EXTRACTION_VERSION = (
    "multimodal-extraction-v1"
)

DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS = (
    180.0
)

_DEPENDENCY_RELATIONSHIP_TYPES = {
    "quote_of",
    "repost_of",
    "crosspost_of",
    "derives_from",
}

_CONVERSATION_RELATIONSHIP_TYPES = {
    "reply_to",
    "part_of",
}

_EXTRACTION_FORBIDDEN_FIELDS = {
    *content_normalization.FORBIDDEN_SEMANTIC_FIELDS,
    "authority",
    "source_role",
    "reliability",
    "reliability_score",
    "training_eligible",
    "trust_score",
    "independence",
    "independent",
    "is_independent",
}


@dataclass(frozen=True)
class ContentTarget:
    platform: str
    surface: str
    container_kind: str
    canonical_url: str
    platform_content_id: str = ""
    actor_hint: Dict[str, Any] = field(
        default_factory=dict
    )
    parent_content_id: str = ""
    detection: str = "generic_web"

    @property
    def structurally_specific(
        self,
    ) -> bool:
        return bool(
            self.platform != "web"
            and self.platform_content_id
            and self.detection
            == "structural"
        )


@dataclass(frozen=True)
class ExtractedSnapshot:
    source_url: str
    extraction_method: str
    observed_at: str
    payload: Dict[str, Any]
    actor: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ExtractedRelationship:
    source_index: int
    target_index: int
    relationship_type: str
    observed_at: str = ""
    extraction_method: str = (
        "adapter_relationship"
    )
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ExtractedBundle:
    items: Sequence[
        ExtractedSnapshot
    ]
    root_indices: Sequence[int] = field(
        default_factory=tuple
    )
    relationships: Sequence[
        ExtractedRelationship
    ] = field(
        default_factory=tuple
    )
    bundle_id: str = ""
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ModalityProcessingPlan:
    item_id: str

    semantic_text_component_ids: Tuple[
        str,
        ...,
    ]

    image_visual_component_ids: Tuple[
        str,
        ...,
    ]

    video_frame_component_ids: Tuple[
        str,
        ...,
    ]

    ocr_component_ids: Tuple[
        str,
        ...,
    ]

    transcription_component_ids: Tuple[
        str,
        ...,
    ]

    short_video_component_ids: Tuple[
        str,
        ...,
    ]

    long_video_component_ids: Tuple[
        str,
        ...,
    ]

    unknown_duration_video_component_ids: (
        Tuple[
            str,
            ...,
        ]
    )

    caption_media_alignment_pairs: Tuple[
        Tuple[
            str,
            str,
        ],
        ...,
    ]

    conversation_traversal_required: bool


@dataclass(frozen=True)
class BundleProcessingPlan:
    item_plans: Tuple[
        ModalityProcessingPlan,
        ...,
    ]

    dependency_relationship_ids: Tuple[
        str,
        ...,
    ]

    conversation_relationship_ids: Tuple[
        str,
        ...,
    ]

    conversation_traversal_required: bool
    dependency_tracing_required: bool


def _normalized_semantic_key(
    value: Any,
) -> str:
    return re.sub(
        r"_+",
        "_",
        str(
            value or ""
        )
        .strip()
        .lower()
        .replace(
            "-",
            "_",
        )
        .replace(
            " ",
            "_",
        ),
    ).strip(
        "_"
    )


def _reject_extraction_semantics(
    value: Any,
    *,
    path: str = "payload",
) -> None:
    if isinstance(
        value,
        Mapping,
    ):
        for (
            raw_key,
            child,
        ) in value.items():
            key = (
                _normalized_semantic_key(
                    raw_key
                )
            )

            if (
                key
                in _EXTRACTION_FORBIDDEN_FIELDS
            ):
                raise ValueError(
                    "Extraction cannot establish "
                    "semantic intelligence field "
                    f"{path}.{raw_key}."
                )

            _reject_extraction_semantics(
                child,
                path=(
                    f"{path}.{raw_key}"
                ),
            )

        return

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        for (
            index,
            child,
        ) in enumerate(
            value
        ):
            _reject_extraction_semantics(
                child,
                path=(
                    f"{path}[{index}]"
                ),
            )


def _raw_http_url(
    url: str,
) -> str:
    raw = str(
        url or ""
    ).strip()

    if not raw:
        raise ValueError(
            "A content URL is required."
        )

    if raw.startswith(
        "//"
    ):
        raw = (
            "https:"
            + raw
        )

    elif not re.match(
        (
            r"^[A-Za-z]"
            r"[A-Za-z0-9+.-]*://"
        ),
        raw,
    ):
        raw = (
            "https://"
            + raw
        )

    parsed = urlparse(
        raw
    )

    if (
        parsed.scheme.lower()
        not in {
            "http",
            "https",
        }
        or not parsed.hostname
    ):
        raise ValueError(
            "The content URL must use "
            "HTTP or HTTPS."
        )

    return raw


def _host_key(
    hostname: str,
) -> str:
    host = str(
        hostname or ""
    ).strip().lower().rstrip(
        "."
    )

    for prefix in (
        "www.",
        "m.",
        "mobile.",
        "old.",
        "new.",
        "web.",
    ):
        if host.startswith(
            prefix
        ):
            host = host[
                len(
                    prefix
                ):
            ]
            break

    return host


def _path_parts(
    parsed: Any,
) -> List[str]:
    return [
        part
        for part
        in str(
            parsed.path or ""
        ).split(
            "/"
        )
        if part
    ]


def _clean_id(
    value: Any,
    pattern: str = (
        r"[A-Za-z0-9_-]+"
    ),
) -> str:
    candidate = str(
        value or ""
    ).strip()

    if (
        candidate
        and re.fullmatch(
            pattern,
            candidate,
        )
    ):
        return candidate

    return ""


def _platform_only(
    platform: str,
    canonical_url: str,
) -> ContentTarget:
    return ContentTarget(
        platform=platform,
        surface="",
        container_kind="unknown",
        canonical_url=canonical_url,
        detection="platform_only",
    )


def detect_content_target(
    url: str,
) -> ContentTarget:
    raw_url = _raw_http_url(
        url
    )

    parsed = urlparse(
        raw_url
    )

    host = _host_key(
        parsed.hostname or ""
    )

    parts = _path_parts(
        parsed
    )

    lower_parts = [
        part.lower()
        for part in parts
    ]

    query = parse_qs(
        parsed.query or "",
        keep_blank_values=True,
    )

    normalized_url = (
        content_resolution
        .normalized_analysis_url(
            raw_url
        )
    )

    if host == "instagram.com":
        if (
            len(parts) >= 2
            and lower_parts[0]
            in {
                "p",
                "reel",
                "reels",
                "tv",
            }
        ):
            content_id = _clean_id(
                parts[1],
                (
                    r"[A-Za-z0-9_-]"
                    r"{3,200}"
                ),
            )

            if content_id:
                surface = {
                    "p": "post",
                    "reel": "reel",
                    "reels": "reel",
                    "tv": "video",
                }[
                    lower_parts[0]
                ]

                path_token = (
                    "reel"
                    if (
                        lower_parts[0]
                        == "reels"
                    )
                    else lower_parts[0]
                )

                return ContentTarget(
                    platform=(
                        "instagram"
                    ),
                    surface=surface,
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://instagram.com/"
                        f"{path_token}/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        if (
            len(parts) >= 3
            and lower_parts[0]
            == "stories"
        ):
            handle = (
                parts[1]
                .lstrip("@")
                .strip()
            )

            content_id = _clean_id(
                parts[2],
                (
                    r"[A-Za-z0-9_-]"
                    r"{1,200}"
                ),
            )

            if (
                handle
                and content_id
            ):
                return ContentTarget(
                    platform=(
                        "instagram"
                    ),
                    surface="story",
                    container_kind=(
                        "story"
                    ),
                    canonical_url=(
                        "https://instagram.com/"
                        f"stories/{handle}/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    actor_hint=(
                        make_actor_identity(
                            handle=handle,
                            profile_url=(
                                "https://"
                                "instagram.com/"
                                f"{handle}"
                            ),
                        )
                    ),
                    detection=(
                        "structural"
                    ),
                )

        return _platform_only(
            "instagram",
            normalized_url,
        )

    if host in {
        "x.com",
        "twitter.com",
    }:
        handle = ""
        content_id = ""

        if (
            len(parts) >= 3
            and lower_parts[1]
            == "status"
        ):
            if (
                lower_parts[0]
                != "i"
            ):
                handle = (
                    parts[0]
                    .lstrip("@")
                    .strip()
                )

            content_id = _clean_id(
                parts[2],
                r"[0-9]{1,40}",
            )

        elif (
            len(parts) >= 4
            and lower_parts[0]
            == "i"
            and lower_parts[1]
            == "web"
            and lower_parts[2]
            == "status"
        ):
            content_id = _clean_id(
                parts[3],
                r"[0-9]{1,40}",
            )

        if content_id:
            if handle:
                canonical = (
                    "https://x.com/"
                    f"{handle}/status/"
                    f"{content_id}"
                )
            else:
                canonical = (
                    "https://x.com/"
                    "i/status/"
                    f"{content_id}"
                )

            if handle:
                actor_hint = (
                    make_actor_identity(
                        handle=handle,
                        profile_url=(
                            "https://x.com/"
                            f"{handle}"
                        ),
                    )
                )
            else:
                actor_hint = {}

            return ContentTarget(
                platform="x",
                surface="post",
                container_kind="post",
                canonical_url=canonical,
                platform_content_id=(
                    content_id
                ),
                actor_hint=actor_hint,
                detection="structural",
            )

        return _platform_only(
            "x",
            normalized_url,
        )

    if host in {
        "tiktok.com",
        "vm.tiktok.com",
        "vt.tiktok.com",
    }:
        if (
            len(parts) >= 3
            and parts[0].startswith(
                "@"
            )
            and lower_parts[1]
            in {
                "video",
                "photo",
            }
        ):
            handle = (
                parts[0][1:]
                .strip()
            )

            content_id = _clean_id(
                parts[2],
                r"[0-9]{1,40}",
            )

            if (
                handle
                and content_id
            ):
                surface = (
                    "video"
                    if (
                        lower_parts[1]
                        == "video"
                    )
                    else "photo"
                )

                return ContentTarget(
                    platform="tiktok",
                    surface=surface,
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://www."
                        "tiktok.com/@"
                        f"{handle}/"
                        f"{lower_parts[1]}/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    actor_hint=(
                        make_actor_identity(
                            handle=handle,
                            profile_url=(
                                "https://www."
                                "tiktok.com/@"
                                f"{handle}"
                            ),
                        )
                    ),
                    detection=(
                        "structural"
                    ),
                )

        return _platform_only(
            "tiktok",
            normalized_url,
        )

    if host in {
        "reddit.com",
        "redd.it",
    }:
        if (
            host == "redd.it"
            and parts
        ):
            post_id = _clean_id(
                parts[0],
                r"[A-Za-z0-9]+",
            )

            if post_id:
                return ContentTarget(
                    platform="reddit",
                    surface="post",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://redd.it/"
                        f"{post_id}"
                    ),
                    platform_content_id=(
                        post_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        comments_index = -1

        for (
            index,
            token,
        ) in enumerate(
            lower_parts
        ):
            if token == "comments":
                comments_index = (
                    index
                )
                break

        if (
            comments_index >= 0
            and len(parts)
            > comments_index + 1
        ):
            post_id = _clean_id(
                parts[
                    comments_index
                    + 1
                ],
                r"[A-Za-z0-9]+",
            )

            if post_id:
                trailing = parts[
                    comments_index + 2:
                ]

                comment_id = ""

                if (
                    len(trailing)
                    >= 2
                ):
                    comment_id = (
                        _clean_id(
                            trailing[1],
                            (
                                r"[A-Za-z"
                                r"0-9]+"
                            ),
                        )
                    )

                if comment_id:
                    return (
                        ContentTarget(
                            platform=(
                                "reddit"
                            ),
                            surface=(
                                "comment"
                            ),
                            container_kind=(
                                "comment"
                            ),
                            canonical_url=(
                                normalized_url
                            ),
                            platform_content_id=(
                                comment_id
                            ),
                            parent_content_id=(
                                post_id
                            ),
                            detection=(
                                "structural"
                            ),
                        )
                    )

                return ContentTarget(
                    platform="reddit",
                    surface="post",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        normalized_url
                    ),
                    platform_content_id=(
                        post_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        return _platform_only(
            "reddit",
            normalized_url,
        )

    if host in {
        "facebook.com",
        "fb.watch",
    }:
        if host == "fb.watch":
            return _platform_only(
                "facebook",
                normalized_url,
            )

        if (
            len(parts) >= 2
            and lower_parts[0]
            == "reel"
        ):
            content_id = _clean_id(
                parts[1],
                (
                    r"[A-Za-z0-9"
                    r"._-]+"
                ),
            )

            if content_id:
                return ContentTarget(
                    platform=(
                        "facebook"
                    ),
                    surface="reel",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://www."
                        "facebook.com/reel/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        if (
            lower_parts
            and lower_parts[0]
            == "watch"
        ):
            content_id = _clean_id(
                (
                    query.get(
                        "v"
                    )
                    or [""]
                )[0],
                r"[0-9]{1,40}",
            )

            if content_id:
                return ContentTarget(
                    platform=(
                        "facebook"
                    ),
                    surface="video",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://www."
                        "facebook.com/watch"
                        f"?v={content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        if (
            len(parts) >= 3
            and lower_parts[1]
            == "posts"
        ):
            actor_handle = (
                parts[0].strip()
            )

            content_id = _clean_id(
                parts[2],
                (
                    r"[A-Za-z0-9"
                    r"._-]+"
                ),
            )

            if (
                actor_handle
                and content_id
            ):
                return ContentTarget(
                    platform=(
                        "facebook"
                    ),
                    surface="post",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://www."
                        "facebook.com/"
                        f"{actor_handle}/"
                        "posts/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    actor_hint=(
                        make_actor_identity(
                            handle=(
                                actor_handle
                            ),
                            profile_url=(
                                "https://www."
                                "facebook.com/"
                                f"{actor_handle}"
                            ),
                        )
                    ),
                    detection=(
                        "structural"
                    ),
                )

        if (
            lower_parts
            and lower_parts[0]
            in {
                "story.php",
                "permalink.php",
            }
        ):
            content_id = _clean_id(
                (
                    query.get(
                        "story_fbid"
                    )
                    or [""]
                )[0],
                r"[0-9]{1,40}",
            )

            actor_id = _clean_id(
                (
                    query.get(
                        "id"
                    )
                    or [""]
                )[0],
                r"[0-9]{1,40}",
            )

            if content_id:
                if actor_id:
                    actor_hint = (
                        make_actor_identity(
                            platform_actor_id=(
                                actor_id
                            )
                        )
                    )
                else:
                    actor_hint = {}

                canonical = (
                    "https://www."
                    "facebook.com/"
                    "story.php"
                    "?story_fbid="
                    f"{content_id}"
                )

                if actor_id:
                    canonical += (
                        f"&id={actor_id}"
                    )

                return ContentTarget(
                    platform=(
                        "facebook"
                    ),
                    surface="post",
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        canonical
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    actor_hint=(
                        actor_hint
                    ),
                    detection=(
                        "structural"
                    ),
                )

        return _platform_only(
            "facebook",
            normalized_url,
        )

    youtube_hosts = {
        _host_key(
            value
        )
        for value
        in (
            content_resolution
            .YOUTUBE_HOSTS
        )
    }

    if host in youtube_hosts:
        if (
            len(parts) >= 2
            and lower_parts[0]
            == "post"
        ):
            content_id = _clean_id(
                parts[1],
                (
                    r"[A-Za-z0-9_-]"
                    r"{3,200}"
                ),
            )

            if content_id:
                return ContentTarget(
                    platform=(
                        "youtube"
                    ),
                    surface=(
                        "community_post"
                    ),
                    container_kind=(
                        "post"
                    ),
                    canonical_url=(
                        "https://youtube.com/"
                        "post/"
                        f"{content_id}"
                    ),
                    platform_content_id=(
                        content_id
                    ),
                    detection=(
                        "structural"
                    ),
                )

        video_id = (
            content_resolution
            .youtube_video_id_from_url(
                parsed
            )
        )

        if video_id:
            surface = (
                "short"
                if (
                    lower_parts
                    and lower_parts[0]
                    == "shorts"
                )
                else "video"
            )

            return ContentTarget(
                platform="youtube",
                surface=surface,
                container_kind="media",
                canonical_url=(
                    "https://youtube.com/"
                    "watch?v="
                    f"{video_id}"
                ),
                platform_content_id=(
                    video_id
                ),
                detection="structural",
            )

        return _platform_only(
            "youtube",
            normalized_url,
        )

    return ContentTarget(
        platform="web",
        surface="web_page",
        container_kind="unknown",
        canonical_url=normalized_url,
        detection="generic_web",
    )


def make_actor_identity(
    *,
    platform_actor_id: Any = "",
    handle: Any = "",
    display_name: Any = "",
    profile_url: Any = "",
    canonical_entity_id: Any = "",
    metadata: Optional[
        Mapping[
            str,
            Any,
        ]
    ] = None,
) -> Dict[str, Any]:
    clean_metadata = deepcopy(
        dict(
            metadata or {}
        )
    )

    _reject_extraction_semantics(
        clean_metadata,
        path="actor.metadata",
    )

    return {
        "platform_actor_id": str(
            platform_actor_id or ""
        ).strip(),
        "handle": str(
            handle or ""
        ).strip().lstrip(
            "@"
        ),
        "display_name": str(
            display_name or ""
        ).strip(),
        "profile_url": str(
            profile_url or ""
        ).strip(),
        "canonical_entity_id": str(
            canonical_entity_id or ""
        ).strip(),
        "metadata": clean_metadata,
    }


def _actor_mapping(
    value: Any,
) -> Dict[str, Any]:
    if value is None:
        return {}

    if isinstance(
        value,
        str,
    ):
        text = value.strip()

        if not text:
            return {}

        if text.startswith(
            "@"
        ):
            return make_actor_identity(
                handle=text
            )

        return make_actor_identity(
            display_name=text
        )

    if not isinstance(
        value,
        Mapping,
    ):
        raise ValueError(
            "Actor identity must be "
            "a string or object."
        )

    raw = dict(
        value
    )

    _reject_extraction_semantics(
        raw,
        path="actor",
    )

    metadata = (
        raw.get(
            "metadata"
        )
        or {}
    )

    if not isinstance(
        metadata,
        Mapping,
    ):
        raise ValueError(
            "Actor metadata must "
            "be an object."
        )

    return make_actor_identity(
        platform_actor_id=raw.get(
            "platform_actor_id",
            raw.get(
                "id",
                "",
            ),
        ),
        handle=raw.get(
            "handle",
            raw.get(
                "username",
                "",
            ),
        ),
        display_name=raw.get(
            "display_name",
            raw.get(
                "name",
                "",
            ),
        ),
        profile_url=raw.get(
            "profile_url",
            raw.get(
                "url",
                "",
            ),
        ),
        canonical_entity_id=raw.get(
            "canonical_entity_id",
            "",
        ),
        metadata=metadata,
    )


def _merge_actor_identities(
    *actors: Any,
) -> Dict[str, Any]:
    merged = (
        make_actor_identity()
    )

    metadata: Dict[
        str,
        Any,
    ] = {}

    for actor_value in actors:
        actor = _actor_mapping(
            actor_value
        )

        if not actor:
            continue

        for field_name in (
            "platform_actor_id",
            "handle",
            "display_name",
            "profile_url",
            "canonical_entity_id",
        ):
            value = str(
                actor.get(
                    field_name
                )
                or ""
            ).strip()

            if value:
                merged[
                    field_name
                ] = value

        metadata.update(
            deepcopy(
                actor.get(
                    "metadata"
                )
                or {}
            )
        )

    merged[
        "metadata"
    ] = metadata

    return merged


def _normalized_platform_token(
    value: Any,
) -> str:
    raw = str(
        value or ""
    ).strip()

    if not raw:
        return ""

    return (
        content_normalization
        .normalize_platform(
            raw
        )
    )


def _normalized_surface_token(
    value: Any,
) -> str:
    raw = str(
        value or ""
    ).strip()

    if not raw:
        return ""

    return (
        content_normalization
        .normalize_surface(
            raw
        )
    )


def _effective_target(
    source_target: ContentTarget,
    adapter_url: str,
) -> ContentTarget:
    if not str(
        adapter_url or ""
    ).strip():
        return source_target

    adapter_target = (
        detect_content_target(
            adapter_url
        )
    )

    if (
        source_target.platform
        != "web"
        and adapter_target.platform
        != "web"
    ):
        if (
            source_target.platform
            != adapter_target.platform
        ):
            raise ValueError(
                "Snapshot canonical URL "
                "conflicts with source "
                "platform."
            )

    if (
        source_target
        .structurally_specific
        and adapter_target
        .structurally_specific
    ):
        if (
            source_target
            .platform_content_id
            != adapter_target
            .platform_content_id
        ):
            raise ValueError(
                "Snapshot canonical URL "
                "conflicts with source "
                "content ID."
            )

        # The original source can carry
        # surface information that a
        # normalized canonical URL loses.
        # Example: YouTube /shorts/<id>
        # canonicalizes to /watch?v=<id>.
        return source_target

    if (
        source_target
        .structurally_specific
    ):
        if (
            adapter_target.platform
            == "web"
        ):
            raise ValueError(
                "Snapshot canonical URL "
                "loses a structurally "
                "detected platform target."
            )

        return source_target

    if (
        source_target.detection
        == "platform_only"
        and adapter_target
        .structurally_specific
        and source_target.platform
        == adapter_target.platform
    ):
        return adapter_target

    if (
        source_target.platform
        == "web"
        and adapter_target.platform
        == "web"
    ):
        return adapter_target

    if (
        source_target.detection
        == "platform_only"
        and adapter_target.detection
        == "platform_only"
    ):
        return adapter_target

    return source_target


def prepare_snapshot_payload(
    snapshot: ExtractedSnapshot,
) -> Dict[str, Any]:
    if not isinstance(
        snapshot,
        ExtractedSnapshot,
    ):
        raise TypeError(
            "snapshot must be an "
            "ExtractedSnapshot."
        )

    if not isinstance(
        snapshot.payload,
        Mapping,
    ):
        raise ValueError(
            "Snapshot payload must "
            "be an object."
        )

    payload = deepcopy(
        dict(
            snapshot.payload
        )
    )

    _reject_extraction_semantics(
        payload
    )

    observed_at = str(
        snapshot.observed_at
        or ""
    ).strip()

    if not observed_at:
        raise ValueError(
            "Extracted snapshot "
            "requires observed_at."
        )

    extraction_method = str(
        snapshot.extraction_method
        or ""
    ).strip()

    if not extraction_method:
        extraction_method = (
            "adapter"
        )

    source_target = (
        detect_content_target(
            snapshot.source_url
        )
    )

    adapter_url = str(
        payload.get(
            "canonical_url"
        )
        or payload.get(
            "url"
        )
        or ""
    ).strip()

    target = _effective_target(
        source_target,
        adapter_url,
    )

    explicit_platform = (
        _normalized_platform_token(
            payload.get(
                "platform",
                payload.get(
                    "source_platform",
                    "",
                ),
            )
        )
    )

    if (
        explicit_platform
        and explicit_platform
        != target.platform
    ):
        raise ValueError(
            "Snapshot platform "
            "conflicts with "
            "structurally detected "
            "platform."
        )

    explicit_content_id = str(
        payload.get(
            "platform_content_id"
        )
        or payload.get(
            "content_id"
        )
        or payload.get(
            "post_id"
        )
        or ""
    ).strip()

    if target.platform_content_id:
        if (
            explicit_content_id
            and explicit_content_id
            != target
            .platform_content_id
        ):
            raise ValueError(
                "Snapshot content ID "
                "conflicts with "
                "structurally detected "
                "content ID."
            )

    elif (
        explicit_content_id
        and target.platform
        != "web"
    ):
        raise ValueError(
            "Platform content ID "
            "requires a structurally "
            "resolved canonical target."
        )

    explicit_surface = (
        _normalized_surface_token(
            payload.get(
                "platform_surface",
                payload.get(
                    "surface",
                    payload.get(
                        "format",
                        "",
                    ),
                ),
            )
        )
    )

    if (
        target.surface
        and target.surface
        != "web_page"
        and explicit_surface
        and explicit_surface
        != target.surface
    ):
        raise ValueError(
            "Snapshot surface "
            "conflicts with "
            "structurally detected "
            "surface."
        )

    existing_actor = payload.get(
        "actor",
        payload.get(
            "author"
        ),
    )

    actor = (
        _merge_actor_identities(
            target.actor_hint,
            existing_actor,
            snapshot.actor,
        )
    )

    provenance = deepcopy(
        dict(
            payload.get(
                "provenance"
            )
            or {}
        )
    )

    _reject_extraction_semantics(
        provenance,
        path="provenance",
    )

    provenance[
        "source_url"
    ] = str(
        snapshot.source_url
        or ""
    ).strip()

    provenance[
        "observed_at"
    ] = observed_at

    provenance[
        "extraction_method"
    ] = extraction_method

    metadata = deepcopy(
        dict(
            payload.get(
                "metadata"
            )
            or {}
        )
    )

    _reject_extraction_semantics(
        metadata,
        path="metadata",
    )

    metadata[
        "multimodal_extraction_version"
    ] = (
        MULTIMODAL_EXTRACTION_VERSION
    )

    metadata[
        "target_detection"
    ] = target.detection

    if target.parent_content_id:
        metadata[
            "parent_content_id"
        ] = (
            target.parent_content_id
        )

    payload[
        "platform"
    ] = target.platform

    if (
        target.surface
        == "web_page"
        and explicit_surface
    ):
        payload[
            "platform_surface"
        ] = explicit_surface
    else:
        payload[
            "platform_surface"
        ] = target.surface

    if (
        target.container_kind
        == "unknown"
    ):
        container_kind = str(
            payload.get(
                "container_kind"
            )
            or payload.get(
                "container_type"
            )
            or ""
        ).strip()

        payload[
            "container_kind"
        ] = (
            container_kind
            or "unknown"
        )
    else:
        payload[
            "container_kind"
        ] = (
            target.container_kind
        )

    payload[
        "canonical_url"
    ] = target.canonical_url

    payload[
        "platform_content_id"
    ] = (
        target.platform_content_id
    )

    payload[
        "observed_at"
    ] = observed_at

    payload[
        "actor"
    ] = actor

    payload[
        "provenance"
    ] = provenance

    payload[
        "metadata"
    ] = metadata

    for alias in (
        "source_platform",
        "surface",
        "format",
        "container_type",
        "url",
        "content_id",
        "post_id",
        "author",
        "captured_at",
    ):
        payload.pop(
            alias,
            None,
        )

    if (
        target.surface
        == "story"
    ):
        payload.setdefault(
            "ephemeral",
            True,
        )

    return payload


def normalize_extracted_snapshot(
    snapshot: ExtractedSnapshot,
) -> content.UnifiedContentItem:
    return (
        content_normalization
        .normalize_content_item(
            prepare_snapshot_payload(
                snapshot
            )
        )
    )


def _validate_item_index(
    index: int,
    item_count: int,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(
            index,
            bool,
        )
        or not isinstance(
            index,
            int,
        )
    ):
        raise ValueError(
            f"{field_name} must be "
            "an integer index."
        )

    if (
        index < 0
        or index >= item_count
    ):
        raise ValueError(
            f"{field_name} is outside "
            "the extracted bundle."
        )

    return index


def normalize_extracted_bundle(
    extracted: ExtractedBundle,
) -> content.UnifiedContentBundle:
    if not isinstance(
        extracted,
        ExtractedBundle,
    ):
        raise TypeError(
            "extracted must be an "
            "ExtractedBundle."
        )

    snapshots = list(
        extracted.items
    )

    if not snapshots:
        raise ValueError(
            "Extracted bundle must "
            "contain at least one "
            "snapshot."
        )

    _reject_extraction_semantics(
        extracted.metadata,
        path="bundle.metadata",
    )

    prepared_items = [
        prepare_snapshot_payload(
            snapshot
        )
        for snapshot
        in snapshots
    ]

    preview_items = [
        content_normalization
        .normalize_content_item(
            raw
        )
        for raw
        in prepared_items
    ]

    item_count = len(
        preview_items
    )

    root_indices = list(
        extracted.root_indices
    )

    if (
        not root_indices
        and item_count == 1
    ):
        root_indices = [
            0
        ]

    roots = [
        preview_items[
            _validate_item_index(
                index,
                item_count,
                field_name=(
                    "root_index"
                ),
            )
        ].item_id
        for index
        in root_indices
    ]

    relationships: List[
        Dict[
            str,
            Any,
        ]
    ] = []

    for relationship in (
        extracted.relationships
    ):
        if not isinstance(
            relationship,
            ExtractedRelationship,
        ):
            raise TypeError(
                "Bundle relationships "
                "must be "
                "ExtractedRelationship "
                "values."
            )

        source_index = (
            _validate_item_index(
                relationship
                .source_index,
                item_count,
                field_name=(
                    "relationship."
                    "source_index"
                ),
            )
        )

        target_index = (
            _validate_item_index(
                relationship
                .target_index,
                item_count,
                field_name=(
                    "relationship."
                    "target_index"
                ),
            )
        )

        metadata = deepcopy(
            dict(
                relationship
                .metadata
                or {}
            )
        )

        _reject_extraction_semantics(
            metadata,
            path=(
                "relationship.metadata"
            ),
        )

        observed_at = str(
            relationship.observed_at
            or snapshots[
                source_index
            ].observed_at
            or ""
        ).strip()

        extraction_method = str(
            relationship
            .extraction_method
            or ""
        ).strip()

        if not extraction_method:
            extraction_method = (
                "adapter_relationship"
            )

        relationships.append(
            {
                "source_item_id": (
                    preview_items[
                        source_index
                    ].item_id
                ),
                "target_item_id": (
                    preview_items[
                        target_index
                    ].item_id
                ),
                "relationship_type": (
                    relationship
                    .relationship_type
                ),
                "provenance": {
                    "source_url": (
                        snapshots[
                            source_index
                        ].source_url
                    ),
                    "observed_at": (
                        observed_at
                    ),
                    "extraction_method": (
                        extraction_method
                    ),
                },
                "metadata": (
                    metadata
                ),
            }
        )

    bundle_metadata = deepcopy(
        dict(
            extracted.metadata
            or {}
        )
    )

    bundle_metadata[
        "multimodal_extraction_version"
    ] = (
        MULTIMODAL_EXTRACTION_VERSION
    )

    raw_bundle: Dict[
        str,
        Any,
    ] = {
        "items": prepared_items,
        "roots": roots,
        "relationships": (
            relationships
        ),
        "metadata": (
            bundle_metadata
        ),
    }

    if extracted.bundle_id:
        raw_bundle[
            "bundle_id"
        ] = str(
            extracted.bundle_id
        ).strip()

    return (
        content_normalization
        .normalize_content_bundle(
            raw_bundle
        )
    )


def bridge_article_snapshot(
    *,
    source_url: str,
    observed_at: str,
    article: Mapping[
        str,
        Any,
    ],
    canonical_url: str = "",
    actor: Optional[
        Mapping[
            str,
            Any,
        ]
    ] = None,
    published_at: str = "",
) -> ExtractedSnapshot:
    if not isinstance(
        article,
        Mapping,
    ):
        raise ValueError(
            "Article resolution must "
            "be an object."
        )

    raw = deepcopy(
        dict(
            article
        )
    )

    _reject_extraction_semantics(
        raw,
        path=(
            "article_resolution"
        ),
    )

    title = str(
        raw.get(
            "title"
        )
        or ""
    ).strip()

    body = str(
        raw.get(
            "text"
        )
        or raw.get(
            "body"
        )
        or ""
    ).strip()

    if not body:
        raise ValueError(
            "Article resolution must "
            "contain extracted "
            "article text."
        )

    legacy_method = str(
        raw.get(
            "extraction_method"
        )
        or "unknown"
    ).strip()

    if not legacy_method:
        legacy_method = (
            "unknown"
        )

    resolved_url = str(
        canonical_url
        or raw.get(
            "final_url"
        )
        or source_url
        or ""
    ).strip()

    target = detect_content_target(
        resolved_url
    )

    if target.platform != "web":
        raise ValueError(
            "Article bridge only "
            "accepts generic "
            "web/article URLs."
        )

    payload: Dict[
        str,
        Any,
    ] = {
        "platform": "web",
        "surface": "article",
        "container_kind": (
            "article"
        ),
        "canonical_url": (
            target.canonical_url
        ),
        "body": body,
        "published_at": str(
            published_at
            or raw.get(
                "published_at"
            )
            or ""
        ).strip(),
        "metadata": {
            "legacy_bridge": (
                "article"
            ),
            (
                "legacy_article_"
                "extraction_method"
            ): legacy_method,
        },
    }

    if title:
        payload[
            "title"
        ] = title

    return ExtractedSnapshot(
        source_url=source_url,
        extraction_method=(
            "article_resolver:"
            f"{legacy_method}"
        ),
        observed_at=observed_at,
        payload=payload,
        actor=deepcopy(
            dict(
                actor
                or raw.get(
                    "actor"
                )
                or {}
            )
        ),
    )


def bridge_article_resolution(
    *,
    source_url: str,
    observed_at: str,
    article: Mapping[
        str,
        Any,
    ],
    canonical_url: str = "",
    actor: Optional[
        Mapping[
            str,
            Any,
        ]
    ] = None,
    published_at: str = "",
) -> content.UnifiedContentItem:
    return (
        normalize_extracted_snapshot(
            bridge_article_snapshot(
                source_url=(
                    source_url
                ),
                observed_at=(
                    observed_at
                ),
                article=article,
                canonical_url=(
                    canonical_url
                ),
                actor=actor,
                published_at=(
                    published_at
                ),
            )
        )
    )


def bridge_youtube_snapshot(
    *,
    source_url: str,
    observed_at: str,
    title: str = "",
    description: str = "",
    transcript: str = "",
    duration_seconds: Optional[
        float
    ] = None,
    media_url: str = "",
    actor: Optional[
        Mapping[
            str,
            Any,
        ]
    ] = None,
    published_at: str = "",
    extraction_method: str = (
        "youtube_resolver"
    ),
    has_audio: Optional[
        bool
    ] = True,
    metadata: Optional[
        Mapping[
            str,
            Any,
        ]
    ] = None,
) -> ExtractedSnapshot:
    target = detect_content_target(
        source_url
    )

    if (
        target.platform
        != "youtube"
        or not target
        .structurally_specific
        or target.surface
        not in {
            "video",
            "short",
        }
    ):
        raise ValueError(
            "YouTube bridge requires "
            "a structurally valid "
            "video or short URL."
        )

    bridge_metadata = deepcopy(
        dict(
            metadata or {}
        )
    )

    _reject_extraction_semantics(
        bridge_metadata,
        path="youtube.metadata",
    )

    bridge_metadata[
        "legacy_bridge"
    ] = "youtube"

    media: Dict[
        str,
        Any,
    ] = {
        "component_id": (
            "video:0"
        ),
        "media_kind": "video",
        "media_url": str(
            media_url
            or target.canonical_url
        ).strip(),
        "has_audio": has_audio,
    }

    if (
        duration_seconds
        is not None
    ):
        media[
            "duration_seconds"
        ] = duration_seconds

    payload: Dict[
        str,
        Any,
    ] = {
        "platform": "youtube",
        "surface": (
            target.surface
        ),
        "container_kind": (
            "media"
        ),
        "canonical_url": (
            target.canonical_url
        ),
        "platform_content_id": (
            target.platform_content_id
        ),
        "published_at": str(
            published_at or ""
        ).strip(),
        "media": [
            media
        ],
        "metadata": (
            bridge_metadata
        ),
    }

    if str(
        title or ""
    ).strip():
        payload[
            "title"
        ] = title

    if str(
        description or ""
    ).strip():
        payload[
            "description"
        ] = description

    if str(
        transcript or ""
    ).strip():
        payload[
            "transcript"
        ] = transcript

    return ExtractedSnapshot(
        source_url=source_url,
        extraction_method=(
            extraction_method
        ),
        observed_at=observed_at,
        payload=payload,
        actor=deepcopy(
            dict(
                actor or {}
            )
        ),
    )


def _text_role_covers_media(
    item: content.UnifiedContentItem,
    *,
    role: str,
    media_component_id: str,
) -> bool:
    if role == "transcript":
        eligible_media = [
            media
            for media
            in item.media_components
            if media.media_kind
            in {
                "video",
                "audio",
            }
        ]

    elif role == "on_screen_text":
        eligible_media = [
            media
            for media
            in item.media_components
            if media.media_kind
            in {
                "image",
                "video",
            }
        ]

    else:
        return False

    matching_text = [
        text_component
        for text_component
        in item.text_components
        if text_component.role
        == role
    ]

    if not matching_text:
        return False

    if (
        len(
            eligible_media
        ) == 1
        and eligible_media[
            0
        ].component_id
        == media_component_id
    ):
        return True

    for text_component in (
        matching_text
    ):
        source_media_id = str(
            (
                text_component.metadata
                or {}
            ).get(
                "source_media_component_id"
            )
            or ""
        ).strip()

        if (
            source_media_id
            == media_component_id
        ):
            return True

    return False


def plan_content_item(
    item: content.UnifiedContentItem,
    *,
    short_video_threshold_seconds: float = (
        DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> ModalityProcessingPlan:
    if (
        short_video_threshold_seconds
        <= 0
    ):
        raise ValueError(
            "Short-video threshold "
            "must be greater than zero."
        )

    semantic_text = tuple(
        component.component_id
        for component
        in item.text_components
    )

    image_visual = tuple(
        media.component_id
        for media
        in item.media_components
        if media.media_kind
        == "image"
    )

    video_frames = tuple(
        media.component_id
        for media
        in item.media_components
        if media.media_kind
        == "video"
    )

    ocr: List[str] = []
    transcription: List[str] = []
    short_videos: List[str] = []
    long_videos: List[str] = []
    unknown_videos: List[str] = []

    for media in (
        item.media_components
    ):
        if (
            media.media_kind
            in {
                "image",
                "video",
            }
            and not (
                _text_role_covers_media(
                    item,
                    role=(
                        "on_screen_text"
                    ),
                    media_component_id=(
                        media.component_id
                    ),
                )
            )
        ):
            ocr.append(
                media.component_id
            )

        supports_transcription = (
            media.media_kind
            == "audio"
            or (
                media.media_kind
                == "video"
                and media.has_audio
                is not False
            )
        )

        if (
            supports_transcription
            and not (
                _text_role_covers_media(
                    item,
                    role="transcript",
                    media_component_id=(
                        media.component_id
                    ),
                )
            )
        ):
            transcription.append(
                media.component_id
            )

        if (
            media.media_kind
            == "video"
        ):
            if (
                media.duration_seconds
                is None
            ):
                unknown_videos.append(
                    media.component_id
                )

            elif (
                media.duration_seconds
                <= (
                    short_video_threshold_seconds
                )
            ):
                short_videos.append(
                    media.component_id
                )

            else:
                long_videos.append(
                    media.component_id
                )

    captions = [
        component.component_id
        for component
        in item.text_components
        if component.role
        == "caption"
    ]

    alignment_pairs = tuple(
        (
            caption_id,
            media.component_id,
        )
        for caption_id
        in captions
        for media
        in item.media_components
    )

    conversation = (
        item.container_kind
        in {
            "thread",
            "comment",
            "reply",
        }
        or item.platform_surface
        in {
            "thread",
            "comment",
            "reply",
        }
    )

    return ModalityProcessingPlan(
        item_id=item.item_id,
        semantic_text_component_ids=(
            semantic_text
        ),
        image_visual_component_ids=(
            image_visual
        ),
        video_frame_component_ids=(
            video_frames
        ),
        ocr_component_ids=tuple(
            ocr
        ),
        transcription_component_ids=(
            tuple(
                transcription
            )
        ),
        short_video_component_ids=(
            tuple(
                short_videos
            )
        ),
        long_video_component_ids=(
            tuple(
                long_videos
            )
        ),
        unknown_duration_video_component_ids=(
            tuple(
                unknown_videos
            )
        ),
        caption_media_alignment_pairs=(
            alignment_pairs
        ),
        conversation_traversal_required=(
            conversation
        ),
    )


def plan_content_bundle(
    bundle: content.UnifiedContentBundle,
    *,
    short_video_threshold_seconds: float = (
        DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> BundleProcessingPlan:
    item_plans = tuple(
        plan_content_item(
            item,
            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )
        for item
        in bundle.items
    )

    dependency_relationship_ids = tuple(
        relationship.relationship_id
        for relationship
        in bundle.relationships
        if relationship
        .relationship_type
        in (
            _DEPENDENCY_RELATIONSHIP_TYPES
        )
    )

    conversation_relationship_ids = (
        tuple(
            relationship
            .relationship_id
            for relationship
            in bundle.relationships
            if relationship
            .relationship_type
            in (
                _CONVERSATION_RELATIONSHIP_TYPES
            )
        )
    )

    conversation_required = (
        bool(
            conversation_relationship_ids
        )
        or any(
            plan
            .conversation_traversal_required
            for plan
            in item_plans
        )
    )

    return BundleProcessingPlan(
        item_plans=item_plans,
        dependency_relationship_ids=(
            dependency_relationship_ids
        ),
        conversation_relationship_ids=(
            conversation_relationship_ids
        ),
        conversation_traversal_required=(
            conversation_required
        ),
        dependency_tracing_required=(
            bool(
                dependency_relationship_ids
            )
        ),
    )


def build_processing_plan(
    value: Union[
        content.UnifiedContentItem,
        content.UnifiedContentBundle,
    ],
    *,
    short_video_threshold_seconds: float = (
        DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> Union[
    ModalityProcessingPlan,
    BundleProcessingPlan,
]:
    if isinstance(
        value,
        content.UnifiedContentItem,
    ):
        return plan_content_item(
            value,
            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )

    if isinstance(
        value,
        content.UnifiedContentBundle,
    ):
        return plan_content_bundle(
            value,
            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )

    raise TypeError(
        "Processing plans require "
        "a UnifiedContentItem or "
        "UnifiedContentBundle."
    )
