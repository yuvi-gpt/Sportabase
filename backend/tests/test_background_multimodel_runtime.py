from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.ai.tasks import (
    AGENTIC_PROVENANCE_INSPECTION,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    LOCAL_RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    RETRIEVAL_EMBEDDING,
)
from app.intelligence.background_multimodel_runtime import (
    BACKGROUND_MULTIMODEL_PLAN_VERSION,
    build_background_multimodel_plan,
    plan_completed_job_specialized_ai,
)


def _env(values):
    return lambda name, default="": values.get(name, default)


def _claim(
    claim_id="claim-1",
    *,
    structured=True,
    state="claim_supported",
    freshness="current",
):
    return {
        "id": claim_id,
        "status": "ok",
        "projection_state": state,
        "freshness_state": freshness,
        "structured_identity": structured,
    }


def _result(claim_state=None):
    claim_state = claim_state or _claim()
    return {
        "status": "completed",
        "execution_mode": "article_history_merit",
        "result": {
            "claim_ids": [claim_state["id"]],
        },
        "intelligence_refresh": {
            "status": "ready",
            "claim_states": [claim_state],
            "story_states": [],
        },
    }


class BackgroundMultimodelRuntimeTests(unittest.TestCase):
    def test_all_specialized_features_default_off(self):
        plan = build_background_multimodel_plan(
            result=_result(),
            connection_factory=lambda: None,
            env_getter=_env({}),
        )

        self.assertEqual(
            plan["version"],
            BACKGROUND_MULTIMODEL_PLAN_VERSION,
        )
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["items"], [])
        self.assertEqual(plan["task_counts"], {})
        self.assertFalse(plan["policy"]["provider_call_performed"])
        self.assertFalse(plan["policy"]["affects_live_merit"])

    def test_hosted_embedding_is_planned_for_structured_claim(self):
        plan = build_background_multimodel_plan(
            result=_result(),
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_EMBEDDING_RUNTIME_ENABLED": "1",
                }
            ),
        )

        self.assertEqual(
            [item["task_id"] for item in plan["items"]],
            [RETRIEVAL_EMBEDDING],
        )
        self.assertEqual(
            plan["task_counts"][RETRIEVAL_EMBEDDING],
            1,
        )

    def test_local_embedding_is_fallback_when_hosted_runtime_is_off(self):
        plan = build_background_multimodel_plan(
            result=_result(),
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_LOCAL_EMBEDDING_RUNTIME_ENABLED": "true",
                }
            ),
        )

        self.assertEqual(
            [item["task_id"] for item in plan["items"]],
            [LOCAL_RETRIEVAL_EMBEDDING],
        )

    def test_conflicting_claim_gets_gemma_shadow_when_enabled(self):
        plan = build_background_multimodel_plan(
            result=_result(
                _claim(
                    state="claim_conflict_present",
                )
            ),
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_GEMMA_SHADOW_ENABLED": "1",
                }
            ),
        )

        self.assertEqual(
            [item["task_id"] for item in plan["items"]],
            [CLAIM_SHADOW_REVIEW],
        )

    @patch(
        "app.intelligence.background_multimodel_runtime.build_claim_support_graph"
    )
    def test_high_impact_conflict_uses_deep_shadow_research_max_and_explicit_web(
        self,
        support_graph,
    ):
        support_graph.return_value = {
            "status": "ok",
            "counts": {
                "qualified_verified_independent_pairs": 0,
            },
        }
        result = _result(
            _claim(
                state="adjudication_history_conflict",
            )
        )
        result["result"]["high_impact_claim_ids"] = ["claim-1"]
        result["result"]["direct_web_inspection_claim_ids"] = ["claim-1"]

        plan = build_background_multimodel_plan(
            result=result,
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_GEMMA_SHADOW_ENABLED": "1",
                    "SPORTABASE_PROVENANCE_AGENTS_ENABLED": "1",
                }
            ),
        )

        task_ids = [item["task_id"] for item in plan["items"]]
        self.assertEqual(
            task_ids,
            [
                PROVENANCE_RESEARCH_MAX,
                AGENTIC_PROVENANCE_INSPECTION,
                CLAIM_DEEP_SHADOW_REVIEW,
            ],
        )
        self.assertNotIn(PROVENANCE_RESEARCH, task_ids)
        self.assertNotIn(CLAIM_SHADOW_REVIEW, task_ids)

    @patch(
        "app.intelligence.background_multimodel_runtime.build_claim_support_graph"
    )
    def test_verified_independence_pair_suppresses_normal_research(
        self,
        support_graph,
    ):
        support_graph.return_value = {
            "status": "ok",
            "counts": {
                "qualified_verified_independent_pairs": 1,
                "distinct_sources": 8,
            },
        }

        plan = build_background_multimodel_plan(
            result=_result(
                _claim(
                    freshness="stale",
                )
            ),
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_PROVENANCE_AGENTS_ENABLED": "1",
                }
            ),
        )

        self.assertEqual(plan["items"], [])
        self.assertTrue(
            plan["policy"]["distinct_sources_do_not_imply_independence"]
        )
        self.assertTrue(
            plan["policy"]["verified_independence_floor_only"]
        )

    def test_unstructured_claim_cannot_trigger_background_specialists(self):
        plan = build_background_multimodel_plan(
            result=_result(
                _claim(
                    structured=False,
                    state="claim_conflict_present",
                    freshness="stale",
                )
            ),
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_EMBEDDING_RUNTIME_ENABLED": "1",
                    "SPORTABASE_GEMMA_SHADOW_ENABLED": "1",
                    "SPORTABASE_PROVENANCE_AGENTS_ENABLED": "1",
                }
            ),
        )

        self.assertEqual(plan["items"], [])

    def test_non_completed_job_is_not_planned(self):
        plan = build_background_multimodel_plan(
            result={"status": "retry_scheduled"},
            connection_factory=lambda: None,
            env_getter=_env(
                {
                    "SPORTABASE_EMBEDDING_RUNTIME_ENABLED": "1",
                }
            ),
        )

        self.assertEqual(plan["status"], "not_applicable")
        self.assertEqual(plan["items"], [])

    def test_completed_job_persists_only_privacy_minimized_plan_summary(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "jobs.sqlite3"

            def factory():
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                return conn

            conn = factory()
            try:
                conn.execute(
                    """
                    CREATE TABLE browser_capture_automation_jobs (
                      id TEXT PRIMARY KEY,
                      status TEXT NOT NULL,
                      result_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO browser_capture_automation_jobs "
                    "(id, status, result_json) VALUES (?, ?, ?)",
                    (
                        "job-1",
                        "completed",
                        json.dumps({"existing": True}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            result = _result()
            result["job"] = {
                "id": "job-1",
                "status": "completed",
            }

            output = plan_completed_job_specialized_ai(
                result=result,
                connection_factory=factory,
                env_getter=_env(
                    {
                        "SPORTABASE_EMBEDDING_RUNTIME_ENABLED": "1",
                    }
                ),
            )

            self.assertEqual(
                output["specialized_ai_plan"]["items"][0]["subject_id"],
                "claim-1",
            )
            self.assertNotIn(
                "items",
                output["result"]["specialized_ai_plan"],
            )

            conn = factory()
            try:
                row = conn.execute(
                    "SELECT result_json FROM browser_capture_automation_jobs "
                    "WHERE id = ?",
                    ("job-1",),
                ).fetchone()
            finally:
                conn.close()

            persisted = json.loads(row["result_json"])["specialized_ai_plan"]
            self.assertEqual(
                persisted["task_counts"][RETRIEVAL_EMBEDDING],
                1,
            )
            self.assertNotIn("items", persisted)
            self.assertNotIn("claim-1", json.dumps(persisted))


if __name__ == "__main__":
    unittest.main()
