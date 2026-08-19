import sys
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
from app.operations import usage as operations_usage
from app.services import usage_reporting


class UsageReportingModuleTests(
    unittest.TestCase
):
    def test_historical_usage_reporting_path_is_true_alias(
        self,
    ):
        self.assertIs(
            usage_reporting,
            operations_usage,
        )

    def test_derived_metrics_use_explicit_pricing_and_capacity(
        self,
    ):
        result = (
            operations_usage
            .usage_derived_metrics(
                {
                    "total_records": 10,
                    "cache_hits": 2,
                    "inflight_joins": 1,
                    "gemini_attempts": 7,
                    "successful_calls": 6,
                    "failed_calls": 1,
                    "expired_reservations": 0,
                    "prompt_tokens": 1000000,
                    "output_tokens": 500000,
                    "thought_tokens": 100000,
                    "total_tokens": 1600000,
                },
                input_cost_per_million_usd=0.1,
                output_cost_per_million_usd=0.4,
                global_daily_call_cap=14,
            )
        )

        self.assertEqual(
            result[
                "provider_avoidance_rate_percent"
            ],
            30.0,
        )

        self.assertEqual(
            result[
                "global_capacity_used_percent"
            ],
            50.0,
        )

        self.assertEqual(
            result[
                "estimated_paid_cost_usd"
            ],
            0.34,
        )

    def test_savings_metrics_fail_closed_without_success_basis(
        self,
    ):
        result = (
            operations_usage
            .usage_savings_metrics(
                {
                    "cache_hits": 2,
                    "inflight_joins": 1,
                    "successful_calls": 0,
                },
                input_cost_per_million_usd=0.1,
                output_cost_per_million_usd=0.4,
            )
        )

        self.assertEqual(
            result[
                "provider_calls_avoided"
            ],
            3,
        )

        self.assertEqual(
            result[
                "unpriced_avoided_calls"
            ],
            3,
        )

        self.assertFalse(
            result[
                "cost_savings_estimate_available"
            ]
        )

    def test_scope_savings_summary_aggregates_modes(
        self,
    ):
        result = (
            operations_usage
            .usage_scope_savings_summary(
                [
                    {
                        "mode": "article",
                        "provider_calls_avoided": 2,
                        "cache_calls_avoided": 1,
                        "inflight_calls_avoided": 1,
                        "unpriced_avoided_calls": 0,
                        "estimated_cache_cost_avoided_usd": 0.1,
                        "estimated_inflight_cost_avoided_usd": 0.2,
                        "estimated_prompt_tokens_avoided": 10,
                        "estimated_output_tokens_avoided": 20,
                        "estimated_thought_tokens_avoided": 5,
                        "estimated_total_tokens_avoided": 35,
                    },
                    {
                        "mode": "video",
                        "provider_calls_avoided": 1,
                        "cache_calls_avoided": 1,
                        "inflight_calls_avoided": 0,
                        "unpriced_avoided_calls": 0,
                        "estimated_cache_cost_avoided_usd": 0.3,
                        "estimated_inflight_cost_avoided_usd": 0.0,
                        "estimated_prompt_tokens_avoided": 15,
                        "estimated_output_tokens_avoided": 25,
                        "estimated_thought_tokens_avoided": 10,
                        "estimated_total_tokens_avoided": 50,
                    },
                ],
                actual_estimated_cost=1.0,
                estimation_basis="test",
            )
        )

        self.assertEqual(
            result[
                "provider_calls_avoided"
            ],
            3,
        )

        self.assertEqual(
            result[
                "estimated_total_cost_avoided_usd"
            ],
            0.6,
        )

        self.assertEqual(
            result[
                "estimated_total_tokens_avoided"
            ],
            85.0,
        )

    def test_main_derived_wrapper_injects_runtime_constants(
        self,
    ):
        original_input = (
            main
            .GEMINI_INPUT_COST_PER_MILLION_USD
        )

        original_output = (
            main
            .GEMINI_OUTPUT_COST_PER_MILLION_USD
        )

        original_cap = (
            main
            .GLOBAL_DAILY_GEMINI_CALL_CAP
        )

        sentinel = {
            "ok": True
        }

        try:
            (
                main
                .GEMINI_INPUT_COST_PER_MILLION_USD
            ) = 1.25

            (
                main
                .GEMINI_OUTPUT_COST_PER_MILLION_USD
            ) = 2.5

            (
                main
                .GLOBAL_DAILY_GEMINI_CALL_CAP
            ) = 123

            with patch.object(
                main,
                "_usage_derived_metrics_reporting_impl",
                return_value=sentinel,
            ) as impl:
                result = (
                    main.usage_derived_metrics(
                        {}
                    )
                )

        finally:
            (
                main
                .GEMINI_INPUT_COST_PER_MILLION_USD
            ) = original_input

            (
                main
                .GEMINI_OUTPUT_COST_PER_MILLION_USD
            ) = original_output

            (
                main
                .GLOBAL_DAILY_GEMINI_CALL_CAP
            ) = original_cap

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertEqual(
            kwargs[
                "input_cost_per_million_usd"
            ],
            1.25,
        )

        self.assertEqual(
            kwargs[
                "output_cost_per_million_usd"
            ],
            2.5,
        )

        self.assertEqual(
            kwargs[
                "global_daily_call_cap"
            ],
            123,
        )

    def test_main_mode_wrapper_injects_current_metric_helpers(
        self,
    ):
        with patch.object(
            main,
            "_usage_mode_metrics_reporting_impl",
            return_value={},
        ) as impl:
            main.usage_mode_metrics(
                {}
            )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs[
                "derived_metrics_resolver"
            ],
            main.usage_derived_metrics,
        )

        self.assertIs(
            kwargs[
                "savings_metrics_resolver"
            ],
            main.usage_savings_metrics,
        )

    def test_admin_wrapper_authenticates_and_injects_dependencies(
        self,
    ):
        request = object()

        sentinel = {
            "generated_at": "test"
        }

        with patch.object(
            main,
            "require_admin",
        ) as require_admin:
            with patch.object(
                main,
                "_admin_usage_summary_reporting_impl",
                return_value=sentinel,
            ) as impl:
                result = (
                    main.admin_usage_summary(
                        request,
                        days=5,
                    )
                )

        require_admin.assert_called_once_with(
            request
        )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertEqual(
            kwargs[
                "days"
            ],
            5,
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "usage_day_resolver"
            ],
            main.utc_usage_day,
        )

        self.assertIs(
            kwargs[
                "expire_reservations"
            ],
            (
                main
                .expire_stale_gemini_reservations
            ),
        )

        self.assertIs(
            kwargs[
                "derived_metrics_resolver"
            ],
            main.usage_derived_metrics,
        )

        self.assertIs(
            kwargs[
                "mode_metrics_resolver"
            ],
            main.usage_mode_metrics,
        )

        self.assertIs(
            kwargs[
                "scope_savings_resolver"
            ],
            main.usage_scope_savings_summary,
        )

    def test_admin_wrapper_stops_before_service_when_auth_fails(
        self,
    ):
        request = object()

        with patch.object(
            main,
            "require_admin",
            side_effect=RuntimeError(
                "denied"
            ),
        ):
            with patch.object(
                main,
                "_admin_usage_summary_reporting_impl",
            ) as impl:
                with self.assertRaises(
                    RuntimeError
                ):
                    main.admin_usage_summary(
                        request,
                        days=7,
                    )

        impl.assert_not_called()

    def test_admin_usage_route_remains_registered(
        self,
    ):
        openapi = (
            main.app.openapi()
        )

        self.assertIn(
            "/admin/usage/summary",
            openapi[
                "paths"
            ],
        )

        self.assertIn(
            "get",
            openapi[
                "paths"
            ][
                "/admin/usage/summary"
            ],
        )


if __name__ == "__main__":
    unittest.main()
