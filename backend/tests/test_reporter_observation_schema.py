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


class ReporterObservationSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "reporter-observation-schema.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_reporter_observation_table_exists(
        self,
    ):
        conn = main.db_conn()

        try:
            row = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'reporter_observations'
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(
            row
        )

    def test_reporter_observation_columns(
        self,
    ):
        expected = {
            "id",
            "reporter_id",
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
                  reporter_observations
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

    def test_reporter_observation_foreign_keys(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA foreign_key_list(
                  reporter_observations
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

        expected = {
            (
                "reporter_id",
                "intelligence_reporters",
                "id",
            ),
            (
                "source_id",
                "intelligence_sources",
                "id",
            ),
            (
                "media_item_id",
                "media_items",
                "id",
            ),
            (
                "story_id",
                "intelligence_stories",
                "id",
            ),
        }

        self.assertTrue(
            expected.issubset(
                relationships
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )