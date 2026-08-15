import json

from typing import (
    Any,
    Dict,
)


from app.intelligence.reviews import (
    list_review_queue_items,
)


REVIEWER_DATA_VERSION = (
    "reviewer-data-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _json_object(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    text = str(
        value or "{}"
    ).strip()

    try:
        parsed = json.loads(
            text
        )

    except Exception as exc:
        raise RuntimeError(
            f"{label} contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise RuntimeError(
            f"{label} must contain a JSON object."
        )

    return parsed


def _review_payload(
    value: Any,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        return {}

    nested = value.get(
        "payload"
    )

    if isinstance(
        nested,
        dict,
    ):
        return nested

    if (
        "field_adjudication"
        in value
        or "evaluator_runs"
        in value
    ):
        return value

    return {}


def _summary(
    row: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    payload = _review_payload(
        row.get(
            "payload",
            {},
        )
    )

    field_adjudication = (
        payload.get(
            "field_adjudication",
            {},
        )
    )

    judgments = []

    if isinstance(
        field_adjudication,
        dict,
    ):
        raw_judgments = (
            field_adjudication.get(
                "judgments",
                [],
            )
        )

        if isinstance(
            raw_judgments,
            list,
        ):
            judgments = (
                raw_judgments
            )

    return {
        "id": _clean(
            row.get(
                "id"
            )
        ),
        "claim_id": _clean(
            row.get(
                "claim_id"
            )
        ),
        "evidence_id": _clean(
            row.get(
                "evidence_id"
            )
        ),
        "field": _clean(
            row.get(
                "field"
            )
        ),
        "queue_reason": _clean(
            row.get(
                "queue_reason"
            )
        ),
        "priority": (
            row.get(
                "priority"
            )
        ),
        "automatic_tier": _clean(
            row.get(
                "automatic_tier"
            )
        ),
        "automatic_value": _clean(
            row.get(
                "automatic_value"
            )
        ),
        "status": _clean(
            row.get(
                "status"
            )
        ),
        "judgment_count": len(
            judgments
        ),
        "created_at": _clean(
            row.get(
                "created_at"
            )
        ),
        "updated_at": _clean(
            row.get(
                "updated_at"
            )
        ),
        "reviewed_by": _clean(
            row.get(
                "reviewed_by"
            )
        ),
        "reviewed_at": _clean(
            row.get(
                "reviewed_at"
            )
        ),
        "resolution_value": _clean(
            row.get(
                "resolution_value"
            )
        ),
    }


def list_reviewer_items(
    *,
    status: str = "pending",
    claim_id: str = "",
    limit: int = 100,
    connection_factory=None,
) -> Dict[str, Any]:
    rows = list_review_queue_items(
        status=status,
        claim_id=claim_id,
        limit=limit,
        connection_factory=(
            connection_factory
        ),
    )

    items = [
        _summary(
            row
        )
        for row
        in rows
    ]

    return {
        "version": (
            REVIEWER_DATA_VERSION
        ),
        "status": (
            status
        ),
        "claim_id": (
            _clean(
                claim_id
            )
        ),
        "count": len(
            items
        ),
        "items": items,
        "policy": {
            "reviewer_list_is_read_only": True,
            "reviewer_list_does_not_change_live_merit": True,
        },
    }


def get_reviewer_item(
    *,
    review_id: str,
    connection_factory=None,
) -> Dict[str, Any]:
    normalized_review_id = (
        _clean(
            review_id
        )
    )

    if not normalized_review_id:
        raise ValueError(
            "Reviewer item ID is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Reviewer item lookup "
            "requires database access."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT
              rq.*,

              c.canonical_text
                AS claim_canonical_text,
              c.subject_key
                AS claim_subject_key,
              c.claim_type
                AS claim_type,

              e.evidence_type
                AS evidence_type,
              e.claim_summary
                AS evidence_claim_summary,
              e.canonical_url
                AS evidence_canonical_url,
              e.reference_key
                AS evidence_reference_key,
              e.verification_status
                AS evidence_verification_status,
              e.published_at
                AS evidence_published_at,
              e.observed_at
                AS evidence_observed_at,
              e.metadata_json
                AS evidence_metadata_json

            FROM review_queue_items rq

            JOIN intelligence_claims c
              ON c.id = rq.claim_id

            JOIN evidence_records e
              ON e.id = rq.evidence_id

            WHERE rq.id = ?
            """,
            (
                normalized_review_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Reviewer item does not exist."
        )

    raw = dict(
        row
    )

    stored_item = _json_object(
        raw.get(
            "payload_json",
            "{}",
        ),
        label=(
            "Review queue payload"
        ),
    )

    payload = _review_payload(
        stored_item
    )

    evidence_metadata = (
        _json_object(
            raw.get(
                "evidence_metadata_json",
                "{}",
            ),
            label=(
                "Evidence metadata"
            ),
        )
    )

    field_adjudication = (
        payload.get(
            "field_adjudication",
            {},
        )
    )

    if not isinstance(
        field_adjudication,
        dict,
    ):
        field_adjudication = {}

    evaluator_runs = (
        payload.get(
            "evaluator_runs",
            [],
        )
    )

    if not isinstance(
        evaluator_runs,
        list,
    ):
        evaluator_runs = []

    raw_judgments = (
        field_adjudication.get(
            "judgments",
            [],
        )
    )

    if not isinstance(
        raw_judgments,
        list,
    ):
        raw_judgments = []

    votes = []

    for judgment in raw_judgments:
        if not isinstance(
            judgment,
            dict,
        ):
            continue

        votes.append(
            {
                "id": _clean(
                    judgment.get(
                        "id"
                    )
                ),
                "value": _clean(
                    judgment.get(
                        "value"
                    )
                ),
                "confidence": (
                    judgment.get(
                        "confidence"
                    )
                ),
                "evaluator_id": (
                    _clean(
                        judgment.get(
                            "evaluator_id"
                        )
                    )
                ),
                "evaluator_family": (
                    _clean(
                        judgment.get(
                            "evaluator_family"
                        )
                    )
                ),
                "basis_class": (
                    _clean(
                        judgment.get(
                            "basis_class"
                        )
                    )
                ),
                "evidence_ids": (
                    judgment.get(
                        "evidence_ids",
                        [],
                    )
                    if isinstance(
                        judgment.get(
                            "evidence_ids",
                            [],
                        ),
                        list,
                    )
                    else []
                ),
            }
        )

    votes = sorted(
        votes,
        key=lambda vote: (
            vote[
                "evaluator_family"
            ],
            vote[
                "evaluator_id"
            ],
            vote[
                "id"
            ],
        ),
    )

    suggested_values = set()

    automatic_value = _clean(
        raw.get(
            "automatic_value"
        )
    )

    if automatic_value:
        suggested_values.add(
            automatic_value
        )

    automatic = (
        field_adjudication.get(
            "automatic",
            {},
        )
    )

    if isinstance(
        automatic,
        dict,
    ):
        conflicting_values = (
            automatic.get(
                "conflicting_values",
                [],
            )
        )

        if isinstance(
            conflicting_values,
            list,
        ):
            for value in (
                conflicting_values
            ):
                cleaned = _clean(
                    value
                )

                if cleaned:
                    suggested_values.add(
                        cleaned
                    )

    for vote in votes:
        if vote[
            "value"
        ]:
            suggested_values.add(
                vote[
                    "value"
                ]
            )

    review = {
        key: value
        for key, value
        in raw.items()
        if key
        not in {
            "payload_json",
            "claim_canonical_text",
            "claim_subject_key",
            "claim_type",
            "evidence_type",
            "evidence_claim_summary",
            "evidence_canonical_url",
            "evidence_reference_key",
            "evidence_verification_status",
            "evidence_published_at",
            "evidence_observed_at",
            "evidence_metadata_json",
        }
    }

    review[
        "payload"
    ] = payload

    return {
        "version": (
            REVIEWER_DATA_VERSION
        ),
        "review": review,
        "claim": {
            "id": _clean(
                raw.get(
                    "claim_id"
                )
            ),
            "canonical_text": (
                _clean(
                    raw.get(
                        "claim_canonical_text"
                    )
                )
            ),
            "subject_key": (
                _clean(
                    raw.get(
                        "claim_subject_key"
                    )
                )
            ),
            "claim_type": (
                _clean(
                    raw.get(
                        "claim_type"
                    )
                )
            ),
        },
        "evidence": {
            "id": _clean(
                raw.get(
                    "evidence_id"
                )
            ),
            "evidence_type": (
                _clean(
                    raw.get(
                        "evidence_type"
                    )
                )
            ),
            "claim_summary": (
                _clean(
                    raw.get(
                        "evidence_claim_summary"
                    )
                )
            ),
            "canonical_url": (
                _clean(
                    raw.get(
                        "evidence_canonical_url"
                    )
                )
            ),
            "reference_key": (
                _clean(
                    raw.get(
                        "evidence_reference_key"
                    )
                )
            ),
            "verification_status": (
                _clean(
                    raw.get(
                        "evidence_verification_status"
                    )
                )
            ),
            "published_at": (
                _clean(
                    raw.get(
                        "evidence_published_at"
                    )
                )
            ),
            "observed_at": (
                _clean(
                    raw.get(
                        "evidence_observed_at"
                    )
                )
            ),
            "metadata": (
                evidence_metadata
            ),
        },
        "field_adjudication": (
            field_adjudication
        ),
        "evaluator_runs": (
            evaluator_runs
        ),
        "votes": votes,
        "suggested_values": (
            sorted(
                suggested_values
            )
        ),
        "policy": {
            "reviewer_detail_is_read_only": True,
            "automatic_history_is_preserved": True,
            "reviewer_detail_does_not_verify_evidence": True,
            "reviewer_detail_does_not_change_live_merit": True,
        },
    }
