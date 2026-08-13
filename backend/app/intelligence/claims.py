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
