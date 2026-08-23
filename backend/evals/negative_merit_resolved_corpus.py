from __future__ import annotations

import hashlib
import json

from datetime import datetime
from pathlib import Path
from typing import Any, Dict


from app.analysis.negative_merit_calibration_dataset import (
    NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION,
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES,
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION,
    NEGATIVE_MERIT_CALIBRATION_ORIGIN,
    build_negative_merit_calibration_dataset,
)


NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION = (
    "negative-merit-resolved-corpus-v1"
)

NEGATIVE_MERIT_RESOLVED_CORPUS_REPORT_VERSION = (
    "negative-merit-resolved-corpus-report-v1"
)

NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES = frozenset(
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES
)


def _clean(value: Any) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(value: Any) -> str:
    return _clean(
        value
    ).lower()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _timestamp(
    value: Any,
    *,
    label: str,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    candidate = text

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )

    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed.isoformat()


def corpus_template() -> Dict[str, Any]:
    return {
        "version": (
            NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION
        ),
        "corpus_id": "",
        "frozen_at": "",
        "cases": [],
        "policy": {
            "real_world_cases_only": True,
            "synthetic_cases_forbidden_in_frozen_corpus": True,
            "immutable_source_captures_required": True,
            "verified_resolution_required_for_resolved_labels": True,
            "no_provider_calls_during_offline_evaluation": True,
            "production_database_not_required": True,
            "numeric_negative_penalty_authorized": False,
            "live_negative_merit_authorized": False,
        },
    }


def _validate_manifest(
    corpus: Any,
) -> Dict[str, Any]:
    if not isinstance(
        corpus,
        dict,
    ):
        raise ValueError(
            "Negative Merit resolved corpus "
            "must be a dictionary."
        )

    if (
        _clean(
            corpus.get(
                "version"
            )
        )
        != NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION
    ):
        raise ValueError(
            "Unsupported Negative Merit "
            "resolved corpus version."
        )

    corpus_id = _clean(
        corpus.get(
            "corpus_id"
        )
    )

    if not corpus_id:
        raise ValueError(
            "Negative Merit resolved corpus "
            "ID is required."
        )

    frozen_at = _timestamp(
        corpus.get(
            "frozen_at"
        ),
        label=(
            "Negative Merit corpus frozen_at"
        ),
    )

    cases = corpus.get(
        "cases"
    )

    if (
        not isinstance(
            cases,
            list,
        )
        or not cases
    ):
        raise ValueError(
            "Negative Merit resolved corpus "
            "requires at least one case."
        )

    seen_ids = set()

    for case in cases:
        if not isinstance(
            case,
            dict,
        ):
            raise ValueError(
                "Negative Merit corpus case "
                "must be a dictionary."
            )

        if (
            _clean(
                case.get(
                    "version"
                )
            )
            != NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
        ):
            raise ValueError(
                "Negative Merit corpus case "
                "uses an unsupported observation version."
            )

        if (
            _key(
                case.get(
                    "origin"
                )
            )
            != NEGATIVE_MERIT_CALIBRATION_ORIGIN
        ):
            raise ValueError(
                "Negative Merit corpus case "
                "must be marked real_world."
            )

        case_id = _clean(
            case.get(
                "id"
            )
        )

        if not case_id:
            raise ValueError(
                "Negative Merit corpus case "
                "ID is required."
            )

        if case_id in seen_ids:
            raise ValueError(
                "Negative Merit corpus case "
                "IDs must be unique."
            )

        seen_ids.add(
            case_id
        )

        observation_class = _key(
            case.get(
                "observation_class"
            )
        )

        if (
            observation_class
            not in NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES
        ):
            raise ValueError(
                "Negative Merit corpus case "
                "has unsupported observation class."
            )

    return {
        "corpus_id": corpus_id,
        "frozen_at": frozen_at,
        "cases": cases,
    }


def evaluate_negative_merit_resolved_corpus(
    *,
    corpus: Dict[str, Any],
    dataset_builder=(
        build_negative_merit_calibration_dataset
    ),
) -> Dict[str, Any]:
    manifest = _validate_manifest(
        corpus
    )

    cases = manifest[
        "cases"
    ]

    dataset = dataset_builder(
        cases=cases
    )

    if not isinstance(
        dataset,
        dict,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "dataset builder returned invalid data."
        )

    if (
        _clean(
            dataset.get(
                "version"
            )
        )
        != NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION
    ):
        raise ValueError(
            "Negative Merit corpus received "
            "an unsupported calibration dataset."
        )

    if (
        dataset.get(
            "status"
        )
        != "measurement_ready"
    ):
        raise ValueError(
            "Negative Merit calibration "
            "dataset is not measurement-ready."
        )

    observations = dataset.get(
        "observations"
    )

    if not isinstance(
        observations,
        list,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "observations are missing."
        )

    if len(
        observations
    ) != len(
        cases
    ):
        raise ValueError(
            "Negative Merit corpus case count "
            "does not match calibration output."
        )

    class_counts = {
        observation_class: 0
        for observation_class
        in sorted(
            NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES
        )
    }

    resolved_count = 0

    for observation in observations:
        if not isinstance(
            observation,
            dict,
        ):
            raise ValueError(
                "Negative Merit calibration "
                "observation is invalid."
            )

        observation_class = _key(
            observation.get(
                "observation_class"
            )
        )

        if observation_class not in class_counts:
            raise ValueError(
                "Negative Merit calibration "
                "produced an unsupported class."
            )

        class_counts[
            observation_class
        ] += 1

        if (
            _key(
                observation.get(
                    "resolution_status"
                )
            )
            == "resolved_against_claim"
        ):
            resolved_count += 1

    missing_required_classes = sorted(
        observation_class
        for observation_class
        in NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES
        if class_counts[
            observation_class
        ]
        == 0
    )

    calibration = dataset.get(
        "calibration"
    )

    if not isinstance(
        calibration,
        dict,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "state is missing."
        )

    if (
        calibration.get(
            "numeric_penalty_authorized"
        )
        is not False
        or calibration.get(
            "live_negative_merit_authorized"
        )
        is not False
        or calibration.get(
            "penalty_weight_selected"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit corpus evaluation "
            "cannot authorize scoring changes."
        )

    dataset_resolved_count = calibration.get(
        "resolved_against_claim_case_count"
    )

    if (
        not isinstance(
            dataset_resolved_count,
            int,
        )
        or isinstance(
            dataset_resolved_count,
            bool,
        )
        or dataset_resolved_count
        != resolved_count
    ):
        raise ValueError(
            "Negative Merit corpus resolved "
            "case count is inconsistent."
        )

    labels_available = calibration.get(
        "canonical_outcome_labels_available"
    )

    if not isinstance(
        labels_available,
        bool,
    ):
        raise ValueError(
            "Negative Merit corpus resolved "
            "label availability must be boolean."
        )

    if (
        labels_available
        != (
            resolved_count > 0
        )
    ):
        raise ValueError(
            "Negative Merit corpus resolved "
            "label availability is inconsistent."
        )

    complete = bool(
        not missing_required_classes
        and resolved_count > 0
    )

    corpus_identity = {
        "version": (
            NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION
        ),
        "corpus_id": (
            manifest[
                "corpus_id"
            ]
        ),
        "frozen_at": (
            manifest[
                "frozen_at"
            ]
        ),
        "cases": cases,
    }

    corpus_digest = _digest(
        corpus_identity
    )

    report_core = {
        "version": (
            NEGATIVE_MERIT_RESOLVED_CORPUS_REPORT_VERSION
        ),
        "status": (
            "pass"
            if complete
            else "incomplete"
        ),
        "corpus": {
            "version": (
                NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION
            ),
            "corpus_id": (
                manifest[
                    "corpus_id"
                ]
            ),
            "frozen_at": (
                manifest[
                    "frozen_at"
                ]
            ),
            "corpus_digest": (
                corpus_digest
            ),
            "case_count": len(
                cases
            ),
            "resolved_against_claim_case_count": (
                resolved_count
            ),
            "class_counts": (
                class_counts
            ),
            "missing_required_classes": (
                missing_required_classes
            ),
        },
        "dataset": dataset,
        "calibration": {
            "corpus_complete_for_measurement": (
                complete
            ),
            "penalty_weight_selected": False,
            "numeric_penalty_authorized": False,
            "live_negative_merit_authorized": False,
            "next_gate": (
                "collect_sufficient_real_world_"
                "resolved_and_control_cases"
            ),
        },
        "policy": {
            "all_required_populations_must_be_present": True,
            "resolved_cases_require_verified_canonical_outcome": True,
            "unresolved_two_gate_cases_remain_separate": True,
            "authority_only_controls_required": True,
            "semantic_only_controls_required": True,
            "no_negative_evidence_controls_required": True,
            "early_exclusive_controls_required": True,
            "synthetic_fixtures_do_not_count_as_real_world_corpus": True,
            "corpus_digest_freezes_case_content": True,
            "evaluation_performs_no_provider_call": True,
            "corpus_does_not_establish_permanent_objective_truth": True,
            "numeric_negative_penalty_authorized": False,
            "live_negative_merit_authorized": False,
        },
    }

    return {
        **report_core,
        "report_digest": _digest(
            report_core
        ),
    }


def write_json(
    path: Path,
    value: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
