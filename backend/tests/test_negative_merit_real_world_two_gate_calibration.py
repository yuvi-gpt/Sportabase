import copy
import hashlib
import json
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


from app.analysis.trusted_validation import (
    VALIDATION_REFERENCE_BASIS_BY_FIELD,
)

from evals.negative_merit_real_world_two_gate_calibration import (
    select_provisional_penalty,
)


class NegativeMeritRealWorldTwoGateCalibrationTests(
    unittest.TestCase
):
    def test_direct_authority_record_is_trusted_for_stance(
        self,
    ):
        self.assertIn(
            "direct_authority_record",
            VALIDATION_REFERENCE_BASIS_BY_FIELD[
                "stance"
            ],
        )

    def test_current_real_world_distribution_selects_minus_fifteen(
        self,
    ):
        result = (
            select_provisional_penalty(
                two_gate_scores=[
                    34,
                    35,
                    46,
                ],
                control_scores=[
                    64,
                    64,
                    56,
                ],
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "provisional_penalty_selected",
        )

        self.assertEqual(
            result[
                "two_gate_median"
            ],
            35.0,
        )

        self.assertEqual(
            result[
                "control_median"
            ],
            64.0,
        )

        self.assertEqual(
            result[
                "median_separation"
            ],
            29.0,
        )

        self.assertEqual(
            result[
                "provisional_adjustment"
            ],
            -15.0,
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )

    def test_penalty_selection_fails_closed_with_too_few_cases(
        self,
    ):
        result = (
            select_provisional_penalty(
                two_gate_scores=[
                    34,
                    35,
                ],
                control_scores=[
                    56,
                    64,
                    64,
                ],
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "insufficient_case_count",
        )

        self.assertIsNone(
            result[
                "provisional_adjustment"
            ]
        )

    def test_penalty_selection_fails_closed_without_separation(
        self,
    ):
        result = (
            select_provisional_penalty(
                two_gate_scores=[
                    70,
                    70,
                    70,
                ],
                control_scores=[
                    60,
                    60,
                    60,
                ],
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "no_positive_median_separation",
        )

        self.assertIsNone(
            result[
                "provisional_adjustment"
            ]
        )

    def test_selection_never_authorizes_live_release(
        self,
    ):
        result = (
            select_provisional_penalty(
                two_gate_scores=[
                    10,
                    20,
                    30,
                ],
                control_scores=[
                    70,
                    80,
                    90,
                ],
            )
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )

        self.assertTrue(
            result[
                "requires_separate_release_certificate"
            ]
        )


if __name__ == "__main__":
    unittest.main()
