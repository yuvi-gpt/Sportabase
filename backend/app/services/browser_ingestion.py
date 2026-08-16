from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Mapping,
)

from app.models import content
from app.services import (
    multimodal_extraction,
)


BROWSER_CAPTURE_VERSION = (
    "browser-capture-v1"
)

BROWSER_INGESTION_VERSION = (
    "browser-ingestion-v1"
)


_ALLOWED_CAPTURE_FIELDS = {
    "version",
    "source_url",
    "observed_at",
    "extraction_method",
    "payload",
    "actor",
}


@dataclass(frozen=True)
class BrowserIngestionResult:
    item: (
        content
        .UnifiedContentItem
    )

    processing_plan: (
        multimodal_extraction
        .ModalityProcessingPlan
    )


def _mapping_copy(
    value: Any,
    *,
    field_name: str,
) -> Dict[
    str,
    Any,
]:
    if value is None:
        return {}

    if not isinstance(
        value,
        Mapping,
    ):
        raise ValueError(
            field_name
            + " must be an object."
        )

    return dict(
        value
    )


def extracted_snapshot_from_browser_capture(
    raw_capture: Mapping[
        str,
        Any,
    ],
) -> (
    multimodal_extraction
    .ExtractedSnapshot
):
    if not isinstance(
        raw_capture,
        Mapping,
    ):
        raise ValueError(
            "Browser capture must "
            "be an object."
        )

    capture = dict(
        raw_capture
    )

    unknown = (
        set(
            capture.keys()
        )
        - _ALLOWED_CAPTURE_FIELDS
    )

    if unknown:
        raise ValueError(
            "Unsupported browser capture "
            "fields: "
            + ", ".join(
                sorted(
                    unknown
                )
            )
        )

    version = str(
        capture.get(
            "version"
        )
        or ""
    ).strip()

    if (
        version
        != BROWSER_CAPTURE_VERSION
    ):
        raise ValueError(
            "Unsupported browser capture "
            "version: "
            + (
                version
                or "<missing>"
            )
        )

    source_url = str(
        capture.get(
            "source_url"
        )
        or ""
    ).strip()

    if not source_url:
        raise ValueError(
            "Browser capture requires "
            "source_url."
        )

    observed_at = str(
        capture.get(
            "observed_at"
        )
        or ""
    ).strip()

    if not observed_at:
        raise ValueError(
            "Browser capture requires "
            "observed_at."
        )

    extraction_method = str(
        capture.get(
            "extraction_method"
        )
        or ""
    ).strip()

    if not (
        extraction_method
        .startswith(
            "browser_"
        )
    ):
        raise ValueError(
            "Browser capture extraction_method "
            "must start with browser_."
        )

    payload = _mapping_copy(
        capture.get(
            "payload"
        ),
        field_name=(
            "Browser capture payload"
        ),
    )

    if not payload:
        raise ValueError(
            "Browser capture payload "
            "cannot be empty."
        )

    actor = _mapping_copy(
        capture.get(
            "actor"
        ),
        field_name=(
            "Browser capture actor"
        ),
    )

    return (
        multimodal_extraction
        .ExtractedSnapshot(
            source_url=(
                source_url
            ),

            extraction_method=(
                extraction_method
            ),

            observed_at=(
                observed_at
            ),

            payload=(
                payload
            ),

            actor=(
                actor
            ),
        )
    )


def normalize_browser_capture(
    raw_capture: Mapping[
        str,
        Any,
    ],
) -> (
    content
    .UnifiedContentItem
):
    snapshot = (
        extracted_snapshot_from_browser_capture(
            raw_capture
        )
    )

    return (
        multimodal_extraction
        .normalize_extracted_snapshot(
            snapshot
        )
    )


def ingest_browser_capture(
    raw_capture: Mapping[
        str,
        Any,
    ],
    *,
    short_video_threshold_seconds: float = (
        multimodal_extraction
        .DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> BrowserIngestionResult:
    item = (
        normalize_browser_capture(
            raw_capture
        )
    )

    plan = (
        multimodal_extraction
        .plan_content_item(
            item,

            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )
    )

    return (
        BrowserIngestionResult(
            item=item,

            processing_plan=(
                plan
            ),
        )
    )
