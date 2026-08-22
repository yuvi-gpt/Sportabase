from __future__ import annotations

import unittest

from app.ai.orchestration import (
    MULTIMODEL_ORCHESTRATION_VERSION,
    build_specialized_ai_plan,
    execute_specialized_ai_plan,
)
from app.ai.tasks import (
    AGENTIC_PROVENANCE_INSPECTION,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    LOCAL_RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    RETRIEVAL_EMBEDDING,
)


class GoogleMultimodelOrchestrationTests(unittest.TestCase):
    def claim(
        self,
        claim_id: str,
        *,
        structured: bool = True,
        state: str = "claim_supported",
        freshness: str = "fresh",
    ) -> dict[str, object]:
        return {
            "id": claim_id,
            "status": "ready",
            "projection_state": state,
            "freshness_state": freshness,
            "structured_identity": structured,
        }

    def task_ids(self, plan):
        return [item["task_id"] for item in plan["items"]]

    def test_plain_structured_claim_only_indexes_when_enabled(self):
        plan = build_specialized_ai_plan(
            claim_states=[self.claim("claim-1")],
            hosted_embeddings_enabled=True,
            local_embeddings_enabled=True,
            gemma_shadow_enabled=True,
            provenance_agents_enabled=True,
        )

        self.assertEqual(plan["version"], MULTIMODEL_ORCHESTRATION_VERSION)
        self.assertEqual(self.task_ids(plan), [RETRIEVAL_EMBEDDING])
        self.assertEqual(plan["counts"]["embedding_items"], 1)
        self.assertEqual(plan["counts"]["shadow_items"], 0)
        self.assertEqual(plan["counts"]["provenance_items"], 0)
        self.assertFalse(plan["policy"]["provider_call_performed"])

    def test_local_embedding_is_used_when_hosted_embedding_is_off(self):
        plan = build_specialized_ai_plan(
            claim_states=[self.claim("claim-1")],
            hosted_embeddings_enabled=False,
            local_embeddings_enabled=True,
        )

        self.assertEqual(self.task_ids(plan), [LOCAL_RETRIEVAL_EMBEDDING])

    def test_unstructured_claim_cannot_trigger_specialized_ai(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    structured=False,
                    state="claim_conflict_present",
                    freshness="stale",
                )
            ],
            hosted_embeddings_enabled=True,
            gemma_shadow_enabled=True,
            provenance_agents_enabled=True,
            high_impact_claim_ids=["claim-1"],
            direct_web_inspection_claim_ids=["claim-1"],
        )

        self.assertEqual(plan["items"], [])

    def test_conflict_triggers_normal_gemma_shadow(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="claim_conflict_present",
                )
            ],
            gemma_shadow_enabled=True,
        )

        self.assertEqual(self.task_ids(plan), [CLAIM_SHADOW_REVIEW])
        self.assertTrue(plan["items"][0]["background_only"])
        self.assertTrue(plan["items"][0]["provider_optional"])

    def test_high_impact_conflict_escalates_to_deep_shadow_and_research_max(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="adjudication_history_conflict",
                )
            ],
            hosted_embeddings_enabled=True,
            gemma_shadow_enabled=True,
            provenance_agents_enabled=True,
            high_impact_claim_ids=["claim-1"],
            independent_source_counts={"claim-1": 1},
        )

        task_ids = self.task_ids(plan)
        self.assertEqual(
            task_ids,
            [
                PROVENANCE_RESEARCH_MAX,
                CLAIM_DEEP_SHADOW_REVIEW,
                RETRIEVAL_EMBEDDING,
            ],
        )
        self.assertNotIn(CLAIM_SHADOW_REVIEW, task_ids)
        self.assertNotIn(PROVENANCE_RESEARCH, task_ids)

    def test_enough_independent_sources_suppress_provenance_research(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="claim_conflict_present",
                )
            ],
            provenance_agents_enabled=True,
            independent_source_counts={"claim-1": 4},
            max_research_independent_sources=1,
        )

        self.assertEqual(plan["items"], [])

    def test_stale_claim_with_low_independent_support_gets_normal_research(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    freshness="stale",
                )
            ],
            provenance_agents_enabled=True,
            independent_source_counts={"claim-1": 0},
        )

        self.assertEqual(self.task_ids(plan), [PROVENANCE_RESEARCH])

    def test_direct_web_inspection_is_explicit_not_automatic(self):
        without_request = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="claim_conflict_present",
                )
            ],
            provenance_agents_enabled=True,
            independent_source_counts={"claim-1": 5},
        )
        with_request = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="claim_conflict_present",
                )
            ],
            provenance_agents_enabled=True,
            independent_source_counts={"claim-1": 5},
            direct_web_inspection_claim_ids=["claim-1"],
        )

        self.assertNotIn(
            AGENTIC_PROVENANCE_INSPECTION,
            self.task_ids(without_request),
        )
        self.assertEqual(
            self.task_ids(with_request),
            [AGENTIC_PROVENANCE_INSPECTION],
        )

    def test_all_specialized_features_default_to_no_work(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim(
                    "claim-1",
                    state="claim_conflict_present",
                    freshness="stale",
                )
            ],
            high_impact_claim_ids=["claim-1"],
            direct_web_inspection_claim_ids=["claim-1"],
        )

        self.assertEqual(plan["items"], [])
        self.assertFalse(plan["policy"]["affects_live_merit"])

    def test_duplicate_claim_rows_are_deduplicated_and_bounded(self):
        plan = build_specialized_ai_plan(
            claim_states=[
                self.claim("claim-1"),
                self.claim("claim-1"),
            ],
            hosted_embeddings_enabled=True,
        )

        self.assertEqual(plan["counts"]["claims_considered"], 1)
        self.assertEqual(len(plan["items"]), 1)

    def test_execution_is_disabled_by_default(self):
        plan = build_specialized_ai_plan(
            claim_states=[self.claim("claim-1")],
            hosted_embeddings_enabled=True,
        )

        with self.assertRaisesRegex(RuntimeError, "disabled by default"):
            execute_specialized_ai_plan(
                plan,
                executors={},
            )

    def test_execution_requires_explicit_task_executor(self):
        plan = build_specialized_ai_plan(
            claim_states=[self.claim("claim-1")],
            hosted_embeddings_enabled=True,
        )

        result = execute_specialized_ai_plan(
            plan,
            executors={},
            allow_provider_execution=True,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["counts"]["blocked"], 1)
        self.assertEqual(
            result["observations"][0]["failure_type"],
            "executor_unavailable",
        )

    def test_execution_uses_only_injected_executor(self):
        plan = build_specialized_ai_plan(
            claim_states=[self.claim("claim-1")],
            hosted_embeddings_enabled=True,
        )
        calls = []

        def executor(item):
            calls.append(dict(item))
            return {"ok": True}

        result = execute_specialized_ai_plan(
            plan,
            executors={RETRIEVAL_EMBEDDING: executor},
            allow_provider_execution=True,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["subject_id"], "claim-1")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["counts"]["completed"], 1)
        self.assertFalse(result["policy"]["affects_live_merit"])


if __name__ == "__main__":
    unittest.main()
