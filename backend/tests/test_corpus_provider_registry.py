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
    PROVIDER_REGISTRY_VERSION,
    get_provider,
    list_providers,
    select_providers,
)


class CorpusProviderRegistryTests(
    unittest.TestCase
):
    def test_major_provider_set_is_registered(
        self,
    ):
        keys = {
            provider[
                "provider_key"
            ]
            for provider in list_providers()
        }

        self.assertTrue(
            {
                "openf1",
                "statsbomb_open",
                "cricsheet",
                "nflverse",
                "nba_api",
                "retrosheet",
                "moneypuck",
                "tennis_atp",
                "gdelt",
            }.issubset(
                keys
            )
        )

    def test_registry_version_is_stable(
        self,
    ):
        provider = get_provider(
            "openf1"
        )

        self.assertEqual(
            provider[
                "version"
            ],
            PROVIDER_REGISTRY_VERSION,
        )

    def test_active_adapters_are_explicit(
        self,
    ):
        active = {
            provider[
                "provider_key"
            ]
            for provider in (
                select_providers(
                    active_only=True
                )
            )
        }

        self.assertEqual(
            active,
            {
                "openf1",
                "statsbomb_open",
                "cricsheet",
                "fivethirtyeight_forecast_archive",
            },
        )

    def test_major_sport_routing(
        self,
    ):
        expectations = {
            "motorsport": "openf1",
            "football": "statsbomb_open",
            "cricket": "cricsheet",
            "american_football": (
                "nflverse"
            ),
            "basketball": "nba_api",
            "baseball": "retrosheet",
            "ice_hockey": "moneypuck",
            "tennis": "tennis_atp",
        }

        for sport, expected in (
            expectations.items()
        ):
            keys = {
                provider[
                    "provider_key"
                ]
                for provider in (
                    select_providers(
                        sport_key=sport
                    )
                )
            }

            self.assertIn(
                expected,
                keys,
            )

    def test_gdelt_is_cross_sport_reporting_provider(
        self,
    ):
        providers = (
            select_providers(
                sport_key="rugby",
                data_family=(
                    "reporting_evidence"
                ),
            )
        )

        keys = {
            provider[
                "provider_key"
            ]
            for provider in providers
        }

        self.assertIn(
            "gdelt",
            keys,
        )

    def test_registry_never_enables_live_merit(
        self,
    ):
        for provider in list_providers():
            self.assertFalse(
                provider[
                    "live_merit_enabled"
                ]
            )

    def test_unknown_provider_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown corpus provider",
        ):
            get_provider(
                "made-up-provider"
            )
