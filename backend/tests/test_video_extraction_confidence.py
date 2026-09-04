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
from app.services.video_support import (
    apply_video_extraction_confidence_policy,
)


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
    def policy_payload(self, **overrides):
        payload = analysis_payload()
        payload.update(overrides)
        return payload

    def test_policy_without_metadata_preserves_model_confidence(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(transcript_confidence=0.83),
            None,
        )

        self.assertFalse(result["transcript_extraction_limited"])
        self.assertEqual(result["transcript_confidence"], 0.83)

    def test_policy_uses_lower_high_extraction_confidence(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(transcript_confidence=0.94),
            {"extraction_confidence": 0.88},
        )

        self.assertFalse(result["transcript_extraction_limited"])
        self.assertEqual(result["transcript_confidence"], 0.88)

    def test_policy_caps_confidence_for_low_extraction(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(transcript_confidence=0.94),
            {"extraction_confidence": 0.42},
        )

        self.assertTrue(result["transcript_extraction_limited"])
        self.assertEqual(result["transcript_confidence"], 0.42)

    def test_policy_limits_very_few_segments_warning(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(),
            {
                "extraction_confidence": 0.9,
                "extraction_warnings": ["very_few_segments"],
            },
        )

        self.assertTrue(result["transcript_extraction_limited"])

    def test_policy_limits_very_short_transcript_warning(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(),
            {
                "extraction_confidence": 0.9,
                "extraction_warnings": ["very_short_transcript"],
            },
        )

        self.assertTrue(result["transcript_extraction_limited"])

    def test_policy_downgrades_strong_limited_result(self):
        source = self.policy_payload(
            evidence_score=88,
            verdict="well_supported_analysis",
            localized_verdict="Well-Supported Analysis",
        )
        result = apply_video_extraction_confidence_policy(
            source,
            {"extraction_confidence": 0.4},
        )

        self.assertEqual(result["evidence_score"], 55)
        self.assertEqual(result["verdict"], "weakly_supported")
        self.assertEqual(result["localized_verdict"], "")
        self.assertEqual(source["verdict"], "well_supported_analysis")

    def test_policy_does_not_rewrite_already_weak_verdict(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(
                verdict="weakly_supported",
                localized_verdict="Weakly Supported",
            ),
            {"extraction_confidence": 0.4},
        )

        self.assertEqual(result["verdict"], "weakly_supported")
        self.assertEqual(result["localized_verdict"], "Weakly Supported")

    def test_policy_caps_strong_result_without_evidence(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(evidence_used=[], evidence_score=88),
            None,
        )

        self.assertEqual(result["evidence_score"], 35)
        self.assertEqual(result["verdict"], "weakly_supported")

    def test_policy_invalid_model_confidence_becomes_zero(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(transcript_confidence="not-a-number"),
            None,
        )

        self.assertEqual(result["model_transcript_confidence"], 0.0)
        self.assertEqual(result["transcript_confidence"], 0.0)

    def test_policy_clamps_scores(self):
        result = apply_video_extraction_confidence_policy(
            self.policy_payload(evidence_score=120, logic_score=-8),
            None,
        )

        self.assertEqual(result["evidence_score"], 100)
        self.assertEqual(result["logic_score"], 0)

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
