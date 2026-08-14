import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional


CORPUS_RECORD_VERSION = (
    "corpus-record-v1"
)

CORPUS_RECORD_LINK_VERSION = (
    "corpus-record-link-v1"
)


CORPUS_ORIGIN_TYPES = {
    "remote_api",
    "remote_bulk",
    "external_dataset",
    "sportabase_live",
    "manual_curated",
}


CORPUS_DATA_FAMILIES = {
    "reporting_evidence",
    "structured_sports_data",
    "benchmark",
}


CORPUS_MEASUREMENT_KINDS = {
    "raw",
    "direct",
    "derived",
    "estimated",
    "modelled",
    "mixed",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _lower_key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _json_payload(
    value: Any,
    *,
    label: str,
) -> str:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{label} must be a dictionary."
        )

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{label} must be JSON serializable."
        ) from exc


def record_corpus_record(
    *,
    origin_type: str,
    data_family: str,
    dataset_name: str,
    external_record_id: str,
    adapter_version: str,
    payload: Dict[str, Any],
    sport_key: str = "",
    competition_key: str = "",
    season_key: str = "",
    event_type: str = "",
    granularity: str = "record",
    measurement_kind: str = "raw",
    canonical_url: str = "",
    published_at: Optional[str] = None,
    occurred_at: Optional[str] = None,
    ingested_at: Optional[str] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    normalize_url=None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_origin = _lower_key(
        origin_type
    )

    normalized_family = _lower_key(
        data_family
    )

    normalized_dataset = _lower_key(
        dataset_name
    )

    normalized_external_id = _clean(
        external_record_id
    )

    normalized_adapter = _lower_key(
        adapter_version
    )

    normalized_sport = _lower_key(
        sport_key
    )

    normalized_competition = _lower_key(
        competition_key
    )

    normalized_season = _lower_key(
        season_key
    )

    normalized_event_type = _lower_key(
        event_type
    )

    normalized_granularity = (
        _lower_key(
            granularity
        )
    )

    normalized_measurement = (
        _lower_key(
            measurement_kind
        )
    )

    if (
        normalized_origin
        not in CORPUS_ORIGIN_TYPES
    ):
        raise ValueError(
            "Unsupported corpus origin type."
        )

    if (
        normalized_family
        not in CORPUS_DATA_FAMILIES
    ):
        raise ValueError(
            "Unsupported corpus data family."
        )

    if not normalized_dataset:
        raise ValueError(
            "Corpus dataset name is required."
        )

    if not normalized_external_id:
        raise ValueError(
            "Corpus external record ID "
            "is required."
        )

    if not normalized_adapter:
        raise ValueError(
            "Corpus adapter version is required."
        )

    if not normalized_granularity:
        raise ValueError(
            "Corpus granularity is required."
        )

    if (
        normalized_measurement
        not in CORPUS_MEASUREMENT_KINDS
    ):
        raise ValueError(
            "Unsupported corpus "
            "measurement kind."
        )

    if (
        normalized_family
        == "structured_sports_data"
        and not normalized_sport
    ):
        raise ValueError(
            "Structured sports data requires "
            "a sport key."
        )

    if connection_factory is None:
        raise ValueError(
            "Corpus connection factory "
            "is required."
        )

    serialized_payload = (
        _json_payload(
            payload,
            label=(
                "Corpus record payload"
            ),
        )
    )

    serialized_metadata = (
        _json_payload(
            metadata or {},
            label="Corpus metadata",
        )
    )

    payload_hash = hashlib.sha256(
        serialized_payload.encode(
            "utf-8"
        )
    ).hexdigest()

    raw_url = _clean(
        canonical_url
    )

    if (
        raw_url
        and normalize_url is not None
    ):
        normalized_url = _clean(
            normalize_url(
                raw_url
            )
        )
    else:
        normalized_url = raw_url

    normalized_published_at = (
        _clean(
            published_at
        )
        or None
    )

    normalized_occurred_at = (
        _clean(
            occurred_at
        )
        or None
    )

    normalized_ingested_at = (
        _clean(
            ingested_at
        )
        or _utc_now()
    )

    identity_payload = json.dumps(
        {
            "origin_type": (
                normalized_origin
            ),
            "data_family": (
                normalized_family
            ),
            "dataset_name": (
                normalized_dataset
            ),
            "external_record_id": (
                normalized_external_id
            ),
            "adapter_version": (
                normalized_adapter
            ),
            "sport_key": (
                normalized_sport
            ),
            "competition_key": (
                normalized_competition
            ),
            "season_key": (
                normalized_season
            ),
            "event_type": (
                normalized_event_type
            ),
            "granularity": (
                normalized_granularity
            ),
            "measurement_kind": (
                normalized_measurement
            ),
            "canonical_url": (
                normalized_url
            ),
            "published_at": (
                normalized_published_at
                or ""
            ),
            "occurred_at": (
                normalized_occurred_at
                or ""
            ),
            "payload_hash": (
                payload_hash
            ),
        },
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    record_id = hashlib.sha256(
        (
            "corpus-record|"
            + identity_payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO corpus_records (
              id,
              origin_type,
              data_family,
              dataset_name,
              external_record_id,
              adapter_version,
              sport_key,
              competition_key,
              season_key,
              event_type,
              granularity,
              measurement_kind,
              canonical_url,
              published_at,
              occurred_at,
              payload_hash,
              payload_json,
              ingested_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                record_id,
                normalized_origin,
                normalized_family,
                normalized_dataset,
                normalized_external_id,
                normalized_adapter,
                normalized_sport,
                normalized_competition,
                normalized_season,
                normalized_event_type,
                normalized_granularity,
                normalized_measurement,
                normalized_url,
                normalized_published_at,
                normalized_occurred_at,
                payload_hash,
                serialized_payload,
                normalized_ingested_at,
                serialized_metadata,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM corpus_records
            WHERE id = ?
            """,
            (
                record_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Corpus record persistence failed."
        )

    return {
        "version": (
            CORPUS_RECORD_VERSION
        ),
        "record": dict(
            row
        ),
        "payload_hash": (
            payload_hash
        ),
        "created": (
            created
        ),
    }


def list_corpus_record_revisions(
    *,
    origin_type: str,
    dataset_name: str,
    external_record_id: str,
    connection_factory,
):
    normalized_origin = _lower_key(
        origin_type
    )

    normalized_dataset = _lower_key(
        dataset_name
    )

    normalized_external_id = _clean(
        external_record_id
    )

    conn = connection_factory()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM corpus_records
            WHERE origin_type = ?
              AND dataset_name = ?
              AND external_record_id = ?
            ORDER BY
              ingested_at ASC,
              id ASC
            """,
            (
                normalized_origin,
                normalized_dataset,
                normalized_external_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return [
        dict(
            row
        )
        for row in rows
    ]


def record_corpus_record_link(
    *,
    corpus_record_id: str,
    story_id: Optional[str] = None,
    media_item_id: Optional[str] = None,
    claim_id: Optional[str] = None,
    relationship_type: str = "materializes",
    linked_at: Optional[str] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_record_id = _clean(
        corpus_record_id
    )

    normalized_story_id = (
        _clean(
            story_id
        )
        or None
    )

    normalized_media_id = (
        _clean(
            media_item_id
        )
        or None
    )

    normalized_claim_id = (
        _clean(
            claim_id
        )
        or None
    )

    normalized_relationship = _lower_key(
        relationship_type
    )

    if not normalized_record_id:
        raise ValueError(
            "Corpus record link record ID "
            "is required."
        )

    targets = [
        value
        for value in (
            normalized_story_id,
            normalized_media_id,
            normalized_claim_id,
        )
        if value is not None
    ]

    if len(
        targets
    ) != 1:
        raise ValueError(
            "Corpus record link requires "
            "exactly one target."
        )

    if not normalized_relationship:
        raise ValueError(
            "Corpus record link relationship "
            "type is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Corpus connection factory "
            "is required."
        )

    if normalized_story_id:
        target_type = "story"
        target_id = (
            normalized_story_id
        )
    elif normalized_media_id:
        target_type = "media_item"
        target_id = (
            normalized_media_id
        )
    else:
        target_type = "claim"
        target_id = (
            normalized_claim_id
        )

    identity_payload = json.dumps(
        {
            "corpus_record_id": (
                normalized_record_id
            ),
            "target_type": (
                target_type
            ),
            "target_id": (
                target_id
            ),
            "relationship_type": (
                normalized_relationship
            ),
        },
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    link_id = hashlib.sha256(
        (
            "corpus-record-link|"
            + identity_payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    normalized_linked_at = (
        _clean(
            linked_at
        )
        or _utc_now()
    )

    serialized_metadata = (
        _json_payload(
            metadata or {},
            label=(
                "Corpus link metadata"
            ),
        )
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO corpus_record_links (
              id,
              corpus_record_id,
              story_id,
              media_item_id,
              claim_id,
              relationship_type,
              linked_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                link_id,
                normalized_record_id,
                normalized_story_id,
                normalized_media_id,
                normalized_claim_id,
                normalized_relationship,
                normalized_linked_at,
                serialized_metadata,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM corpus_record_links
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
            "Corpus record link "
            "persistence failed."
        )

    return {
        "version": (
            CORPUS_RECORD_LINK_VERSION
        ),
        "link": dict(
            row
        ),
        "created": (
            created
        ),
    }
