import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse


def source_domain_for_url(
    url: str,
    *,
    normalize_url,
) -> str:
    canonical_url = normalize_url(
        url
    )

    if not canonical_url:
        return ""

    try:
        parsed = urlparse(
            canonical_url
        )

        hostname = str(
            parsed.hostname or ""
        ).strip().lower()

    except Exception:
        return ""

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def source_key_for_url(
    url: str,
    source_type: str = "publisher",
    *,
    domain_resolver,
) -> str:
    canonical_domain = (
        domain_resolver(
            url
        )
    )

    normalized_source_type = str(
        source_type or ""
    ).strip().lower()

    if not canonical_domain:
        raise ValueError(
            "Source domain is required."
        )

    if not normalized_source_type:
        raise ValueError(
            "Source type is required."
        )

    return (
        normalized_source_type
        + "|"
        + canonical_domain
    )


def source_id_for_url(
    url: str,
    source_type: str = "publisher",
    *,
    key_resolver,
) -> str:
    source_key = key_resolver(
        url,
        source_type,
    )

    return hashlib.sha256(
        (
            "source|"
            + source_key
        ).encode("utf-8")
    ).hexdigest()


def upsert_intelligence_source(
    *,
    url: str,
    display_name: str = "",
    source_type: str = "publisher",
    publication_founded_at: Optional[
        str
    ] = None,
    domain_registered_at: Optional[
        str
    ] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
    domain_resolver,
    connection_factory,
) -> Dict[str, Any]:
    canonical_domain = (
        domain_resolver(
            url
        )
    )

    normalized_source_type = str(
        source_type or ""
    ).strip().lower()

    if not canonical_domain:
        raise ValueError(
            "Source domain is required."
        )

    if not normalized_source_type:
        raise ValueError(
            "Source type is required."
        )

    source_key = (
        normalized_source_type
        + "|"
        + canonical_domain
    )

    source_id = hashlib.sha256(
        (
            "source|"
            + source_key
        ).encode("utf-8")
    ).hexdigest()

    normalized_display_name = str(
        display_name or ""
    ).strip()

    normalized_founded_at = (
        str(
            publication_founded_at or ""
        ).strip()
        or None
    )

    normalized_registered_at = (
        str(
            domain_registered_at or ""
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

    conn = connection_factory()

    try:
        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id,
              source_key,
              display_name,
              source_type,
              canonical_domain,
              publication_founded_at,
              domain_registered_at,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?
            )
            ON CONFLICT(source_key)
            DO UPDATE SET
              display_name = CASE
                WHEN excluded.display_name != ''
                THEN excluded.display_name
                ELSE intelligence_sources.display_name
              END,
              publication_founded_at = COALESCE(
                excluded.publication_founded_at,
                intelligence_sources.publication_founded_at
              ),
              domain_registered_at = COALESCE(
                excluded.domain_registered_at,
                intelligence_sources.domain_registered_at
              ),
              last_seen_at =
                excluded.last_seen_at,
              metadata_json = CASE
                WHEN excluded.metadata_json != '{}'
                THEN excluded.metadata_json
                ELSE intelligence_sources.metadata_json
              END
            """,
            (
                source_id,
                source_key,
                normalized_display_name,
                normalized_source_type,
                canonical_domain,
                normalized_founded_at,
                normalized_registered_at,
                normalized_seen_at,
                normalized_seen_at,
                metadata_json,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM intelligence_sources
            WHERE source_key = ?
            """,
            (
                source_key,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Source persistence failed."
        )

    return dict(row)
