from __future__ import annotations

import unittest

from app.ai.benchmark import (
    GOLDEN_ARTICLE_SINGLE_PASS_CASES,
    compile_article_single_pass_evaluation_cases,
)
from app.ai.benchmark_corpus import (
    ARTICLE_BENCHMARK_CORPUS_VERSION,
    EXPANDED_ARTICLE_SINGLE_PASS_CASES,
    GOLDEN_ARTICLE_CORPUS,
    HIGH_INFORMATION_GENERATION_CASE_IDS,
    covered_article_types,
    golden_article_case,
    select_golden_article_cases,
)
from app.ai.tasks import ARTICLE_SINGLE_PASS
from app.services.article_rules import AI_ARTICLE_TYPE_VALUES


class GoogleBenchmarkCorpusTests(unittest.TestCase):
    def test_corpus_version_is_explicit(self):
        self.assertEqual(
            ARTICLE_BENCHMARK_CORPUS_VERSION,
            "sportabase-article-corpus-v2",
        )

    def test_expanded_corpus_contains_twenty_cases(self):
        self.assertEqual(
            len(GOLDEN_ARTICLE_SINGLE_PASS_CASES),
            4,
        )
        self.assertEqual(
            len(EXPANDED_ARTICLE_SINGLE_PASS_CASES),
            16,
        )
        self.assertEqual(
            len(GOLDEN_ARTICLE_CORPUS),
            20,
        )

    def test_original_four_cases_are_preserved_first(self):
        self.assertEqual(
            GOLDEN_ARTICLE_CORPUS[:4],
            GOLDEN_ARTICLE_SINGLE_PASS_CASES,
        )

    def test_case_ids_are_unique(self):
        case_ids = tuple(
            case.case_id
            for case in GOLDEN_ARTICLE_CORPUS
        )
        self.assertEqual(
            len(case_ids),
            len(set(case_ids)),
        )

    def test_every_case_uses_supported_article_type(self):
        for case in GOLDEN_ARTICLE_CORPUS:
            with self.subTest(case=case.case_id):
                self.assertIn(
                    case.expected_article_type,
                    AI_ARTICLE_TYPE_VALUES,
                )
                self.assertEqual(
                    len(case.required_facts),
                    3,
                )
                for fact in case.required_facts:
                    self.assertTrue(
                        str(fact).strip()
                    )

    def test_corpus_covers_twenty_distinct_article_types(self):
        article_types = covered_article_types()
        self.assertEqual(
            len(article_types),
            20,
        )
        self.assertEqual(
            len(article_types),
            len(set(article_types)),
        )

    def test_expanded_types_cover_key_non_transfer_boundaries(self):
        expected = {
            "injury_rumor",
            "match_report",
            "lineup_confirmed",
            "lineup_predicted",
            "manager_interview",
            "player_interview",
            "press_conference",
            "managerial_news",
            "contract_news",
            "tactical_analysis",
            "stats_data_report",
            "opinion_analysis",
            "discipline_legal",
            "fixture_schedule",
            "ownership_finance",
            "generic_news",
        }
        self.assertTrue(
            expected.issubset(set(covered_article_types()))
        )

    def test_high_information_selection_is_five_unique_cases(self):
        self.assertEqual(
            len(HIGH_INFORMATION_GENERATION_CASE_IDS),
            5,
        )
        self.assertEqual(
            len(set(HIGH_INFORMATION_GENERATION_CASE_IDS)),
            5,
        )

        cases = select_golden_article_cases()

        self.assertEqual(
            tuple(case.case_id for case in cases),
            HIGH_INFORMATION_GENERATION_CASE_IDS,
        )
        self.assertEqual(
            len({case.expected_article_type for case in cases}),
            5,
        )

    def test_expanded_cases_compile_through_production_prompt_capture(self):
        cases = select_golden_article_cases(
            (
                "injury-rumor-training-doubt",
                "match-report-late-winner",
                "tactical-analysis-pressing",
            )
        )

        compiled = compile_article_single_pass_evaluation_cases(
            cases
        )

        self.assertEqual(len(compiled), 3)

        for source_case, evaluation_case in zip(cases, compiled):
            with self.subTest(case=source_case.case_id):
                self.assertEqual(
                    evaluation_case.case_id,
                    source_case.case_id,
                )
                self.assertEqual(
                    evaluation_case.task_id,
                    ARTICLE_SINGLE_PASS,
                )
                self.assertIn(
                    source_case.title,
                    evaluation_case.contents,
                )
                self.assertIn(
                    source_case.text,
                    evaluation_case.contents,
                )
                self.assertIn(
                    "Return ONLY valid JSON.",
                    evaluation_case.contents,
                )

    def test_named_lookup_round_trips_every_case(self):
        for case in GOLDEN_ARTICLE_CORPUS:
            with self.subTest(case=case.case_id):
                self.assertIs(
                    golden_article_case(case.case_id),
                    case,
                )

    def test_unknown_case_fails_closed(self):
        with self.assertRaises(KeyError):
            golden_article_case("not-a-golden-case")

    def test_duplicate_selection_fails_closed(self):
        with self.assertRaises(ValueError):
            select_golden_article_cases(
                (
                    "match-report-late-winner",
                    "match-report-late-winner",
                )
            )

    def test_empty_selection_fails_closed(self):
        with self.assertRaises(ValueError):
            select_golden_article_cases(())


if __name__ == "__main__":
    unittest.main()
