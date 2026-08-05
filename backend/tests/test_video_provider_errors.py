import sys
import unittest

from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


def run_failed_analysis(error):
    with (
        patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ),
        patch.object(
            main,
            "generate_gemini_content",
            side_effect=error,
        ),
    ):
        return main.ai_video_claim_readout(
            title="Mercedes analysis",
            transcript=(
                "The presenter compares race pace, "
                "qualifying, results, and tyre wear. "
            ) * 20,
            url="https://youtube.com/watch?v=test",
            client_key="provider-error-test",
        )


class VideoProviderErrorTests(unittest.TestCase):
    def test_503_has_friendly_message(self):
        result = run_failed_analysis(
            Exception(
                "503 UNAVAILABLE: model is "
                "experiencing high demand"
            )
        )

        self.assertEqual(
            result["debug"]["error_code"],
            "provider_capacity",
        )

        self.assertIn(
            "temporarily busy",
            result["debug"]["error"],
        )

        self.assertIn(
            "503 UNAVAILABLE",
            result["debug"]["provider_error"],
        )


    def test_failure_is_not_consistency_adjusted(self):
        result = run_failed_analysis(
            Exception("503 UNAVAILABLE")
        )

        validated = (
            main
            .validate_video_analysis_consistency(
                result
            )
        )

        self.assertFalse(
            validated["debug"][
                "consistency_adjusted"
            ]
        )

        decision = (
            main.video_analysis_cache_decision(
                validated
            )
        )

        self.assertEqual(
            decision["reason"],
            "analysis_failed",
        )


    def test_provider_429_is_classified(self):
        result = run_failed_analysis(
            Exception(
                "429 RESOURCE_EXHAUSTED"
            )
        )

        self.assertEqual(
            result["debug"]["error_code"],
            "provider_rate_limited",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
