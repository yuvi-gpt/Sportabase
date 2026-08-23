import hashlib
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


from app.db.connection import (
    connect_database,
)

from app.db.schema import (
    SCHEMA,
)

from evals.historical_article_claim_backfill import (
    HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION,
    build_frozen_allowlist_from_plan,
    execute_historical_article_claim_backfill,
)

from evals.historical_article_claim_backfill_plan import (
    build_historical_article_claim_backfill_plan,
)

from evals.negative_merit_real_case_inventory import (
    build_negative_merit_real_case_inventory,
)


class HistoricalArticleClaimBackfillTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp.name
            )
            / "backfill.db"
        )

        conn = connect_database(
            self.db_path
        )

        try:
            conn.executescript(
                SCHEMA
            )

            conn.execute(
                """
                INSERT INTO stories (
                  id,
                  source,
                  sport,
                  title,
                  link,
                  published,
                  summary,
                  tldr_json,
                  merit_score,
                  badge,
                  created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-contract-story",
                    "Example Sports",
                    "football",
                    (
                        "Sources: Foden agrees "
                        "new deal with Man City"
                    ),
                    (
                        "https://example.com/"
                        "foden-contract"
                    ),
                    (
                        "2026-05-05T18:23:19+00:00"
                    ),
                    (
                        "Phil Foden has reached "
                        "agreement on a new contract "
                        "with Manchester City."
                    ),
                    "[]",
                    0,
                    "",
                    (
                        "2026-05-05T23:46:21+00:00"
                    ),
                ),
            )

            conn.commit()

        finally:
            conn.close()

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    def allowlist(
        self,
    ):
        plan = (
            build_historical_article_claim_backfill_plan(
                db_path=(
                    self.db_path
                )
            )
        )

        self.assertEqual(
            plan[
                "metrics"
            ][
                "admit_count"
            ],
            1,
        )

        return (
            build_frozen_allowlist_from_plan(
                plan=plan
            )
        )

    def counts(
        self,
    ):
        conn = connect_database(
            self.db_path
        )

        try:
            return {
                table: conn.execute(
                    (
                        "SELECT COUNT(*) "
                        "FROM "
                        + table
                    )
                ).fetchone()[
                    0
                ]
                for table
                in (
                    "media_items",
                    "intelligence_sources",
                    "intelligence_claims",
                    "source_observations",
                    "claim_links",
                    "analysis_snapshots",
                    "evidence_records",
                )
            }

        finally:
            conn.close()

    def test_validation_only_does_not_write(
        self,
    ):
        allowlist = self.allowlist()

        before = hashlib.sha256(
            self.db_path.read_bytes()
        ).hexdigest()

        report = (
            execute_historical_article_claim_backfill(
                db_path=(
                    self.db_path
                ),
                allowlist=(
                    allowlist
                ),
                apply=False,
            )
        )

        after = hashlib.sha256(
            self.db_path.read_bytes()
        ).hexdigest()

        self.assertEqual(
            before,
            after,
        )

        self.assertEqual(
            report[
                "status"
            ],
            "validated_no_write",
        )

    def test_apply_persists_only_reported_claim_seed_layer(
        self,
    ):
        report = (
            execute_historical_article_claim_backfill(
                db_path=(
                    self.db_path
                ),
                allowlist=(
                    self.allowlist()
                ),
                apply=True,
            )
        )

        self.assertEqual(
            report[
                "version"
            ],
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION,
        )

        self.assertEqual(
            report[
                "entry_count"
            ],
            1,
        )

        counts = self.counts()

        self.assertEqual(
            counts[
                "media_items"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "intelligence_sources"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "intelligence_claims"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "source_observations"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "claim_links"
            ],
            1,
        )

        self.assertEqual(
            counts[
                "analysis_snapshots"
            ],
            0,
        )

        self.assertEqual(
            counts[
                "evidence_records"
            ],
            0,
        )

    def test_apply_is_idempotent(
        self,
    ):
        allowlist = self.allowlist()

        execute_historical_article_claim_backfill(
            db_path=(
                self.db_path
            ),
            allowlist=allowlist,
            apply=True,
        )

        first = self.counts()

        execute_historical_article_claim_backfill(
            db_path=(
                self.db_path
            ),
            allowlist=allowlist,
            apply=True,
        )

        second = self.counts()

        self.assertEqual(
            first,
            second,
        )

    def test_historical_feed_seed_is_not_full_capture_ready(
        self,
    ):
        execute_historical_article_claim_backfill(
            db_path=(
                self.db_path
            ),
            allowlist=(
                self.allowlist()
            ),
            apply=True,
        )

        inventory = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        self.assertEqual(
            inventory[
                "metrics"
            ][
                "primary_claims"
            ],
            1,
        )

        self.assertEqual(
            inventory[
                "metrics"
            ][
                "article_captures_ready"
            ],
            0,
        )

        self.assertEqual(
            inventory[
                "metrics"
            ][
                "corpus_export_ready"
            ],
            0,
        )

        self.assertIn(
            "full_article_capture_unavailable",
            inventory[
                "cases"
            ][
                0
            ][
                "blockers"
            ],
        )

    def test_tampered_allowlist_is_rejected(
        self,
    ):
        allowlist = self.allowlist()

        allowlist[
            "entries"
        ][
            0
        ][
            "title"
        ] = "Tampered title"

        with self.assertRaisesRegex(
            ValueError,
            "digest mismatch",
        ):
            from evals.historical_article_claim_backfill import (
                load_allowlist,
                write_allowlist,
            )

            path = (
                Path(
                    self.temp.name
                )
                / "tampered.json"
            )

            write_allowlist(
                path,
                allowlist,
            )

            load_allowlist(
                path
            )


if __name__ == "__main__":
    unittest.main()
