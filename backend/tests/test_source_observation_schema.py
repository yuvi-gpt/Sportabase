import sys
import tempfile
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


from app import main


class SourceObservationSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "source-observation-schema.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_source_observation_table_exists(
        self,
    ):
        conn = main.db_conn()

        try:
            row = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'source_observations'
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(
            row
        )

    def test_source_observation_columns(
        self,
    ):
        expected = {
            "id",
            "source_id",
            "media_item_id",
            "story_id",
            "subject_key",
            "observation_type",
            "status",
            "claim_summary",
            "provenance_url",
            "confidence",
            "observed_at",
            "recorded_at",
            "metadata_json",
        }

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA table_info(
                  source_observations
                )
                """
            ).fetchall()

            actual = {
                str(row["name"])
                for row in rows
            }
        finally:
            conn.close()

        self.assertEqual(
            actual,
            expected,
        )

    def test_source_observation_foreign_keys(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA foreign_key_list(
                  source_observations
                )
                """
            ).fetchall()

            relationships = {
                (
                    str(row["from"]),
                    str(row["table"]),
                    str(row["to"]),
                )
                for row in rows
            }
        finally:
            conn.close()

        self.assertIn(
            (
                "source_id",
                "intelligence_sources",
                "id",
            ),
            relationships,
        )

        self.assertIn(
            (
                "media_item_id",
                "media_items",
                "id",
            ),
            relationships,
        )

        self.assertIn(
            (
                "story_id",
                "intelligence_stories",
                "id",
            ),
            relationships,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )