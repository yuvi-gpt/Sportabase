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


from app.ai.models import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_GENERATION_MODEL_IDS,
    GEMMA_HOSTED_MODEL_IDS,
    HOSTED_GENERATION_MODEL_IDS,
    MODEL_REGISTRY_VERSION,
)
from app.ai.quota import (
    capacity_policy_for_model,
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
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    ARTICLE_TLDR,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
    PROVENANCE_RESEARCH,
    RETRIEVAL_EMBEDDING,
    TASK_REGISTRY_VERSION,
    VIDEO_ANALYSIS,
    registered_task_ids,
    task_policy,
)


EXPECTED_RESOURCES = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemini-embedding-2",
    "antigravity-preview-05-2026",
    "deep-research-preview-04-2026",
    "deep-research-max-preview-04-2026",
    "google/embeddinggemma-300M",
)

LIVE_GENERATION_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_SINGLE_PASS,
    ARTICLE_CLASSIFIER,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
)

EXPECTED_TASKS = (
    *LIVE_GENERATION_TASKS,
    RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
)


class GoogleAIResourceFoundationTests(
    unittest.TestCase
):
    def test_registry_versions_are_explicit(self):
        self.assertEqual(
            AI_RESOURCE_REGISTRY_VERSION,
            "google-ai-resource-registry-v1",
        )
        self.assertEqual(
            MODEL_REGISTRY_VERSION,
            "google-generation-model-registry-v2",
        )
        self.assertEqual(
            TASK_REGISTRY_VERSION,
            "ai-task-registry-v2",
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
            (
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
            ),
        )
        self.assertEqual(
            GEMMA_HOSTED_MODEL_IDS,
            (
                "gemma-4-31b-it",
                "gemma-4-26b-a4b-it",
            ),
        )
        self.assertEqual(
            HOSTED_GENERATION_MODEL_IDS,
            (
                *GEMINI_GENERATION_MODEL_IDS,
                *GEMMA_HOSTED_MODEL_IDS,
            ),
        )

    def test_default_model_preserves_current_live_behavior(self):
        self.assertEqual(
            DEFAULT_GEMINI_MODEL,
            "gemini-3.5-flash",
        )
        current = resource_spec(
            DEFAULT_GEMINI_MODEL
        )
        self.assertFalse(
            current.requires_project_capacity_config
        )

    def test_new_hosted_resources_require_project_capacity_config(self):
        for resource_id in EXPECTED_RESOURCES:
            spec = resource_spec(
                resource_id
            )

            if resource_id == DEFAULT_GEMINI_MODEL:
                continue

            if spec.hosted:
                with self.subTest(
                    resource=resource_id
                ):
                    self.assertTrue(
                        spec.requires_project_capacity_config
                    )

    def test_specialized_resource_kinds_are_separate(self):
        self.assertEqual(
            resource_spec(
                "gemini-embedding-2"
            ).resource_kind,
            EMBEDDING,
        )
        self.assertEqual(
            resource_spec(
                "google/embeddinggemma-300M"
            ).resource_kind,
            LOCAL_EMBEDDING,
        )
        self.assertEqual(
            resource_spec(
                "antigravity-preview-05-2026"
            ).resource_kind,
            MANAGED_AGENT,
        )
        self.assertEqual(
            resource_spec(
                "gemma-4-31b-it"
            ).resource_kind,
            GENERATION,
        )

    def test_task_registry_is_exact(self):
        self.assertEqual(
            registered_task_ids(),
            EXPECTED_TASKS,
        )

    def test_all_current_live_tasks_remain_on_35_flash(self):
        for task_id in LIVE_GENERATION_TASKS:
            with self.subTest(
                task=task_id
            ):
                policy = task_policy(
                    task_id
                )
                self.assertTrue(
                    policy.production_enabled
                )
                self.assertEqual(
                    policy.primary_resource_id,
                    DEFAULT_GEMINI_MODEL,
                )
                self.assertFalse(
                    policy.automatic_fallback_enabled
                )
                self.assertEqual(
                    policy.fallback_resource_ids,
                    (),
                )

                route = route_task(
                    task_id
                )
                self.assertEqual(
                    route.resource_id,
                    DEFAULT_GEMINI_MODEL,
                )
                self.assertEqual(
                    route.selection_source,
                    "task_primary",
                )
                self.assertFalse(
                    route.requires_project_capacity_config
                )

    def test_generation_evaluation_can_select_hosted_gemma(self):
        route = route_task(
            ARTICLE_CLASSIFIER,
            requested_resource_id=(
                "gemma-4-26b-a4b-it"
            ),
        )
        self.assertEqual(
            route.resource_id,
            "gemma-4-26b-a4b-it",
        )
        self.assertEqual(
            route.selection_source,
            "explicit_evaluation_override",
        )
        self.assertTrue(
            route.requires_project_capacity_config
        )
        self.assertFalse(
            route.automatic_fallback_enabled
        )

    def test_embedding_task_is_evaluation_only(self):
        policy = task_policy(
            RETRIEVAL_EMBEDDING
        )
        self.assertFalse(
            policy.production_enabled
        )
        self.assertIsNone(
            policy.primary_resource_id
        )

        with self.assertRaises(
            RuntimeError
        ):
            route_task(
                RETRIEVAL_EMBEDDING
            )

        hosted = route_task(
            RETRIEVAL_EMBEDDING,
            requested_resource_id=(
                "gemini-embedding-2"
            ),
        )
        local = route_task(
            RETRIEVAL_EMBEDDING,
            requested_resource_id=(
                "google/embeddinggemma-300M"
            ),
        )

        self.assertEqual(
            hosted.resource_kind,
            EMBEDDING,
        )
        self.assertTrue(
            hosted.requires_project_capacity_config
        )
        self.assertEqual(
            local.resource_kind,
            LOCAL_EMBEDDING,
        )
        self.assertFalse(
            local.requires_project_capacity_config
        )

    def test_provenance_agents_are_evaluation_only(self):
        policy = task_policy(
            PROVENANCE_RESEARCH
        )
        self.assertFalse(
            policy.production_enabled
        )
        self.assertIsNone(
            policy.primary_resource_id
        )

        with self.assertRaises(
            RuntimeError
        ):
            route_task(
                PROVENANCE_RESEARCH
            )

        route = route_task(
            PROVENANCE_RESEARCH,
            requested_resource_id=(
                "antigravity-preview-05-2026"
            ),
        )
        self.assertEqual(
            route.resource_kind,
            MANAGED_AGENT,
        )
        self.assertTrue(
            route.requires_project_capacity_config
        )

    def test_resource_kinds_cannot_cross_task_boundaries(self):
        with self.assertRaises(
            ValueError
        ):
            route_task(
                ARTICLE_TLDR,
                requested_resource_id=(
                    "antigravity-preview-05-2026"
                ),
            )

        with self.assertRaises(
            ValueError
        ):
            route_task(
                RETRIEVAL_EMBEDDING,
                requested_resource_id=(
                    "gemma-4-31b-it"
                ),
            )

    def test_current_default_still_integrates_with_existing_quota_policy(self):
        policy = capacity_policy_for_model(
            DEFAULT_GEMINI_MODEL
        )
        self.assertEqual(
            policy.model,
            DEFAULT_GEMINI_MODEL,
        )
        self.assertGreater(
            policy.provider_rpm,
            0,
        )
        self.assertGreater(
            policy.usable_tpm,
            0,
        )
        self.assertGreater(
            policy.usable_rpd,
            0,
        )

    def test_model_resolver_remains_generation_only(self):
        self.assertEqual(
            resolve_model_for_task(
                ARTICLE_SINGLE_PASS
            ),
            DEFAULT_GEMINI_MODEL,
        )

        with self.assertRaises(
            RuntimeError
        ):
            resolve_model_for_task(
                RETRIEVAL_EMBEDDING
            )

    def test_unknown_resources_and_tasks_fail_closed(self):
        with self.assertRaises(
            KeyError
        ):
            resource_spec(
                "not-a-real-resource"
            )

        with self.assertRaises(
            KeyError
        ):
            route_task(
                "not-a-real-task"
            )


if __name__ == "__main__":
    unittest.main()
