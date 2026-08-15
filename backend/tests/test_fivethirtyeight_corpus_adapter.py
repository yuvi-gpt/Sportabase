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


from app.analysis.corpus_expansion import (
    build_validation_corpus_expansion,
)

from app.intelligence.providers import (
    get_provider,
    select_providers,
)

from app.services.corpus_adapters import (
    build_fivethirtyeight_forecast_request,
    fetch_remote_request,
    normalize_fivethirtyeight_forecast_rows,
)

from app.services.corpus_expansion_automation import (
    build_corpus_expansion_tasks,
    execute_corpus_expansion_tasks,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        content=b"",
    ):
        self.status_code = status_code
        self.content = content


class FiveThirtyEightCorpusAdapterTests(
    unittest.TestCase
):
    def test_provider_is_active_but_never_live_merit(
        self,
    ):
        provider = get_provider(
            "fivethirtyeight_forecast_archive"
        )

        self.assertEqual(
            provider[
                "adapter_status"
            ],
            "active",
        )

        self.assertEqual(
            provider[
                "license_class"
            ],
            "cc-by-4.0",
        )

        self.assertEqual(
            set(
                provider[
                    "sports"
                ]
            ),
            {
                "american_football",
                "baseball",
                "basketball",
                "ice_hockey",
                "tennis",
            },
        )

        self.assertFalse(
            provider[
                "live_merit_enabled"
            ]
        )

    def test_restricted_legacy_sources_are_not_activated(
        self,
    ):
        for provider_key in (
            "nba_api",
            "moneypuck",
            "tennis_atp",
        ):
            self.assertNotEqual(
                get_provider(
                    provider_key
                )[
                    "adapter_status"
                ],
                "active",
            )

    def test_request_mapping_covers_five_sports(
        self,
    ):
        expectations = {
            "american_football": (
                "nfl_games.csv"
            ),
            "baseball": (
                "mlb_games.csv"
            ),
            "basketball": (
                "nba_games.csv"
            ),
            "ice_hockey": (
                "nhl_games.csv"
            ),
            "tennis": (
                "tennis_men.csv"
            ),
        }

        for sport, filename in (
            expectations.items()
        ):
            request = (
                build_fivethirtyeight_forecast_request(
                    sport_key=sport
                )
            )

            self.assertEqual(
                request[
                    "expected_format"
                ],
                "csv",
            )

            self.assertEqual(
                request[
                    "sport_key"
                ],
                sport,
            )

            self.assertTrue(
                request[
                    "url"
                ].endswith(
                    "/"
                    + filename
                )
            )

    def test_tennis_women_archive_can_be_selected(
        self,
    ):
        request = (
            build_fivethirtyeight_forecast_request(
                sport_key="tennis",
                dataset_key=(
                    "tennis_women"
                ),
            )
        )

        self.assertEqual(
            request[
                "dataset_key"
            ],
            "tennis_women",
        )

        self.assertTrue(
            request[
                "url"
            ].endswith(
                "/tennis_women.csv"
            )
        )

    def test_unknown_sport_fails_closed(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported FiveThirtyEight",
        ):
            build_fivethirtyeight_forecast_request(
                sport_key="rugby"
            )

    def test_remote_csv_fetch_uses_existing_fetch_boundary(
        self,
    ):
        request = (
            build_fivethirtyeight_forecast_request(
                sport_key="basketball"
            )
        )

        payload = fetch_remote_request(
            request,
            http_get=(
                lambda url, timeout: (
                    FakeResponse(
                        content=(
                            b"season,date,team1,team2,"
                            b"prob1,prob1_outcome,"
                            b"prob2,prob2_outcome\n"
                            b"2022,2022-06-01,A,B,"
                            b"0.6,1,0.4,0\n"
                        )
                    )
                )
            ),
        )

        self.assertEqual(
            len(payload),
            1,
        )

        self.assertEqual(
            payload[0][
                "team1"
            ],
            "A",
        )

    def test_game_normalization_preserves_doubleheader_identity(
        self,
    ):
        row = (
            normalize_fivethirtyeight_forecast_rows(
                sport_key="baseball",
                rows=[
                    {
                        "season": "2022",
                        "date": (
                            "2022-10-05"
                        ),
                        "team1": "Orioles",
                        "team2": (
                            "Blue Jays"
                        ),
                        "dh": "1",
                        "prob1": "0.40",
                        "prob1_outcome": (
                            "1"
                        ),
                        "prob2": "0.60",
                        "prob2_outcome": (
                            "0"
                        ),
                    }
                ],
            )[0]
        )

        self.assertEqual(
            row[
                "sport_key"
            ],
            "baseball",
        )

        self.assertEqual(
            row[
                "competition_key"
            ],
            "mlb",
        )

        self.assertEqual(
            row[
                "measurement_kind"
            ],
            "mixed",
        )

        self.assertIn(
            "dh=1",
            row[
                "external_record_id"
            ],
        )

        self.assertEqual(
            row[
                "metadata"
            ][
                "license_class"
            ],
            "cc-by-4.0",
        )

        self.assertFalse(
            row[
                "metadata"
            ][
                "live_merit_effect_enabled"
            ]
        )

    def test_tennis_normalization_is_player_forecast_row(
        self,
    ):
        row = (
            normalize_fivethirtyeight_forecast_rows(
                sport_key="tennis",
                rows=[
                    {
                        "season": "2022",
                        "forecast_date": (
                            "2022-07-10"
                        ),
                        "player": (
                            "Example Player"
                        ),
                        "round_1": "0.90",
                        "round_1_outcome": (
                            "1"
                        ),
                    }
                ],
            )[0]
        )

        self.assertEqual(
            row[
                "event_type"
            ],
            (
                "tournament_forecast_outcome"
            ),
        )

        self.assertEqual(
            row[
                "granularity"
            ],
            (
                "player_tournament_forecast"
            ),
        )

        self.assertEqual(
            row[
                "occurred_at"
            ],
            "2022-07-10",
        )

    def test_all_eight_target_sports_have_executable_tasks(
        self,
    ):
        expansion = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=1,
            )
        )

        plan = (
            build_corpus_expansion_tasks(
                expansion=expansion,
                provider_parameters={
                    "openf1": {
                        "endpoint": (
                            "meetings"
                        ),
                        "filters": {
                            "year": 2022,
                        },
                    },
                    "statsbomb_open": {
                        "resource": (
                            "competitions"
                        ),
                    },
                    "cricsheet": {
                        "archive_name": (
                            "ipl_json.zip"
                        ),
                        "competition_key": (
                            "ipl"
                        ),
                    },
                    "fivethirtyeight_forecast_archive": {},
                },
            )
        )

        self.assertEqual(
            len(
                plan[
                    "tasks"
                ]
            ),
            8,
        )

        self.assertEqual(
            plan[
                "blocked"
            ],
            [],
        )

        task_by_sport = {
            row[
                "sport_key"
            ]: row[
                "provider_key"
            ]
            for row
            in plan[
                "tasks"
            ]
        }

        self.assertEqual(
            set(
                task_by_sport
            ),
            {
                "american_football",
                "baseball",
                "basketball",
                "cricket",
                "football",
                "ice_hockey",
                "motorsport",
                "tennis",
            },
        )

        for sport in (
            "american_football",
            "baseball",
            "basketball",
            "ice_hockey",
            "tennis",
        ):
            self.assertEqual(
                task_by_sport[
                    sport
                ],
                (
                    "fivethirtyeight_forecast_archive"
                ),
            )

    def test_fivethirtyeight_execution_is_capped_to_deficit(
        self,
    ):
        expansion = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=2,
            )
        )

        full_plan = (
            build_corpus_expansion_tasks(
                expansion=expansion,
                provider_parameters={
                    "fivethirtyeight_forecast_archive": {},
                },
            )
        )

        basketball_task = next(
            row
            for row
            in full_plan[
                "tasks"
            ]
            if (
                row[
                    "sport_key"
                ]
                == "basketball"
            )
        )

        single_plan = {
            "version": (
                full_plan[
                    "version"
                ]
            ),
            "tasks": [
                basketball_task
            ],
            "blocked": [],
        }

        captured = []

        def fetcher(
            request
        ):
            self.assertEqual(
                request[
                    "dataset_key"
                ],
                "nba_games",
            )

            return [
                {
                    "season": "2022",
                    "date": (
                        "2022-06-01"
                    ),
                    "team1": "A",
                    "team2": "B",
                    "prob1": "0.6",
                    "prob1_outcome": "1",
                    "prob2": "0.4",
                    "prob2_outcome": "0",
                },
                {
                    "season": "2022",
                    "date": (
                        "2022-06-02"
                    ),
                    "team1": "C",
                    "team2": "D",
                    "prob1": "0.5",
                    "prob1_outcome": "0",
                    "prob2": "0.5",
                    "prob2_outcome": "1",
                },
                {
                    "season": "2022",
                    "date": (
                        "2022-06-03"
                    ),
                    "team1": "E",
                    "team2": "F",
                    "prob1": "0.7",
                    "prob1_outcome": "1",
                    "prob2": "0.3",
                    "prob2_outcome": "0",
                },
            ]

        def ingestor(
            *,
            records,
            connection_factory,
        ):
            captured.extend(
                records
            )

            return {
                "counts": {
                    "processed": len(
                        records
                    ),
                    "created": len(
                        records
                    ),
                    "existing": 0,
                }
            }

        result = (
            execute_corpus_expansion_tasks(
                task_plan=single_plan,
                connection_factory=(
                    lambda: None
                ),
                fetcher=fetcher,
                ingestor=ingestor,
            )
        )

        row = result[
            "results"
        ][0]

        self.assertEqual(
            row[
                "fetched_record_count"
            ],
            3,
        )

        self.assertEqual(
            row[
                "selected_record_count"
            ],
            2,
        )

        self.assertEqual(
            len(captured),
            2,
        )

        self.assertTrue(
            all(
                record[
                    "sport_key"
                ]
                == "basketball"
                for record
                in captured
            )
        )


if __name__ == "__main__":
    unittest.main()
