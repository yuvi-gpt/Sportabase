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
    video_analysis_cache_decision,
)


def valid_result():
    return {
        "content_type": "sports_analysis",
        "claim": (
            "Mercedes has produced a strong "
            "car during the current season."
        ),
        "evidence_used": [
            "Race pace is compared across events."
        ],
        "verdict": "well_supported_analysis",
        "debug": {
            "temporal_guard_triggered": False,
        },
    }


class VideoCacheSafetyTests(unittest.TestCase):
    def test_valid_analysis_can_be_cached(self):
        decision = (
            video_analysis_cache_decision(
                valid_result()
            )
        )

        self.assertTrue(
            decision["allowed"]
        )

        self.assertEqual(
            decision["reason"],
            "eligible",
        )


    def test_guarded_analysis_is_not_cached(self):
        result = valid_result()

        result["debug"][
            "temporal_guard_triggered"
        ] = True

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
            "temporal_guard_triggered",
        )


    def test_failed_analysis_is_not_cached(self):
        result = valid_result()
        result["verdict"] = "analysis_failed"

        decision = (
            video_analysis_cache_decision(
                result
            )
        )

        self.assertFalse(
            decision["allowed"]
        )


    def test_unknown_content_is_not_cached(self):
        result = valid_result()
        result["content_type"] = "unknown"

        decision = (
            video_analysis_cache_decision(
                result
            )
        )

        self.assertFalse(
            decision["allowed"]
        )


    def test_strong_verdict_requires_evidence(self):
        result = valid_result()
        result["evidence_used"] = []

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
            "strong_verdict_without_evidence",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
