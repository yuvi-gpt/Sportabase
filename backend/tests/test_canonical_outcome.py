import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.analysis.canonical_outcome import (
    CANONICAL_OUTCOME_CONTRACT_VERSION,
    compare_canonical_claim_to_outcome,
)

from app.intelligence.canonical_claims import (
    CanonicalClaimInputError,
)


PLAYER = (
    "football|player|example-player"
)

CLUB_A = (
    "football|club|example-a"
)

CLUB_B = (
    "football|club|example-b"
)

ORIGIN = (
    "football|club|example-origin"
)


def transfer(
    *,
    state,
    destination=CLUB_A,
    period="2026-summer",
    origin=ORIGIN,
    transfer_kind="permanent",
    negated=False,
):
    roles = {
        "destination": destination,
    }

    if origin:
        roles[
            "origin"
        ] = origin

    facets = {}

    if period:
        facets[
            "effective_period"
        ] = period

    if transfer_kind:
        facets[
            "transfer_kind"
        ] = transfer_kind

    return {
        "subject_key": PLAYER,
        "event_type": (
            "transfer"
        ),
        "state": state,
        "negated": negated,
        "roles": roles,
        "facets": facets,
    }


def compare(
    claim,
    outcome,
    *,
    claim_time=(
        "2026-08-01T10:00:00Z"
    ),
    outcome_time=(
        "2026-08-02T10:00:00Z"
    ),
):
    return (
        compare_canonical_claim_to_outcome(
            claim_candidate=(
                claim
            ),
            outcome_candidate=(
                outcome
            ),
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
        )
    )


class CanonicalOutcomeContractTests(
    unittest.TestCase
):
    def test_completed_transfer_then_failed_is_against_candidate(
        self,
    ):
        result = compare(
            transfer(
                state="completed"
            ),
            transfer(
                state="failed"
            ),
        )

        self.assertEqual(
            result[
                "version"
            ],
            CANONICAL_OUTCOME_CONTRACT_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "resolution_against_claim_candidate"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "against_claim",
        )

        self.assertEqual(
            result[
                "rule_id"
            ],
            (
                "transfer_completed_then_failed"
            ),
        )

        self.assertTrue(
            result[
                "candidate_resolution"
            ][
                "against_claim"
            ]
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "claim_truth_established"
            ]
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "machine_verified"
            ]
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "live_merit_effect_enabled"
            ]
        )

    def test_completed_transfer_then_cancelled_is_against_candidate(
        self,
    ):
        result = compare(
            transfer(
                state="signed"
            ),
            transfer(
                state="cancelled"
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "resolution_against_claim_candidate"
            ),
        )

        self.assertEqual(
            result[
                "rule_id"
            ],
            (
                "transfer_completed_then_cancelled"
            ),
        )

    def test_explicit_negation_of_completed_transfer_is_against_candidate(
        self,
    ):
        result = compare(
            transfer(
                state="completed"
            ),
            transfer(
                state="completed",
                negated=True,
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "resolution_against_claim_candidate"
            ),
        )

        self.assertEqual(
            result[
                "rule_id"
            ],
            (
                "transfer_completed_explicitly_negated"
            ),
        )

    def test_completed_transfer_confirmation_supports_claim_candidate(
        self,
    ):
        result = compare(
            transfer(
                state="completed"
            ),
            transfer(
                state="joined"
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "resolution_supports_claim_candidate"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "supports_claim",
        )

        self.assertEqual(
            result[
                "rule_id"
            ],
            (
                "transfer_completed_confirmed"
            ),
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "claim_truth_established"
            ]
        )

    def test_agreed_then_failed_is_not_treated_as_falsehood(
        self,
    ):
        result = compare(
            transfer(
                state="agreed"
            ),
            transfer(
                state="failed"
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "state_transition_not_decisive"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "indeterminate",
        )

    def test_missing_effective_period_fails_closed(
        self,
    ):
        result = compare(
            transfer(
                state="completed",
                period="",
            ),
            transfer(
                state="failed",
                period="",
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "resolution_event_identity_insufficient"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "indeterminate",
        )

    def test_different_effective_period_is_different_occurrence(
        self,
    ):
        result = compare(
            transfer(
                state="completed",
                period="2026-summer",
            ),
            transfer(
                state="failed",
                period="2027-summer",
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "different_transfer_occurrence"
            ),
        )

    def test_different_destination_is_not_same_transfer_occurrence(
        self,
    ):
        result = compare(
            transfer(
                state="completed",
                destination=CLUB_A,
            ),
            transfer(
                state="failed",
                destination=CLUB_B,
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "different_transfer_destination"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "indeterminate",
        )

    def test_conflicting_explicit_origin_fails_closed(
        self,
    ):
        result = compare(
            transfer(
                state="completed",
                origin=ORIGIN,
            ),
            transfer(
                state="failed",
                origin=(
                    "football|club|other-origin"
                ),
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "material_transfer_conflict"
            ),
        )

    def test_outcome_must_be_later_than_claim(
        self,
    ):
        result = compare(
            transfer(
                state="completed"
            ),
            transfer(
                state="failed"
            ),
            claim_time=(
                "2026-08-02T10:00:00Z"
            ),
            outcome_time=(
                "2026-08-01T10:00:00Z"
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "outcome_not_later_than_claim"
            ),
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "indeterminate",
        )

    def test_unsupported_event_type_fails_closed(
        self,
    ):
        claim = {
            "subject_key": PLAYER,
            "event_type": (
                "availability"
            ),
            "state": (
                "available"
            ),
            "roles": {},
            "facets": {
                "event_key": (
                    "match-1"
                ),
            },
        }

        outcome = {
            "subject_key": PLAYER,
            "event_type": (
                "availability"
            ),
            "state": (
                "unavailable"
            ),
            "roles": {},
            "facets": {
                "event_key": (
                    "match-1"
                ),
            },
        }

        result = compare(
            claim,
            outcome,
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "event_type_not_supported_for_resolution"
            ),
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "against_claim"
            ]
        )

    def test_truth_field_is_rejected_by_existing_claim_contract(
        self,
    ):
        claim = transfer(
            state="completed"
        )

        claim[
            "truth"
        ] = True

        with self.assertRaises(
            CanonicalClaimInputError
        ):
            compare(
                claim,
                transfer(
                    state="failed"
                ),
            )

    def test_policy_never_authorizes_live_or_verified_resolution(
        self,
    ):
        result = compare(
            transfer(
                state="completed"
            ),
            transfer(
                state="failed"
            ),
        )

        policy = result[
            "policy"
        ]

        self.assertTrue(
            policy[
                "comparison_does_not_verify_source"
            ]
        )

        self.assertTrue(
            policy[
                "comparison_does_not_verify_authority"
            ]
        )

        self.assertTrue(
            policy[
                "comparison_does_not_establish_claim_truth"
            ]
        )

        self.assertTrue(
            policy[
                "machine_verified_outcome_required_before_resolved_label"
            ]
        )

        self.assertFalse(
            policy[
                "numeric_negative_penalty_authorized"
            ]
        )

        self.assertFalse(
            policy[
                "live_negative_merit_authorized"
            ]
        )



from app.analysis.canonical_outcome import (
    CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
)


TENURE_DRIVER = (
    "motorsport|driver|oscar-piastri"
)

TENURE_TEAM = (
    "motorsport|team|alpine-f1-team"
)


def tenure(
    *,
    state="appointed",
    negated=False,
    organization=TENURE_TEAM,
    role="formula_1_race_driver",
    period="2023-season",
):
    facets = {}

    if role:
        facets["role"] = role

    if period:
        facets[
            "effective_period"
        ] = period

    return {
        "subject_key": TENURE_DRIVER,
        "event_type": "tenure",
        "state": state,
        "negated": negated,
        "roles": {
            "organization": organization,
        },
        "facets": facets,
    }


class CanonicalTenureOutcomeContractTests(
    unittest.TestCase
):
    def test_same_appointment_explicitly_negated_is_against_claim(
        self,
    ):
        result = compare(
            tenure(),
            tenure(
                negated=True
            ),
        )

        self.assertEqual(
            result["version"],
            CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
        )

        self.assertEqual(
            result["status"],
            "resolution_against_claim_candidate",
        )

        self.assertEqual(
            result["direction"],
            "against_claim",
        )

        self.assertEqual(
            result["rule_id"],
            "tenure_appointed_explicitly_negated",
        )

        self.assertFalse(
            result[
                "candidate_resolution"
            ][
                "claim_truth_established"
            ]
        )

    def test_same_appointment_reconfirmed_supports_claim(
        self,
    ):
        result = compare(
            tenure(),
            tenure(),
        )

        self.assertEqual(
            result["status"],
            "resolution_supports_claim_candidate",
        )

        self.assertEqual(
            result["direction"],
            "supports_claim",
        )

    def test_different_tenure_organization_fails_closed(
        self,
    ):
        result = compare(
            tenure(),
            tenure(
                organization=(
                    "motorsport|team|mclaren"
                )
            ),
        )

        self.assertEqual(
            result["status"],
            "different_tenure_organization",
        )

        self.assertEqual(
            result["direction"],
            "indeterminate",
        )

    def test_missing_tenure_period_fails_closed(
        self,
    ):
        result = compare(
            tenure(
                period=""
            ),
            tenure(
                period=""
            ),
        )

        self.assertEqual(
            result["status"],
            "resolution_event_identity_insufficient",
        )

        self.assertEqual(
            result["direction"],
            "indeterminate",
        )

    def test_departure_after_appointment_is_not_retroactive_falsehood(
        self,
    ):
        result = compare(
            tenure(),
            tenure(
                state="departed",
            ),
        )

        self.assertEqual(
            result["status"],
            "state_transition_not_decisive",
        )

        self.assertEqual(
            result["direction"],
            "indeterminate",
        )


if __name__ == "__main__":
    unittest.main()
