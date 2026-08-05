import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.main import (
    validate_video_analysis_consistency,
    video_analysis_cache_decision,
)


def result_template():
    return {
        "content_type": "sports_analysis",
        "claim": (
            "Mercedes has produced one of "
            "the strongest cars this season."
        ),
        "evidence_used": [
            "Race pace is compared.",
            "Qualifying pace is compared.",
        ],
        "logic_check": (
            "The evidence is connected "
            "to the central argument."
        ),
        "hype_check": (
            "The presentation is dramatic "
            "but not materially misleading."
        ),
        "evidence_score": 80,
        "logic_score": 82,
        "verdict": (
            "well_supported_analysis"
        ),
        "localized_verdict": (
            "Well-Supported Analysis"
        ),
        "debug": {},
    }


class VideoConsistencyTests(
    unittest.TestCase
):
    def test_valid_analysis_is_preserved(self):
        result = (
            validate_video_analysis_consistency(
                result_template()
            )
        )

        self.assertEqual(
            result["verdict"],
            "well_supported_analysis",
        )
        self.assertFalse(
            result["debug"][
                "consistency_adjusted"
            ]
        )


    def test_wrong_verdict_for_type_is_downgraded(self):
        source = result_template()
        source["content_type"] = "rumor"
        source["verdict"] = "confirmed"

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )


    def test_strong_verdict_requires_scores(self):
        source = result_template()
        source["evidence_score"] = 25
        source["logic_score"] = 40

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )


    def test_confirmed_requires_multiple_evidence_items(self):
        source = result_template()
        source["content_type"] = (
            "confirmed_news"
        )
        source["verdict"] = "confirmed"
        source["evidence_score"] = 95
        source["logic_score"] = 90
        source["evidence_used"] = [
            "Only one supporting item."
        ]

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )


    def test_valid_confirmation_survives(self):
        source = result_template()
        source["content_type"] = (
            "confirmed_news"
        )
        source["verdict"] = "confirmed"
        source["evidence_score"] = 92
        source["logic_score"] = 86
        source["evidence_used"] = [
            (
                "An official team statement "
                "confirms the announcement."
            ),
            (
                "The governing body's official "
                "result supports the report."
            ),
        ]

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "confirmed",
        )


    def test_duplicate_evidence_is_removed(self):
        source = result_template()
        source["evidence_used"] = [
            "Race pace is compared.",
            "",
            "Race pace is compared.",
        ]

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["evidence_used"],
            [
                "Race pace is compared."
            ],
        )


    def test_missing_claim_forces_safe_result(self):
        source = result_template()
        source["claim"] = ""

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )
        self.assertLessEqual(
            result["evidence_score"],
            40,
        )
        self.assertTrue(
            result["claim"]
        )


    def test_negative_verdict_cannot_have_high_support(self):
        source = result_template()
        source["verdict"] = "misleading"
        source["evidence_score"] = 90
        source["logic_score"] = 90

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )


    def test_adjusted_result_is_not_cached(self):
        source = result_template()
        source["content_type"] = "rumor"
        source["verdict"] = "confirmed"

        result = (
            validate_video_analysis_consistency(
                source
            )
        )

        decision = (
            video_analysis_cache_decision(
                result
            )
        )

        self.assertFalse(
            decision["allowed"]
        )
        self.assertEqual(
            decision["reason"],
            "consistency_adjusted",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
