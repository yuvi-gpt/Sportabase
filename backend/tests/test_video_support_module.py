import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.services import (
    video_support,
)


class VideoSupportModuleTests(
    unittest.TestCase
):
    def test_main_reexports_video_support_surface(
        self,
    ):
        names = (
            "prepare_video_transcript",
            "split_video_transcript",
            "get_language_detector",
            "lingua_language_name",
            "detect_content_language",
            "_video_context_tokens",
            "_video_context_sentences",
            "build_video_transcript_context",
            "normalize_video_transcript_metadata",
            "VIDEO_MODEL_UI_LABEL_KEYS",
            "clean_video_model_text",
            "sanitize_video_model_payload",
            "classify_video_provider_error",
            "VIDEO_CONTENT_TYPES",
            "VIDEO_VERDICTS",
            "VIDEO_ALLOWED_VERDICTS_BY_TYPE",
            "VIDEO_VERDICT_REQUIREMENTS",
            "VIDEO_VERDICT_LABELS",
            "bounded_video_score",
            "validate_video_analysis_consistency",
            "video_analysis_cache_decision",
        )

        for name in names:
            with self.subTest(
                name=name
            ):
                self.assertIs(
                    getattr(
                        main,
                        name,
                    ),
                    getattr(
                        video_support,
                        name,
                    ),
                )

    def test_transcript_preparation_preserved(
        self,
    ):
        result = (
            video_support
            .prepare_video_transcript(
                (
                    "Race pace [Music] "
                    "was strong.   "
                    "[Applause] "
                    "Tyre wear improved."
                )
            )
        )

        self.assertNotIn(
            "[Music]",
            result[
                "cleaned_transcript"
            ],
        )

        self.assertNotIn(
            "[Applause]",
            result[
                "cleaned_transcript"
            ],
        )

        self.assertIn(
            "Race pace",
            result[
                "cleaned_transcript"
            ],
        )

    def test_transcript_chunking_preserved(
        self,
    ):
        chunks = (
            video_support
            .split_video_transcript(
                "abcdefghij",
                chunk_size=6,
                overlap=2,
            )
        )

        self.assertEqual(
            chunks,
            [
                "abcdef",
                "efghij",
            ],
        )

    def test_empty_language_detection_is_safe(
        self,
    ):
        result = (
            video_support
            .detect_content_language(
                ""
            )
        )

        self.assertEqual(
            result[
                "detected_language"
            ],
            "unknown",
        )

        self.assertEqual(
            result[
                "languages"
            ],
            [],
        )

        self.assertFalse(
            result[
                "mixed_language"
            ]
        )

    def test_transcript_metadata_sanitization_preserved(
        self,
    ):
        result = (
            video_support
            .normalize_video_transcript_metadata(
                {
                    "extraction_confidence": 4,
                    "segment_count": -5,
                    "character_count": "500",
                    "extraction_warnings": [
                        "Very Short Transcript",
                        "very short transcript",
                    ],
                }
            )
        )

        self.assertTrue(
            result[
                "provided"
            ]
        )

        self.assertEqual(
            result[
                "extraction_confidence"
            ],
            1.0,
        )

        self.assertEqual(
            result[
                "segment_count"
            ],
            0,
        )

        self.assertEqual(
            result[
                "character_count"
            ],
            500,
        )

        self.assertEqual(
            result[
                "extraction_warnings"
            ],
            [
                "very_short_transcript"
            ],
        )

    def test_model_payload_sanitization_preserved(
        self,
    ):
        result = (
            video_support
            .sanitize_video_model_payload(
                {
                    "detected_language":
                        "English",
                    "languages": [
                        "English",
                        "English",
                    ],
                    "content_type":
                        "SPORTS_ANALYSIS",
                    "claim":
                        "  Main claim.  ",
                    "evidence_used": [
                        "Evidence one.",
                        "Evidence one.",
                        "",
                    ],
                    "logic_check":
                        "Reasoning holds.",
                    "hype_check":
                        "Presentation is careful.",
                    "evidence_score": 150,
                    "logic_score": -5,
                    "verdict":
                        "WELL_SUPPORTED_ANALYSIS",
                    "ui_labels": {
                        "verdict":
                            "Verdict",
                        "unsafe_unknown_key":
                            "drop me",
                    },
                }
            )
        )

        self.assertEqual(
            result[
                "content_type"
            ],
            "sports_analysis",
        )

        self.assertEqual(
            result[
                "evidence_used"
            ],
            [
                "Evidence one."
            ],
        )

        self.assertEqual(
            result[
                "evidence_score"
            ],
            100,
        )

        self.assertEqual(
            result[
                "logic_score"
            ],
            0,
        )

        self.assertNotIn(
            "unsafe_unknown_key",
            result[
                "ui_labels"
            ],
        )

    def test_provider_error_classification_preserved(
        self,
    ):
        result = (
            video_support
            .classify_video_provider_error(
                RuntimeError(
                    "503 service unavailable"
                )
            )
        )

        self.assertEqual(
            result[
                "code"
            ],
            "provider_capacity",
        )

        self.assertTrue(
            result[
                "message"
            ],
        )

    def test_consistency_and_cache_guard_remain_connected(
        self,
    ):
        source = {
            "content_type":
                "rumor",
            "claim":
                "A transfer may happen.",
            "evidence_used": [
                "One report is discussed."
            ],
            "logic_check":
                "The reasoning is tentative.",
            "hype_check":
                "The presentation is dramatic.",
            "evidence_score":
                95,
            "logic_score":
                95,
            "verdict":
                "confirmed",
            "debug": {},
        }

        validated = (
            video_support
            .validate_video_analysis_consistency(
                source
            )
        )

        decision = (
            video_support
            .video_analysis_cache_decision(
                validated
            )
        )

        self.assertEqual(
            validated[
                "verdict"
            ],
            "weakly_supported",
        )

        self.assertFalse(
            decision[
                "allowed"
            ]
        )

        self.assertEqual(
            decision[
                "reason"
            ],
            "consistency_adjusted",
        )


if __name__ == "__main__":
    unittest.main()
