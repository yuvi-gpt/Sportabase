import hashlib
import json

from typing import (
    Any,
    Dict,
)


from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_ADJUDICATION_VERSION,
    MULTI_EVALUATOR_FIELDS,
)


REVIEW_QUEUE_PACKET_VERSION = (
    "adjudication-review-queue-v1"
)

REVIEW_QUEUE_ITEM_VERSION = (
    "adjudication-review-item-v1"
)

REVIEW_REASON_PRIORITIES = {
    "contested": 400,
    "blocked_auto_gold_reference": 350,
    "unresolved": 300,
    "auto_silver": 200,
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _content_hash(
    value: Any,
) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "review-queue-content|"
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def review_key_for_item(
    *,
    claim_id: str,
    evidence_id: str,
    field: str,
    adjudication_version: str,
    content_sha256: str,
) -> str:
    normalized = {
        "claim_id": _clean(
            claim_id
        ),
        "evidence_id": _clean(
            evidence_id
        ),
        "field": _clean(
            field
        ).lower(),
        "adjudication_version": (
            _clean(
                adjudication_version
            )
        ),
        "content_sha256": (
            _clean(
                content_sha256
            ).lower()
        ),
    }

    if not all(
        normalized.values()
    ):
        raise ValueError(
            "Review queue identity "
            "is incomplete."
        )

    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        (
            "review-queue-key|"
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def build_adjudication_review_queue(
    *,
    adjudication: Dict[
        str,
        Any,
    ],
    evidence_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        adjudication,
        dict,
    ):
        raise ValueError(
            "Review queue adjudication "
            "must be a dictionary."
        )

    if (
        _clean(
            adjudication.get(
                "version"
            )
        )
        != (
            MULTI_EVALUATOR_ADJUDICATION_VERSION
        )
    ):
        raise ValueError(
            "Review queue requires the "
            "current multi-evaluator "
            "adjudication version."
        )

    claim_id = _clean(
        adjudication.get(
            "claim_id"
        )
    )

    normalized_evidence_id = (
        _clean(
            evidence_id
        )
    )

    if not claim_id:
        raise ValueError(
            "Review queue claim ID "
            "is required."
        )

    if not normalized_evidence_id:
        raise ValueError(
            "Review queue evidence ID "
            "is required."
        )

    fields = adjudication.get(
        "fields"
    )

    evaluators = adjudication.get(
        "evaluators",
        [],
    )

    if not isinstance(
        fields,
        dict,
    ):
        raise ValueError(
            "Review queue adjudication "
            "fields are required."
        )

    if not isinstance(
        evaluators,
        list,
    ):
        raise ValueError(
            "Review queue evaluators "
            "must be a list."
        )

    judgment_to_run = {}

    for evaluator in evaluators:
        if not isinstance(
            evaluator,
            dict,
        ):
            raise ValueError(
                "Review queue evaluator "
                "must be a dictionary."
            )

        run_id = _clean(
            evaluator.get(
                "run_id"
            )
        )

        judgments = evaluator.get(
            "judgments",
            [],
        )

        if not run_id:
            raise ValueError(
                "Review queue evaluator "
                "run ID is required."
            )

        if not isinstance(
            judgments,
            list,
        ):
            raise ValueError(
                "Review queue evaluator "
                "judgments must be a list."
            )

        for judgment in judgments:
            if not isinstance(
                judgment,
                dict,
            ):
                raise ValueError(
                    "Review queue judgment "
                    "must be a dictionary."
                )

            judgment_id = _clean(
                judgment.get(
                    "id"
                )
            )

            if not judgment_id:
                raise ValueError(
                    "Review queue judgment "
                    "ID is required."
                )

            previous = (
                judgment_to_run.get(
                    judgment_id
                )
            )

            if (
                previous is not None
                and previous != run_id
            ):
                raise ValueError(
                    "Review queue judgment "
                    "ownership is ambiguous."
                )

            judgment_to_run[
                judgment_id
            ] = run_id

    items = []

    missing_evaluation_fields = []
    corrected_fields = []
    trusted_auto_gold_fields = []

    for field in (
        MULTI_EVALUATOR_FIELDS
    ):
        result = fields.get(
            field
        )

        if not isinstance(
            result,
            dict,
        ):
            raise ValueError(
                "Review queue field "
                f"{field} is missing."
            )

        correction = result.get(
            "correction",
            {},
        )

        if correction:
            corrected_fields.append(
                field
            )
            continue

        automatic = result.get(
            "automatic"
        )

        judgments = result.get(
            "judgments",
            [],
        )

        if not isinstance(
            automatic,
            dict,
        ):
            raise ValueError(
                "Review queue automatic "
                "adjudication is missing."
            )

        if not isinstance(
            judgments,
            list,
        ):
            raise ValueError(
                "Review queue field "
                "judgments must be a list."
            )

        tier = _clean(
            automatic.get(
                "tier"
            )
        ).lower()

        queue_reason = ""

        if tier == "contested":
            queue_reason = (
                "contested"
            )

        elif tier == "auto_silver":
            queue_reason = (
                "auto_silver"
            )

        elif tier == "unresolved":
            if judgments:
                queue_reason = (
                    "unresolved"
                )

            else:
                missing_evaluation_fields.append(
                    field
                )
                continue

        elif tier == "auto_gold":
            reference_gate = (
                result.get(
                    "reference_gate",
                    {},
                )
            )

            if not isinstance(
                reference_gate,
                dict,
            ):
                raise ValueError(
                    "Review queue auto-gold "
                    "reference gate is invalid."
                )

            if bool(
                reference_gate.get(
                    "training_reference_allowed"
                )
            ):
                trusted_auto_gold_fields.append(
                    field
                )
                continue

            queue_reason = (
                "blocked_auto_gold_reference"
            )

        else:
            raise ValueError(
                "Review queue encountered "
                "an unsupported adjudication tier."
            )

        content_sha256 = (
            _content_hash(
                result
            )
        )

        review_key = (
            review_key_for_item(
                claim_id=claim_id,
                evidence_id=(
                    normalized_evidence_id
                ),
                field=field,
                adjudication_version=(
                    adjudication[
                        "version"
                    ]
                ),
                content_sha256=(
                    content_sha256
                ),
            )
        )

        judgment_ids = sorted(
            {
                _clean(
                    row.get(
                        "id"
                    )
                )
                for row
                in judgments
                if (
                    isinstance(
                        row,
                        dict,
                    )
                    and _clean(
                        row.get(
                            "id"
                        )
                    )
                )
            }
        )

        selected_run_ids = sorted(
            {
                judgment_to_run[
                    judgment_id
                ]
                for judgment_id
                in judgment_ids
                if judgment_id
                in judgment_to_run
            }
        )

        selected_evaluators = [
            evaluator
            for evaluator
            in evaluators
            if _clean(
                evaluator.get(
                    "run_id"
                )
            )
            in selected_run_ids
        ]

        supporting_ids = sorted(
            {
                _clean(
                    value
                )
                for value
                in automatic.get(
                    "supporting_judgment_ids",
                    [],
                )
                if _clean(
                    value
                )
            }
        )

        supporting_families = sorted(
            {
                _clean(
                    value
                ).lower()
                for value
                in automatic.get(
                    "supporting_evaluator_families",
                    [],
                )
                if _clean(
                    value
                )
            }
        )

        conflicting_values = sorted(
            {
                _clean(
                    value
                )
                for value
                in automatic.get(
                    "conflicting_values",
                    [],
                )
                if _clean(
                    value
                )
            }
        )

        items.append(
            {
                "version": (
                    REVIEW_QUEUE_ITEM_VERSION
                ),
                "review_key": (
                    review_key
                ),
                "claim_id": (
                    claim_id
                ),
                "evidence_id": (
                    normalized_evidence_id
                ),
                "field": field,
                "queue_reason": (
                    queue_reason
                ),
                "priority": (
                    REVIEW_REASON_PRIORITIES[
                        queue_reason
                    ]
                ),
                "automatic_tier": (
                    tier
                ),
                "automatic_value": (
                    _clean(
                        automatic.get(
                            "value"
                        )
                    )
                ),
                "conflicting_values": (
                    conflicting_values
                ),
                "judgment_ids": (
                    judgment_ids
                ),
                "supporting_judgment_ids": (
                    supporting_ids
                ),
                "supporting_evaluator_families": (
                    supporting_families
                ),
                "evaluator_run_ids": (
                    selected_run_ids
                ),
                "adjudication_version": (
                    adjudication[
                        "version"
                    ]
                ),
                "content_sha256": (
                    content_sha256
                ),
                "payload": {
                    "field_adjudication": (
                        result
                    ),
                    "evaluator_runs": (
                        selected_evaluators
                    ),
                },
            }
        )

    items = sorted(
        items,
        key=lambda row: (
            -row[
                "priority"
            ],
            row[
                "field"
            ],
            row[
                "review_key"
            ],
        ),
    )

    return {
        "version": (
            REVIEW_QUEUE_PACKET_VERSION
        ),
        "claim_id": (
            claim_id
        ),
        "evidence_id": (
            normalized_evidence_id
        ),
        "items": items,
        "summary": {
            "review_item_count": (
                len(
                    items
                )
            ),
            "queued_fields": sorted(
                row[
                    "field"
                ]
                for row
                in items
            ),
            "missing_evaluation_fields": (
                sorted(
                    missing_evaluation_fields
                )
            ),
            "corrected_fields": (
                sorted(
                    corrected_fields
                )
            ),
            "trusted_auto_gold_fields": (
                sorted(
                    trusted_auto_gold_fields
                )
            ),
        },
        "policy": {
            "contested_fields_require_review": True,
            "blocked_auto_gold_requires_review": True,
            "unresolved_with_judgments_requires_review": True,
            "auto_silver_is_reviewable": True,
            "missing_evaluator_coverage_is_not_human_review": True,
            "trusted_auto_gold_is_not_queued": True,
            "corrected_fields_are_not_requeued": True,
            "review_identity_includes_adjudication_content_hash": True,
            "review_queue_does_not_determine_truth": True,
            "review_queue_does_not_apply_corrections": True,
            "review_queue_does_not_change_live_merit": True,
        },
    }
