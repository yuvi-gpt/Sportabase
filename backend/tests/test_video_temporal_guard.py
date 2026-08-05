import copy
import json
import sys
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


def base_payload():
    return {
        "detected_language": "English",
        "languages": ["English"],
        "mixed_language": False,
        "language_confidence": 0.98,
        "transcript_confidence": 0.94,
        "uncertain_corrections": [],
        "content_type": "sports_analysis",
        "localized_content_type": "Sports Analysis",
        "localized_verdict": "Well-Supported Analysis",
        "ui_labels": {},
        "claim": (
            "Mercedes has developed the strongest "
            "overall car during the current season."
        ),
        "evidence_used": [
            (
                "The presenter compares Mercedes race "
                "pace across several Grands Prix."
            ),
            (
                "Russell and Antonelli's performances "
                "are used as supporting examples."
            ),
        ],
        "logic_check": (
            "The examples are connected clearly to "
            "the argument about car performance."
        ),
        "hype_check": (
            "The presentation is enthusiastic but "
            "does not substantially exaggerate the claim."
        ),
        "evidence_score": 85,
        "logic_score": 90,
        "verdict": "well_supported_analysis",
    }


def run_mocked_analysis(
    payload,
    *,
    title=(
        "Why Mercedes Built the Best F1 Car "
        "of the Current Season"
    ),
    transcript=(
        "The presenter reviews Mercedes race pace, "
        "qualifying performance, tyre management, "
        "Russell's results, and Antonelli's development. "
    ) * 15,
):
    fake_response = SimpleNamespace(
        text=json.dumps(payload)
    )

    with (
        patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ),
        patch.object(
            main,
            "generate_gemini_content",
            return_value=fake_response,
        ),
    ):
        return main.ai_video_claim_readout(
            title=title,
            transcript=transcript,
            url="https://youtube.com/watch?v=test",
            client_key="unit-test-client",
        )


class VideoTemporalGuardTests(
    unittest.TestCase
):
    def test_normal_analysis_is_unchanged(self):
        payload = base_payload()

        result = run_mocked_analysis(
            payload
        )

        self.assertFalse(
            result["debug"][
                "temporal_guard_triggered"
            ]
        )

        self.assertEqual(
            result["evidence_score"],
            85,
        )

        self.assertEqual(
            result["logic_score"],
            90,
        )

        self.assertEqual(
            result["logic_check"],
            payload["logic_check"],
        )

        self.assertEqual(
            result["hype_check"],
            payload["hype_check"],
        )


    def test_negated_simulation_phrase_does_not_trigger(self):
        payload = base_payload()

        payload["claim"] = (
            "The presenter explains that this is not "
            "a simulated season and discusses real races."
        )

        result = run_mocked_analysis(
            payload
        )

        self.assertFalse(
            result["debug"][
                "temporal_guard_triggered"
            ]
        )

        self.assertEqual(
            result["claim"],
            payload["claim"],
        )


    def test_only_contaminated_fields_are_rewritten(self):
        payload = base_payload()

        payload[
            "localized_content_type"
        ] = "Simulated Sports Narrative"

        payload["evidence_used"] = [
            (
                "The fictional season contains "
                "several invented race results."
            ),
            (
                "The presenter compares Mercedes race "
                "pace across four Grands Prix."
            ),
        ]

        original_logic = (
            payload["logic_check"]
        )

        original_hype = (
            payload["hype_check"]
        )

        result = run_mocked_analysis(
            payload
        )

        self.assertTrue(
            result["debug"][
                "temporal_guard_triggered"
            ]
        )

        self.assertEqual(
            result[
                "localized_content_type"
            ],
            "Sports Analysis",
        )

        self.assertEqual(
            result["evidence_used"],
            [
                (
                    "The presenter compares Mercedes "
                    "race pace across four Grands Prix."
                )
            ],
        )

        self.assertEqual(
            result["logic_check"],
            original_logic,
        )

        self.assertEqual(
            result["hype_check"],
            original_hype,
        )

        self.assertEqual(
            result["evidence_score"],
            65,
        )

        self.assertEqual(
            result["logic_score"],
            90,
        )

        self.assertEqual(
            result["verdict"],
            "well_supported_analysis",
        )


    def test_real_career_mode_allows_simulation_language(self):
        payload = base_payload()

        payload[
            "localized_content_type"
        ] = "Simulated Career Mode Analysis"

        payload["claim"] = (
            "The video analyzes a fictional "
            "F1 career-mode season."
        )

        result = run_mocked_analysis(
            payload,
            title=(
                "F1 26 Career Mode: "
                "My Simulated Mercedes Season"
            ),
            transcript=(
                "This F1 26 career mode gameplay "
                "simulates a fictional championship. "
            ) * 15,
        )

        self.assertFalse(
            result["debug"][
                "temporal_guard_triggered"
            ]
        )

        self.assertEqual(
            result[
                "localized_content_type"
            ],
            "Simulated Career Mode Analysis",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
