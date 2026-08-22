import tempfile
import unittest
from pathlib import Path

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_evolution_backfill import run_claim_evolution_backfill
from app.intelligence.claim_materialization import materialize_canonical_claim


NOW = "2026-08-22T10:00:00+00:00"
LATER = "2026-08-22T11:00:00+00:00"
SUBJECT = "player|one"
DESTINATION = "club|arsenal"


class ClaimEvolutionBackfillTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        initialize_database(self.factory, SCHEMA)

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate(state):
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": state,
            "negated": False,
            "roles": {"destination": DESTINATION},
            "facets": {},
        }

    def seed_progression(self):
        materialize_canonical_claim(
            candidate=self.candidate("interest"),
            claim_text="Player One linked with Arsenal",
            observed_at=NOW,
            connection_factory=self.factory,
        )
        materialize_canonical_claim(
            candidate=self.candidate("negotiating"),
            claim_text="Player One negotiating with Arsenal",
            observed_at=LATER,
            connection_factory=self.factory,
        )

    def link_count(self):
        conn = self.factory()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM claim_evolution_links"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def test_dry_run_is_default_and_does_not_write(self):
        self.seed_progression()
        self.assertEqual(self.link_count(), 0)

        result = run_claim_evolution_backfill(
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "planned")
        self.assertFalse(result["apply"])
        self.assertEqual(result["counts"]["claims_selected"], 2)
        self.assertEqual(self.link_count(), 0)

    def test_apply_reconciles_and_is_idempotent(self):
        self.seed_progression()

        first = run_claim_evolution_backfill(
            connection_factory=self.factory,
            apply=True,
        )
        first_count = self.link_count()
        second = run_claim_evolution_backfill(
            connection_factory=self.factory,
            apply=True,
        )
        second_count = self.link_count()

        self.assertEqual(first["status"], "completed")
        self.assertGreaterEqual(first["counts"]["reconciled"], 1)
        self.assertGreaterEqual(first_count, 1)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second_count, first_count)

    def test_limit_is_bounded(self):
        with self.assertRaises(ValueError):
            run_claim_evolution_backfill(
                connection_factory=self.factory,
                limit=0,
            )

        with self.assertRaises(ValueError):
            run_claim_evolution_backfill(
                connection_factory=self.factory,
                limit=50001,
            )


if __name__ == "__main__":
    unittest.main()
