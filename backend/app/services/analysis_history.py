import hashlib
import json
import sqlite3

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


def media_item_id_for_url(
    url: str,
    *,
    normalize_url,
) -> str:
    canonical_url = normalize_url(
        url
    )

    if not canonical_url:
        raise ValueError(
            "Media item URL is required."
        )

    return hashlib.sha256(
        (
            "media|"
            + canonical_url
        ).encode("utf-8")
    ).hexdigest()


def upsert_media_item(
    *,
    url: str,
    mode: str,
    title: str,
    content_hash: str,
    published_at: Optional[str] = None,
    source_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    seen_at: Optional[str] = None,
    normalize_url,
    id_resolver,
    connection_factory,
) -> Dict[str, Any]:
    canonical_url = normalize_url(
        url
    )

    if not canonical_url:
        raise ValueError(
            "Media item URL is required."
        )

    normalized_mode = str(
        mode or ""
    ).strip().lower()

    if not normalized_mode:
        raise ValueError(
            "Media item mode is required."
        )

    normalized_content_hash = str(
        content_hash or ""
    ).strip()

    if not normalized_content_hash:
        raise ValueError(
            "Media item content hash is required."
        )

    normalized_title = str(
        title or ""
    ).strip()

    normalized_published_at = (
        str(
            published_at or ""
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

    media_item_id = (
        id_resolver(
            canonical_url
        )
    )

    conn = connection_factory()

    try:
        conn.execute(
            """
            INSERT INTO media_items (
              id,
              canonical_url,
              mode,
              source_id,
              reporter_id,
              title,
              published_at,
              latest_content_hash,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?
            )
            ON CONFLICT(canonical_url)
            DO UPDATE SET
              mode = excluded.mode,
              source_id = COALESCE(
                excluded.source_id,
                media_items.source_id
              ),
              reporter_id = COALESCE(
                excluded.reporter_id,
                media_items.reporter_id
              ),
              title = CASE
                WHEN excluded.title != ''
                THEN excluded.title
                ELSE media_items.title
              END,
              published_at = COALESCE(
                excluded.published_at,
                media_items.published_at
              ),
              latest_content_hash =
                excluded.latest_content_hash,
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE media_items.metadata_json
              END
            """,
            (
                media_item_id,
                canonical_url,
                normalized_mode,
                normalized_source_id,
                normalized_reporter_id,
                normalized_title,
                normalized_published_at,
                normalized_content_hash,
                normalized_seen_at,
                normalized_seen_at,
                metadata_json,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM media_items
            WHERE canonical_url = ?
            """,
            (
                canonical_url,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Media item persistence failed."
        )

    return dict(row)


def find_analysis_snapshot(
    *,
    media_item_id: str,
    mode: str,
    content_hash: str,
    context_hash: str = "",
    analysis_version: Optional[str] = None,
    scoring_version: Optional[str] = None,
    default_analysis_version: str,
    default_scoring_version: str,
    connection_factory,
) -> Optional[Dict[str, Any]]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    normalized_mode = str(
        mode or ""
    ).strip().lower()

    normalized_content_hash = str(
        content_hash or ""
    ).strip()

    normalized_context_hash = str(
        context_hash or ""
    ).strip()

    normalized_analysis_version = str(
        analysis_version
        or default_analysis_version
    ).strip()

    normalized_scoring_version = str(
        scoring_version
        or default_scoring_version
    ).strip()

    if (
        not normalized_media_item_id
        or not normalized_mode
        or not normalized_content_hash
        or not normalized_analysis_version
        or not normalized_scoring_version
    ):
        return None

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM analysis_snapshots
            WHERE media_item_id = ?
              AND mode = ?
              AND content_hash = ?
              AND context_hash = ?
              AND analysis_version = ?
              AND scoring_version = ?
            LIMIT 1
            """,
            (
                normalized_media_item_id,
                normalized_mode,
                normalized_content_hash,
                normalized_context_hash,
                normalized_analysis_version,
                normalized_scoring_version,
            ),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return dict(row)


def persist_analysis_snapshot(
    *,
    media_item_id: str,
    mode: str,
    content_hash: str,
    response: Dict[str, Any],
    context_hash: str = "",
    analyzed_at: Optional[str] = None,
    analysis_version: Optional[str] = None,
    scoring_version: Optional[str] = None,
    story_id: Optional[str] = None,
    merit_score: Optional[int] = None,
    evidence_score: Optional[int] = None,
    logic_score: Optional[int] = None,
    badge: str = "",
    verdict: str = "",
    article_type: str = "",
    score_components: Optional[
        Dict[str, Any]
    ] = None,
    score_calculation: Optional[
        Dict[str, Any]
    ] = None,
    reasons: Optional[List[str]] = None,
    default_analysis_version: str,
    default_scoring_version: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "Snapshot media item ID is required."
        )

    normalized_mode = str(
        mode or ""
    ).strip().lower()

    if not normalized_mode:
        raise ValueError(
            "Snapshot mode is required."
        )

    normalized_content_hash = str(
        content_hash or ""
    ).strip()

    if not normalized_content_hash:
        raise ValueError(
            "Snapshot content hash is required."
        )

    normalized_context_hash = str(
        context_hash or ""
    ).strip()

    normalized_analysis_version = str(
        analysis_version
        or default_analysis_version
    ).strip()

    if not normalized_analysis_version:
        raise ValueError(
            "Snapshot analysis version is required."
        )

    normalized_scoring_version = str(
        scoring_version
        or default_scoring_version
    ).strip()

    if not normalized_scoring_version:
        raise ValueError(
            "Snapshot scoring version is required."
        )

    normalized_analyzed_at = (
        str(
            analyzed_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    normalized_story_id = (
        str(
            story_id or ""
        ).strip()
        or None
    )

    response_json = json.dumps(
        response or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    components_json = json.dumps(
        score_components or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    calculation_json = json.dumps(
        score_calculation or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    reasons_json = json.dumps(
        reasons or [],
        ensure_ascii=False,
    )

    identity_values = (
        normalized_media_item_id,
        normalized_mode,
        normalized_content_hash,
        normalized_context_hash,
        normalized_analysis_version,
        normalized_scoring_version,
    )

    conn = connection_factory()

    try:
        existing = conn.execute(
            """
            SELECT *
            FROM analysis_snapshots
            WHERE media_item_id = ?
              AND mode = ?
              AND content_hash = ?
              AND context_hash = ?
              AND analysis_version = ?
              AND scoring_version = ?
            LIMIT 1
            """,
            identity_values,
        ).fetchone()

        if existing is not None:
            return {
                "snapshot": dict(existing),
                "created": False,
            }

        try:
            cursor = conn.execute(
                """
                INSERT INTO analysis_snapshots (
                  media_item_id,
                  story_id,
                  analyzed_at,
                  mode,
                  analysis_version,
                  scoring_version,
                  content_hash,
                  context_hash,
                  merit_score,
                  evidence_score,
                  logic_score,
                  badge,
                  verdict,
                  article_type,
                  score_components_json,
                  score_calculation_json,
                  reasons_json,
                  response_json
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?
                )
                """,
                (
                    normalized_media_item_id,
                    normalized_story_id,
                    normalized_analyzed_at,
                    normalized_mode,
                    normalized_analysis_version,
                    normalized_scoring_version,
                    normalized_content_hash,
                    normalized_context_hash,
                    merit_score,
                    evidence_score,
                    logic_score,
                    str(
                        badge or ""
                    ).strip(),
                    str(
                        verdict or ""
                    ).strip(),
                    str(
                        article_type or ""
                    ).strip(),
                    components_json,
                    calculation_json,
                    reasons_json,
                    response_json,
                ),
            )

            snapshot_id = int(
                cursor.lastrowid
            )

            row = conn.execute(
                """
                SELECT *
                FROM analysis_snapshots
                WHERE id = ?
                """,
                (
                    snapshot_id,
                ),
            ).fetchone()

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()

            existing = conn.execute(
                """
                SELECT *
                FROM analysis_snapshots
                WHERE media_item_id = ?
                  AND mode = ?
                  AND content_hash = ?
                  AND context_hash = ?
                  AND analysis_version = ?
                  AND scoring_version = ?
                LIMIT 1
                """,
                identity_values,
            ).fetchone()

            if existing is None:
                raise

            return {
                "snapshot": dict(existing),
                "created": False,
            }

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Snapshot persistence failed."
        )

    return {
        "snapshot": dict(row),
        "created": True,
    }


def record_user_history(
    *,
    client_key: str,
    media_item_id: str,
    snapshot_id: Optional[int] = None,
    analyzed_at: Optional[str] = None,
    connection_factory,
) -> Dict[str, Any]:
    normalized_client_key = str(
        client_key or ""
    ).strip()

    if not normalized_client_key:
        raise ValueError(
            "User history client key is required."
        )

    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "User history media item ID is required."
        )

    normalized_analyzed_at = (
        str(
            analyzed_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    normalized_snapshot_id = None

    if snapshot_id is not None:
        normalized_snapshot_id = int(
            snapshot_id
        )

        if normalized_snapshot_id <= 0:
            raise ValueError(
                "Snapshot ID must be positive."
            )

    conn = connection_factory()

    try:
        media_row = conn.execute(
            """
            SELECT id
            FROM media_items
            WHERE id = ?
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchone()

        if media_row is None:
            raise ValueError(
                "User history media item does not exist."
            )

        if normalized_snapshot_id is not None:
            snapshot_row = conn.execute(
                """
                SELECT id
                FROM analysis_snapshots
                WHERE id = ?
                  AND media_item_id = ?
                """,
                (
                    normalized_snapshot_id,
                    normalized_media_item_id,
                ),
            ).fetchone()

            if snapshot_row is None:
                raise ValueError(
                    "Snapshot does not belong to "
                    "the supplied media item."
                )

        conn.execute(
            """
            INSERT INTO user_history (
              client_key,
              media_item_id,
              first_analyzed_at,
              last_analyzed_at,
              analysis_count,
              last_snapshot_id
            )
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(
              client_key,
              media_item_id
            )
            DO UPDATE SET
              last_analyzed_at =
                excluded.last_analyzed_at,
              analysis_count =
                user_history.analysis_count + 1,
              last_snapshot_id = COALESCE(
                excluded.last_snapshot_id,
                user_history.last_snapshot_id
              )
            """,
            (
                normalized_client_key,
                normalized_media_item_id,
                normalized_analyzed_at,
                normalized_analyzed_at,
                normalized_snapshot_id,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM user_history
            WHERE client_key = ?
              AND media_item_id = ?
            """,
            (
                normalized_client_key,
                normalized_media_item_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "User history persistence failed."
        )

    return dict(row)
