import copy
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
    VALIDATION_CORPUS_EXPANSION_VERSION,
    build_balanced_validation_sample,
    build_validation_corpus_expansion,
)


class ValidationCorpusExpansionTests(
    unittest.TestCase
):
    def record(
        self,
        *,
        sport,
        external_id,
        dataset=None,
        payload_hash=None,
        record_id=None,
    ):
        dataset = (
            dataset
            or f"{sport}-dataset"
        )

        payload_hash = (
            payload_hash
            or f"hash-{external_id}"
        )

        record_id = (
            record_id
            or (
                f"{sport}-{external_id}-"
                f"{payload_hash}"
            )
        )

        return {
            "id": record_id,
            "origin_type": (
                "external_dataset"
            ),
            "data_family": (
                "structured_sports_data"
            ),
            "dataset_name": dataset,
            "external_record_id": (
                external_id
            ),
            "sport_key": sport,
            "payload_hash": (
                payload_hash
            ),
            "ingested_at": (
                "2026-08-15T06:00:00+00:00"
            ),
        }

    def coverage_for(
        self,
        result,
        sport,
    ):
        return next(
            row
            for row
            in result["coverage"]
            if (
                row["sport_key"]
                == sport
            )
        )

    def test_version_and_policy(
        self,
    ):
        result = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=5,
            )
        )

        self.assertEqual(
            result["version"],
            (
                VALIDATION_CORPUS_EXPANSION_VERSION
            ),
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "payload_revisions_do_not_inflate_coverage"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_fetch_remote_data"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_change_live_merit"
            ]
        )

    def test_revisions_do_not_inflate_unique_record_count(
        self,
    ):
        records = [
            self.record(
                sport="football",
                external_id="match-1",
                payload_hash="v1",
            ),
            self.record(
                sport="football",
                external_id="match-1",
                payload_hash="v2",
            ),
        ]

        result = (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=5,
            )
        )

        football = self.coverage_for(
            result,
            "football",
        )

        self.assertEqual(
            football[
                "unique_record_count"
            ],
            1,
        )

    def test_deficit_uses_unique_external_records(
        self,
    ):
        records = [
            self.record(
                sport="cricket",
                external_id="game-1",
            ),
            self.record(
                sport="cricket",
                external_id="game-2",
            ),
        ]

        result = (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=5,
            )
        )

        cricket = self.coverage_for(
            result,
            "cricket",
        )

        self.assertEqual(
            cricket["deficit"],
            3,
        )

        self.assertEqual(
            cricket[
                "coverage_status"
            ],
            "under_covered",
        )

    def test_covered_scope_leaves_expansion_queue(
        self,
    ):
        records = [
            self.record(
                sport="football",
                external_id="one",
            ),
            self.record(
                sport="football",
                external_id="two",
            ),
        ]

        result = (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=2,
            )
        )

        football = self.coverage_for(
            result,
            "football",
        )

        self.assertEqual(
            football[
                "coverage_status"
            ],
            "covered",
        )

        queued_sports = {
            row["sport_key"]
            for row
            in result[
                "expansion_queue"
            ]
        }

        self.assertNotIn(
            "football",
            queued_sports,
        )

    def test_review_gated_provider_is_blocked_by_default(
        self,
    ):
        result = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=1,
            )
        )

        basketball = self.coverage_for(
            result,
            "basketball",
        )

        ready = {
            row["provider_key"]
            for row
            in basketball[
                "provider_candidates"
            ]
        }

        blocked = {
            row["provider_key"]
            for row
            in basketball[
                "blocked_provider_candidates"
            ]
        }

        self.assertNotIn(
            "nba_api",
            ready,
        )

        self.assertIn(
            "nba_api",
            blocked,
        )

        self.assertEqual(
            basketball[
                "execution_status"
            ],
            "blocked",
        )

    def test_review_gated_provider_can_be_explicitly_opted_in(
        self,
    ):
        result = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=1,
                allowed_provider_statuses=(
                    "active",
                    "registered",
                    "registered_terms_review",
                ),
            )
        )

        basketball = self.coverage_for(
            result,
            "basketball",
        )

        ready = {
            row["provider_key"]
            for row
            in basketball[
                "provider_candidates"
            ]
        }

        self.assertIn(
            "nba_api",
            ready,
        )

        self.assertEqual(
            basketball[
                "execution_status"
            ],
            "ready",
        )

    def test_benchmark_wildcards_are_not_sport_targets(
        self,
    ):
        result = (
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=1,
            )
        )

        self.assertNotIn(
            "*",
            result[
                "target_sports"
            ],
        )

        provider_keys = {
            provider[
                "provider_key"
            ]
            for row
            in result[
                "coverage"
            ]
            for provider
            in (
                row[
                    "provider_candidates"
                ]
                + row[
                    "blocked_provider_candidates"
                ]
            )
        }

        self.assertNotIn(
            "averitec",
            provider_keys,
        )

        self.assertNotIn(
            "fever",
            provider_keys,
        )

    def test_balanced_sample_is_cross_sport_and_revision_safe(
        self,
    ):
        records = [
            self.record(
                sport="football",
                external_id="f1",
                dataset="football-a",
                payload_hash="v1",
            ),
            self.record(
                sport="football",
                external_id="f1",
                dataset="football-a",
                payload_hash="v2",
            ),
            self.record(
                sport="football",
                external_id="f2",
                dataset="football-b",
            ),
            self.record(
                sport="cricket",
                external_id="c1",
                dataset="cricket-a",
            ),
            self.record(
                sport="cricket",
                external_id="c2",
                dataset="cricket-b",
            ),
        ]

        sample = (
            build_balanced_validation_sample(
                records=records,
                per_sport_limit=2,
            )
        )

        self.assertEqual(
            len(sample),
            4,
        )

        by_sport = {}

        for row in sample:
            by_sport.setdefault(
                row[
                    "sport_key"
                ],
                [],
            ).append(row)

        self.assertEqual(
            len(
                by_sport[
                    "football"
                ]
            ),
            2,
        )

        self.assertEqual(
            len(
                by_sport[
                    "cricket"
                ]
            ),
            2,
        )

        football_external_ids = {
            row[
                "external_record_id"
            ]
            for row
            in by_sport[
                "football"
            ]
        }

        self.assertEqual(
            football_external_ids,
            {
                "f1",
                "f2",
            },
        )

    def test_input_order_is_deterministic(
        self,
    ):
        records = [
            self.record(
                sport="football",
                external_id="f1",
            ),
            self.record(
                sport="cricket",
                external_id="c1",
            ),
            self.record(
                sport="motorsport",
                external_id="m1",
            ),
        ]

        forward = (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=3,
            )
        )

        reverse = (
            build_validation_corpus_expansion(
                records=list(
                    reversed(
                        copy.deepcopy(
                            records
                        )
                    )
                ),
                target_records_per_sport=3,
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )

    def test_invalid_configuration_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "at least 1",
        ):
            build_validation_corpus_expansion(
                records=[],
                target_records_per_sport=0,
            )

        with self.assertRaisesRegex(
            ValueError,
            "At least one",
        ):
            build_validation_corpus_expansion(
                records=[],
                allowed_provider_statuses=[],
            )


if __name__ == "__main__":
    unittest.main()
