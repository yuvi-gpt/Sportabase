import hashlib
import json

from typing import Any, Dict, Optional


EVIDENCE_CONTEXT_VERSION = "evidence-context-v2"

MEDIA_EVIDENCE_CONTEXT_POLICY_VERSION = (
    "media-evidence-graph-v1"
)


def _evidence_context_confidence(
    value: Any,
    *,
    field_name: str,
) -> Optional[float]:
    if value is None:
        return None

    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be numeric."
        ) from exc

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} must be between 0 and 1."
        )

    return normalized


def _deduplicate_evidence_context_entries(
    entries: list,
    *,
    collection_name: str,
) -> list:
    by_id: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        entry_id = str(
            entry.get("id") or ""
        ).strip()

        if not entry_id:
            raise ValueError(
                f"{collection_name} entry ID is required."
            )

        existing = by_id.get(entry_id)

        if (
            existing is not None
            and existing != entry
        ):
            raise ValueError(
                f"{collection_name} contains conflicting "
                f"rows for ID {entry_id}."
            )

        by_id[entry_id] = entry

    return [
        by_id[entry_id]
        for entry_id in sorted(by_id)
    ]


def _evidence_context_row(
    row: Any,
    *,
    collection_name: str,
) -> Dict[str, Any]:
    try:
        normalized = dict(row)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{collection_name} rows must be mapping-like."
        ) from exc

    return normalized


def build_evidence_context(
    *,
    subject_key: str = "",
    media_item_id: str = "",
    story_id: str = "",
    source_id: str = "",
    reporter_id: str = "",
    source_observations: Optional[list] = None,
    reporter_observations: Optional[list] = None,
    evidence_records: Optional[list] = None,
    evidence_links: Optional[list] = None,
) -> Dict[str, Any]:
    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    normalized_story_id = str(
        story_id or ""
    ).strip()

    normalized_source_id = str(
        source_id or ""
    ).strip()

    normalized_reporter_id = str(
        reporter_id or ""
    ).strip()

    normalized_source_observations = []

    for raw_row in source_observations or []:
        row = _evidence_context_row(
            raw_row,
            collection_name="source_observations",
        )

        normalized_source_observations.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "source_id": str(
                    row.get("source_id") or ""
                ).strip(),
                "media_item_id": str(
                    row.get("media_item_id") or ""
                ).strip(),
                "story_id": str(
                    row.get("story_id") or ""
                ).strip(),
                "subject_key": str(
                    row.get("subject_key") or ""
                ).strip(),
                "observation_type": str(
                    row.get("observation_type") or ""
                ).strip().lower(),
                "status": str(
                    row.get("status") or ""
                ).strip().lower(),
                "provenance_url": str(
                    row.get("provenance_url") or ""
                ).strip(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Source observation confidence"
                        ),
                    )
                ),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

    normalized_reporter_observations = []

    for raw_row in reporter_observations or []:
        row = _evidence_context_row(
            raw_row,
            collection_name="reporter_observations",
        )

        normalized_reporter_observations.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "reporter_id": str(
                    row.get("reporter_id") or ""
                ).strip(),
                "source_id": str(
                    row.get("source_id") or ""
                ).strip(),
                "media_item_id": str(
                    row.get("media_item_id") or ""
                ).strip(),
                "story_id": str(
                    row.get("story_id") or ""
                ).strip(),
                "subject_key": str(
                    row.get("subject_key") or ""
                ).strip(),
                "observation_type": str(
                    row.get("observation_type") or ""
                ).strip().lower(),
                "status": str(
                    row.get("status") or ""
                ).strip().lower(),
                "provenance_url": str(
                    row.get("provenance_url") or ""
                ).strip(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Reporter observation confidence"
                        ),
                    )
                ),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

    normalized_evidence_records = []

    for raw_row in evidence_records or []:
        row = _evidence_context_row(
            raw_row,
            collection_name="evidence_records",
        )

        normalized_evidence_records.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "evidence_key": str(
                    row.get("evidence_key") or ""
                ).strip(),
                "evidence_type": str(
                    row.get("evidence_type") or ""
                ).strip().lower(),
                "subject_key": str(
                    row.get("subject_key") or ""
                ).strip(),
                "canonical_url": str(
                    row.get("canonical_url") or ""
                ).strip(),
                "reference_key": str(
                    row.get("reference_key") or ""
                ).strip(),
                "verification_status": str(
                    row.get("verification_status") or ""
                ).strip().lower(),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

    normalized_evidence_links = []

    for raw_row in evidence_links or []:
        row = _evidence_context_row(
            raw_row,
            collection_name="evidence_links",
        )

        targets = [
            (
                target_type,
                str(
                    row.get(column_name) or ""
                ).strip(),
            )
            for target_type, column_name in (
                ("media_item", "media_item_id"),
                ("story", "story_id"),
                ("source", "source_id"),
                ("reporter", "reporter_id"),
            )
            if str(
                row.get(column_name) or ""
            ).strip()
        ]

        if len(targets) != 1:
            raise ValueError(
                "Evidence context link requires exactly "
                "one target."
            )

        target_type, target_id = targets[0]

        normalized_evidence_links.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "evidence_id": str(
                    row.get("evidence_id") or ""
                ).strip(),
                "target_type": target_type,
                "target_id": target_id,
                "relationship_type": str(
                    row.get("relationship_type") or ""
                ).strip().lower(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Evidence link confidence"
                        ),
                    )
                ),
            }
        )

    return {
        "version": EVIDENCE_CONTEXT_VERSION,
        "scope": {
            "subject_key": normalized_subject_key,
            "media_item_id": normalized_media_item_id,
            "story_id": normalized_story_id,
            "source_id": normalized_source_id,
            "reporter_id": normalized_reporter_id,
        },
        "source_observations": (
            _deduplicate_evidence_context_entries(
                normalized_source_observations,
                collection_name="source_observations",
            )
        ),
        "reporter_observations": (
            _deduplicate_evidence_context_entries(
                normalized_reporter_observations,
                collection_name="reporter_observations",
            )
        ),
        "evidence_records": (
            _deduplicate_evidence_context_entries(
                normalized_evidence_records,
                collection_name="evidence_records",
            )
        ),
        "evidence_links": (
            _deduplicate_evidence_context_entries(
                normalized_evidence_links,
                collection_name="evidence_links",
            )
        ),
    }


def evidence_context_hash(
    context: Dict[str, Any],
) -> str:
    if not isinstance(context, dict):
        raise ValueError(
            "Evidence context must be a dictionary."
        )

    canonical_json = json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "evidence-context|"
            + canonical_json
        ).encode("utf-8")
    ).hexdigest()


def load_evidence_context_for_source(
    *,
    source_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_source_id = str(
        source_id or ""
    ).strip()

    if not normalized_source_id:
        raise ValueError(
            "Evidence context source ID is required."
        )

    conn = connection_factory()

    try:
        source_observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE source_id = ?
            ORDER BY id
            """,
            (
                normalized_source_id,
            ),
        ).fetchall()

        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE source_id = ?
            ORDER BY id
            """,
            (
                normalized_source_id,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE source_id = ?
            ORDER BY id
            """,
            (
                normalized_source_id,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT evidence_records.*
            FROM evidence_records
            INNER JOIN evidence_links
              ON evidence_links.evidence_id =
                 evidence_records.id
            WHERE evidence_links.source_id = ?
            ORDER BY evidence_records.id
            """,
            (
                normalized_source_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_context(
        source_id=normalized_source_id,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )


def load_evidence_context_for_reporter(
    *,
    reporter_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_reporter_id = str(
        reporter_id or ""
    ).strip()

    if not normalized_reporter_id:
        raise ValueError(
            "Evidence context reporter ID is required."
        )

    conn = connection_factory()

    try:
        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE reporter_id = ?
            ORDER BY id
            """,
            (
                normalized_reporter_id,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE reporter_id = ?
            ORDER BY id
            """,
            (
                normalized_reporter_id,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT evidence_records.*
            FROM evidence_records
            INNER JOIN evidence_links
              ON evidence_links.evidence_id =
                 evidence_records.id
            WHERE evidence_links.reporter_id = ?
            ORDER BY evidence_records.id
            """,
            (
                normalized_reporter_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_context(
        reporter_id=normalized_reporter_id,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )


def load_evidence_context_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "Evidence context media item ID is required."
        )

    conn = connection_factory()

    try:
        source_observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE media_item_id = ?
            ORDER BY id
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchall()

        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE media_item_id = ?
            ORDER BY id
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE media_item_id = ?
            ORDER BY id
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT evidence_records.*
            FROM evidence_records
            INNER JOIN evidence_links
              ON evidence_links.evidence_id =
                 evidence_records.id
            WHERE evidence_links.media_item_id = ?
            ORDER BY evidence_records.id
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_context(
        media_item_id=normalized_media_item_id,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )


def load_expanded_evidence_context_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "Expanded evidence context media item "
            "ID is required."
        )

    conn = connection_factory()

    try:
        story_links = conn.execute(
            """
            SELECT
              story_id,
              relationship_type,
              confidence
            FROM story_media_links
            WHERE media_item_id = ?
            ORDER BY story_id
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchall()

        source_observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE media_item_id = ?
               OR story_id IN (
                    SELECT story_id
                    FROM story_media_links
                    WHERE media_item_id = ?
               )
            ORDER BY id
            """,
            (
                normalized_media_item_id,
                normalized_media_item_id,
            ),
        ).fetchall()

        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE media_item_id = ?
               OR story_id IN (
                    SELECT story_id
                    FROM story_media_links
                    WHERE media_item_id = ?
               )
            ORDER BY id
            """,
            (
                normalized_media_item_id,
                normalized_media_item_id,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE media_item_id = ?
               OR story_id IN (
                    SELECT story_id
                    FROM story_media_links
                    WHERE media_item_id = ?
               )
            ORDER BY id
            """,
            (
                normalized_media_item_id,
                normalized_media_item_id,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT DISTINCT
              evidence_records.*
            FROM evidence_records
            INNER JOIN evidence_links
              ON evidence_links.evidence_id =
                 evidence_records.id
            WHERE evidence_links.media_item_id = ?
               OR evidence_links.story_id IN (
                    SELECT story_id
                    FROM story_media_links
                    WHERE media_item_id = ?
               )
            ORDER BY evidence_records.id
            """,
            (
                normalized_media_item_id,
                normalized_media_item_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    context = build_evidence_context(
        media_item_id=normalized_media_item_id,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )

    context["expansion"] = {
        "policy": (
            MEDIA_EVIDENCE_CONTEXT_POLICY_VERSION
        ),
        "story_links": [
            {
                "story_id": str(
                    row["story_id"] or ""
                ).strip(),
                "relationship_type": str(
                    row["relationship_type"] or ""
                ).strip().lower(),
                "confidence": (
                    _evidence_context_confidence(
                        row["confidence"],
                        field_name=(
                            "Story media link confidence"
                        ),
                    )
                ),
            }
            for row in story_links
        ],
    }

    return context


def evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> str:
    context = (
        load_evidence_context_for_media_item(
            media_item_id=media_item_id,
            connection_factory=connection_factory,
        )
    )

    return evidence_context_hash(
        context
    )


def expanded_evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> str:
    context = (
        load_expanded_evidence_context_for_media_item(
            media_item_id=media_item_id,
            connection_factory=connection_factory,
        )
    )

    return evidence_context_hash(
        context
    )


def load_evidence_context_for_story(
    *,
    story_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_story_id = str(
        story_id or ""
    ).strip()

    if not normalized_story_id:
        raise ValueError(
            "Evidence context story ID is required."
        )

    conn = connection_factory()

    try:
        source_observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE story_id = ?
            ORDER BY id
            """,
            (
                normalized_story_id,
            ),
        ).fetchall()

        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE story_id = ?
            ORDER BY id
            """,
            (
                normalized_story_id,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE story_id = ?
            ORDER BY id
            """,
            (
                normalized_story_id,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT evidence_records.*
            FROM evidence_records
            INNER JOIN evidence_links
              ON evidence_links.evidence_id =
                 evidence_records.id
            WHERE evidence_links.story_id = ?
            ORDER BY evidence_records.id
            """,
            (
                normalized_story_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_context(
        story_id=normalized_story_id,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )


def load_evidence_context_for_subject(
    *,
    subject_key: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_subject_key = str(
        subject_key or ""
    ).strip()

    if not normalized_subject_key:
        raise ValueError(
            "Evidence context subject key is required."
        )

    conn = connection_factory()

    try:
        source_observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE subject_key = ?
            ORDER BY id
            """,
            (
                normalized_subject_key,
            ),
        ).fetchall()

        reporter_observations = conn.execute(
            """
            SELECT *
            FROM reporter_observations
            WHERE subject_key = ?
            ORDER BY id
            """,
            (
                normalized_subject_key,
            ),
        ).fetchall()

        evidence_records = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE subject_key = ?
            ORDER BY id
            """,
            (
                normalized_subject_key,
            ),
        ).fetchall()

        evidence_links = conn.execute(
            """
            SELECT evidence_links.*
            FROM evidence_links
            INNER JOIN evidence_records
              ON evidence_records.id =
                 evidence_links.evidence_id
            WHERE evidence_records.subject_key = ?
            ORDER BY evidence_links.id
            """,
            (
                normalized_subject_key,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_context(
        subject_key=normalized_subject_key,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
    )
