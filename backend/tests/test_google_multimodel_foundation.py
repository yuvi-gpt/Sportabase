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
    FREE_GEMINI_MODEL_IDS,
    MODEL_REGISTRY_VERSION,
    model_spec,
    registered_model_ids,
)
from app.ai.quota import (
    capacity_policy_for_model,
)
from app.ai.router import (
    MODEL_ROUTER_VERSION,
    resolve_model_for_task,
    route_task,
)
from app.ai.tasks import (
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    ARTICLE_TLDR,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
    TASK_REGISTRY_VERSION,
    VIDEO_ANALYSIS,
    registered_task_ids,
    task_policy,
)


EXPECTED_FREE_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)

EXPECTED_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_SINGLE_PASS,
    ARTICLE_CLASSIFIER,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
)


class GoogleMultimodelFoundationTests(
    unittest.TestCase
):
    def test_registry_versions_are_explicit(self):
        self.assertEqual(
            MODEL_REGISTRY_VERSION,
            "google-model-registry-v1",
        )
        self.assertEqual(
            TASK_REGISTRY_VERSION,
            "ai-task-registry-v1",
        )
        self.assertEqual(
            MODEL_ROUTER_VERSION,
            "google-model-router-v1",
        )

    def test_free_model_pool_is_exact_and_registered(self):
        self.assertEqual(
            FREE_GEMINI_MODEL_IDS,
            EXPECTED_FREE_MODELS,
        )
        self.assertEqual(
            registered_model_ids(),
            EXPECTED_FREE_MODELS,
        )

        for model_id in EXPECTED_FREE_MODELS:
            with self.subTest(
                model=model_id
            ):
                spec = model_spec(
                    model_id
                )
                self.assertEqual(
                    spec.provider,
                    "google",
                )
                self.assertEqual(
                    spec.model_family,
                    "gemini",
                )
                self.assertTrue(
                    spec.stable
                )
                self.assertTrue(
                    spec.free_pool
                )

    def test_default_model_preserves_current_live_behavior(self):
        self.assertEqual(
            DEFAULT_GEMINI_MODEL,
            "gemini-3.5-flash",
        )

    def test_task_registry_is_exact_and_fail_closed(self):
        self.assertEqual(
            registered_task_ids(),
            EXPECTED_TASKS,
        )

        for task_id in EXPECTED_TASKS:
            with self.subTest(
                task=task_id
            ):
                policy = task_policy(
                    task_id
                )

                self.assertEqual(
                    policy.primary_model,
                    DEFAULT_GEMINI_MODEL,
                )
                self.assertEqual(
                    policy.evaluation_models,
                    EXPECTED_FREE_MODELS,
                )
                self.assertFalse(
                    policy.automatic_fallback_enabled
                )
                self.assertEqual(
                    policy.fallback_models,
                    (),
                )

    def test_default_router_never_changes_live_primary(self):
        for task_id in EXPECTED_TASKS:
            with self.subTest(
                task=task_id
            ):
                route = route_task(
                    task_id
                )

                self.assertEqual(
                    route.model_id,
                    "gemini-3.5-flash",
                )
                self.assertEqual(
                    route.selection_source,
                    "task_primary",
                )
                self.assertFalse(
                    route.automatic_fallback_enabled
                )
                self.assertEqual(
                    route.fallback_models,
                    (),
                )

    def test_explicit_evaluation_override_is_bounded(self):
        route = route_task(
            ARTICLE_CLASSIFIER,
            requested_model=(
                "gemini-3.5-flash-lite"
            ),
        )

        self.assertEqual(
            route.model_id,
            "gemini-3.5-flash-lite",
        )
        self.assertEqual(
            route.selection_source,
            "explicit_evaluation_override",
        )
        self.assertFalse(
            route.automatic_fallback_enabled
        )

    def test_resolver_returns_only_registered_models(self):
        for task_id in EXPECTED_TASKS:
            with self.subTest(
                task=task_id
            ):
                model_id = (
                    resolve_model_for_task(
                        task_id
                    )
                )
                self.assertIn(
                    model_id,
                    registered_model_ids(),
                )

    def test_each_registered_model_integrates_with_capacity_policy(self):
        for model_id in EXPECTED_FREE_MODELS:
            with self.subTest(
                model=model_id
            ):
                policy = (
                    capacity_policy_for_model(
                        model_id
                    )
                )
                self.assertEqual(
                    policy.model,
                    model_id,
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

    def test_unknown_task_and_model_fail_closed(self):
        with self.assertRaises(
            KeyError
        ):
            route_task(
                "not-a-real-task"
            )

        with self.assertRaises(
            KeyError
        ):
            route_task(
                ARTICLE_TLDR,
                requested_model=(
                    "gemini-not-real"
                ),
            )


if __name__ == "__main__":
    unittest.main()
