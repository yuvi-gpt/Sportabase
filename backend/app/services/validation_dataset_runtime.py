import json

from typing import (
    Any,
    Dict,
)


from app.analysis.trusted_validation import (
    build_trusted_validation_bundle,
)


PERSISTED_VALIDATION_DATASET_RUNTIME_VERSION = (
    "persisted-validation-dataset-runtime-v1"
)


def _decode_revision(
    value: Any,
):
    try:
        parsed = json.loads(
            str(
                value or ""
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Persisted validation revision "
            "contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise RuntimeError(
            "Persisted validation revision "
            "must be a JSON object."
        )

    return parsed


def build_persisted_validation_bundle(
    *,
    connection_factory,
) -> Dict[
    str,
    Any,
]:
    if connection_factory is None:
        raise ValueError(
            "Persisted validation connection "
            "factory is required."
        )

    conn = connection_factory()

    try:
        revision_rows = conn.execute(
            """
            SELECT
                id,
                claim_id,
                as_of,
                recorded_at,
                revision_json
            FROM adjudication_state_revisions
            ORDER BY
                claim_id ASC,
                as_of ASC,
                recorded_at ASC,
                id ASC
            """
        ).fetchall()

        verified_rows = conn.execute(
            """
            SELECT id
            FROM evidence_records
            WHERE
                LOWER(
                    TRIM(
                        verification_status
                    )
                ) = 'verified'
            ORDER BY id ASC
            """
        ).fetchall()

    finally:
        conn.close()

    revisions = [
        _decode_revision(
            row[
                "revision_json"
            ]
        )
        for row
        in revision_rows
    ]

    verified_evidence_ids = [
        str(
            row[
                "id"
            ]
        ).strip()
        for row
        in verified_rows
        if str(
            row[
                "id"
            ]
        ).strip()
    ]

    bundle = (
        build_trusted_validation_bundle(
            revisions=revisions,
            verified_evidence_ids=(
                verified_evidence_ids
            ),
        )
    )

    return {
        "version": (
            PERSISTED_VALIDATION_DATASET_RUNTIME_VERSION
        ),
        "bundle": bundle,
        "summary": {
            "persisted_revision_count": len(
                revisions
            ),
            "verified_evidence_count": len(
                verified_evidence_ids
            ),
            **bundle[
                "summary"
            ],
        },
        "policy": {
            "database_read_only_by_contract": True,
            "only_verified_evidence_can_validate": True,
            "revision_history_is_source_of_predictions": True,
            "no_manual_case_construction": True,
            "does_not_persist": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
            "human_review_required": False,
        },
    }
