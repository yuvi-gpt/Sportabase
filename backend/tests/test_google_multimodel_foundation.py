import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.models import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_GENERATION_MODEL_IDS,
    GEMMA_HOSTED_MODEL_IDS,
    HOSTED_GENERATION_MODEL_IDS,
    MODEL_REGISTRY_VERSION,
)
from app.ai.resources import (
    AI_RESOURCE_REGISTRY_VERSION,
    EMBEDDING,
    GENERATION,
    LOCAL_EMBEDDING,
    MANAGED_AGENT,
    resource_spec,
    registered_resource_ids,
)
from app.ai.router import (
    RESOURCE_ROUTER_VERSION,
    resolve_model_for_task,
    route_task,
)
from app.ai.tasks import (
    AGENTIC_PROVENANCE_AGENT,
    AGENTIC_PROVENANCE_INSPECTION,
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    ARTICLE_TLDR,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    COMPATIBILITY_GENERATION_FALLBACK,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
    EVIDENCE_SEMANTICS_GENERATION_MODEL,
    FAST_UTILITY_GENERATION_MODEL,
    GENERAL_ANALYSIS_GENERATION_MODEL,
    GEMMA_DEEP_SHADOW_MODEL,
    GEMMA_SHADOW_MODEL,
    HOSTED_RETRIEVAL_EMBEDDING_MODEL,
    LOCAL_RETRIEVAL_EMBEDDING,
    LOCAL_RETRIEVAL_EMBEDDING_MODEL,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_AGENT,
    PROVENANCE_RESEARCH_MAX,
    PROVENANCE_RESEARCH_MAX_AGENT,
    RETRIEVAL_EMBEDDING,
    TASK_REGISTRY_VERSION,
    VIDEO_ANALYSIS,
    registered_task_ids,
    task_policy,
)


EXPECTED_RESOURCES = (
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemini-embedding-2",
    "antigravity-preview-05-2026",
    "deep-research-preview-04-2026",
    "deep-research-max-preview-04-2026",
    "google/embeddinggemma-300M",
)

EXPECTED_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
    CLAIM_SHADOW_REVIEW,
    CLAIM_DEEP_SHADOW_REVIEW,
    RETRIEVAL_EMBEDDING,
    LOCAL_RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    AGENTIC_PROVENANCE_INSPECTION,
)

EXPECTED_PRIMARY = {
    ARTICLE_TLDR: "gemini-3.5-flash-lite",
    ARTICLE_CLASSIFIER: "gemini-3.5-flash-lite",
    ARTICLE_SINGLE_PASS: "gemini-3.6-flash",
    VIDEO_ANALYSIS: "gemini-3.6-flash",
    CORROBORATION_CANDIDATE_SEMANTICS: "gemini-3.5-flash",
    CORROBORATION_COLLECTION_SEMANTICS: "gemini-3.5-flash",
    CLAIM_SHADOW_REVIEW: "gemma-4-26b-a4b-it",
    CLAIM_DEEP_SHADOW_REVIEW: "gemma-4-31b-it",
    RETRIEVAL_EMBEDDING: "gemini-embedding-2",
    LOCAL_RETRIEVAL_EMBEDDING: "google/embeddinggemma-300M",
    PROVENANCE_RESEARCH: "deep-research-preview-04-2026",
    PROVENANCE_RESEARCH_MAX: "deep-research-max-preview-04-2026",
    AGENTIC_PROVENANCE_INSPECTION: "antigravity-preview-05-2026",
}


class GoogleAIResourceFoundationTests(unittest.TestCase):
    def test_registry_versions_are_explicit(self):
        self.assertEqual(
            AI_RESOURCE_REGISTRY_VERSION,
            "google-ai-resource-registry-v2",
        )
        self.assertEqual(
            MODEL_REGISTRY_VERSION,
            "google-generation-model-registry-v3",
        )
        self.assertEqual(
            TASK_REGISTRY_VERSION,
            "ai-task-registry-v5",
        )
        self.assertEqual(
            RESOURCE_ROUTER_VERSION,
            "google-ai-resource-router-v2",
        )

    def test_resource_registry_is_exact(self):
        self.assertEqual(
            registered_resource_ids(),
            EXPECTED_RESOURCES,
        )

    def test_generation_pool_contains_gemini_and_gemma(self):
        self.assertEqual(
            GEMINI_GENERATION_MODEL_IDS,
            EXPECTED_RESOURCES[:8],
        )
        self.assertEqual(
            GEMMA_HOSTED_MODEL_IDS,
            EXPECTED_RESOURCES[8:10],
        )
        self.assertEqual(
            HOSTED_GENERATION_MODEL_IDS,
            EXPECTED_RESOURCES[:10],
        )

    def test_named_model_roles_are_explicit(self):
        self.assertEqual(
            DEFAULT_GEMINI_MODEL,
            "gemini-3.5-flash",
        )
        self.assertEqual(
            COMPATIBILITY_GENERATION_FALLBACK,
            DEFAULT_GEMINI_MODEL,
        )
        self.assertEqual(
            FAST_UTILITY_GENERATION_MODEL,
            "gemini-3.5-flash-lite",
        )
        self.assertEqual(
            GENERAL_ANALYSIS_GENERATION_MODEL,
            "gemini-3.6-flash",
        )
        self.assertEqual(
            EVIDENCE_SEMANTICS_GENERATION_MODEL,
            "gemini-3.5-flash",
        )
        self.assertEqual(
            GEMMA_SHADOW_MODEL,
            "gemma-4-26b-a4b-it",
        )
        self.assertEqual(
            GEMMA_DEEP_SHADOW_MODEL,
            "gemma-4-31b-it",
        )
        self.assertEqual(
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
            "gemini-embedding-2",
        )
        self.assertEqual(
            LOCAL_RETRIEVAL_EMBEDDING_MODEL,
            "google/embeddinggemma-300M",
        )
        self.assertEqual(
            PROVENANCE_RESEARCH_AGENT,
            "deep-research-preview-04-2026",
        )
        self.assertEqual(
            PROVENANCE_RESEARCH_MAX_AGENT,
            "deep-research-max-preview-04-2026",
        )
        self.assertEqual(
            AGENTIC_PROVENANCE_AGENT,
            "antigravity-preview-05-2026",
        )

    def test_task_registry_is_exact_and_production_routable(self):
        self.assertEqual(
            registered_task_ids(),
            EXPECTED_TASKS,
        )

        for task_id, expected_resource in EXPECTED_PRIMARY.items():
            with self.subTest(task=task_id):
                policy = task_policy(task_id)
                route = route_task(task_id)

                self.assertTrue(policy.production_enabled)
                self.assertEqual(
                    policy.primary_resource_id,
                    expected_resource,
                )
                self.assertEqual(
                    route.resource_id,
                    expected_resource,
                )
                self.assertEqual(
                    route.selection_source,
                    "task_primary",
                )

    def test_generation_tasks_use_expected_resource_kinds(self):
        for task_id in (
            ARTICLE_TLDR,
            ARTICLE_CLASSIFIER,
            ARTICLE_SINGLE_PASS,
            VIDEO_ANALYSIS,
            CORROBORATION_CANDIDATE_SEMANTICS,
            CORROBORATION_COLLECTION_SEMANTICS,
            CLAIM_SHADOW_REVIEW,
            CLAIM_DEEP_SHADOW_REVIEW,
        ):
            with self.subTest(task=task_id):
                self.assertEqual(
                    route_task(task_id).resource_kind,
                    GENERATION,
                )

    def test_specialized_tasks_use_separate_resource_kinds(self):
        self.assertEqual(
            route_task(RETRIEVAL_EMBEDDING).resource_kind,
            EMBEDDING,
        )
        self.assertEqual(
            route_task(LOCAL_RETRIEVAL_EMBEDDING).resource_kind,
            LOCAL_EMBEDDING,
        )

        for task_id in (
            PROVENANCE_RESEARCH,
            PROVENANCE_RESEARCH_MAX,
            AGENTIC_PROVENANCE_INSPECTION,
        ):
            with self.subTest(task=task_id):
                self.assertEqual(
                    route_task(task_id).resource_kind,
                    MANAGED_AGENT,
                )

    def test_gemma_shadow_tasks_are_restricted_to_gemma(self):
        for task_id in (
            CLAIM_SHADOW_REVIEW,
            CLAIM_DEEP_SHADOW_REVIEW,
        ):
            policy = task_policy(task_id)
            self.assertEqual(
                policy.evaluation_resource_ids,
                GEMMA_HOSTED_MODEL_IDS,
            )

            with self.assertRaises(ValueError):
                route_task(
                    task_id,
                    requested_resource_id="gemini-3.7-flash",
                )

    def test_managed_agent_tasks_allow_controlled_agent_override(self):
        route = route_task(
            PROVENANCE_RESEARCH,
            requested_resource_id=AGENTIC_PROVENANCE_AGENT,
        )
        self.assertEqual(
            route.resource_id,
            AGENTIC_PROVENANCE_AGENT,
        )
        self.assertEqual(
            route.resource_kind,
            MANAGED_AGENT,
        )
        self.assertEqual(
            route.selection_source,
            "explicit_evaluation_override",
        )

    def test_resource_kinds_cannot_cross_task_boundaries(self):
        with self.assertRaises(ValueError):
            route_task(
                RETRIEVAL_EMBEDDING,
                requested_resource_id=GEMMA_SHADOW_MODEL,
            )

        with self.assertRaises(ValueError):
            route_task(
                PROVENANCE_RESEARCH,
                requested_resource_id=HOSTED_RETRIEVAL_EMBEDDING_MODEL,
            )

    def test_model_resolver_returns_specialized_primaries(self):
        for task_id, expected_resource in EXPECTED_PRIMARY.items():
            with self.subTest(task=task_id):
                self.assertEqual(
                    resolve_model_for_task(task_id),
                    expected_resource,
                )

    def test_hosted_specialized_resources_remain_capacity_gated(self):
        for resource_id in (
            GEMMA_SHADOW_MODEL,
            GEMMA_DEEP_SHADOW_MODEL,
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
            PROVENANCE_RESEARCH_AGENT,
            PROVENANCE_RESEARCH_MAX_AGENT,
            AGENTIC_PROVENANCE_AGENT,
        ):
            with self.subTest(resource=resource_id):
                self.assertTrue(
                    resource_spec(
                        resource_id
                    ).requires_project_capacity_config
                )

        self.assertFalse(
            resource_spec(
                LOCAL_RETRIEVAL_EMBEDDING_MODEL
            ).requires_project_capacity_config
        )

    def test_unknown_resources_and_tasks_fail_closed(self):
        with self.assertRaises(KeyError):
            resource_spec("not-a-real-resource")

        with self.assertRaises(KeyError):
            route_task("not-a-real-task")


if __name__ == "__main__":
    unittest.main()
