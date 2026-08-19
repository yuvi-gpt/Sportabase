import os
import sys
import threading
import unittest

from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.ai import generation
from app.ai import routed_generation
from app.ai.models import DEFAULT_GEMINI_MODEL
from app.ai.tasks import (
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    ARTICLE_TLDR,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
    VIDEO_ANALYSIS,
)
from app.services import gemini_runtime


LIVE_GENERATION_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_SINGLE_PASS,
    ARTICLE_CLASSIFIER,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
)

EVALUATION_MODEL = "gemma-4-26b-a4b-it"


class GoogleModelRouterWiringTests(
    unittest.TestCase
):
    def _delegate_kwargs(
        self,
        *,
        mode=ARTICLE_TLDR,
        model=DEFAULT_GEMINI_MODEL,
    ):
        return {
            "client": object(),
            "client_key": "client",
            "mode": mode,
            "model": model,
            "contents": "prompt",
            "inflight_lock": threading.Lock(),
            "inflight_calls": {},
            "fingerprint_resolver": object(),
            "reserve_call": object(),
            "finish_call": object(),
            "classify_failure": object(),
            "record_join": object(),
            "sleep_func": object(),
        }

    def _capacity_env(
        self,
        resource_id=EVALUATION_MODEL,
    ):
        keys = (
            routed_generation
            .model_capacity_env_keys(
                resource_id
            )
        )

        values = (
            "5",
            "4",
            "250000",
            "200000",
            "20",
            "4",
            "50000",
            "75",
        )

        return dict(
            zip(
                keys,
                values,
            )
        )

    def test_historical_runtime_alias_points_to_routed_facade(
        self,
    ):
        self.assertIs(
            gemini_runtime,
            routed_generation,
        )

        self.assertIs(
            main._generate_gemini_content_runtime_impl,
            routed_generation.generate_gemini_content,
        )

    def test_non_generation_helpers_remain_canonical_objects(
        self,
    ):
        self.assertIs(
            routed_generation.reserve_gemini_call,
            generation.reserve_gemini_call,
        )
        self.assertIs(
            routed_generation.finish_gemini_call,
            generation.finish_gemini_call,
        )
        self.assertIs(
            routed_generation.gemini_request_fingerprint,
            generation.gemini_request_fingerprint,
        )
        self.assertIs(
            routed_generation.classify_gemini_failure,
            generation.classify_gemini_failure,
        )

    def test_every_live_task_preserves_current_primary(
        self,
    ):
        for task_id in LIVE_GENERATION_TASKS:
            with self.subTest(
                task=task_id
            ):
                resolved = (
                    routed_generation
                    .resolve_routed_generation_model(
                        mode=task_id,
                        model=(
                            DEFAULT_GEMINI_MODEL
                        ),
                    )
                )

                self.assertEqual(
                    resolved,
                    "gemini-3.5-flash",
                )

    def test_legacy_default_string_is_a_task_primary_sentinel(
        self,
    ):
        resolved = (
            routed_generation
            .resolve_routed_generation_model(
                mode=ARTICLE_TLDR,
                model="gemini-3.5-flash",
            )
        )

        self.assertEqual(
            resolved,
            DEFAULT_GEMINI_MODEL,
        )

    def test_unknown_legacy_mode_preserves_requested_model(
        self,
    ):
        resolved = (
            routed_generation
            .resolve_routed_generation_model(
                mode="legacy-unregistered-mode",
                model="model-x",
            )
        )

        self.assertEqual(
            resolved,
            "model-x",
        )

    def test_new_hosted_resource_fails_closed_without_capacity_config(
        self,
    ):
        empty_env = {
            key: ""
            for key in (
                routed_generation
                .model_capacity_env_keys(
                    EVALUATION_MODEL
                )
            )
        }

        with patch.dict(
            os.environ,
            empty_env,
            clear=False,
        ):
            with self.assertRaises(
                routed_generation
                .AIResourceCapacityConfigurationError
            ):
                (
                    routed_generation
                    .resolve_routed_generation_model(
                        mode=ARTICLE_TLDR,
                        model=EVALUATION_MODEL,
                    )
                )

    def test_explicit_evaluation_resource_routes_after_capacity_config(
        self,
    ):
        with patch.dict(
            os.environ,
            self._capacity_env(),
            clear=False,
        ):
            resolved = (
                routed_generation
                .resolve_routed_generation_model(
                    mode=ARTICLE_TLDR,
                    model=EVALUATION_MODEL,
                )
            )

        self.assertEqual(
            resolved,
            EVALUATION_MODEL,
        )

    def test_wrong_resource_kind_is_rejected_before_execution(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            (
                routed_generation
                .resolve_routed_generation_model(
                    mode=ARTICLE_TLDR,
                    model="gemini-embedding-2",
                )
            )

    def test_wrapper_delegates_current_primary_without_behavior_change(
        self,
    ):
        sentinel = object()

        with patch.object(
            generation,
            "generate_gemini_content",
            return_value=sentinel,
        ) as delegate:
            result = (
                routed_generation
                .generate_gemini_content(
                    **self._delegate_kwargs()
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertEqual(
            delegate.call_args.kwargs[
                "model"
            ],
            DEFAULT_GEMINI_MODEL,
        )
        self.assertEqual(
            delegate.call_args.kwargs[
                "mode"
            ],
            ARTICLE_TLDR,
        )
        self.assertEqual(
            delegate.call_args.kwargs[
                "contents"
            ],
            "prompt",
        )

    def test_wrapper_never_calls_delegate_when_capacity_gate_fails(
        self,
    ):
        empty_env = {
            key: ""
            for key in (
                routed_generation
                .model_capacity_env_keys(
                    EVALUATION_MODEL
                )
            )
        }

        with patch.dict(
            os.environ,
            empty_env,
            clear=False,
        ):
            with patch.object(
                generation,
                "generate_gemini_content",
            ) as delegate:
                with self.assertRaises(
                    routed_generation
                    .AIResourceCapacityConfigurationError
                ):
                    (
                        routed_generation
                        .generate_gemini_content(
                            **self._delegate_kwargs(
                                model=(
                                    EVALUATION_MODEL
                                )
                            )
                        )
                    )

        delegate.assert_not_called()

    def test_wrapper_delegates_explicit_evaluation_model_when_configured(
        self,
    ):
        sentinel = object()

        with patch.dict(
            os.environ,
            self._capacity_env(),
            clear=False,
        ):
            with patch.object(
                generation,
                "generate_gemini_content",
                return_value=sentinel,
            ) as delegate:
                result = (
                    routed_generation
                    .generate_gemini_content(
                        **self._delegate_kwargs(
                            model=EVALUATION_MODEL
                        )
                    )
                )

        self.assertIs(
            result,
            sentinel,
        )
        self.assertEqual(
            delegate.call_args.kwargs[
                "model"
            ],
            EVALUATION_MODEL,
        )


if __name__ == "__main__":
    unittest.main()
