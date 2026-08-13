import hashlib
import json
import re

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def story_id_for_canonical_key(
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
            "Story canonical key is required."
        )

    return hashlib.sha256(
        (
            "story|"
            + normalized_canonical_key
        ).encode("utf-8")
    ).hexdigest()


def upsert_intelligence_story(
    *,
    canonical_key: str,
    canonical_title: str = "",
    status: str = "developing",
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

    if not normalized_canonical_key:
        raise ValueError(
            "Story canonical key is required."
        )

    normalized_status = str(
        status or ""
    ).strip().lower()

    if not normalized_status:
        raise ValueError(
            "Story status is required."
        )

    story_id = id_resolver(
        normalized_canonical_key
    )

    normalized_canonical_title = str(
        canonical_title or ""
    ).strip()

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
        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id,
              canonical_key,
              canonical_title,
              status,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(canonical_key)
            DO UPDATE SET
              canonical_title = CASE
                WHEN excluded.canonical_title != ''
                THEN excluded.canonical_title
                ELSE intelligence_stories.canonical_title
              END,
              status = excluded.status,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE intelligence_stories.metadata_json
              END
            """,
            (
                story_id,
                normalized_canonical_key,
                normalized_canonical_title,
                normalized_status,
                normalized_seen_at,
                normalized_seen_at,
                metadata_json,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM intelligence_stories
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
            "Story persistence failed."
        )

    return dict(row)
