import hashlib
import json
import re

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def reporter_id_for_identity_key(
    identity_key: str,
) -> str:
    normalized_identity_key = re.sub(
        r"\s+",
        " ",
        str(
            identity_key or ""
        ).strip(),
    ).lower()

    if not normalized_identity_key:
        raise ValueError(
            "Reporter identity key is required."
        )

    return hashlib.sha256(
        (
            "reporter|"
            + normalized_identity_key
        ).encode("utf-8")
    ).hexdigest()


def upsert_intelligence_reporter(
    *,
    identity_key: str,
    display_name: str = "",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    id_resolver,
    connection_factory,
) -> Dict[str, Any]:
    normalized_identity_key = re.sub(
        r"\s+",
        " ",
        str(
            identity_key or ""
        ).strip(),
    ).lower()

    if not normalized_identity_key:
        raise ValueError(
            "Reporter identity key is required."
        )

    reporter_id = id_resolver(
        normalized_identity_key
    )

    normalized_display_name = str(
        display_name or ""
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
            INSERT INTO intelligence_reporters (
              id,
              identity_key,
              display_name,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(identity_key)
            DO UPDATE SET
              display_name = CASE
                WHEN excluded.display_name != ''
                THEN excluded.display_name
                ELSE intelligence_reporters.display_name
              END,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE intelligence_reporters.metadata_json
              END
            """,
            (
                reporter_id,
                normalized_identity_key,
                normalized_display_name,
                normalized_seen_at,
                normalized_seen_at,
                metadata_json,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM intelligence_reporters
            WHERE identity_key = ?
            """,
            (
                normalized_identity_key,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Reporter persistence failed."
        )

    return dict(row)
