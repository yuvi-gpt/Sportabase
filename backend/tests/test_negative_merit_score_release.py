import copy
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


from app.analysis.negative_merit_score_release import (
    NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
    NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT,
    NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_DIGEST,
    build_negative_merit_score_release_certificate,
    validate_negative_merit_score_release_certificate,
)


REPORT_PATH = (
    BACKEND_DIR
    / "evals"
    / "negative_merit_real_world_resolved_release_gate_v1.json"
)

CERTIFICATE_PATH = (
    BACKEND_DIR
    / "data"
    / "negative_merit_score_release_certificate.json"
)


class NegativeMeritScoreReleaseTests(
    unittest.TestCase
):
    @staticmethod
    def report():
        return json.loads(
            REPORT_PATH.read_text(
                encoding="utf-8"
            )
        )

    @staticmethod
    def certificate():
        return json.loads(
            CERTIFICATE_PATH.read_text(
                encoding="utf-8"
            )
        )

    def test_committed_certificate_rebuilds_exactly(
        self,
    ):
        certificate = (
            self.certificate()
        )

        rebuilt = (
            build_negative_merit_score_release_certificate(
                release_gate_report=(
                    self.report()
                )
            )
        )

        self.assertEqual(
            certificate,
            rebuilt,
        )

        validated = (
            validate_negative_merit_score_release_certificate(
                certificate
            )
        )

        self.assertEqual(
            validated[
                "version"
            ],
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
        )

        self.assertEqual(
            validated[
                "status"
            ],
            "authorized",
        )

        self.assertTrue(
            validated[
                "live_enablement_authorized"
            ]
        )

        self.assertEqual(
            validated[
                "blockers"
            ],
            [],
        )

        self.assertEqual(
            float(
                validated[
                    "certified_adjustment"
                ]
            ),
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT,
        )

        self.assertEqual(
            validated[
                "release_gate"
            ][
                "report_digest"
            ],
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_DIGEST,
        )

    def test_certificate_clears_only_numeric_release_blocker(
        self,
    ):
        certificate = (
            self.certificate()
        )

        report = certificate[
            "release_gate_report"
        ]

        self.assertEqual(
            report[
                "calibration_dataset"
            ][
                "calibration"
            ][
                "blockers"
            ],
            [
                "numeric_penalty_not_calibrated"
            ],
        )

        self.assertEqual(
            certificate[
                "blockers"
            ],
            [],
        )

        self.assertEqual(
            certificate[
                "certified_adjustment"
            ],
            -15.0,
        )

    def test_certificate_rejects_adjustment_tamper(
        self,
    ):
        certificate = copy.deepcopy(
            self.certificate()
        )

        certificate[
            "certified_adjustment"
        ] = -20.0

        with self.assertRaises(
            ValueError
        ):
            validate_negative_merit_score_release_certificate(
                certificate
            )

    def test_certificate_rejects_release_gate_tamper(
        self,
    ):
        certificate = copy.deepcopy(
            self.certificate()
        )

        certificate[
            "release_gate_report"
        ][
            "temporal_false_positive_control"
        ][
            "penalty_authorized"
        ] = True

        with self.assertRaises(
            ValueError
        ):
            validate_negative_merit_score_release_certificate(
                certificate
            )

    def test_certificate_preserves_truth_boundary(
        self,
    ):
        certificate = (
            self.certificate()
        )

        policy = certificate[
            "policy"
        ]

        self.assertTrue(
            policy[
                "claim_truth_is_not_established_by_release"
            ]
        )

        self.assertTrue(
            policy[
                "absence_of_corroboration_is_not_negative_evidence"
            ]
        )

        self.assertTrue(
            policy[
                "club_denial_alone_never_authorizes_negative_merit"
            ]
        )


if __name__ == "__main__":
    unittest.main()
