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
    CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
    compare_canonical_claim_to_outcome,
)

from evals.negative_merit_real_world_resolved_release_gate import (
    build_temporal_false_positive_control,
)


class NegativeMeritResolvedReleaseGateTests(
    unittest.TestCase
):
    def test_tenure_resolution_contract_is_distinct_from_transfer_contract(
        self,
    ):
        claim = {
            "subject_key": (
                "motorsport|driver|test"
            ),
            "event_type": "tenure",
            "state": "appointed",
            "negated": False,
            "roles": {
                "organization": (
                    "motorsport|team|test"
                ),
            },
            "facets": {
                "role": (
                    "formula_1_race_driver"
                ),
                "effective_period": (
                    "2023-season"
                ),
            },
        }

        outcome = {
            **claim,
            "negated": True,
        }

        result = (
            compare_canonical_claim_to_outcome(
                claim_candidate=claim,
                outcome_candidate=outcome,
                claim_observed_at=(
                    "2022-08-02T12:00:00+00:00"
                ),
                outcome_observed_at=(
                    "2023-03-19T22:00:00+00:00"
                ),
            )
        )

        self.assertEqual(
            result["version"],
            CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
        )

        self.assertEqual(
            result["direction"],
            "against_claim",
        )

    def test_cucurella_style_denial_is_not_automatic_falsehood(
        self,
    ):
        control = (
            build_temporal_false_positive_control(
                denial_capture={
                    "url": (
                        "https://brighton.example/"
                        "cucurella"
                    ),
                    "content_sha256": (
                        "a" * 64
                    ),
                    "captured_at": (
                        "2026-08-23T10:00:00+00:00"
                    ),
                },
                completion_capture={
                    "url": (
                        "https://chelsea.example/"
                        "cucurella"
                    ),
                    "content_sha256": (
                        "b" * 64
                    ),
                    "captured_at": (
                        "2026-08-23T10:01:00+00:00"
                    ),
                },
            )
        )

        self.assertEqual(
            control[
                "denial_comparison"
            ][
                "status"
            ],
            "state_transition_not_decisive",
        )

        self.assertEqual(
            control[
                "denial_comparison"
            ][
                "direction"
            ],
            "indeterminate",
        )

        self.assertFalse(
            control[
                "penalty_authorized"
            ]
        )

    def test_tenure_different_organization_never_resolves_against_claim(
        self,
    ):
        claim = {
            "subject_key": (
                "motorsport|driver|test"
            ),
            "event_type": "tenure",
            "state": "appointed",
            "negated": False,
            "roles": {
                "organization": (
                    "motorsport|team|one"
                ),
            },
            "facets": {
                "role": (
                    "formula_1_race_driver"
                ),
                "effective_period": (
                    "2023-season"
                ),
            },
        }

        outcome = {
            **claim,
            "negated": True,
            "roles": {
                "organization": (
                    "motorsport|team|two"
                ),
            },
        }

        result = (
            compare_canonical_claim_to_outcome(
                claim_candidate=claim,
                outcome_candidate=outcome,
                claim_observed_at=(
                    "2022-08-02T12:00:00+00:00"
                ),
                outcome_observed_at=(
                    "2023-03-19T22:00:00+00:00"
                ),
            )
        )

        self.assertEqual(
            result[
                "direction"
            ],
            "indeterminate",
        )




class NegativeMeritOfficialRawHtmlFallbackTests(
    unittest.TestCase
):
    def test_official_raw_html_preserves_exact_denial_semantics(
        self,
    ):
        from evals.negative_merit_real_world_resolved_release_gate import (
            _raw_semantic_text,
        )

        raw = (
            '<span>'
            'Contrary to inaccurate reports, '
            'no agreement has been reached with any club '
            'to sell Marc Cucurella.'
            '</span>'
        )

        decoded = (
            _raw_semantic_text(
                raw
            )
        )

        self.assertIn(
            "no agreement has been reached",
            decoded,
        )

        self.assertIn(
            "sell Marc Cucurella",
            decoded,
        )


if __name__ == "__main__":
    unittest.main()
