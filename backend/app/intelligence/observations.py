import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def record_source_observation(
    *,
    source_id: str,
    subject_key: str,
    observation_type: str,
    observed_at: str,
    status: str = "unresolved",
    claim_summary: str = "",
    provenance_url: str = "",
    confidence: Optional[float] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    normalize_url=None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_source_id = str(
        source_id or ""
    ).strip()

    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_observation_type = str(
        observation_type or ""
    ).strip().lower()

    normalized_status = str(
        status or ""
    ).strip().lower()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    if not normalized_source_id:
        raise ValueError(
            "Source observation source ID is required."
        )

    if not normalized_subject_key:
        raise ValueError(
            "Source observation subject key is required."
        )

    if not normalized_observation_type:
        raise ValueError(
            "Source observation type is required."
        )

    if not normalized_status:
        raise ValueError(
            "Source observation status is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Source observation observed time is required."
        )

    normalized_claim_summary = str(
        claim_summary or ""
    ).strip()

    raw_provenance_url = str(
        provenance_url or ""
    ).strip()

    normalized_provenance_url = (
        normalize_url(
            raw_provenance_url
        )
        if raw_provenance_url
        else ""
    )

    normalized_media_item_id = (
        str(
            media_item_id or ""
        ).strip()
        or None
    )

    normalized_story_id = (
        str(
            story_id or ""
        ).strip()
        or None
    )

    normalized_recorded_at = (
        str(
            recorded_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    normalized_confidence = None

    if confidence is not None:
        try:
            normalized_confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Source observation confidence "
                "must be numeric."
            ) from exc

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):
            raise ValueError(
                "Source observation confidence "
                "must be between 0 and 1."
            )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    identity_payload = json.dumps(
        {
            "source_id": normalized_source_id,
            "media_item_id": (
                normalized_media_item_id
                or ""
            ),
            "story_id": (
                normalized_story_id
                or ""
            ),
            "subject_key": (
                normalized_subject_key
            ),
            "observation_type": (
                normalized_observation_type
            ),
            "status": normalized_status,
            "provenance_url": (
                normalized_provenance_url
            ),
            "confidence": (
                normalized_confidence
            ),
            "observed_at": (
                normalized_observed_at
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    observation_id = hashlib.sha256(
        (
            "source-observation|"
            + identity_payload
        ).encode("utf-8")
    ).hexdigest()

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO source_observations (
              id,
              source_id,
              media_item_id,
              story_id,
              subject_key,
              observation_type,
              status,
              claim_summary,
              provenance_url,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                observation_id,
                normalized_source_id,
                normalized_media_item_id,
                normalized_story_id,
                normalized_subject_key,
                normalized_observation_type,
                normalized_status,
                normalized_claim_summary,
                normalized_provenance_url,
                normalized_confidence,
                normalized_observed_at,
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE id = ?
            """,
            (
                observation_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Source observation persistence failed."
        )

    return {
        "observation": dict(row),
        "created": created,
    }


def record_reporter_observation(
    *,
    reporter_id: str,
    subject_key: str,
    observation_type: str,
    observed_at: str,
    status: str = "unresolved",
    claim_summary: str = "",
    provenance_url: str = "",
    confidence: Optional[float] = None,
    source_id: Optional[str] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    normalize_url=None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_reporter_id = str(
        reporter_id or ""
    ).strip()

    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_observation_type = str(
        observation_type or ""
    ).strip().lower()

    normalized_status = str(
        status or ""
    ).strip().lower()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    if not normalized_reporter_id:
        raise ValueError(
            "Reporter observation reporter ID is required."
        )

    if not normalized_subject_key:
        raise ValueError(
            "Reporter observation subject key is required."
        )

    if not normalized_observation_type:
        raise ValueError(
            "Reporter observation type is required."
        )

    if not normalized_status:
        raise ValueError(
            "Reporter observation status is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Reporter observation observed time is required."
        )

    normalized_claim_summary = str(
        claim_summary or ""
    ).strip()

    raw_provenance_url = str(
        provenance_url or ""
    ).strip()

    normalized_provenance_url = (
        normalize_url(
            raw_provenance_url
        )
        if raw_provenance_url
        else ""
    )

    normalized_source_id = (
        str(
            source_id or ""
        ).strip()
        or None
    )

    normalized_media_item_id = (
        str(
            media_item_id or ""
        ).strip()
        or None
    )

    normalized_story_id = (
        str(
            story_id or ""
        ).strip()
        or None
    )

    normalized_recorded_at = (
        str(
            recorded_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    normalized_confidence = None

    if confidence is not None:
        try:
            normalized_confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Reporter observation confidence "
                "must be numeric."
            ) from exc

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):
            raise ValueError(
                "Reporter observation confidence "
                "must be between 0 and 1."
            )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    identity_payload = json.dumps(
        {
            "reporter_id": (
                normalized_reporter_id
            ),
            "source_id": (
                normalized_source_id
                or ""
            ),
            "media_item_id": (
                normalized_media_item_id
                or ""
            ),
            "story_id": (
                normalized_story_id
                or ""
            ),
            "subject_key": (
                normalized_subject_key
            ),
            "observation_type": (
                normalized_observation_type
            ),
            "status": (
                normalized_status
            ),
            "provenance_url": (
                normalized_provenance_url
            ),
            "confidence": (
                normalized_confidence
            ),
            "observed_at": (
                normalized_observed_at
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    observation_id = hashlib.sha256(
        (
            "reporter-observation|"
            + identity_payload
        ).encode("utf-8")
    ).hexdigest()

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO reporter_observations (
              id,
              reporter_id,
              source_id,
              media_item_id,
              story_id,
              subject_key,
              observation_type,
              status,
              claim_summary,
              provenance_url,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                observation_id,
                normalized_reporter_id,
                normalized_source_id,
                normalized_media_item_id,
                normalized_story_id,
                normalized_subject_key,
                normalized_observation_type,
                normalized_status,
                normalized_claim_summary,
                normalized_provenance_url,
                normalized_confidence,
                normalized_observed_at,
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE id = ?
            """,
            (
                observation_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Reporter observation persistence failed."
        )

    return {
        "observation": dict(row),
        "created": created,
    }
