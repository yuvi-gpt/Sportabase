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

        self.assertEqual(
            result["window_coverage"],
            1.0,
        )
        self.assertEqual(result["coverage_window_count"], 1)
        self.assertEqual(result["represented_window_count"], 1)
        self.assertEqual(result["coverage_anchor_count"], 0)
        self.assertEqual(result["global_salience_count"], 0)

    def test_exactly_9000_cleaned_characters_remains_full(self):
        transcript = "x" * 9000
        result = build_video_transcript_context("Boundary", transcript)
        self.assertEqual(result["source_chars"], 9000)
        self.assertEqual(result["strategy"], "full_transcript")
        self.assertEqual(result["text"], transcript)

    def test_9001_cleaned_characters_compresses(self):
        transcript = "x" * 9001
        result = build_video_transcript_context("Boundary", transcript)
        self.assertEqual(result["source_chars"], 9001)
        self.assertEqual(
            result["strategy"],
            "all_chunk_extractive_compression",
        )
        self.assertTrue(result["compression_applied"])
        self.assertLessEqual(len(result["text"]), 9000)
        self.assertIn("[SOURCE WINDOW ", result["text"])

    def test_compression_is_byte_deterministic(self):
        transcript = " ".join(
            f"Section {index} reports result {index % 7}-1 because data shows progress."
            for index in range(500)
        )
        first = build_video_transcript_context("Result analysis", transcript)
        second = build_video_transcript_context("Result analysis", transcript)
        self.assertEqual(first, second)

    def test_coverage_represents_beginning_middle_and_end_in_order(self):
        parts = [
            f"Region {index:03d} discusses ordinary training preparation and team shape."
            for index in range(360)
        ]
        result = build_video_transcript_context(
            "Training preparation",
            " ".join(parts),
        )
        text = result["text"]
        window_count = result["coverage_window_count"]
        first = text.find(f"[SOURCE WINDOW 1 OF {window_count}]")
        middle = text.find(
            f"[SOURCE WINDOW {window_count // 2} OF {window_count}]"
        )
        end_region = text.find(
            f"[SOURCE WINDOW {window_count} OF {window_count}]"
        )
        self.assertGreaterEqual(first, 0)
        self.assertGreaterEqual(middle, 0)
        self.assertGreaterEqual(end_region, 0)
        self.assertLess(first, middle)
        self.assertLess(middle, end_region)
        self.assertEqual(result["window_coverage"], 1.0)

    def test_huge_transcript_uses_bounded_window_count(self):
        transcript = " ".join(
            f"Passage {index} contains routine discussion of the squad."
            for index in range(12000)
        )
        result = build_video_transcript_context("Squad", transcript)
        self.assertEqual(result["coverage_window_count"], 12)
        self.assertLessEqual(result["represented_window_count"], 12)
        self.assertLessEqual(result["context_chars"], 9000)

    def test_final_five_percent_important_claim_survives(self):
        filler = "Routine preparation continued without a material update. "
        transcript = filler * 500 + (
            "Official club statement confirmed striker Nia Vale signed a three-year contract."
        )
        result = build_video_transcript_context("Nia Vale contract", transcript)
        self.assertIn("Official club statement", result["text"])
        self.assertIn(
            f"[SOURCE WINDOW {result['coverage_window_count']} OF ",
            result["text"],
        )

    def test_global_salience_and_chronological_rendering(self):
        parts = [
            f"Topic {index} offers ordinary commentary about preparation."
            for index in range(260)
        ]
        parts[40] = "According to Mira Sen, the official result was 3-1 on 12/08/2026."
        parts[190] = "The club later discussed routine travel arrangements."
        result = build_video_transcript_context("Official result", " ".join(parts))
        self.assertIn("Mira Sen", result["text"])
        markers = [
            int(value)
            for value in __import__("re").findall(
                r"\[SOURCE WINDOW (\d+) OF \d+\]",
                result["text"],
            )
        ]
        self.assertEqual(markers, sorted(markers))
        self.assertGreater(result["global_salience_count"], 0)

    def test_punctuation_poor_and_unbroken_sources_are_bounded(self):
        punctuation_poor = " ".join(f"word{index}" for index in range(4000))
        first = build_video_transcript_context("Words", punctuation_poor)
        second = build_video_transcript_context("Unbroken", "z" * 20000)
        self.assertLessEqual(first["context_chars"], 9000)
        self.assertLessEqual(second["context_chars"], 9000)
        for result in (first, second):
            excerpts = __import__("re").split(
                r"\[SOURCE WINDOW \d+ OF \d+\]\n",
                result["text"],
            )[1:]
            self.assertTrue(excerpts)
            self.assertTrue(
                all(len(item.strip()) <= 360 for item in excerpts)
            )

    def test_structured_fact_and_domain_salience(self):
        filler = "General discussion continued around the team and its preparation. "
        facts = (
            'According to Ana Ruiz, "the score was 3-2" on 12/08/2026, '
            "with 64% possession and a EUR 20 million transfer fee. "
            "The official injury statement said the player was ruled out. "
        )
        result = build_video_transcript_context(
            "Transfer injury result",
            filler * 90 + facts + filler * 90,
            max_chars=1800,
        )
        self.assertIn("Ana Ruiz", result["text"])
        self.assertIn("64%", result["text"])
        self.assertIn("ruled out", result["text"])

    def test_hinglish_selection_is_deterministic(self):
        filler = "Team ke baare mein normal baat chal rahi hai lekin update nahi hai. "
        claim = "Ravi ke mutabik transfer confirm nahi hai kyunki official bid nahi aayi. "
        transcript = filler * 100 + claim + filler * 100
        first = build_video_transcript_context("Ravi transfer", transcript, max_chars=1800)
        second = build_video_transcript_context("Ravi transfer", transcript, max_chars=1800)
        self.assertEqual(first, second)
        self.assertIn("Ravi ke mutabik", first["text"])

    def test_duplicate_policy_preserves_windows_without_global_fill_waste(self):
        repeated = "Official result remained 2-1 after the final whistle. "
        transcript = repeated * 400
        result = build_video_transcript_context("Official result", transcript)
        self.assertEqual(result["window_coverage"], 1.0)
        self.assertEqual(
            result["text"].count("[SOURCE WINDOW "),
            result["coverage_anchor_count"],
        )
        self.assertEqual(result["global_salience_count"], 0)

    def test_no_salience_still_has_distributed_coverage(self):
        opening = (
            "amber opening texture remains quiet and plain throughout. "
            * 90
        )
        middle = (
            "mauve central texture remains quiet and plain throughout. "
            * 90
        )
        ending = (
            "zinnia closing texture remains quiet and plain throughout. "
            * 90
        )
        result = build_video_transcript_context(
            "unrelated heading",
            opening + middle + ending,
        )
        self.assertEqual(result["window_coverage"], 1.0)
        text = result["text"]
        opening_position = text.find("amber opening texture")
        middle_position = text.find("mauve central texture")
        ending_position = text.find("zinnia closing texture")
        self.assertGreaterEqual(opening_position, 0)
        self.assertGreaterEqual(middle_position, 0)
        self.assertGreaterEqual(ending_position, 0)
        self.assertLess(opening_position, middle_position)
        self.assertLess(middle_position, ending_position)

    def test_metrics_match_rendered_selections_and_legacy_chunks(self):
        transcript = " ".join(
            f"Section {index} reports match result {index % 5}-0 with supporting data."
            for index in range(600)
        )
        result = build_video_transcript_context("Match result", transcript)
        marker_count = result["text"].count("[SOURCE WINDOW ")
        self.assertEqual(result["selected_sentence_count"], marker_count)
        self.assertEqual(
            result["coverage_anchor_count"] + result["global_salience_count"],
            marker_count,
        )
        self.assertEqual(result["context_chars"], len(result["text"]))
        self.assertLessEqual(
            result["represented_chunk_count"],
            result["source_chunk_count"],
        )

    def test_marker_cost_is_included_and_candidates_are_not_cut(self):
        first_candidate = "A" * 350 + "."
        second_candidate = "B" * 350 + "."
        transcript = f"{first_candidate} {second_candidate}"
        result = build_video_transcript_context(
            "Budget",
            transcript,
            max_chars=440,
            chunk_size=500,
        )
        self.assertLessEqual(len(result["text"]), 440)
        self.assertIn(first_candidate, result["text"])
        self.assertNotIn(second_candidate, result["text"])
        self.assertNotIn("B" * 40, result["text"])
        self.assertFalse(result["text"].endswith("[SOURCE WINDOW"))

    def test_english_but_does_not_gain_event_preference(self):
        neutral = (
            "Ordinary commentary remains balanced yet offers no special "
            "sporting detail for viewers today."
        )
        ambiguous = (
            "Ordinary commentary remains balanced but offers no special "
            "sporting detail for viewers today."
        )
        result = build_video_transcript_context(
            "unrelated heading",
            f"{neutral} {ambiguous}",
            max_chars=150,
            chunk_size=500,
        )
        self.assertIn(neutral, result["text"])
        self.assertNotIn(ambiguous, result["text"])

    def test_legacy_chunk_metrics_count_every_overlapped_chunk(self):
        crossing_candidate = (
            "Official result was 3-1 and the supporting data remained "
            + "clear " * 35
            + "."
        )
        transcript = "p" * 449 + " " + crossing_candidate
        result = build_video_transcript_context(
            "Official result",
            transcript,
            max_chars=440,
            chunk_size=500,
        )
        self.assertIn("Official result was 3-1", result["text"])
        self.assertEqual(result["source_chunk_count"], 2)
        self.assertEqual(result["represented_chunk_count"], 2)
        self.assertEqual(result["chunk_coverage"], 1.0)


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
