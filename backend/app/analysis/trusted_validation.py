import hashlib
import json

from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
)


from app.analysis.adjudication_state import (
    AUTOMATED_ADJUDICATION_STATE_VERSION,
)

from app.analysis.confidence_calibration import (
    build_local_confidence_calibration,
    build_local_confidence_cases,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
    TRUSTED_REFERENCE_DERIVATION_MODES,
)

from app.analysis.shadow_calibration import (
    build_shadow_calibrated_adjudication,
)


TRUSTED_VALIDATION_BUNDLE_VERSION = (
    "trusted-validation-bundle-v1"
)

TRUSTED_HOLDOUT_CASE_VERSION = (
    "trusted-holdout-case-v1"
)

VALIDATION_CLAIM_PARTITION_VERSION = (
    "validation-claim-partition-v1"
)

TRUSTED_VALIDATION_MIN_CONFIDENCE = 0.95


# Holdout validation is intentionally distinct
# from training-reference eligibility.
#
# Every accepted reference must ALSO come from
# a machine_verified evaluator run and evidence
# that was actually persisted as verified.
VALIDATION_REFERENCE_BASIS_BY_FIELD = {
    "source_role": {
        "canonical_resolution",
        "structured_fact",
        "direct_authority_record",
    },

    "authority_class": {
        "direct_authority_record",
        "canonical_resolution",
    },

    "reliability_class": {
        "structured_fact",
        "deterministic_rule",
    },

    "provenance_class": {
        "canonical_resolution",
        "provenance_graph",
        "structured_fact",
    },

    "stance": {
        "canonical_resolution",
        "direct_authority_record",
        "structured_fact",
    },

    "independence_status": {
        "provenance_graph",
        "structured_fact",
        "deterministic_rule",
    },
}


TRUSTED_OUTCOME_TRIGGER_TYPES = {
    "evidence_verified",
    "canonical_outcome",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _canonical_json(
    value: Any,
) -> str:
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


def _canonical_copy(
    value: Any,
) -> Any:
    return json.loads(
        _canonical_json(
            value
        )
    )


def _hash(
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
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Trusted validation confidence "
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
            "Trusted validation confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Trusted validation confidence "
            "must be between 0 and 1."
        )

    return result


def _timestamp(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            text
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

    return parsed


def _string_set(
    values: Any,
) -> Set[str]:
    if not isinstance(
        values,
        (
            list,
            tuple,
            set,
        ),
    ):
        return set()

    return {
        _clean(
            value
        )
        for value
        in values
        if _clean(
            value
        )
    }


def validation_partition_for_claim(
    claim_id: str,
) -> str:
    normalized = _clean(
        claim_id
    )

    if not normalized:
        raise ValueError(
            "Validation partition claim ID "
            "is required."
        )

    digest = hashlib.sha256(
        (
            VALIDATION_CLAIM_PARTITION_VERSION
            + "|"
            + normalized
        ).encode(
            "utf-8"
        )
    ).digest()

    # Assignment is fixed before observing
    # whether the model was right or wrong.
    return (
        "calibration"
        if digest[0] < 128
        else "holdout"
    )


def _revision(
    value: Any,
) -> Dict[
    str,
    Any,
]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Trusted validation revision "
            "must be a dictionary."
        )

    revision = _canonical_copy(
        value
    )

    if (
        _clean(
            revision.get(
                "version"
            )
        )
        != (
            AUTOMATED_ADJUDICATION_STATE_VERSION
        )
    ):
        raise ValueError(
            "Trusted validation revision "
            "version is unsupported."
        )

    if not _clean(
        revision.get(
            "revision_id"
        )
    ):
        raise ValueError(
            "Trusted validation revision ID "
            "is required."
        )

    if not _clean(
        revision.get(
            "claim_id"
        )
    ):
        raise ValueError(
            "Trusted validation claim ID "
            "is required."
        )

    fields = revision.get(
        "fields"
    )

    if (
        not isinstance(
            fields,
            dict,
        )
        or set(
            fields
        )
        != set(
            MULTI_EVALUATOR_FIELDS
        )
    ):
        raise ValueError(
            "Trusted validation revision "
            "field coverage is invalid."
        )

    adjudication = revision.get(
        "adjudication"
    )

    if not isinstance(
        adjudication,
        dict,
    ):
        raise ValueError(
            "Trusted validation revision "
            "adjudication is required."
        )

    evaluators = adjudication.get(
        "evaluators"
    )

    if not isinstance(
        evaluators,
        list,
    ):
        raise ValueError(
            "Trusted validation evaluator "
            "history must be a list."
        )

    trigger = revision.get(
        "trigger"
    )

    if not isinstance(
        trigger,
        dict,
    ):
        raise ValueError(
            "Trusted validation revision "
            "trigger is required."
        )

    _timestamp(
        revision.get(
            "as_of"
        ),
        label=(
            "Trusted validation revision as_of"
        ),
    )

    return revision


def _direct_pair(
    *,
    previous_revision: Any,
    current_revision: Any,
):
    previous = _revision(
        previous_revision
    )

    current = _revision(
        current_revision
    )

    if (
        previous[
            "claim_id"
        ]
        != current[
            "claim_id"
        ]
    ):
        raise ValueError(
            "Trusted validation revisions "
            "belong to different claims."
        )

    if (
        _clean(
            current.get(
                "previous_revision_id"
            )
        )
        != previous[
            "revision_id"
        ]
    ):
        raise ValueError(
            "Trusted validation requires "
            "direct consecutive revisions."
        )

    previous_time = _timestamp(
        previous[
            "as_of"
        ],
        label=(
            "Previous validation revision as_of"
        ),
    )

    current_time = _timestamp(
        current[
            "as_of"
        ],
        label=(
            "Current validation revision as_of"
        ),
    )

    if not (
        current_time
        > previous_time
    ):
        raise ValueError(
            "Trusted validation outcome "
            "must be later than the baseline."
        )

    return (
        previous,
        current,
    )


def _judgment_index(
    revision: Dict[
        str,
        Any,
    ],
):
    index = {}

    for run in revision[
        "adjudication"
    ][
        "evaluators"
    ]:
        if not isinstance(
            run,
            dict,
        ):
            raise ValueError(
                "Trusted validation evaluator "
                "run is invalid."
            )

        for judgment in run.get(
            "judgments",
            [],
        ):
            if not isinstance(
                judgment,
                dict,
            ):
                raise ValueError(
                    "Trusted validation judgment "
                    "is invalid."
                )

            judgment_id = _clean(
                judgment.get(
                    "id"
                )
            )

            if not judgment_id:
                raise ValueError(
                    "Trusted validation judgment "
                    "ID is required."
                )

            if judgment_id in index:
                raise ValueError(
                    "Trusted validation judgment "
                    "IDs must be unique."
                )

            index[
                judgment_id
            ] = (
                run,
                judgment,
            )

    return index


def _verified_training_fields(
    *,
    current_revision: Dict[
        str,
        Any,
    ],
    verified_evidence_ids: Set[
        str
    ],
) -> Set[str]:
    trigger = current_revision[
        "trigger"
    ]

    trigger_type = _key(
        trigger.get(
            "type"
        )
    )

    if (
        trigger_type
        not in TRUSTED_OUTCOME_TRIGGER_TYPES
    ):
        return set()

    trigger_evidence_ids = _string_set(
        trigger.get(
            "evidence_ids",
            [],
        )
    )

    usable_evidence_ids = (
        trigger_evidence_ids
        & verified_evidence_ids
    )

    if not usable_evidence_ids:
        return set()

    judgment_index = _judgment_index(
        current_revision
    )

    verified_fields = set()

    for field in MULTI_EVALUATOR_FIELDS:
        packet = current_revision[
            "fields"
        ][
            field
        ]

        if not isinstance(
            packet,
            dict,
        ):
            continue

        state = packet.get(
            "state",
            {},
        )

        lineage = packet.get(
            "lineage",
            {},
        )

        if (
            not isinstance(
                state,
                dict,
            )
            or not isinstance(
                lineage,
                dict,
            )
        ):
            continue

        if (
            state.get(
                "training_reference_allowed"
            )
            is not True
        ):
            continue

        trusted_ids = _string_set(
            lineage.get(
                (
                    "trusted_hard_reference_"
                    "judgment_ids"
                ),
                [],
            )
        )

        if not trusted_ids:
            continue

        reference_found = False

        for judgment_id in trusted_ids:
            entry = judgment_index.get(
                judgment_id
            )

            if entry is None:
                continue

            run, judgment = entry

            if (
                _key(
                    run.get(
                        "derivation_mode"
                    )
                )
                not in (
                    TRUSTED_REFERENCE_DERIVATION_MODES
                )
            ):
                continue

            if (
                judgment.get(
                    "training_eligible"
                )
                is not True
            ):
                continue

            judgment_evidence = _string_set(
                judgment.get(
                    "evidence_ids",
                    [],
                )
            )

            if (
                judgment_evidence
                & usable_evidence_ids
            ):
                reference_found = True
                break

        if reference_found:
            verified_fields.add(
                field
            )

    return verified_fields


def _trusted_validation_reference(
    *,
    revision: Dict[
        str,
        Any,
    ],
    field: str,
    verified_evidence_ids: Set[
        str
    ],
):
    trigger = revision[
        "trigger"
    ]

    trigger_type = _key(
        trigger.get(
            "type"
        )
    )

    if (
        trigger_type
        not in TRUSTED_OUTCOME_TRIGGER_TYPES
    ):
        return None

    trigger_evidence_ids = _string_set(
        trigger.get(
            "evidence_ids",
            [],
        )
    )

    usable_evidence_ids = (
        trigger_evidence_ids
        & verified_evidence_ids
    )

    if not usable_evidence_ids:
        return None

    candidates = []

    for run in revision[
        "adjudication"
    ][
        "evaluators"
    ]:
        if not isinstance(
            run,
            dict,
        ):
            raise ValueError(
                "Trusted validation evaluator "
                "run is invalid."
            )

        derivation_mode = _key(
            run.get(
                "derivation_mode"
            )
        )

        if (
            derivation_mode
            not in (
                TRUSTED_REFERENCE_DERIVATION_MODES
            )
        ):
            continue

        if (
            run.get(
                "reference_trusted"
            )
            is not True
        ):
            continue

        evaluator_family = _key(
            run.get(
                "evaluator_family"
            )
        )

        for judgment in run.get(
            "judgments",
            [],
        ):
            if not isinstance(
                judgment,
                dict,
            ):
                raise ValueError(
                    "Trusted validation judgment "
                    "is invalid."
                )

            if (
                _key(
                    judgment.get(
                        "field"
                    )
                )
                != field
            ):
                continue

            basis_class = _key(
                judgment.get(
                    "basis_class"
                )
            )

            if (
                basis_class
                not in (
                    VALIDATION_REFERENCE_BASIS_BY_FIELD[
                        field
                    ]
                )
            ):
                continue

            value = _clean(
                judgment.get(
                    "value"
                )
            )

            if not value:
                continue

            confidence = _confidence(
                judgment.get(
                    "confidence"
                )
            )

            if (
                confidence
                < TRUSTED_VALIDATION_MIN_CONFIDENCE
            ):
                continue

            evidence_ids = _string_set(
                judgment.get(
                    "evidence_ids",
                    [],
                )
            )

            matched_evidence = (
                evidence_ids
                & usable_evidence_ids
            )

            if not matched_evidence:
                continue

            judgment_id = _clean(
                judgment.get(
                    "id"
                )
            )

            if not judgment_id:
                raise ValueError(
                    "Trusted validation judgment "
                    "ID is required."
                )

            candidates.append(
                {
                    "judgment_id": (
                        judgment_id
                    ),
                    "value": value,
                    "confidence": confidence,
                    "evaluator_family": (
                        evaluator_family
                    ),
                    "basis_class": (
                        basis_class
                    ),
                    "evidence_ids": sorted(
                        matched_evidence
                    ),
                }
            )

    if not candidates:
        return None

    values = {
        row[
            "value"
        ]
        for row
        in candidates
    }

    if len(
        values
    ) != 1:
        raise ValueError(
            "Conflicting machine-verified "
            f"validation references for {field}."
        )

    verified_value = next(
        iter(
            values
        )
    )

    return {
        "value": verified_value,
        "confidence": min(
            row[
                "confidence"
            ]
            for row
            in candidates
        ),
        "judgment_ids": sorted(
            {
                row[
                    "judgment_id"
                ]
                for row
                in candidates
            }
        ),
        "evaluator_families": sorted(
            {
                row[
                    "evaluator_family"
                ]
                for row
                in candidates
            }
        ),
        "basis_classes": sorted(
            {
                row[
                    "basis_class"
                ]
                for row
                in candidates
            }
        ),
        "evidence_ids": sorted(
            {
                evidence_id
                for row
                in candidates
                for evidence_id
                in row[
                    "evidence_ids"
                ]
            }
        ),
    }


def build_trusted_holdout_cases(
    *,
    previous_revision: Dict[
        str,
        Any,
    ],
    current_revision: Dict[
        str,
        Any,
    ],
    verified_evidence_ids: Iterable[
        str
    ],
) -> List[
    Dict[
        str,
        Any,
    ]
]:
    previous, current = _direct_pair(
        previous_revision=(
            previous_revision
        ),
        current_revision=(
            current_revision
        ),
    )

    verified_ids = _string_set(
        list(
            verified_evidence_ids
        )
    )

    cases = []

    for field in MULTI_EVALUATOR_FIELDS:
        reference = (
            _trusted_validation_reference(
                revision=current,
                field=field,
                verified_evidence_ids=(
                    verified_ids
                ),
            )
        )

        if reference is None:
            continue

        payload = {
            "version": (
                TRUSTED_HOLDOUT_CASE_VERSION
            ),
            "claim_id": (
                current[
                    "claim_id"
                ]
            ),
            "field": field,
            "verified_value": (
                reference[
                    "value"
                ]
            ),
            "baseline_revision_id": (
                previous[
                    "revision_id"
                ]
            ),
            "verification_revision_id": (
                current[
                    "revision_id"
                ]
            ),
            "verification_as_of": (
                current[
                    "as_of"
                ]
            ),
            "verification_confidence": (
                reference[
                    "confidence"
                ]
            ),
            "verification_judgment_ids": (
                reference[
                    "judgment_ids"
                ]
            ),
            "verification_evaluator_families": (
                reference[
                    "evaluator_families"
                ]
            ),
            "verification_basis_classes": (
                reference[
                    "basis_classes"
                ]
            ),
            "verification_evidence_ids": (
                reference[
                    "evidence_ids"
                ]
            ),
            "validation_only": True,
            "training_reference_required": (
                False
            ),
        }

        cases.append(
            {
                **payload,
                "id": _hash(
                    payload,
                    prefix=(
                        "trusted-holdout-case|"
                    ),
                ),
            }
        )

    return sorted(
        cases,
        key=lambda row: (
            row[
                "field"
            ],
            row[
                "id"
            ],
        ),
    )


def _revision_pairs(
    revisions: List[
        Dict[
            str,
            Any,
        ]
    ],
):
    normalized = [
        _revision(
            revision
        )
        for revision
        in revisions
    ]

    by_id = {}

    for revision in normalized:
        revision_id = revision[
            "revision_id"
        ]

        if revision_id in by_id:
            if (
                _canonical_json(
                    by_id[
                        revision_id
                    ]
                )
                != _canonical_json(
                    revision
                )
            ):
                raise ValueError(
                    "Validation revision ID "
                    "collision detected."
                )

            continue

        by_id[
            revision_id
        ] = revision

    pairs = []

    for current in by_id.values():
        previous_id = _clean(
            current.get(
                "previous_revision_id"
            )
        )

        if not previous_id:
            continue

        previous = by_id.get(
            previous_id
        )

        if previous is None:
            raise ValueError(
                "Persisted validation history "
                "is missing a parent revision."
            )

        previous, current = _direct_pair(
            previous_revision=previous,
            current_revision=current,
        )

        pairs.append(
            (
                previous,
                current,
            )
        )

    pairs.sort(
        key=lambda pair: (
            pair[1][
                "claim_id"
            ],
            pair[1][
                "as_of"
            ],
            pair[1][
                "revision_id"
            ],
        )
    )

    return pairs


def build_trusted_validation_bundle(
    *,
    revisions: List[
        Dict[
            str,
            Any,
        ]
    ],
    verified_evidence_ids: Iterable[
        str
    ],
) -> Dict[
    str,
    Any,
]:
    if not isinstance(
        revisions,
        list,
    ):
        raise ValueError(
            "Trusted validation revisions "
            "must be a list."
        )

    verified_ids = _string_set(
        list(
            verified_evidence_ids
        )
    )

    pairs = _revision_pairs(
        revisions
    )

    calibration_cases = []

    holdout_pair_by_claim = {}

    for previous, current in pairs:
        claim_id = current[
            "claim_id"
        ]

        partition = (
            validation_partition_for_claim(
                claim_id
            )
        )

        if partition == "calibration":
            verified_training_fields = (
                _verified_training_fields(
                    current_revision=(
                        current
                    ),
                    verified_evidence_ids=(
                        verified_ids
                    ),
                )
            )

            if not verified_training_fields:
                continue

            extracted = (
                build_local_confidence_cases(
                    previous_revision=(
                        previous
                    ),
                    current_revision=(
                        current
                    ),
                )
            )

            calibration_cases.extend(
                case
                for case
                in extracted
                if (
                    case[
                        "field"
                    ]
                    in verified_training_fields
                )
            )

            continue

        existing = (
            holdout_pair_by_claim.get(
                claim_id
            )
        )

        if (
            existing is None
            or (
                current[
                    "as_of"
                ],
                current[
                    "revision_id"
                ],
            )
            > (
                existing[1][
                    "as_of"
                ],
                existing[1][
                    "revision_id"
                ],
            )
        ):
            holdout_pair_by_claim[
                claim_id
            ] = (
                previous,
                current,
            )

    calibration_by_id = {
        case[
            "id"
        ]: case
        for case
        in calibration_cases
    }

    calibration_cases = sorted(
        calibration_by_id.values(),
        key=lambda row: (
            row[
                "claim_id"
            ],
            row[
                "field"
            ],
            row[
                "id"
            ],
        ),
    )

    calibration = (
        build_local_confidence_calibration(
            cases=calibration_cases
        )
    )

    holdout_cases = []

    holdout_baselines = {}

    for claim_id in sorted(
        holdout_pair_by_claim
    ):
        previous, current = (
            holdout_pair_by_claim[
                claim_id
            ]
        )

        cases = (
            build_trusted_holdout_cases(
                previous_revision=(
                    previous
                ),
                current_revision=(
                    current
                ),
                verified_evidence_ids=(
                    verified_ids
                ),
            )
        )

        if not cases:
            continue

        holdout_cases.extend(
            cases
        )

        holdout_baselines[
            claim_id
        ] = previous

    holdout_cases = sorted(
        holdout_cases,
        key=lambda row: (
            row[
                "claim_id"
            ],
            row[
                "field"
            ],
            row[
                "id"
            ],
        ),
    )

    calibration_claim_ids = {
        case[
            "claim_id"
        ]
        for case
        in calibration_cases
    }

    holdout_claim_ids = {
        case[
            "claim_id"
        ]
        for case
        in holdout_cases
    }

    overlap = (
        calibration_claim_ids
        & holdout_claim_ids
    )

    if overlap:
        raise RuntimeError(
            "Deterministic validation "
            "partition produced overlap."
        )

    shadow_results = []

    for claim_id in sorted(
        holdout_claim_ids
    ):
        baseline = (
            holdout_baselines[
                claim_id
            ]
        )

        evaluator_runs = (
            baseline[
                "adjudication"
            ][
                "evaluators"
            ]
        )

        shadow_results.append(
            build_shadow_calibrated_adjudication(
                claim_id=claim_id,
                evaluator_runs=(
                    evaluator_runs
                ),
                calibration=(
                    calibration
                ),
            )
        )

    field_coverage = sorted(
        {
            case[
                "field"
            ]
            for case
            in holdout_cases
        }
    )

    missing_fields = sorted(
        set(
            MULTI_EVALUATOR_FIELDS
        )
        - set(
            field_coverage
        )
    )

    return {
        "version": (
            TRUSTED_VALIDATION_BUNDLE_VERSION
        ),
        "calibration": calibration,
        "holdout_cases": (
            holdout_cases
        ),
        "shadow_results": (
            shadow_results
        ),
        "summary": {
            "revision_count": len(
                revisions
            ),
            "consecutive_pair_count": len(
                pairs
            ),
            "verified_evidence_count": len(
                verified_ids
            ),
            "calibration_case_count": len(
                calibration_cases
            ),
            "calibration_claim_count": len(
                calibration_claim_ids
            ),
            "shadow_ready_profile_count": (
                calibration[
                    "summary"
                ][
                    "shadow_ready_profile_count"
                ]
            ),
            "holdout_case_count": len(
                holdout_cases
            ),
            "holdout_claim_count": len(
                holdout_claim_ids
            ),
            "holdout_field_coverage": (
                field_coverage
            ),
            "missing_holdout_fields": (
                missing_fields
            ),
            "shadow_result_count": len(
                shadow_results
            ),
            "shadow_adjustment_count": sum(
                result[
                    "summary"
                ][
                    "adjusted_judgment_count"
                ]
                for result
                in shadow_results
            ),
        },
        "policy": {
            "claim_partition_is_deterministic": True,
            "claim_partition_precedes_outcome_scoring": True,
            "calibration_and_holdout_claims_do_not_overlap": True,
            "calibration_still_requires_training_reference": True,
            "holdout_does_not_require_training_permission": True,
            "holdout_requires_machine_verified_evaluator": True,
            "holdout_requires_verified_persisted_evidence": True,
            "holdout_requires_later_revision": True,
            "holdout_requires_verified_or_canonical_trigger": True,
            "conflicting_machine_verified_references_fail_closed": True,
            "model_assisted_output_cannot_validate_holdout": True,
            "does_not_expand_auto_gold_basis": True,
            "does_not_persist": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
            "human_review_required": False,
        },
    }
