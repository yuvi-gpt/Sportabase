import hashlib
import json
import re

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def claim_id_for_canonical_key(
    canonical_key: str,
) -> str:
    normalized_canonical_key = re.sub(
        r"\s+",
        " ",
        str(
            canonical_key or ""
        ).strip(),
    ).lower()

    if not normalized_canonical_key:
        raise ValueError(
            "Claim canonical key is required."
        )

    return hashlib.sha256(
        (
            "claim|"
            + normalized_canonical_key
        ).encode("utf-8")
    ).hexdigest()


def upsert_intelligence_claim(
    *,
    canonical_key: str,
    subject_key: str,
    canonical_text: str = "",
    claim_type: str = "assertion",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    id_resolver,
    connection_factory,
) -> Dict[str, Any]:
    normalized_canonical_key = re.sub(
        r"\s+",
        " ",
        str(
            canonical_key or ""
        ).strip(),
    ).lower()

    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_canonical_text = str(
        canonical_text or ""
    ).strip()

    normalized_claim_type = str(
        claim_type or ""
    ).strip().lower()

    if not normalized_canonical_key:
        raise ValueError(
            "Claim canonical key is required."
        )

    if not normalized_subject_key:
        raise ValueError(
            "Claim subject key is required."
        )

    if not normalized_claim_type:
        raise ValueError(
            "Claim type is required."
        )

    claim_id = id_resolver(
        normalized_canonical_key
    )

    normalized_seen_at = (
        str(
            seen_at or ""
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
        existing = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE canonical_key = ?
            """,
            (
                normalized_canonical_key,
            ),
        ).fetchone()

        if (
            existing is not None
            and str(
                existing["subject_key"]
                or ""
            ).strip()
            != normalized_subject_key
        ):
            raise ValueError(
                "Claim canonical key is already "
                "assigned to a different subject."
            )

        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id,
              canonical_key,
              subject_key,
              canonical_text,
              claim_type,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(canonical_key)
            DO UPDATE SET
              canonical_text = CASE
                WHEN excluded.canonical_text != ''
                THEN excluded.canonical_text
                ELSE intelligence_claims.canonical_text
              END,
              claim_type =
                excluded.claim_type,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE intelligence_claims.metadata_json
              END
            """,
            (
                claim_id,
                normalized_canonical_key,
                normalized_subject_key,
                normalized_canonical_text,
                normalized_claim_type,
                normalized_seen_at,
                normalized_seen_at,
                metadata_json,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE canonical_key = ?
            """,
            (
                normalized_canonical_key,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Claim persistence failed."
        )

    return dict(row)

def _claim_link_identity(
    *,
    claim_id: str,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    source_observation_id: Optional[str] = None,
    reporter_observation_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_claim_id = str(
        claim_id or ""
    ).strip()

    normalized_relationship_type = str(
        relationship_type or ""
    ).strip().lower()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    if not normalized_claim_id:
        raise ValueError(
            "Claim link claim ID is required."
        )

    if not normalized_relationship_type:
        raise ValueError(
            "Claim link relationship type is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Claim link observed_at is required."
        )

    normalized_targets = [
        (
            "source_observation",
            str(source_observation_id or "").strip(),
        ),
        (
            "reporter_observation",
            str(reporter_observation_id or "").strip(),
        ),
        (
            "evidence",
            str(evidence_id or "").strip(),
        ),
    ]

    active_targets = [
        (target_type, target_id)
        for target_type, target_id
        in normalized_targets
        if target_id
    ]

    if len(active_targets) != 1:
        raise ValueError(
            "Claim link requires exactly one target."
        )

    normalized_confidence = None

    if confidence is not None:
        try:
            normalized_confidence = float(
                confidence
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Claim link confidence must be numeric."
            ) from exc

        if not 0.0 <= normalized_confidence <= 1.0:
            raise ValueError(
                "Claim link confidence must be between 0 and 1."
            )

    target_type, target_id = active_targets[0]

    return {
        "claim_id": normalized_claim_id,
        "target_type": target_type,
        "target_id": target_id,
        "relationship_type": (
            normalized_relationship_type
        ),
        "confidence": normalized_confidence,
        "observed_at": normalized_observed_at,
    }


def claim_link_id_for_record(
    *,
    claim_id: str,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    source_observation_id: Optional[str] = None,
    reporter_observation_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> str:
    identity = _claim_link_identity(
        claim_id=claim_id,
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
    )

    canonical_json = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "claim-link|"
            + canonical_json
        ).encode("utf-8")
    ).hexdigest()


def record_claim_link(
    *,
    claim_id: str,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    source_observation_id: Optional[str] = None,
    reporter_observation_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    recorded_at: Optional[str] = None,
    connection_factory,
) -> Dict[str, Any]:
    identity = _claim_link_identity(
        claim_id=claim_id,
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
    )

    link_id = claim_link_id_for_record(
        claim_id=identity["claim_id"],
        relationship_type=identity[
            "relationship_type"
        ],
        observed_at=identity["observed_at"],
        confidence=identity["confidence"],
        source_observation_id=(
            identity["target_id"]
            if identity["target_type"]
            == "source_observation"
            else None
        ),
        reporter_observation_id=(
            identity["target_id"]
            if identity["target_type"]
            == "reporter_observation"
            else None
        ),
        evidence_id=(
            identity["target_id"]
            if identity["target_type"]
            == "evidence"
            else None
        ),
    )

    normalized_recorded_at = (
        str(recorded_at or "").strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    source_target = (
        identity["target_id"]
        if identity["target_type"]
        == "source_observation"
        else None
    )

    reporter_target = (
        identity["target_id"]
        if identity["target_type"]
        == "reporter_observation"
        else None
    )

    evidence_target = (
        identity["target_id"]
        if identity["target_type"]
        == "evidence"
        else None
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO claim_links (
              id,
              claim_id,
              source_observation_id,
              reporter_observation_id,
              evidence_id,
              relationship_type,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                link_id,
                identity["claim_id"],
                source_target,
                reporter_target,
                evidence_target,
                identity["relationship_type"],
                identity["confidence"],
                identity["observed_at"],
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = cursor.rowcount == 1

        row = conn.execute(
            """
            SELECT *
            FROM claim_links
            WHERE id = ?
            """,
            (link_id,),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Claim link persistence failed."
        )

    return {
        "link": dict(row),
        "created": created,
    }
