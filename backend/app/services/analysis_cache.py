import hashlib
import json
import time

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    Optional,
)


def analysis_content_hash(
    content: str,
    *,
    clean_html,
) -> str:
    normalized = " ".join(
        clean_html(
            content
        ).split()
    ).strip()

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


def make_analysis_cache_key(
    mode: str,
    url: str,
    content: str,
    variant: str = "",
    context_hash: str = "",
    *,
    analysis_version: str,
    scoring_version: str,
    normalize_url,
    content_hash_resolver,
) -> str:
    normalized_mode = str(
        mode or ""
    ).strip().lower()

    normalized_context_hash = str(
        context_hash or ""
    ).strip()

    key_parts = [
        str(
            analysis_version
            or ""
        ),
        normalized_mode,
        normalize_url(
            url
        ),
        content_hash_resolver(
            content
        ),
        str(
            variant or ""
        ).strip().lower(),
    ]

    if normalized_mode == "article":
        key_parts.insert(
            1,
            str(
                scoring_version
                or ""
            ),
        )

        key_parts.append(
            normalized_context_hash
        )

    raw_key = "|".join(
        key_parts
    )

    return hashlib.sha256(
        raw_key.encode(
            "utf-8"
        )
    ).hexdigest()


def cache_ttl_for_analysis(
    mode: str,
    article_type: str = "",
    *,
    analysis_cache_ttl_seconds: int,
    live_cache_ttl_seconds: int,
) -> int:
    normalized_mode = str(
        mode or ""
    ).strip().lower()

    normalized_type = str(
        article_type or ""
    ).strip().lower()

    if (
        normalized_mode == "article"
        and normalized_type
        in {
            "live_commentary",
            "live_updates",
        }
    ):
        return max(
            0,
            int(
                live_cache_ttl_seconds
            ),
        )

    return max(
        0,
        int(
            analysis_cache_ttl_seconds
        ),
    )


def get_cached_analysis(
    cache_key: str,
    *,
    connection_factory,
    now_epoch: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if now_epoch is None:
        current_epoch = int(
            time.time()
        )
    else:
        current_epoch = int(
            now_epoch
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT
              response_json,
              article_type,
              created_at,
              expires_at
            FROM analysis_cache
            WHERE cache_key = ?
            """,
            (
                cache_key,
            ),
        ).fetchone()

        if row is None:
            return None

        if (
            int(
                row["expires_at"]
            )
            <= current_epoch
        ):
            conn.execute(
                """
                DELETE FROM analysis_cache
                WHERE cache_key = ?
                """,
                (
                    cache_key,
                ),
            )

            conn.commit()

            return None

        payload = json.loads(
            row[
                "response_json"
            ]
        )

        if not isinstance(
            payload,
            dict,
        ):
            return None

        debug = payload.get(
            "debug"
        )

        if not isinstance(
            debug,
            dict,
        ):
            debug = {}

        debug["cache"] = {
            "hit": True,
            "article_type": (
                row[
                    "article_type"
                ]
                or ""
            ),
            "created_at": (
                row[
                    "created_at"
                ]
            ),
            "expires_at": int(
                row[
                    "expires_at"
                ]
            ),
        }

        payload[
            "debug"
        ] = debug

        return payload

    except Exception as error:
        print(
            "analysis cache read failed:",
            type(
                error
            ).__name__,
            str(
                error
            )[:160],
        )

        return None

    finally:
        conn.close()


def set_cached_analysis(
    cache_key: str,
    mode: str,
    request_url: str,
    content: str,
    response_payload: Any,
    article_type: str = "",
    *,
    connection_factory,
    ttl_resolver,
    normalize_url,
    content_hash_resolver,
    analysis_version: str,
    now_epoch: Optional[int] = None,
    created_at: Optional[str] = None,
) -> None:
    ttl_seconds = int(
        ttl_resolver(
            mode,
            article_type,
        )
    )

    if ttl_seconds <= 0:
        return

    if hasattr(
        response_payload,
        "model_dump",
    ):
        payload = (
            response_payload
            .model_dump()
        )
    else:
        payload = (
            response_payload
        )

    if not isinstance(
        payload,
        dict,
    ):
        return

    if now_epoch is None:
        current_epoch = int(
            time.time()
        )
    else:
        current_epoch = int(
            now_epoch
        )

    normalized_created_at = (
        str(
            created_at
            or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    expires_at = (
        current_epoch
        + ttl_seconds
    )

    conn = connection_factory()

    try:
        conn.execute(
            """
            DELETE FROM analysis_cache
            WHERE expires_at <= ?
            """,
            (
                current_epoch,
            ),
        )

        conn.execute(
            """
            INSERT INTO analysis_cache (
              cache_key,
              mode,
              request_url,
              content_hash,
              analysis_version,
              response_json,
              article_type,
              created_at,
              expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key)
            DO UPDATE SET
              response_json =
                excluded.response_json,
              article_type =
                excluded.article_type,
              created_at =
                excluded.created_at,
              expires_at =
                excluded.expires_at
            """,
            (
                cache_key,
                str(
                    mode
                ),
                normalize_url(
                    request_url
                ),
                content_hash_resolver(
                    content
                ),
                str(
                    analysis_version
                    or ""
                ),
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
                str(
                    article_type
                    or ""
                ),
                normalized_created_at,
                expires_at,
            ),
        )

        conn.commit()

    except Exception as error:
        print(
            "analysis cache write failed:",
            type(
                error
            ).__name__,
            str(
                error
            )[:160],
        )

    finally:
        conn.close()
