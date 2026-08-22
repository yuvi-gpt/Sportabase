import sys
import unittest

from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.specialized_runtime import (
    SPECIALIZED_AI_RUNTIME_VERSION,
    SpecializedAIConfigurationError,
    SpecializedAIInputError,
    cancel_provenance_research,
    get_provenance_research_status,
    run_gemma_shadow_review,
    run_hosted_retrieval_embedding,
    run_local_retrieval_embedding,
    specialized_resource_enable_key,
    start_provenance_research,
)
from app.ai.tasks import (
    AGENTIC_PROVENANCE_AGENT,
    AGENTIC_PROVENANCE_INSPECTION,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    GEMMA_DEEP_SHADOW_MODEL,
    GEMMA_SHADOW_MODEL,
    HOSTED_RETRIEVAL_EMBEDDING_MODEL,
    LOCAL_RETRIEVAL_EMBEDDING_MODEL,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_AGENT,
    PROVENANCE_RESEARCH_MAX,
    PROVENANCE_RESEARCH_MAX_AGENT,
)


class _FakeModels:
    def __init__(self):
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        contents = list(kwargs["contents"])
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(
                    values=[
                        float(index + 1),
                        0.25,
                        -0.5,
                    ]
                )
                for index, _ in enumerate(contents)
            ]
        )


class _FakeInteractions:
    def __init__(self):
        self.create_calls = []
        self.get_calls = []
        self.cancel_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleNamespace(
            id="interaction-123",
            status="in_progress",
        )

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        content = SimpleNamespace(
            text="bounded research result"
        )
        step = SimpleNamespace(
            type="model_output",
            content=[content],
        )
        return SimpleNamespace(
            status="completed",
            steps=[step],
        )

    def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return None


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()
        self.interactions = _FakeInteractions()


class _FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, normalize_embeddings=False):
        self.calls.append(
            {
                "texts": list(texts),
                "normalize_embeddings": normalize_embeddings,
            }
        )
        return [
            [1.0, 0.0],
            [0.0, 1.0],
        ][: len(texts)]


def _env(values):
    return lambda name, default="": values.get(
        name,
        default,
    )


def _enabled_env(flag_name, resource_id):
    return {
        flag_name: "1",
        specialized_resource_enable_key(
            resource_id
        ): "1",
    }


class GoogleSpecializedRuntimeTests(unittest.TestCase):
    def test_version_is_explicit(self):
        self.assertEqual(
            SPECIALIZED_AI_RUNTIME_VERSION,
            "google-specialized-ai-runtime-v1",
        )

    def test_hosted_embedding_is_disabled_by_default(self):
        with self.assertRaises(
            SpecializedAIConfigurationError
        ):
            run_hosted_retrieval_embedding(
                client=_FakeClient(),
                texts=["alpha"],
                env_getter=_env({}),
            )

    def test_hosted_embedding_calls_gemini_embedding_2_when_enabled(self):
        client = _FakeClient()
        env = _enabled_env(
            "SPORTABASE_EMBEDDING_RUNTIME_ENABLED",
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
        )

        result = run_hosted_retrieval_embedding(
            client=client,
            texts=["alpha", "beta"],
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
            env_getter=_env(env),
        )

        self.assertEqual(
            result["status"],
            "completed",
        )
        self.assertEqual(
            result["resource_id"],
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
        )
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["dimension"], 3)
        self.assertEqual(len(result["vectors"]), 2)
        self.assertFalse(
            result["policy"]["input_text_returned"]
        )
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )

        call = client.models.calls[0]
        self.assertEqual(
            call["model"],
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
        )
        self.assertEqual(
            call["contents"],
            ["alpha", "beta"],
        )

    def test_hosted_embedding_rejects_unbounded_batches(self):
        env = _enabled_env(
            "SPORTABASE_EMBEDDING_RUNTIME_ENABLED",
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
        )

        with self.assertRaises(
            SpecializedAIInputError
        ):
            run_hosted_retrieval_embedding(
                client=_FakeClient(),
                texts=["x"] * 33,
                env_getter=_env(env),
            )

    def test_local_embeddinggemma_path_is_provider_free(self):
        encoder = _FakeEncoder()
        result = run_local_retrieval_embedding(
            texts=["alpha", "beta"],
            encoder=encoder,
            env_getter=_env(
                {
                    "SPORTABASE_LOCAL_EMBEDDING_RUNTIME_ENABLED": "true"
                }
            ),
        )

        self.assertEqual(
            result["resource_id"],
            LOCAL_RETRIEVAL_EMBEDDING_MODEL,
        )
        self.assertEqual(result["count"], 2)
        self.assertTrue(
            result["policy"]["hosted_provider_call"]
            is False
        )
        self.assertTrue(
            encoder.calls[0]["normalize_embeddings"]
        )

    def test_gemma_shadow_is_disabled_by_default(self):
        with self.assertRaises(
            SpecializedAIConfigurationError
        ):
            run_gemma_shadow_review(
                prompt="Review this structured claim.",
                generation_executor=lambda **kwargs: None,
                env_getter=_env({}),
            )

    def test_gemma_shadow_routes_26b_and_never_affects_merit(self):
        calls = []

        def executor(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                text="shadow disagreement"
            )

        env = _enabled_env(
            "SPORTABASE_GEMMA_SHADOW_ENABLED",
            GEMMA_SHADOW_MODEL,
        )

        result = run_gemma_shadow_review(
            prompt="Review this structured claim.",
            generation_executor=executor,
            env_getter=_env(env),
        )

        self.assertEqual(
            calls[0]["mode"],
            CLAIM_SHADOW_REVIEW,
        )
        self.assertEqual(
            calls[0]["model"],
            GEMMA_SHADOW_MODEL,
        )
        self.assertEqual(
            result["output_text"],
            "shadow disagreement",
        )
        self.assertTrue(
            result["policy"]["shadow_only"]
        )
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )
        self.assertFalse(
            result["policy"]["establishes_truth"]
        )

    def test_gemma_deep_shadow_routes_31b(self):
        calls = []

        def executor(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text="deep review")

        env = _enabled_env(
            "SPORTABASE_GEMMA_SHADOW_ENABLED",
            GEMMA_DEEP_SHADOW_MODEL,
        )

        result = run_gemma_shadow_review(
            prompt="Review this difficult claim.",
            generation_executor=executor,
            task_id=CLAIM_DEEP_SHADOW_REVIEW,
            env_getter=_env(env),
        )

        self.assertEqual(
            calls[0]["model"],
            GEMMA_DEEP_SHADOW_MODEL,
        )
        self.assertEqual(
            result["task_id"],
            CLAIM_DEEP_SHADOW_REVIEW,
        )

    def _agent_env(self, resource_id):
        return _enabled_env(
            "SPORTABASE_PROVENANCE_AGENTS_ENABLED",
            resource_id,
        )

    def test_deep_research_starts_only_as_background_interaction(self):
        client = _FakeClient()
        result = start_provenance_research(
            client=client,
            prompt="Research the provenance of this transfer claim.",
            task_id=PROVENANCE_RESEARCH,
            env_getter=_env(
                self._agent_env(
                    PROVENANCE_RESEARCH_AGENT
                )
            ),
        )

        call = client.interactions.create_calls[0]
        self.assertEqual(
            call["agent"],
            PROVENANCE_RESEARCH_AGENT,
        )
        self.assertTrue(call["background"])
        self.assertTrue(call["store"])
        self.assertEqual(
            call["agent_config"]["type"],
            "deep-research",
        )
        self.assertNotIn("environment", call)
        self.assertEqual(
            result["interaction_id"],
            "interaction-123",
        )
        self.assertTrue(
            result["policy"]["public_request_does_not_wait"]
        )
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )

    def test_deep_research_max_uses_max_agent(self):
        client = _FakeClient()
        start_provenance_research(
            client=client,
            prompt="Research this complex provenance graph.",
            task_id=PROVENANCE_RESEARCH_MAX,
            env_getter=_env(
                self._agent_env(
                    PROVENANCE_RESEARCH_MAX_AGENT
                )
            ),
        )

        self.assertEqual(
            client.interactions.create_calls[0]["agent"],
            PROVENANCE_RESEARCH_MAX_AGENT,
        )

    def test_antigravity_uses_remote_environment_and_bounded_budget(self):
        client = _FakeClient()
        start_provenance_research(
            client=client,
            prompt="Inspect source provenance and public web context.",
            task_id=AGENTIC_PROVENANCE_INSPECTION,
            max_total_tokens=999999,
            env_getter=_env(
                self._agent_env(
                    AGENTIC_PROVENANCE_AGENT
                )
            ),
        )

        call = client.interactions.create_calls[0]
        self.assertEqual(
            call["agent"],
            AGENTIC_PROVENANCE_AGENT,
        )
        self.assertEqual(
            call["environment"],
            "remote",
        )
        self.assertEqual(
            call["agent_config"]["type"],
            "antigravity",
        )
        self.assertEqual(
            call["agent_config"]["max_total_tokens"],
            100000,
        )

    def test_agent_runtime_does_not_fallback_when_resource_disabled(self):
        env = {
            "SPORTABASE_PROVENANCE_AGENTS_ENABLED": "1"
        }

        with self.assertRaises(
            SpecializedAIConfigurationError
        ):
            start_provenance_research(
                client=_FakeClient(),
                prompt="Research this claim.",
                task_id=PROVENANCE_RESEARCH,
                env_getter=_env(env),
            )

    def test_agent_status_and_cancellation_are_explicit(self):
        client = _FakeClient()

        status = get_provenance_research_status(
            client=client,
            interaction_id="interaction-123",
        )
        cancelled = cancel_provenance_research(
            client=client,
            interaction_id="interaction-123",
        )

        self.assertEqual(
            status["status"],
            "completed",
        )
        self.assertEqual(
            status["output_text"],
            "bounded research result",
        )
        self.assertFalse(
            status["policy"]["establishes_truth"]
        )
        self.assertEqual(
            cancelled["status"],
            "cancel_requested",
        )
        self.assertEqual(
            client.interactions.get_calls[0],
            {"id": "interaction-123"},
        )
        self.assertEqual(
            client.interactions.cancel_calls[0],
            {"id": "interaction-123"},
        )


if __name__ == "__main__":
    unittest.main()
