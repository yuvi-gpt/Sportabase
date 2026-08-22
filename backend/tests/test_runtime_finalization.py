import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.runtime_finalization import (
    INTELLIGENCE_RUNTIME_FINALIZATION_VERSION,
    finalize_structured_claim_materialization,
)


NOW = "2026-08-22T10:00:00+00:00"
LATER = "2026-08-22T11:00:00+00:00"
SUBJECT = "player|one"
DESTINATION = "club|arsenal"


class RuntimeFinalizationTests(unittest.TestCase):
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

    def test_non_materialized_result_skips_reconciliation(self):
        with patch(
            "app.intelligence.runtime_finalization.reconcile_claim_evolution_safely"
        ) as reconciler:
            result = finalize_structured_claim_materialization(
                materialization={
                    "status": "not_materialized",
                    "canonical_claim_id": "",
                },
                connection_factory=self.factory,
            )

        self.assertEqual(result["version"], INTELLIGENCE_RUNTIME_FINALIZATION_VERSION)
        self.assertEqual(result["status"], "skipped")
        reconciler.assert_not_called()

    def test_reconciliation_failure_is_advisory(self):
        with patch(
            "app.intelligence.runtime_finalization.reconcile_claim_evolution_safely",
            return_value={
                "status": "unavailable",
                "reason": "claim_evolution_runtime_failure",
                "error_type": "RuntimeError",
            },
        ):
            result = finalize_structured_claim_materialization(
                materialization={
                    "status": "materialized",
                    "canonical_claim_id": "claim-1",
                },
                connection_factory=self.factory,
            )

        self.assertEqual(result["status"], "advisory_failure")
        self.assertFalse(result["policy"]["affects_live_merit"])
        self.assertTrue(result["policy"]["failure_is_advisory"])

    def test_real_materialized_progression_is_reconciled(self):
        first = materialize_canonical_claim(
            candidate=self.candidate("interest"),
            claim_text="Player One is linked with Arsenal",
            observed_at=NOW,
            connection_factory=self.factory,
        )
        second = materialize_canonical_claim(
            candidate=self.candidate("negotiating"),
            claim_text="Player One is negotiating with Arsenal",
            observed_at=LATER,
            connection_factory=self.factory,
        )

        result = finalize_structured_claim_materialization(
            materialization={
                "status": "materialized",
                "canonical_claim_id": second["claim"]["id"],
            },
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "completed")
        evolution = result["evolution"]
        self.assertEqual(evolution["status"], "reconciled")
        self.assertGreaterEqual(evolution["links_written"], 1)

        conn = self.factory()
        try:
            row = conn.execute(
                """
                SELECT relationship_type
                FROM claim_evolution_links
                WHERE predecessor_claim_id = ?
                  AND successor_claim_id = ?
                """,
                (first["claim"]["id"], second["claim"]["id"]),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["relationship_type"], "progresses_to")


if __name__ == "__main__":
    unittest.main()
