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


def analysis_payload():
    return {
        "detected_language": "English",
        "languages": ["English"],
        "mixed_language": False,
        "language_confidence": 0.98,
        "transcript_confidence": 0.94,
        "uncertain_corrections": [],
        "content_type": "sports_analysis",
        "localized_content_type": (
            "Sports Analysis"
        ),
        "localized_verdict": (
            "Well-Supported Analysis"
        ),
        "ui_labels": {},
        "claim": (
            "Mercedes currently has one of the "
            "strongest overall cars."
        ),
        "evidence_used": [
            (
                "The presenter compares qualifying "
                "pace across several races."
            ),
            (
                "Race pace and tyre degradation "
                "figures support the argument."
            ),
        ],
        "logic_check": (
            "The evidence is connected directly "
            "to the central performance claim."
        ),
        "hype_check": (
            "The delivery is enthusiastic without "
            "substantially distorting the evidence."
        ),
        "evidence_score": 88,
        "logic_score": 90,
        "verdict": "well_supported_analysis",
    }


def run_mocked_analysis(
    transcript_metadata,
):
    response = SimpleNamespace(
        text=json.dumps(
            analysis_payload()
        )
    )

    transcript = (
        "The presenter compares Mercedes "
        "qualifying pace, race pace, tyre "
        "degradation, strategy, and results. "
    ) * 25

    with (
        patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ),
        patch.object(
            main,
            "generate_gemini_content",
            return_value=response,
        ),
    ):
        return main.ai_video_claim_readout(
            title=(
                "Mercedes performance analysis"
            ),
            transcript=transcript,
            url=(
                "https://youtube.com/"
                "watch?v=confidence-test"
            ),
            transcript_metadata=(
                transcript_metadata
            ),
            client_key="unit-test-client",
        )


class VideoExtractionConfidenceTests(
    unittest.TestCase
):
    def test_missing_metadata_remains_unprovided(
        self,
    ):
        first = (
            main
            .normalize_video_transcript_metadata(
                {}
            )
        )

        second = (
            main
            .normalize_video_transcript_metadata(
                first
            )
        )

        self.assertFalse(
            first["provided"]
        )

        self.assertFalse(
            second["provided"]
        )

        self.assertEqual(
            second[
                "extraction_confidence"
            ],
            1.0,
        )


    def test_metadata_values_are_sanitized(
        self,
    ):
        result = (
            main
            .normalize_video_transcript_metadata(
                {
                    "extraction_confidence": 4,
                    "segment_count": -12,
                    "character_count": (
                        "500"
                    ),
                    "duplicate_ratio": -2,
                    "extraction_warnings": [
                        "Very Short Transcript",
                        "very short transcript",
                        "<Unsafe Warning>",
                    ],
                }
            )
        )

        self.assertTrue(
            result["provided"]
        )

        self.assertEqual(
            result[
                "extraction_confidence"
            ],
            1.0,
        )

        self.assertEqual(
            result["segment_count"],
            0,
        )

        self.assertEqual(
            result["character_count"],
            500,
        )

        self.assertEqual(
            result["duplicate_ratio"],
            0.0,
        )

        self.assertEqual(
            result[
                "extraction_warnings"
            ],
            [
                "very_short_transcript",
                "unsafe_warning",
            ],
        )


    def test_low_confidence_caps_strong_result(
        self,
    ):
        result = run_mocked_analysis(
            {
                "extraction_confidence": (
                    0.42
                ),
                "extraction_warnings": [],
                "segment_count": 40,
                "character_count": 4800,
                "duplicate_segment_count": 0,
                "duplicate_ratio": 0,
                "average_segment_length": 120,
                "timestamps_available": True,
            }
        )

        self.assertTrue(
            result["debug"][
                "transcript_extraction_limited"
            ]
        )

        self.assertEqual(
            result["evidence_score"],
            55,
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )

        self.assertEqual(
            result["localized_verdict"],
            "",
        )

        self.assertEqual(
            result["debug"][
                "model_transcript_confidence"
            ],
            0.94,
        )

        self.assertEqual(
            result["debug"][
                "transcript_confidence"
            ],
            0.42,
        )


    def test_warning_can_limit_high_confidence(
        self,
    ):
        result = run_mocked_analysis(
            {
                "extraction_confidence": (
                    0.90
                ),
                "extraction_warnings": [
                    "very_short_transcript",
                ],
                "segment_count": 2,
                "character_count": 95,
            }
        )

        self.assertTrue(
            result["debug"][
                "transcript_extraction_limited"
            ]
        )

        self.assertEqual(
            result["evidence_score"],
            55,
        )

        self.assertEqual(
            result["verdict"],
            "weakly_supported",
        )


    def test_good_extraction_preserves_result(
        self,
    ):
        result = run_mocked_analysis(
            {
                "extraction_confidence": (
                    0.97
                ),
                "extraction_warnings": [],
                "segment_count": 120,
                "character_count": 12000,
                "duplicate_segment_count": 1,
                "duplicate_ratio": 0.008,
                "average_segment_length": 100,
                "timestamps_available": True,
            }
        )

        self.assertFalse(
            result["debug"][
                "transcript_extraction_limited"
            ]
        )

        self.assertEqual(
            result["evidence_score"],
            88,
        )

        self.assertEqual(
            result["verdict"],
            "well_supported_analysis",
        )

        self.assertEqual(
            result["debug"][
                "transcript_confidence"
            ],
            0.94,
        )


    def test_limited_capture_is_not_cached(
        self,
    ):
        result = run_mocked_analysis(
            {
                "extraction_confidence": (
                    0.30
                ),
                "extraction_warnings": [
                    "very_few_segments",
                ],
                "segment_count": 1,
                "character_count": 80,
            }
        )

        decision = (
            main
            .video_analysis_cache_decision(
                result
            )
        )

        self.assertFalse(
            decision["allowed"]
        )

        self.assertEqual(
            decision["reason"],
            (
                "transcript_extraction_"
                "limited"
            ),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
