import hashlib
import json

from typing import Any, Dict, Optional

from app.intelligence.context import (
    _deduplicate_evidence_context_entries,
    _evidence_context_confidence,
    _evidence_context_row,
)

from app.intelligence.dependencies import (
    _observation_dependency_identity,
)


EVIDENCE_ANALYSIS_BUNDLE_VERSION = (
    "evidence-analysis-v2"
)


def _evidence_analysis_text(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def build_evidence_analysis_bundle(
    *,
    media_item_id: str,
    story_links: Optional[list] = None,
    source_observations: Optional[list] = None,
    reporter_observations: Optional[list] = None,
    evidence_records: Optional[list] = None,
    evidence_links: Optional[list] = None,
    observation_dependencies: Optional[list] = None,
) -> Dict[str, Any]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "Evidence analysis media item ID "
            "is required."
        )

    normalized_story_links = {}
    normalized_source_observations = []
    normalized_reporter_observations = []
    normalized_evidence_records = []
    normalized_evidence_links = []
    normalized_observation_dependencies = []

    for raw_row in story_links or []:
        row = _evidence_context_row(
            raw_row,
            collection_name="story_links",
        )

        story_id = str(
            row.get("story_id") or ""
        ).strip()

        if not story_id:
            raise ValueError(
                "Evidence analysis story link "
                "requires a story ID."
            )

        normalized_row = {
            "story_id": story_id,
            "relationship_type": str(
                row.get("relationship_type") or ""
            ).strip().lower(),
            "confidence": (
                _evidence_context_confidence(
                    row.get("confidence"),
                    field_name=(
                        "Story media link confidence"
                    ),
                )
            ),
        }

        existing = normalized_story_links.get(
            story_id
        )

        if (
            existing is not None
            and existing != normalized_row
        ):
            raise ValueError(
                "Evidence analysis contains "
                "conflicting story links."
            )

        normalized_story_links[
            story_id
        ] = normalized_row

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
                "claim_summary": (
                    _evidence_analysis_text(
                        row.get("claim_summary")
                    )
                ),
                "provenance_url": str(
                    row.get("provenance_url") or ""
                ).strip(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Source observation "
                            "confidence"
                        ),
                    )
                ),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

    for raw_row in reporter_observations or []:
        row = _evidence_context_row(
            raw_row,
            collection_name=(
                "reporter_observations"
            ),
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
                "claim_summary": (
                    _evidence_analysis_text(
                        row.get("claim_summary")
                    )
                ),
                "provenance_url": str(
                    row.get("provenance_url") or ""
                ).strip(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Reporter observation "
                            "confidence"
                        ),
                    )
                ),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

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
                "claim_summary": (
                    _evidence_analysis_text(
                        row.get("claim_summary")
                    )
                ),
                "canonical_url": str(
                    row.get("canonical_url") or ""
                ).strip(),
                "reference_key": str(
                    row.get("reference_key") or ""
                ).strip(),
                "verification_status": str(
                    row.get(
                        "verification_status"
                    ) or ""
                ).strip().lower(),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

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
                (
                    "media_item",
                    "media_item_id",
                ),
                (
                    "story",
                    "story_id",
                ),
                (
                    "source",
                    "source_id",
                ),
                (
                    "reporter",
                    "reporter_id",
                ),
            )
            if str(
                row.get(column_name) or ""
            ).strip()
        ]

        if len(targets) != 1:
            raise ValueError(
                "Evidence analysis link requires "
                "exactly one target."
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
                    row.get(
                        "relationship_type"
                    ) or ""
                ).strip().lower(),
                "confidence": (
                    _evidence_context_confidence(
                        row.get("confidence"),
                        field_name=(
                            "Evidence link "
                            "confidence"
                        ),
                    )
                ),
            }
        )

    for raw_row in observation_dependencies or []:
        row = _evidence_context_row(
            raw_row,
            collection_name=(
                "observation_dependencies"
            ),
        )

        identity = (
            _observation_dependency_identity(
                relationship_type=row.get(
                    "relationship_type"
                ),
                observed_at=row.get(
                    "observed_at"
                ),
                confidence=row.get(
                    "confidence"
                ),
                downstream_source_observation_id=(
                    row.get(
                        "downstream_source_observation_id"
                    )
                ),
                downstream_reporter_observation_id=(
                    row.get(
                        "downstream_reporter_observation_id"
                    )
                ),
                upstream_source_observation_id=(
                    row.get(
                        "upstream_source_observation_id"
                    )
                ),
                upstream_reporter_observation_id=(
                    row.get(
                        "upstream_reporter_observation_id"
                    )
                ),
                upstream_source_id=row.get(
                    "upstream_source_id"
                ),
                upstream_reporter_id=row.get(
                    "upstream_reporter_id"
                ),
            )
        )

        normalized_observation_dependencies.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "downstream_type": (
                    identity[
                        "downstream_type"
                    ]
                ),
                "downstream_id": (
                    identity[
                        "downstream_id"
                    ]
                ),
                "upstream_type": (
                    identity[
                        "upstream_type"
                    ]
                ),
                "upstream_id": (
                    identity[
                        "upstream_id"
                    ]
                ),
                "relationship_type": (
                    identity[
                        "relationship_type"
                    ]
                ),
                "confidence": (
                    identity["confidence"]
                ),
                "observed_at": (
                    identity["observed_at"]
                ),
            }
        )


    return {
        "version": (
            EVIDENCE_ANALYSIS_BUNDLE_VERSION
        ),
        "scope": {
            "media_item_id": (
                normalized_media_item_id
            ),
        },
        "story_links": [
            normalized_story_links[key]
            for key in sorted(
                normalized_story_links
            )
        ],
        "source_observations": (
            _deduplicate_evidence_context_entries(
                normalized_source_observations,
                collection_name=(
                    "source_observations"
                ),
            )
        ),
        "reporter_observations": (
            _deduplicate_evidence_context_entries(
                normalized_reporter_observations,
                collection_name=(
                    "reporter_observations"
                ),
            )
        ),
        "evidence_records": (
            _deduplicate_evidence_context_entries(
                normalized_evidence_records,
                collection_name=(
                    "evidence_records"
                ),
            )
        ),
        "evidence_links": (
            _deduplicate_evidence_context_entries(
                normalized_evidence_links,
                collection_name=(
                    "evidence_links"
                ),
            )
        ),
        "observation_dependencies": (
            _deduplicate_evidence_context_entries(
                normalized_observation_dependencies,
                collection_name=(
                    "observation_dependencies"
                ),
            )
        ),
    }


def evidence_analysis_bundle_hash(
    bundle: Dict[str, Any],
) -> str:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Evidence analysis bundle must "
            "be a dictionary."
        )

    canonical_json = json.dumps(
        bundle,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "evidence-analysis|"
            + canonical_json
        ).encode("utf-8")
    ).hexdigest()


def load_evidence_analysis_bundle_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    if not normalized_media_item_id:
        raise ValueError(
            "Evidence analysis media item ID "
            "is required."
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

        observation_dependencies = conn.execute(
            """
            SELECT *
            FROM observation_dependencies
            WHERE downstream_source_observation_id
                  IN (
                    SELECT id
                    FROM source_observations
                    WHERE media_item_id = ?
                       OR story_id IN (
                            SELECT story_id
                            FROM story_media_links
                            WHERE media_item_id = ?
                       )
                  )
               OR downstream_reporter_observation_id
                  IN (
                    SELECT id
                    FROM reporter_observations
                    WHERE media_item_id = ?
                       OR story_id IN (
                            SELECT story_id
                            FROM story_media_links
                            WHERE media_item_id = ?
                       )
                  )
            ORDER BY id
            """,
            (
                normalized_media_item_id,
                normalized_media_item_id,
                normalized_media_item_id,
                normalized_media_item_id,
            ),
        ).fetchall()

    finally:
        conn.close()

    return build_evidence_analysis_bundle(
        media_item_id=normalized_media_item_id,
        story_links=story_links,
        source_observations=source_observations,
        reporter_observations=reporter_observations,
        evidence_records=evidence_records,
        evidence_links=evidence_links,
        observation_dependencies=(
            observation_dependencies
        ),
    )


def load_evidence_analysis_state_for_media_item(
    *,
    media_item_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    bundle = (
        load_evidence_analysis_bundle_for_media_item(
            media_item_id=media_item_id,
            connection_factory=connection_factory,
        )
    )

    return {
        "bundle": bundle,
        "context_hash": (
            evidence_analysis_bundle_hash(
                bundle
            )
        ),
    }
