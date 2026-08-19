from __future__ import annotations

import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark_campaign import (
    GENERATION_BENCHMARK_CAMPAIGN_VERSION,
    HIGH_INFORMATION_CAMPAIGN_MAX_ESTIMATED_INPUT_TOKENS,
    HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS,
    HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS,
    build_high_information_generation_campaign,
    high_information_campaign_manifest,
)
from app.ai.benchmark_corpus import (
    ARTICLE_BENCHMARK_CORPUS_VERSION,
    HIGH_INFORMATION_GENERATION_CASE_IDS,
)


class GoogleGenerationCampaignTests(unittest.TestCase):
    def test_campaign_contract_is_explicit(self):
        self.assertEqual(
            GENERATION_BENCHMARK_CAMPAIGN_VERSION,
            "sportabase-google-generation-campaign-v1",
        )
        self.assertEqual(
            ARTICLE_BENCHMARK_CORPUS_VERSION,
            "sportabase-article-corpus-v2",
        )
        self.assertEqual(
            HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS,
            15,
        )
        self.assertEqual(
            HIGH_INFORMATION_CAMPAIGN_MAX_ESTIMATED_INPUT_TOKENS,
            100_000,
        )
        self.assertEqual(
            HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS,
            (
                "gemini-3.6-flash",
                "gemma-4-26b-a4b-it",
            ),
        )

    def test_campaign_is_five_cases_by_three_resources(self):
        cases, plan = build_high_information_generation_campaign(
            capacity_configured_resolver=lambda _: True,
        )

        self.assertEqual(
            tuple(case.case_id for case in cases),
            HIGH_INFORMATION_GENERATION_CASE_IDS,
        )
        self.assertEqual(len(cases), 5)
        self.assertEqual(
            len({case.expected_article_type for case in cases}),
            5,
        )
        self.assertEqual(plan.planned_provider_calls, 15)
        self.assertEqual(plan.executable_provider_calls, 15)
        self.assertEqual(plan.blocked_provider_calls, 0)

        expected_resources = (
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemma-4-26b-a4b-it",
        )

        for case in cases:
            resources = tuple(
                item.resource_id
                for item in plan.items
                if item.case_id == case.case_id
            )
            self.assertEqual(resources, expected_resources)

    def test_campaign_compiles_real_production_article_prompt(self):
        cases, plan = build_high_information_generation_campaign(
            capacity_configured_resolver=lambda _: True,
        )

        for case in cases:
            item = next(
                item
                for item in plan.items
                if item.case_id == case.case_id
            )
            self.assertIn(case.title, item.contents)
            self.assertIn(case.text, item.contents)
            self.assertIn(case.url, item.contents)
            self.assertIn("Return ONLY valid JSON.", item.contents)
            self.assertIn("Allowed article_type values:", item.contents)

    def test_capacity_gate_fails_closed_for_challengers(self):
        cases, plan = build_high_information_generation_campaign(
            capacity_configured_resolver=lambda _: False,
        )

        self.assertEqual(len(cases), 5)
        self.assertEqual(plan.planned_provider_calls, 15)
        self.assertEqual(plan.executable_provider_calls, 5)
        self.assertEqual(plan.blocked_provider_calls, 10)

        blocked = {
            item.resource_id
            for item in plan.items
            if item.capacity_blocked
        }
        self.assertEqual(
            blocked,
            {
                "gemini-3.6-flash",
                "gemma-4-26b-a4b-it",
            },
        )

    def test_manifest_is_explicitly_offline(self):
        manifest = high_information_campaign_manifest(
            capacity_configured_resolver=lambda _: True,
        )

        self.assertEqual(manifest["execution"], "disabled")
        self.assertEqual(manifest["provider_calls_made"], 0)
        self.assertEqual(
            tuple(manifest["case_ids"]),
            HIGH_INFORMATION_GENERATION_CASE_IDS,
        )
        self.assertEqual(
            manifest["resource_ids"],
            [
                "gemini-3.5-flash",
                "gemini-3.6-flash",
                "gemma-4-26b-a4b-it",
            ],
        )
        self.assertEqual(
            manifest["plan"]["planned_provider_calls"],
            15,
        )

    def test_offline_planner_cli_has_no_execution_path(self):
        script = (
            BACKEND_DIR
            / "scripts"
            / "plan_google_generation_campaign.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("--execute", script)
        self.assertNotIn("generate_gemini_content", script)
        self.assertNotIn("run_generation_evaluation", script)
        self.assertNotIn("google.genai", script)


if __name__ == "__main__":
    unittest.main()
