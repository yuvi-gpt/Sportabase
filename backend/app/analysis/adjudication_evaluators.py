from typing import (
    Any,
    Dict,
)


from app.analysis.adjudication import (
    build_automated_adjudication,
)

from app.analysis.authority import (
    CLAIM_AUTHORITY_POLICY_VERSION,
)

from app.analysis.validation_snapshot import (
    build_claim_evidence_snapshot,
)


AUTHORITY_STATE_EVALUATOR_VERSION = (
    "authority-state-evaluator-v1"
)

_DIRECT_STAKEHOLDER_STATES = {
    "stakeholder_confirmed",
    "stakeholder_contradicted",
    "stakeholder_contested",
}

_DIRECT_INSTITUTIONAL_STATES = {
    "institutionally_confirmed",
    "institutionally_contradicted",
    "institutionally_contested",
}


def _direct_authority_evidence_ids(
    *,
    state: str,
    observations,
):
    if (
        state
        in _DIRECT_STAKEHOLDER_STATES
    ):
        return sorted(
            row["id"]
            for row in observations
            if (
                row["source_role"]
                == "primary_stakeholder"
                and row["authority_class"]
                == "direct"
                and row["provenance_class"]
                == "direct_statement"
                and row["stance"]
                in {
                    "supports",
                    "contradicts",
                }
            )
        )

    if (
        state
        in _DIRECT_INSTITUTIONAL_STATES
    ):
        return sorted(
            row["id"]
            for row in observations
            if (
                row["source_role"]
                == "official_institution"
                and row["authority_class"]
                == "institutional"
                and row["provenance_class"]
                in {
                    "direct_statement",
                    "direct_official_reporting",
                }
                and row["stance"]
                in {
                    "supports",
                    "contradicts",
                }
            )
        )

    return []


def build_authority_state_adjudication(
    *,
    evidence_snapshot: Dict[
        str,
        Any,
    ],
    correction: Any = None,
) -> Dict[str, Any]:
    normalized_snapshot = (
        build_claim_evidence_snapshot(
            evidence_snapshot
        )
    )

    claim_id = normalized_snapshot[
        "claim_id"
    ]

    assessment = normalized_snapshot[
        "authority_assessment"
    ]

    state = assessment[
        "confirmation_state"
    ]

    authority_observations = (
        assessment[
            "observations"
        ]
    )

    direct_evidence_ids = (
        _direct_authority_evidence_ids(
            state=state,
            observations=(
                authority_observations
            ),
        )
    )

    if direct_evidence_ids:
        basis_class = (
            "direct_authority_record"
        )

        confidence = 1.0

        evidence_ids = (
            direct_evidence_ids
        )

    else:
        basis_class = (
            "deterministic_rule"
        )

        confidence = 1.0

        evidence_ids = sorted(
            row["id"]
            for row
            in authority_observations
        )

    judgment = {
        "id": (
            "authority-state:"
            + claim_id
            + ":"
            + AUTHORITY_STATE_EVALUATOR_VERSION
        ),
        "value": state,
        "confidence": confidence,
        "evaluator_id": (
            AUTHORITY_STATE_EVALUATOR_VERSION
        ),
        "evaluator_family": (
            "authority_policy"
        ),
        "basis_class": (
            basis_class
        ),
        "evidence_ids": (
            evidence_ids
        ),
    }

    result = (
        build_automated_adjudication(
            claim_id=claim_id,
            field="authority_state",
            judgments=[
                judgment
            ],
            correction=correction,
        )
    )

    derivation = normalized_snapshot[
        "derivation"
    ]

    human_approved = (
        normalized_snapshot[
            "review"
        ][
            "status"
        ]
        == "approved"
    )

    machine_verified = (
        derivation[
            "mode"
        ]
        == "machine_verified"
    )

    reference_input_trusted = (
        human_approved
        or machine_verified
    )

    learning_signal = dict(
        result[
            "learning_signal"
        ]
    )

    if (
        not correction
        and result[
            "automatic"
        ][
            "tier"
        ]
        == "auto_gold"
        and not reference_input_trusted
    ):
        learning_signal = {
            **learning_signal,
            "status": (
                "reference_blocked_"
                "untrusted_snapshot"
            ),
            "training_eligible": (
                False
            ),
            "reference_input_trusted": (
                False
            ),
        }

    elif learning_signal:
        learning_signal[
            "reference_input_trusted"
        ] = (
            reference_input_trusted
        )

    return {
        **result,
        "learning_signal": (
            learning_signal
        ),
        "evaluator": {
            "version": (
                AUTHORITY_STATE_EVALUATOR_VERSION
            ),
            "authority_policy_version": (
                CLAIM_AUTHORITY_POLICY_VERSION
            ),
            "snapshot_version": (
                normalized_snapshot[
                    "version"
                ]
            ),
            "recomputed_from_observations": (
                True
            ),
            "stored_derived_authority_is_not_trusted": (
                True
            ),
            "snapshot_derivation_mode": (
                derivation[
                    "mode"
                ]
            ),
            "snapshot_human_approved": (
                human_approved
            ),
            "reference_input_trusted": (
                reference_input_trusted
            ),
        },
        "policy": {
            **result[
                "policy"
            ],
            "direct_stakeholder_authority_can_be_auto_gold": True,
            "direct_institutional_authority_can_be_auto_gold": True,
            "reported_unconfirmed_is_not_auto_gold_from_authority_policy_alone": True,
            "unconfirmed_is_not_auto_gold_from_absence_of_authority": True,
            "authority_is_recomputed_from_snapshot_observations": True,
            "auto_gold_and_training_eligibility_are_separate": True,
            "untrusted_snapshot_cannot_self_train_from_auto_gold": True,
            "machine_verified_snapshot_may_supply_training_reference": True,
            "human_approved_snapshot_remains_a_trusted_reference_path": True,
            "model_assisted_snapshot_is_not_self_validating": True,
            "manual_draft_snapshot_is_not_self_validating": True,
            "automatic_authority_adjudication_does_not_establish_truth": True,
            "automatic_authority_adjudication_does_not_change_live_merit": True,
        },
    }
