import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.analysis.corpus_expansion import (
    build_validation_corpus_expansion,
)

from app.db.connection import (
    connect_database,
)

from app.db.migrations import (
    initialize_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.corpus import (
    record_corpus_record,
)

from app.services.corpus_expansion_automation import (
    CORPUS_EXPANSION_AUTOMATION_VERSION,
    build_corpus_expansion_tasks,
    execute_corpus_expansion_tasks,
    load_persisted_structured_corpus_records,
    run_corpus_expansion_automation,
)


class CorpusExpansionAutomationTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp_dir.name
            )
            / "automation.db"
        )

        initialize_database(
            self.connection_factory,
            SCHEMA,
        )

    def tearDown(
        self,
    ):
        self.temp_dir.cleanup()

    def connection_factory(
        self,
    ):
        return connect_database(
            self.db_path
        )

    def expansion(
        self,
        *,
        records=None,
        target=2,
    ):
        return (
            build_validation_corpus_expansion(
                records=(
                    records
                    or []
                ),
                target_records_per_sport=(
                    target
                ),
            )
        )

    def fake_ingestor(
        self,
        *,
        records,
        connection_factory,
    ):
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

    def test_version_and_policy(
        self,
    ):
        result = (
            run_corpus_expansion_automation(
                connection_factory=(
                    self.connection_factory
                ),
                records=[],
                provider_parameters={},
                target_records_per_sport=1,
                dry_run=True,
            )
        )

        self.assertEqual(
            result["version"],
            (
                CORPUS_EXPANSION_AUTOMATION_VERSION
            ),
        )

        self.assertTrue(
            result[
                "execution"
            ][
                "policy"
            ][
                "ingestion_is_capped_to_coverage_deficit"
            ]
        )

        self.assertTrue(
            result[
                "execution"
            ][
                "policy"
            ][
                "does_not_change_live_merit"
            ]
        )

    def test_loader_reads_only_structured_sports_rows(
        self,
    ):
        record_corpus_record(
            origin_type="external_dataset",
            data_family=(
                "structured_sports_data"
            ),
            dataset_name="football-data",
            external_record_id="match-1",
            adapter_version="test-v1",
            sport_key="football",
            payload={
                "match": 1
            },
            ingested_at=(
                "2026-08-15T06:00:00+00:00"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        record_corpus_record(
            origin_type="external_dataset",
            data_family="benchmark",
            dataset_name="benchmark-data",
            external_record_id="claim-1",
            adapter_version="test-v1",
            payload={
                "claim": 1
            },
            ingested_at=(
                "2026-08-15T06:00:00+00:00"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        rows = (
            load_persisted_structured_corpus_records(
                connection_factory=(
                    self.connection_factory
                )
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0][
                "sport_key"
            ],
            "football",
        )

    def test_missing_parameters_block_execution(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={},
            )
        )

        blocked = {
            row[
                "sport_key"
            ]: row[
                "status"
            ]
            for row
            in plan[
                "blocked"
            ]
        }

        self.assertEqual(
            blocked[
                "football"
            ],
            "blocked_missing_parameters",
        )

        self.assertEqual(
            blocked[
                "cricket"
            ],
            "blocked_missing_parameters",
        )

        self.assertEqual(
            blocked[
                "motorsport"
            ],
            "blocked_missing_parameters",
        )

    def test_unimplemented_registered_adapter_is_blocked(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "nflverse": {
                        "season": "2025"
                    }
                },
            )
        )

        american_football = next(
            row
            for row
            in plan["blocked"]
            if (
                row["sport_key"]
                == "american_football"
            )
        )

        self.assertEqual(
            american_football[
                "status"
            ],
            "blocked_adapter_not_implemented",
        )

    def test_review_gated_provider_stays_blocked(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "basketball": {
                        "nba_api": {
                            "endpoint": (
                                "scoreboard"
                            )
                        }
                    }
                },
            )
        )

        basketball = next(
            row
            for row
            in plan["blocked"]
            if (
                row["sport_key"]
                == "basketball"
            )
        )

        self.assertEqual(
            basketball[
                "status"
            ],
            "blocked_provider_gate",
        )

    def test_dry_run_never_fetches(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "openf1": {
                        "endpoint": (
                            "meetings"
                        ),
                        "filters": {
                            "year": 2025
                        },
                    }
                },
            )
        )

        def forbidden_fetcher(
            request
        ):
            raise AssertionError(
                "Fetcher must not run "
                "during dry run."
            )

        result = (
            execute_corpus_expansion_tasks(
                task_plan=plan,
                connection_factory=(
                    self.connection_factory
                ),
                dry_run=True,
                fetcher=(
                    forbidden_fetcher
                ),
            )
        )

        motorsport = next(
            row
            for row
            in result["results"]
            if (
                row["sport_key"]
                == "motorsport"
            )
        )

        self.assertEqual(
            motorsport["status"],
            "planned",
        )

    def test_openf1_execution_is_capped_to_deficit(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=2
                    )
                ),
                provider_parameters={
                    "openf1": {
                        "endpoint": (
                            "meetings"
                        ),
                        "filters": {
                            "year": 2025
                        },
                        "season_key": (
                            "2025"
                        ),
                    }
                },
            )
        )

        def fetcher(
            request
        ):
            return [
                {
                    "meeting_key": 1,
                    "year": 2025,
                    "date_start": (
                        "2025-03-01"
                    ),
                },
                {
                    "meeting_key": 2,
                    "year": 2025,
                    "date_start": (
                        "2025-03-08"
                    ),
                },
                {
                    "meeting_key": 3,
                    "year": 2025,
                    "date_start": (
                        "2025-03-15"
                    ),
                },
            ]

        result = (
            execute_corpus_expansion_tasks(
                task_plan=plan,
                connection_factory=(
                    self.connection_factory
                ),
                fetcher=fetcher,
                ingestor=(
                    self.fake_ingestor
                ),
            )
        )

        motorsport = next(
            row
            for row
            in result["results"]
            if (
                row["sport_key"]
                == "motorsport"
            )
        )

        self.assertEqual(
            motorsport[
                "fetched_record_count"
            ],
            3,
        )

        self.assertEqual(
            motorsport[
                "selected_record_count"
            ],
            2,
        )

        self.assertEqual(
            motorsport[
                "created_record_count"
            ],
            2,
        )

    def test_statsbomb_execution_uses_existing_normalizer(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "statsbomb_open": {
                        "resource": (
                            "matches"
                        ),
                        "competition_id": 9,
                        "season_id": 281,
                        "competition_key": (
                            "bundesliga"
                        ),
                        "season_key": (
                            "2023-24"
                        ),
                    }
                },
            )
        )

        def fetcher(
            request
        ):
            return [
                {
                    "match_id": 1234
                }
            ]

        result = (
            execute_corpus_expansion_tasks(
                task_plan=plan,
                connection_factory=(
                    self.connection_factory
                ),
                fetcher=fetcher,
                ingestor=(
                    self.fake_ingestor
                ),
            )
        )

        football = next(
            row
            for row
            in result["results"]
            if (
                row["sport_key"]
                == "football"
            )
        )

        self.assertEqual(
            football["status"],
            "completed",
        )

        self.assertEqual(
            football[
                "selected_record_count"
            ],
            1,
        )

    def test_cricsheet_execution_uses_existing_normalizer(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "cricsheet": {
                        "archive_name": (
                            "ipl_json.zip"
                        ),
                        "competition_key": (
                            "ipl"
                        ),
                    }
                },
            )
        )

        def fetcher(
            request
        ):
            return b"fake-zip"

        def reader(
            content
        ):
            self.assertEqual(
                content,
                b"fake-zip",
            )

            return [
                {
                    "external_record_id": (
                        "ipl-1"
                    ),
                    "payload": {
                        "info": {
                            "season": 2025,
                            "dates": [
                                "2025-03-22"
                            ],
                        },
                        "innings": [],
                    },
                }
            ]

        result = (
            execute_corpus_expansion_tasks(
                task_plan=plan,
                connection_factory=(
                    self.connection_factory
                ),
                fetcher=fetcher,
                ingestor=(
                    self.fake_ingestor
                ),
                cricsheet_reader=reader,
            )
        )

        cricket = next(
            row
            for row
            in result["results"]
            if (
                row["sport_key"]
                == "cricket"
            )
        )

        self.assertEqual(
            cricket["status"],
            "completed",
        )

        self.assertEqual(
            cricket[
                "created_record_count"
            ],
            1,
        )

    def test_provider_failure_is_isolated(
        self,
    ):
        plan = (
            build_corpus_expansion_tasks(
                expansion=(
                    self.expansion(
                        target=1
                    )
                ),
                provider_parameters={
                    "openf1": {
                        "endpoint": (
                            "meetings"
                        )
                    },
                    "statsbomb_open": {
                        "resource": (
                            "competitions"
                        )
                    },
                },
            )
        )

        def fetcher(
            request
        ):
            if (
                request[
                    "provider_key"
                ]
                == "openf1"
            ):
                raise RuntimeError(
                    "provider down"
                )

            return [
                {
                    "competition_id": 1,
                    "season_id": 2,
                    "competition_name": (
                        "League"
                    ),
                    "season_name": (
                        "2025"
                    ),
                }
            ]

        result = (
            execute_corpus_expansion_tasks(
                task_plan=plan,
                connection_factory=(
                    self.connection_factory
                ),
                fetcher=fetcher,
                ingestor=(
                    self.fake_ingestor
                ),
            )
        )

        statuses = {
            row[
                "sport_key"
            ]: row[
                "status"
            ]
            for row
            in result["results"]
        }

        self.assertEqual(
            statuses[
                "motorsport"
            ],
            "failed",
        )

        self.assertEqual(
            statuses[
                "football"
            ],
            "completed",
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "failed_task_count"
            ],
            1,
        )

    def test_task_plan_is_deterministic(
        self,
    ):
        expansion = (
            self.expansion(
                target=1
            )
        )

        parameters_a = {
            "openf1": {
                "endpoint": (
                    "meetings"
                ),
                "filters": {
                    "year": 2025,
                    "meeting_key": 1,
                },
            },
            "cricsheet": {
                "archive_name": (
                    "ipl_json.zip"
                ),
            },
        }

        parameters_b = {
            "cricsheet": {
                "archive_name": (
                    "ipl_json.zip"
                ),
            },
            "openf1": {
                "filters": {
                    "meeting_key": 1,
                    "year": 2025,
                },
                "endpoint": (
                    "meetings"
                ),
            },
        }

        first = (
            build_corpus_expansion_tasks(
                expansion=expansion,
                provider_parameters=(
                    parameters_a
                ),
            )
        )

        second = (
            build_corpus_expansion_tasks(
                expansion=expansion,
                provider_parameters=(
                    parameters_b
                ),
            )
        )

        self.assertEqual(
            first,
            second,
        )


if __name__ == "__main__":
    unittest.main()
