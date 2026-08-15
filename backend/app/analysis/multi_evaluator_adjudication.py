from typing import (
    Any,
    Dict,
    List,
)


from app.analysis.adjudication import (
    ADJUDICATION_FIELDS,
    AUTO_GOLD_BASIS_BY_FIELD,
    AUTO_GOLD_CONFIDENCE_THRESHOLD,
    build_automated_adjudication,
)

from app.analysis.validation_snapshot import (
    SNAPSHOT_DERIVATION_MODES,
)


MULTI_EVALUATOR_ADJUDICATION_VERSION = (
    "multi-evaluator-adjudication-v1"
)

MULTI_EVALUATOR_FIELDS = (
    "source_role",
    "authority_class",
    "reliability_class",
    "provenance_class",
    "stance",
    "independence_status",
)

TRUSTED_REFERENCE_DERIVATION_MODES = {
    "machine_verified",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _normalize_run(
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            "Multi-evaluator run "
            "must be a dictionary."
        )

    run_id = _clean(
        raw.get(
            "run_id"
        )
    )

    evaluator_id = _clean(
        raw.get(
            "evaluator_id"
        )
    )

    evaluator_family = (
        _clean(
            raw.get(
                "evaluator_family"
            )
        ).lower()
    )

    derivation_mode = (
        _clean(
            raw.get(
                "derivation_mode"
            )
        ).lower()
    )

    if not run_id:
        raise ValueError(
            "Multi-evaluator run ID "
            "is required."
        )

    if not evaluator_id:
        raise ValueError(
            "Multi-evaluator evaluator ID "
            "is required."
        )

    if not evaluator_family:
        raise ValueError(
            "Multi-evaluator evaluator family "
            "is required."
        )

    if (
        derivation_mode
        not in SNAPSHOT_DERIVATION_MODES
    ):
        raise ValueError(
            "Multi-evaluator derivation mode "
            "is unsupported."
        )

    judgments = raw.get(
        "judgments",
        [],
    )

    if not isinstance(
        judgments,
        list,
    ):
        raise ValueError(
            "Multi-evaluator judgments "
            "must be a list."
        )

    normalized_judgments = []
    seen_fields = set()

    reference_trusted = (
        derivation_mode
        in TRUSTED_REFERENCE_DERIVATION_MODES
    )

    for judgment in judgments:
        if not isinstance(
            judgment,
            dict,
        ):
            raise ValueError(
                "Multi-evaluator judgment "
                "must be a dictionary."
            )

        field = (
            _clean(
                judgment.get(
                    "field"
                )
            ).lower()
        )

        if (
            field
            not in MULTI_EVALUATOR_FIELDS
        ):
            raise ValueError(
                "Multi-evaluator judgment field "
                "is unsupported."
            )

        if field in seen_fields:
            raise ValueError(
                "One evaluator run may provide "
                "at most one judgment per field."
            )

        seen_fields.add(
            field
        )

        judgment_evaluator_id = (
            _clean(
                judgment.get(
                    "evaluator_id"
                )
            )
        )

        judgment_family = (
            _clean(
                judgment.get(
                    "evaluator_family"
                )
            ).lower()
        )

        if (
            judgment_evaluator_id
            != evaluator_id
        ):
            raise ValueError(
                "Judgment evaluator ID does not "
                "match its evaluator run."
            )

        if (
            judgment_family
            != evaluator_family
        ):
            raise ValueError(
                "Judgment evaluator family does "
                "not match its evaluator run."
            )

        training_eligible = (
            judgment.get(
                "training_eligible",
                False,
            )
        )

        if not isinstance(
            training_eligible,
            bool,
        ):
            raise ValueError(
                "Judgment training eligibility "
                "must be boolean."
            )

        if (
            training_eligible
            and not reference_trusted
        ):
            raise ValueError(
                "Untrusted evaluator run cannot "
                "mark a judgment training eligible."
            )

        normalized_judgments.append(
            {
                "id": _clean(
                    judgment.get(
                        "id"
                    )
                ),
                "field": field,
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
                    evaluator_id
                ),
                "evaluator_family": (
                    evaluator_family
                ),
                "basis_class": (
                    _clean(
                        judgment.get(
                            "basis_class"
                        )
                    ).lower()
                ),
                "evidence_ids": (
                    judgment.get(
                        "evidence_ids",
                        [],
                    )
                ),
                "training_eligible": (
                    training_eligible
                ),
            }
        )

    return {
        "run_id": run_id,
        "evaluator_id": evaluator_id,
        "evaluator_family": (
            evaluator_family
        ),
        "derivation_mode": (
            derivation_mode
        ),
        "reference_trusted": (
            reference_trusted
        ),
        "judgments": sorted(
            normalized_judgments,
            key=lambda row: (
                row[
                    "field"
                ],
                row[
                    "id"
                ],
            ),
        ),
    }


def _apply_reference_gate(
    *,
    adjudication: Dict[str, Any],
    trusted_judgments: Dict[
        str,
        bool,
    ],
) -> Dict[str, Any]:
    learning_signal = dict(
        adjudication.get(
            "learning_signal",
            {},
        )
    )

    automatic = adjudication[
        "automatic"
    ]

    correction = adjudication[
        "correction"
    ]

    field = adjudication[
        "field"
    ]

    trusted_hard_ids = []

    if (
        not correction
        and automatic[
            "tier"
        ]
        == "auto_gold"
    ):
        gold_basis = (
            AUTO_GOLD_BASIS_BY_FIELD.get(
                field,
                set(),
            )
        )

        supporting_ids = set(
            automatic[
                "supporting_judgment_ids"
            ]
        )

        hard_reference_ids = [
            row[
                "id"
            ]
            for row
            in adjudication[
                "judgments"
            ]
            if (
                row[
                    "id"
                ]
                in supporting_ids
                and row[
                    "basis_class"
                ]
                in gold_basis
                and row[
                    "confidence"
                ]
                >= (
                    AUTO_GOLD_CONFIDENCE_THRESHOLD
                )
            )
        ]

        trusted_hard_ids = sorted(
            row_id
            for row_id
            in hard_reference_ids
            if trusted_judgments.get(
                row_id,
                False,
            )
        )

        if trusted_hard_ids:
            if learning_signal:
                learning_signal[
                    "reference_input_trusted"
                ] = True

                learning_signal[
                    "trusted_reference_judgment_ids"
                ] = (
                    trusted_hard_ids
                )

        else:
            if learning_signal:
                learning_signal = {
                    **learning_signal,
                    "status": (
                        "reference_blocked_"
                        "untrusted_evaluators"
                    ),
                    "training_eligible": (
                        False
                    ),
                    "reference_input_trusted": (
                        False
                    ),
                    "trusted_reference_judgment_ids": [],
                }

    return {
        **adjudication,
        "learning_signal": (
            learning_signal
        ),
        "reference_gate": {
            "automatic_tier": (
                automatic[
                    "tier"
                ]
            ),
            "trusted_hard_reference_judgment_ids": (
                trusted_hard_ids
            ),
            "training_reference_allowed": (
                bool(
                    learning_signal
                    and learning_signal.get(
                        "training_eligible"
                    )
                )
            ),
        },
    }


def build_multi_evaluator_adjudication(
    *,
    claim_id: str,
    evaluator_runs: List[
        Dict[str, Any]
    ],
    corrections: Any = None,
) -> Dict[str, Any]:
    normalized_claim_id = (
        _clean(
            claim_id
        )
    )

    if not normalized_claim_id:
        raise ValueError(
            "Multi-evaluator claim ID "
            "is required."
        )

    if not isinstance(
        evaluator_runs,
        list,
    ):
        raise ValueError(
            "Multi-evaluator runs "
            "must be a list."
        )

    if corrections is None:
        corrections = {}

    if not isinstance(
        corrections,
        dict,
    ):
        raise ValueError(
            "Multi-evaluator corrections "
            "must be a dictionary."
        )

    unknown_corrections = (
        set(
            corrections.keys()
        )
        - set(
            MULTI_EVALUATOR_FIELDS
        )
    )

    if unknown_corrections:
        raise ValueError(
            "Multi-evaluator correction field "
            "is unsupported."
        )

    normalized_runs = []
    run_ids = set()

    judgment_owner = {}
    trusted_judgments = {}

    judgments_by_field = {
        field: []
        for field
        in MULTI_EVALUATOR_FIELDS
    }

    for raw in evaluator_runs:
        run = _normalize_run(
            raw
        )

        if (
            run[
                "run_id"
            ]
            in run_ids
        ):
            raise ValueError(
                "Multi-evaluator run IDs "
                "must be unique."
            )

        run_ids.add(
            run[
                "run_id"
            ]
        )

        for judgment in run[
            "judgments"
        ]:
            judgment_id = judgment[
                "id"
            ]

            if not judgment_id:
                raise ValueError(
                    "Multi-evaluator judgment ID "
                    "is required."
                )

            if (
                judgment_id
                in judgment_owner
            ):
                raise ValueError(
                    "Multi-evaluator judgment IDs "
                    "must be globally unique."
                )

            judgment_owner[
                judgment_id
            ] = run[
                "run_id"
            ]

            trusted_judgments[
                judgment_id
            ] = bool(
                run[
                    "reference_trusted"
                ]
                and judgment[
                    "training_eligible"
                ]
            )

            judgments_by_field[
                judgment[
                    "field"
                ]
            ].append(
                {
                    key: value
                    for (
                        key,
                        value,
                    )
                    in judgment.items()
                    if key
                    not in {
                        "field",
                        "training_eligible",
                    }
                }
            )

        normalized_runs.append(
            run
        )

    normalized_runs = sorted(
        normalized_runs,
        key=lambda row: (
            row[
                "evaluator_family"
            ],
            row[
                "evaluator_id"
            ],
            row[
                "run_id"
            ],
        ),
    )

    field_results = {}

    for field in (
        MULTI_EVALUATOR_FIELDS
    ):
        adjudication = (
            build_automated_adjudication(
                claim_id=(
                    normalized_claim_id
                ),
                field=field,
                judgments=(
                    judgments_by_field[
                        field
                    ]
                ),
                correction=(
                    corrections.get(
                        field
                    )
                ),
            )
        )

        field_results[
            field
        ] = (
            _apply_reference_gate(
                adjudication=(
                    adjudication
                ),
                trusted_judgments=(
                    trusted_judgments
                ),
            )
        )

    summary = {
        "auto_gold_fields": [],
        "auto_silver_fields": [],
        "contested_fields": [],
        "unresolved_fields": [],
        "corrected_fields": [],
    }

    for (
        field,
        result,
    ) in field_results.items():
        tier = result[
            "automatic"
        ][
            "tier"
        ]

        summary[
            f"{tier}_fields"
        ].append(
            field
        )

        if result[
            "correction"
        ]:
            summary[
                "corrected_fields"
            ].append(
                field
            )

    for key in summary:
        summary[
            key
        ] = sorted(
            summary[
                key
            ]
        )

    return {
        "version": (
            MULTI_EVALUATOR_ADJUDICATION_VERSION
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "fields": (
            field_results
        ),
        "evaluators": (
            normalized_runs
        ),
        "summary": summary,
        "policy": {
            "one_vote_per_evaluator_per_field": True,
            "evaluator_identity_must_match_run": True,
            "judgment_ids_are_globally_unique": True,
            "same_family_votes_do_not_create_silver_consensus": True,
            "distinct_evaluator_families_may_create_silver_consensus": True,
            "high_confidence_disagreement_becomes_contested": True,
            "model_assisted_evaluator_cannot_self_mark_training_eligible": True,
            "auto_gold_training_requires_trusted_hard_reference": True,
            "machine_verified_evaluator_is_trusted_reference_path": True,
            "trusted_reference_requires_judgment_training_eligibility": True,
            "automatic_tier_and_training_eligibility_are_separate": True,
            "multi_evaluator_adjudication_does_not_establish_truth": True,
            "multi_evaluator_adjudication_does_not_persist_by_itself": True,
            "multi_evaluator_adjudication_does_not_change_live_merit": True,
        },
    }
