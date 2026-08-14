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


from app.intelligence.providers import (
    get_provider,
    select_providers,
)


class BenchmarkProviderRegistryTests(
    unittest.TestCase
):
    def test_benchmark_providers_are_registered(
        self,
    ):
        providers = {
            provider[
                "provider_key"
            ]
            for provider in (
                select_providers(
                    data_family="benchmark"
                )
            )
        }

        self.assertTrue(
            {
                "averitec",
                "fever",
                "multifc",
            }.issubset(
                providers
            )
        )

    def test_averitec_is_research_only(
        self,
    ):
        provider = get_provider(
            "averitec"
        )

        self.assertEqual(
            provider[
                "adapter_status"
            ],
            "research_only",
        )

        self.assertEqual(
            provider[
                "license_class"
            ],
            "cc-by-nc-4.0",
        )

    def test_fever_is_benchmark_active(
        self,
    ):
        provider = get_provider(
            "fever"
        )

        self.assertEqual(
            provider[
                "adapter_status"
            ],
            "benchmark_active",
        )

    def test_multifc_remains_schema_review_only(
        self,
    ):
        provider = get_provider(
            "multifc"
        )

        self.assertEqual(
            provider[
                "adapter_status"
            ],
            "registered_schema_review",
        )

    def test_benchmarks_do_not_supply_independence_labels(
        self,
    ):
        for key in (
            "averitec",
            "fever",
            "multifc",
        ):
            provider = get_provider(
                key
            )

            capabilities = (
                provider[
                    "benchmark_capabilities"
                ]
            )

            self.assertFalse(
                capabilities[
                    "independence_labels"
                ]
            )

            self.assertFalse(
                capabilities[
                    "corroboration_labels"
                ]
            )

    def test_benchmarks_never_enable_live_merit(
        self,
    ):
        for key in (
            "averitec",
            "fever",
            "multifc",
        ):
            self.assertFalse(
                get_provider(
                    key
                )[
                    "live_merit_enabled"
                ]
            )


if __name__ == "__main__":
    unittest.main()
