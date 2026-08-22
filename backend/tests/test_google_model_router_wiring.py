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
    task_policy,
)
from app.services import gemini_runtime


TASK_PRIMARY = {
    ARTICLE_TLDR: "gemini-3.5-flash-lite",
    ARTICLE_CLASSIFIER: "gemini-3.5-flash-lite",
    ARTICLE_SINGLE_PASS: "gemini-3.6-flash",
    VIDEO_ANALYSIS: "gemini-3.6-flash",
    CORROBORATION_CANDIDATE_SEMANTICS: "gemini-3.5-flash",
    CORROBORATION_COLLECTION_SEMANTICS: "gemini-3.5-flash",
}

CAPACITY_GATED_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_CLASSIFIER,
    ARTICLE_SINGLE_PASS,
    VIDEO_ANALYSIS,
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
        resource_id,
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

    def _empty_capacity_env(
        self,
        resource_id,
    ):
        return {
            key: ""
            for key in (
                routed_generation
                .model_capacity_env_keys(
                    resource_id
                )
            )
        }

    def test_router_wiring_version_is_explicit(self):
        self.assertEqual(
            routed_generation.ROUTED_GENERATION_VERSION,
            "google-model-router-wiring-v2",
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

    def test_task_registry_has_distinct_generation_primaries(
        self,
    ):
        for task_id, expected_model in TASK_PRIMARY.items():
            with self.subTest(
                task=task_id
            ):
                self.assertEqual(
                    task_policy(
                        task_id
                    ).primary_resource_id,
                    expected_model,
                )

    def test_capacity_gated_task_primaries_use_35_compatibility_fallback_when_unconfigured(
        self,
    ):
        for task_id in CAPACITY_GATED_TASKS:
            primary = TASK_PRIMARY[
                task_id
            ]
            with self.subTest(
                task=task_id,
                primary=primary,
            ):
                with patch.dict(
                    os.environ,
                    self._empty_capacity_env(
                        primary
                    ),
                    clear=False,
                ):
                    resolved = (
                        routed_generation
                        .resolve_routed_generation_model(
                            mode=task_id,
                            model=DEFAULT_GEMINI_MODEL,
                        )
                    )

                self.assertEqual(
                    resolved,
                    DEFAULT_GEMINI_MODEL,
                )

    def test_capacity_gated_task_primaries_activate_when_configured(
        self,
    ):
        for task_id in CAPACITY_GATED_TASKS:
            primary = TASK_PRIMARY[
                task_id
            ]
            with self.subTest(
                task=task_id,
                primary=primary,
            ):
                with patch.dict(
                    os.environ,
                    self._capacity_env(
                        primary
                    ),
                    clear=False,
                ):
                    resolved = (
                        routed_generation
                        .resolve_routed_generation_model(
                            mode=task_id,
                            model=DEFAULT_GEMINI_MODEL,
                        )
                    )

                self.assertEqual(
                    resolved,
                    primary,
                )

    def test_evidence_semantics_remain_on_35_flash_without_fallback(
        self,
    ):
        for task_id in (
            CORROBORATION_CANDIDATE_SEMANTICS,
            CORROBORATION_COLLECTION_SEMANTICS,
        ):
            resolved = (
                routed_generation
                .resolve_routed_generation_model(
                    mode=task_id,
                    model=DEFAULT_GEMINI_MODEL,
                )
            )

            self.assertEqual(
                resolved,
                DEFAULT_GEMINI_MODEL,
            )
            self.assertFalse(
                task_policy(
                    task_id
                ).automatic_fallback_enabled
            )

    def test_legacy_default_string_is_a_task_primary_sentinel(
        self,
    ):
        primary = TASK_PRIMARY[
            ARTICLE_TLDR
        ]

        with patch.dict(
            os.environ,
            self._capacity_env(
                primary
            ),
            clear=False,
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
            primary,
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

    def test_explicit_evaluation_resource_fails_closed_without_capacity_config(
        self,
    ):
        with patch.dict(
            os.environ,
            self._empty_capacity_env(
                EVALUATION_MODEL
            ),
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
            self._capacity_env(
                EVALUATION_MODEL
            ),
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

    def test_wrapper_delegates_compatibility_fallback_when_primary_unconfigured(
        self,
    ):
        sentinel = object()
        primary = TASK_PRIMARY[
            ARTICLE_TLDR
        ]

        with patch.dict(
            os.environ,
            self._empty_capacity_env(
                primary
            ),
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

    def test_wrapper_delegates_task_primary_when_capacity_is_configured(
        self,
    ):
        sentinel = object()
        primary = TASK_PRIMARY[
            ARTICLE_TLDR
        ]

        with patch.dict(
            os.environ,
            self._capacity_env(
                primary
            ),
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
            primary,
        )
        self.assertEqual(
            delegate.call_args.kwargs[
                "mode"
            ],
            ARTICLE_TLDR,
        )

    def test_wrapper_never_calls_delegate_when_explicit_capacity_gate_fails(
        self,
    ):
        with patch.dict(
            os.environ,
            self._empty_capacity_env(
                EVALUATION_MODEL
            ),
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
            self._capacity_env(
                EVALUATION_MODEL
            ),
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
