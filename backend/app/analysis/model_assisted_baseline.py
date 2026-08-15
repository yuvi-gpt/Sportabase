import hashlib
import json

from typing import (
    Any,
    Dict,
    List,
)


from app.analysis.adjudication import (
    JUDGMENT_BASIS_CLASSES,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)

from app.analysis.observation_semantics import (
    CLAIM_OBSERVATION_SEMANTICS_VERSION,
)


MODEL_ASSISTED_BASELINE_VERSION = (
    "model-assisted-baseline-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _stable_id(
    value: Any,
    *,
    prefix: str,
) -> str:
    return hashlib.sha256(
        (
            prefix
            + _canonical_json(
                value
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _confidence(
    value: Any,
) -> float | None:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Model-assisted baseline confidence "
            "must be numeric."
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Model-assisted baseline confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Model-assisted baseline confidence "
            "must be between 0 and 1."
        )

    return result


def build_model_assisted_baseline_evaluator_runs(
    *,
    semantic_assessment: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    if not isinstance(
        semantic_assessment,
        dict,
    ):
        raise ValueError(
            "Model-assisted baseline semantic "
            "assessment must be a dictionary."
        )

    if (
        _clean(
            semantic_assessment.get(
                "version"
            )
        )
        != CLAIM_OBSERVATION_SEMANTICS_VERSION
    ):
        raise ValueError(
            "Model-assisted baseline requires "
            "the current observation semantic "
            "version."
        )

    claim_id = _clean(
        semantic_assessment.get(
            "claim_id"
        )
    )

    source_url = _clean(
        semantic_assessment.get(
            "source_url"
        )
    )

    if not claim_id:
        raise ValueError(
            "Model-assisted baseline claim ID "
            "is required."
        )

    if not source_url:
        raise ValueError(
            "Model-assisted baseline source URL "
            "is required."
        )

    derivation = (
        semantic_assessment.get(
            "derivation",
            {},
        )
    )

    if not isinstance(
        derivation,
        dict,
    ):
        raise ValueError(
            "Model-assisted baseline derivation "
            "must be a dictionary."
        )

    if (
        _clean(
            derivation.get(
                "mode"
            )
        ).lower()
        != "model_assisted"
    ):
        raise ValueError(
            "Model-assisted baseline requires "
            "model-assisted derivation."
        )

    if bool(
        derivation.get(
            "self_validating"
        )
    ):
        raise ValueError(
            "Model-assisted baseline cannot be "
            "self-validating."
        )

    if bool(
        derivation.get(
            "training_eligible"
        )
    ):
        raise ValueError(
            "Model-assisted baseline cannot be "
            "training eligible."
        )

    raw_judgments = (
        semantic_assessment.get(
            "field_judgments"
        )
    )

    if not isinstance(
        raw_judgments,
        list,
    ):
        raise ValueError(
            "Model-assisted baseline field "
            "judgments must be a list."
        )

    fields_seen = set()
    judgment_ids = set()
    normalized = []
    unscored_fields = []

    for raw in raw_judgments:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Model-assisted baseline judgment "
                "must be a dictionary."
            )

        field = _clean(
            raw.get(
                "field"
            )
        ).lower()

        if (
            field
            not in MULTI_EVALUATOR_FIELDS
        ):
            raise ValueError(
                "Model-assisted baseline judgment "
                "field is unsupported."
            )

        if field in fields_seen:
            raise ValueError(
                "Model-assisted baseline contains "
                "duplicate field judgments."
            )

        fields_seen.add(
            field
        )

        judgment_id = _clean(
            raw.get(
                "id"
            )
        )

        evaluator_id = _clean(
            raw.get(
                "evaluator_id"
            )
        )

        evaluator_family = _clean(
            raw.get(
                "evaluator_family"
            )
        ).lower()

        value = _clean(
            raw.get(
                "value"
            )
        )

        basis_class = _clean(
            raw.get(
                "basis_class"
            )
        ).lower()

        if not judgment_id:
            raise ValueError(
                "Model-assisted baseline judgment "
                "ID is required."
            )

        if judgment_id in judgment_ids:
            raise ValueError(
                "Model-assisted baseline judgment "
                "IDs must be unique."
            )

        judgment_ids.add(
            judgment_id
        )

        if not evaluator_id:
            raise ValueError(
                "Model-assisted baseline evaluator "
                "ID is required."
            )

        if not evaluator_family:
            raise ValueError(
                "Model-assisted baseline evaluator "
                "family is required."
            )

        if not value:
            raise ValueError(
                "Model-assisted baseline judgment "
                "value is required."
            )

        if (
            basis_class
            not in JUDGMENT_BASIS_CLASSES
        ):
            raise ValueError(
                "Model-assisted baseline judgment "
                "basis class is unsupported."
            )

        if bool(
            raw.get(
                "training_eligible",
                False,
            )
        ):
            raise ValueError(
                "Model-assisted baseline judgment "
                "cannot be training eligible."
            )

        evidence_ids = raw.get(
            "evidence_ids",
            [],
        )

        if not isinstance(
            evidence_ids,
            list,
        ):
            raise ValueError(
                "Model-assisted baseline judgment "
                "evidence IDs must be a list."
            )

        if [
            value
            for value
            in evidence_ids
            if _clean(
                value
            )
        ]:
            raise ValueError(
                "Pre-persistence model-assisted "
                "baseline cannot claim persisted "
                "evidence IDs."
            )

        confidence = _confidence(
            raw.get(
                "confidence"
            )
        )

        if confidence is None:
            unscored_fields.append(
                field
            )
            continue

        normalized.append(
            {
                "id": judgment_id,
                "field": field,
                "value": value,
                "confidence": confidence,
                "evaluator_id": (
                    evaluator_id
                ),
                "evaluator_family": (
                    evaluator_family
                ),
                "basis_class": (
                    basis_class
                ),
                "evidence_ids": [],
                "training_eligible": False,
            }
        )

    expected_fields = set(
        MULTI_EVALUATOR_FIELDS
    )

    if fields_seen != expected_fields:
        missing = sorted(
            expected_fields
            - fields_seen
        )

        extra = sorted(
            fields_seen
            - expected_fields
        )

        raise ValueError(
            "Model-assisted baseline requires "
            "all six semantic field judgments. "
            f"Missing={missing}; extra={extra}"
        )

    grouped = {}

    for judgment in normalized:
        key = (
            judgment[
                "evaluator_id"
            ],
            judgment[
                "evaluator_family"
            ],
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            judgment
        )

    runs: List[
        Dict[str, Any]
    ] = []

    for (
        evaluator_id,
        evaluator_family,
    ), judgments in sorted(
        grouped.items()
    ):
        ordered = sorted(
            judgments,
            key=lambda row: (
                row["field"],
                row["id"],
            ),
        )

        identity = {
            "claim_id": claim_id,
            "source_url": source_url,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "judgment_ids": [
                row["id"]
                for row
                in ordered
            ],
        }

        runs.append(
            {
                "run_id": _stable_id(
                    identity,
                    prefix=(
                        "model-assisted-"
                        "baseline-run|"
                    ),
                ),
                "evaluator_id": (
                    evaluator_id
                ),
                "evaluator_family": (
                    evaluator_family
                ),
                "derivation_mode": (
                    "model_assisted"
                ),
                "judgments": (
                    ordered
                ),
            }
        )

    return {
        "version": (
            MODEL_ASSISTED_BASELINE_VERSION
        ),
        "status": "ready",
        "claim_id": claim_id,
        "source_url": source_url,
        "evaluator_runs": runs,
        "field_count": len(
            MULTI_EVALUATOR_FIELDS
        ),
        "scored_field_count": len(
            normalized
        ),
        "unscored_fields": sorted(
            unscored_fields
        ),
        "policy": {
            "model_output_is_not_truth": True,
            "model_output_is_not_self_validating": True,
            "derivation_remains_model_assisted": True,
            "training_eligible": False,
            "pre_persistence_evidence_ids_forbidden": True,
            "missing_confidence_is_not_fabricated": True,
            "all_six_semantic_fields_must_be_present": True,
            "baseline_does_not_change_live_merit": True,
        },
    }