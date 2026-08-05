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
    build_video_transcript_context,
)


class VideoTranscriptContextTests(
    unittest.TestCase
):
    def test_empty_transcript(self):
        result = (
            build_video_transcript_context(
                title="Empty video",
                transcript="",
            )
        )

        self.assertEqual(
            result["strategy"],
            "empty",
        )

        self.assertEqual(
            result["text"],
            "",
        )


    def test_short_transcript_is_preserved(self):
        transcript = (
            "Mercedes showed strong race pace. "
            "The presenter compares qualifying "
            "performance and tyre management."
        )

        result = (
            build_video_transcript_context(
                title=(
                    "Mercedes race pace analysis"
                ),
                transcript=transcript,
                max_chars=9000,
            )
        )

        self.assertEqual(
            result["strategy"],
            "full_transcript",
        )

        self.assertFalse(
            result["compression_applied"]
        )

        self.assertEqual(
            result["text"],
            transcript,
        )

        self.assertEqual(
            result["chunk_coverage"],
            1.0,
        )


    def test_late_evidence_is_preserved(self):
        filler_sentence = (
            "The presenter continues discussing "
            "general racing context without making "
            "a decisive claim about performance. "
        )

        transcript_parts = []

        for section in range(8):
            transcript_parts.append(
                (
                    f"Section {section + 1}. "
                    + filler_sentence * 5
                )
            )

        transcript_parts[6] += (
            "Official Mercedes telemetry showed "
            "a three-tenths qualifying advantage "
            "and stronger tyre degradation across "
            "the final twelve laps. "
        )

        transcript = " ".join(
            transcript_parts
        )

        result = (
            build_video_transcript_context(
                title=(
                    "Mercedes qualifying pace "
                    "and tyre degradation"
                ),
                transcript=transcript,
                max_chars=2400,
                chunk_size=500,
            )
        )

        self.assertEqual(
            result["strategy"],
            (
                "all_chunk_extractive_"
                "compression"
            ),
        )

        self.assertTrue(
            result["compression_applied"]
        )

        self.assertIn(
            "Official Mercedes telemetry",
            result["text"],
        )

        self.assertIn(
            "tyre degradation",
            result["text"],
        )

        self.assertGreaterEqual(
            result[
                "represented_chunk_count"
            ],
            4,
        )

        self.assertGreater(
            result["chunk_coverage"],
            0.0,
        )


    def test_title_relevant_sentence_is_selected(self):
        transcript = (
            (
                "The host discusses unrelated "
                "paddock atmosphere and travel. "
            )
            * 20
            + (
                "Russell's qualifying pace directly "
                "supports the Mercedes performance "
                "argument using lap-time comparisons. "
            )
            + (
                "The host returns to general comments "
                "about the season and presentation. "
            )
            * 20
        )

        result = (
            build_video_transcript_context(
                title=(
                    "Russell Mercedes qualifying "
                    "pace analysis"
                ),
                transcript=transcript,
                max_chars=1600,
                chunk_size=500,
            )
        )

        self.assertIn(
            "Russell's qualifying pace",
            result["text"],
        )

        self.assertIn(
            "lap-time comparisons",
            result["text"],
        )


    def test_context_respects_character_budget(self):
        transcript = (
            (
                "Official race data compares lap "
                "times, tyre wear, qualifying pace, "
                "and final results across the season. "
            )
            * 100
        )

        max_chars = 2000

        result = (
            build_video_transcript_context(
                title="Season performance data",
                transcript=transcript,
                max_chars=max_chars,
                chunk_size=600,
            )
        )

        self.assertLessEqual(
            result["context_chars"],
            max_chars,
        )

        self.assertEqual(
            result["context_chars"],
            len(result["text"]),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
