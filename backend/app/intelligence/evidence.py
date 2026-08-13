import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def evidence_key_for_record(
    *,
    evidence_type: str,
    subject_key: str,
    observed_at: str,
    canonical_url: str = "",
    reference_key: str = "",
    verification_status: str = "unverified",
    normalize_url=None,
) -> str:
    normalized_evidence_type = str(
        evidence_type or ""
    ).strip().lower()

    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    normalized_verification_status = str(
        verification_status or ""
    ).strip().lower()

    raw_canonical_url = str(
        canonical_url or ""
    ).strip()

    normalized_canonical_url = (
        normalize_url(
            raw_canonical_url
        )
        if raw_canonical_url
        else ""
    )

    normalized_reference_key = str(
        reference_key or ""
    ).strip()

    if not normalized_evidence_type:
        raise ValueError(
            "Evidence type is required."
        )

    if not normalized_subject_key:
        raise ValueError(
            "Evidence subject key is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Evidence observed time is required."
        )

    if not normalized_verification_status:
        raise ValueError(
            "Evidence verification status is required."
        )

    if (
        not normalized_canonical_url
        and not normalized_reference_key
    ):
        raise ValueError(
            "Evidence requires a canonical URL "
            "or reference key."
        )

    identity_payload = json.dumps(
        {
            "evidence_type": (
                normalized_evidence_type
            ),
            "subject_key": (
                normalized_subject_key
            ),
            "canonical_url": (
                normalized_canonical_url
            ),
            "reference_key": (
                normalized_reference_key
            ),
            "verification_status": (
                normalized_verification_status
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

    return hashlib.sha256(
        (
            "evidence-key|"
            + identity_payload
        ).encode("utf-8")
    ).hexdigest()


def record_evidence(
    *,
    evidence_type: str,
    subject_key: str,
    observed_at: str,
    claim_summary: str = "",
    canonical_url: str = "",
    reference_key: str = "",
    verification_status: str = "unverified",
    published_at: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    normalize_url=None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_evidence_type = str(
        evidence_type or ""
    ).strip().lower()

    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    normalized_verification_status = str(
        verification_status or ""
    ).strip().lower()

    raw_canonical_url = str(
        canonical_url or ""
    ).strip()

    normalized_canonical_url = (
        normalize_url(
            raw_canonical_url
        )
        if raw_canonical_url
        else ""
    )

    normalized_reference_key = str(
        reference_key or ""
    ).strip()

    evidence_key = evidence_key_for_record(
        evidence_type=(
            normalized_evidence_type
        ),
        subject_key=(
            normalized_subject_key
        ),
        observed_at=(
            normalized_observed_at
        ),
        canonical_url=(
            normalized_canonical_url
        ),
        reference_key=(
            normalized_reference_key
        ),
        verification_status=(
            normalized_verification_status
        ),
        normalize_url=normalize_url,
    )

    evidence_id = hashlib.sha256(
        (
            "evidence|"
            + evidence_key
        ).encode("utf-8")
    ).hexdigest()

    normalized_claim_summary = str(
        claim_summary or ""
    ).strip()

    normalized_published_at = (
        str(
            published_at or ""
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

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO evidence_records (
              id,
              evidence_key,
              evidence_type,
              subject_key,
              claim_summary,
              canonical_url,
              reference_key,
              verification_status,
              published_at,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?
            )
            ON CONFLICT(evidence_key)
            DO NOTHING
            """,
            (
                evidence_id,
                evidence_key,
                normalized_evidence_type,
                normalized_subject_key,
                normalized_claim_summary,
                normalized_canonical_url,
                normalized_reference_key,
                normalized_verification_status,
                normalized_published_at,
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
            FROM evidence_records
            WHERE evidence_key = ?
            """,
            (
                evidence_key,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Evidence persistence failed."
        )

    return {
        "evidence": dict(row),
        "created": created,
    }


def record_evidence_link(
    *,
    evidence_id: str,
    relationship_type: str = "supports",
    confidence: Optional[float] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    source_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    linked_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_evidence_id = str(
        evidence_id or ""
    ).strip()

    normalized_relationship_type = str(
        relationship_type or ""
    ).strip().lower()

    if not normalized_evidence_id:
        raise ValueError(
            "Evidence link evidence ID is required."
        )

    if not normalized_relationship_type:
        raise ValueError(
            "Evidence link relationship type is required."
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

    normalized_source_id = (
        str(
            source_id or ""
        ).strip()
        or None
    )

    normalized_reporter_id = (
        str(
            reporter_id or ""
        ).strip()
        or None
    )

    targets = {
        "media_item": normalized_media_item_id,
        "story": normalized_story_id,
        "source": normalized_source_id,
        "reporter": normalized_reporter_id,
    }

    active_targets = [
        (
            target_type,
            target_id,
        )
        for (
            target_type,
            target_id,
        ) in targets.items()
        if target_id is not None
    ]

    if len(active_targets) != 1:
        raise ValueError(
            "Evidence link requires exactly one target."
        )

    (
        target_type,
        target_id,
    ) = active_targets[0]

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
                "Evidence link confidence "
                "must be numeric."
            ) from exc

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):
            raise ValueError(
                "Evidence link confidence "
                "must be between 0 and 1."
            )

    normalized_linked_at = (
        str(
            linked_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    identity_payload = json.dumps(
        {
            "evidence_id": (
                normalized_evidence_id
            ),
            "target_type": (
                target_type
            ),
            "target_id": (
                target_id
            ),
            "relationship_type": (
                normalized_relationship_type
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    link_id = hashlib.sha256(
        (
            "evidence-link|"
            + identity_payload
        ).encode("utf-8")
    ).hexdigest()

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO evidence_links (
              id,
              evidence_id,
              media_item_id,
              story_id,
              source_id,
              reporter_id,
              relationship_type,
              confidence,
              linked_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                link_id,
                normalized_evidence_id,
                normalized_media_item_id,
                normalized_story_id,
                normalized_source_id,
                normalized_reporter_id,
                normalized_relationship_type,
                normalized_confidence,
                normalized_linked_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE id = ?
            """,
            (
                link_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Evidence link persistence failed."
        )

    return {
        "link": dict(row),
        "created": created,
    }
