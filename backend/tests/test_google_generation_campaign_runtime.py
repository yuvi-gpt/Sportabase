from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark_campaign import (
    build_high_information_generation_campaign,
)
from app.ai.benchmark_campaign_runtime import (
    GENERATION_CAMPAIGN_CLIENT_KEY,
    GENERATION_CAMPAIGN_EXECUTION_VERSION,
    CampaignDailyUsageSnapshot,
    campaign_required_calls_by_model,
    evaluate_campaign_execution_preflight,
    load_campaign_daily_usage_snapshot,
)


class GoogleGenerationCampaignRuntimeTests(unittest.TestCase):
    def _plan(self, *, capacity_configured=True):
        _, plan = build_high_information_generation_campaign(
            capacity_configured_resolver=(
                lambda _: bool(capacity_configured)
            )
        )
        return plan

    def _snapshot(
        self,
        *,
        global_count=0,
        client_count=0,
        global_cap=16,
        client_cap=16,
        model_counts=None,
    ):
        return CampaignDailyUsageSnapshot(
            provider_day="2026-08-20",
            global_count=global_count,
            client_count=client_count,
            model_counts=(
                model_counts
                or {
                    "gemini-3.5-flash": 0,
                    "gemini-3.6-flash": 0,
                    "gemma-4-26b-a4b-it": 0,
                }
            ),
            global_daily_call_cap=global_cap,
            client_daily_call_cap=client_cap,
        )

    @staticmethod
    def _policy(_):
        return SimpleNamespace(usable_rpd=100)

    def test_campaign_requires_five_calls_per_model(self):
        plan = self._plan()

        self.assertEqual(
            campaign_required_calls_by_model(plan),
            {
                "gemini-3.5-flash": 5,
                "gemini-3.6-flash": 5,
                "gemma-4-26b-a4b-it": 5,
            },
        )

    def test_fresh_day_with_widened_client_cap_passes(self):
        plan = self._plan()

        preflight = evaluate_campaign_execution_preflight(
            plan,
            snapshot=self._snapshot(),
            policy_resolver=self._policy,
        )

        self.assertEqual(
            preflight.version,
            GENERATION_CAMPAIGN_EXECUTION_VERSION,
        )
        self.assertTrue(preflight.allowed)
        self.assertEqual(preflight.reasons, ())
        self.assertEqual(preflight.planned_provider_calls, 15)
        self.assertEqual(preflight.global_remaining_before_campaign, 16)
        self.assertEqual(preflight.client_remaining_before_campaign, 16)

    def test_exhausted_global_day_blocks_before_execution(self):
        plan = self._plan()

        preflight = evaluate_campaign_execution_preflight(
            plan,
            snapshot=self._snapshot(global_count=16),
            policy_resolver=self._policy,
        )

        self.assertFalse(preflight.allowed)
        self.assertTrue(
            any(
                "global daily call cap" in reason
                for reason in preflight.reasons
            )
        )

    def test_default_eight_call_client_cap_blocks_fifteen_call_campaign(self):
        plan = self._plan()

        preflight = evaluate_campaign_execution_preflight(
            plan,
            snapshot=self._snapshot(client_cap=8),
            policy_resolver=self._policy,
        )

        self.assertFalse(preflight.allowed)
        self.assertTrue(
            any(
                "campaign-client daily call cap" in reason
                for reason in preflight.reasons
            )
        )

    def test_capacity_blocked_challengers_fail_closed(self):
        plan = self._plan(capacity_configured=False)

        preflight = evaluate_campaign_execution_preflight(
            plan,
            snapshot=self._snapshot(),
            policy_resolver=self._policy,
        )

        self.assertFalse(preflight.allowed)
        self.assertEqual(
            preflight.capacity_blocked_resource_ids,
            (
                "gemini-3.6-flash",
                "gemma-4-26b-a4b-it",
            ),
        )

    def test_model_daily_envelope_blocks_when_five_calls_do_not_fit(self):
        plan = self._plan()

        def policy(resource_id):
            return SimpleNamespace(
                usable_rpd=(
                    4
                    if resource_id == "gemini-3.6-flash"
                    else 100
                )
            )

        preflight = evaluate_campaign_execution_preflight(
            plan,
            snapshot=self._snapshot(),
            policy_resolver=policy,
        )

        self.assertFalse(preflight.allowed)
        self.assertTrue(
            any(
                "gemini-3.6-flash" in reason
                for reason in preflight.reasons
            )
        )

    def test_snapshot_reads_true_provider_usage_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "usage.db"
            conn = sqlite3.connect(db_path)

            try:
                conn.execute(
                    """
                    CREATE TABLE gemini_usage (
                        provider_day TEXT,
                        client_key TEXT,
                        model TEXT,
                        status TEXT,
                        cache_hit INTEGER NOT NULL DEFAULT 0,
                        inflight_join INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )

                rows = (
                    (
                        "2026-08-20",
                        GENERATION_CAMPAIGN_CLIENT_KEY,
                        "gemini-3.5-flash",
                        "success",
                        0,
                        0,
                    ),
                    (
                        "2026-08-20",
                        GENERATION_CAMPAIGN_CLIENT_KEY,
                        "gemini-3.6-flash",
                        "failed",
                        0,
                        0,
                    ),
                    (
                        "2026-08-20",
                        "other-client",
                        "gemma-4-26b-a4b-it",
                        "reserved",
                        0,
                        0,
                    ),
                    (
                        "2026-08-20",
                        GENERATION_CAMPAIGN_CLIENT_KEY,
                        "gemini-3.5-flash",
                        "success",
                        1,
                        0,
                    ),
                    (
                        "2026-08-20",
                        GENERATION_CAMPAIGN_CLIENT_KEY,
                        "gemini-3.5-flash",
                        "success",
                        0,
                        1,
                    ),
                    (
                        "2026-08-19",
                        GENERATION_CAMPAIGN_CLIENT_KEY,
                        "gemini-3.5-flash",
                        "success",
                        0,
                        0,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO gemini_usage (
                        provider_day,
                        client_key,
                        model,
                        status,
                        cache_hit,
                        inflight_join
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()

            finally:
                conn.close()

            snapshot = load_campaign_daily_usage_snapshot(
                db_path=db_path,
                provider_day="2026-08-20",
                client_key=GENERATION_CAMPAIGN_CLIENT_KEY,
                resource_ids=(
                    "gemini-3.5-flash",
                    "gemini-3.6-flash",
                    "gemma-4-26b-a4b-it",
                ),
                global_daily_call_cap=16,
                client_daily_call_cap=16,
            )

        self.assertEqual(snapshot.global_count, 3)
        self.assertEqual(snapshot.client_count, 2)
        self.assertEqual(
            snapshot.model_counts,
            {
                "gemini-3.5-flash": 1,
                "gemini-3.6-flash": 1,
                "gemma-4-26b-a4b-it": 1,
            },
        )

    def test_live_cli_has_explicit_execution_and_preflight_gates(self):
        source_path = (
            BACKEND_DIR
            / "scripts"
            / "run_google_generation_campaign.py"
        )
        source = source_path.read_text(encoding="utf-8")

        self.assertIn('"--preflight"', source)
        self.assertIn('"--execute"', source)
        self.assertIn("if not preflight.allowed:", source)
        self.assertIn("GENERATION_CAMPAIGN_CLIENT_KEY", source)
        self.assertIn("generate_gemini_content", source)
        self.assertIn("run_generation_evaluation", source)
        self.assertIn(
            "score_article_observations_with_reliability",
            source,
        )

        self.assertNotIn("google.genai", source)
        self.assertNotIn("from google", source)
        self.assertNotIn("import google", source)


if __name__ == "__main__":
    unittest.main()
