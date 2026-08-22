import tempfile
import unittest
from pathlib import Path

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA


class ClaimEvolutionMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def test_fresh_database_bootstraps_claim_evolution_schema(self):
        initialize_database(self.factory, SCHEMA)

        conn = self.factory()
        try:
            table = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'claim_evolution_links'
                """
            ).fetchone()
            indexes = {
                row[0]
                for row in conn.execute(
                    "PRAGMA index_list(claim_evolution_links)"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIsNotNone(table)
        self.assertIn("idx_claim_evolution_predecessor", indexes)
        self.assertIn("idx_claim_evolution_successor", indexes)
        self.assertIn("idx_claim_evolution_family", indexes)
        self.assertIn("idx_claim_evolution_subject", indexes)

    def test_migration_is_idempotent(self):
        initialize_database(self.factory, SCHEMA)
        initialize_database(self.factory, SCHEMA)

        conn = self.factory()
        try:
            count = conn.execute(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'claim_evolution_links'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(int(count), 1)


if __name__ == "__main__":
    unittest.main()
