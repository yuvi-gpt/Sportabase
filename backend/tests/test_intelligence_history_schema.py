import sqlite3
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


class IntelligenceHistorySchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "history-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_intelligence_tables_exist(
        self,
    ):
        expected_tables = {
            "intelligence_sources",
            "intelligence_reporters",
            "media_items",
            "intelligence_stories",
            "story_media_links",
            "analysis_snapshots",
            "user_history",
        }

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()

            actual_tables = {
                str(row["name"])
                for row in rows
            }
        finally:
            conn.close()

        self.assertTrue(
            expected_tables.issubset(
                actual_tables
            )
        )

    def test_media_item_url_is_unique(
        self,
    ):
        conn = main.db_conn()

        try:
            indexes = conn.execute(
                """
                PRAGMA index_list(media_items)
                """
            ).fetchall()

            unique_column_sets = []

            for index_row in indexes:
                if int(
                    index_row["unique"]
                ) != 1:
                    continue

                columns = conn.execute(
                    "PRAGMA index_info("
                    + str(index_row["name"])
                    + ")"
                ).fetchall()

                unique_column_sets.append(
                    [
                        str(column["name"])
                        for column in columns
                    ]
                )
        finally:
            conn.close()

        self.assertIn(
            ["canonical_url"],
            unique_column_sets,
        )

    def test_snapshot_keeps_analysis_and_scoring_versions(
        self,
    ):
        conn = main.db_conn()

        try:
            columns = conn.execute(
                """
                PRAGMA table_info(
                  analysis_snapshots
                )
                """
            ).fetchall()

            column_names = {
                str(row["name"])
                for row in columns
            }
        finally:
            conn.close()

        self.assertIn(
            "analysis_version",
            column_names,
        )

        self.assertIn(
            "scoring_version",
            column_names,
        )

        self.assertIn(
            "content_hash",
            column_names,
        )

        self.assertIn(
            "response_json",
            column_names,
        )

    def test_foreign_keys_are_enabled_and_enforced(
        self,
    ):
        conn = main.db_conn()

        try:
            enabled = int(
                conn.execute(
                    "PRAGMA foreign_keys"
                ).fetchone()[0]
            )

            self.assertEqual(
                enabled,
                1,
            )

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO analysis_snapshots (
                      media_item_id,
                      analyzed_at,
                      mode,
                      analysis_version,
                      scoring_version,
                      content_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-media-item",
                        "2026-08-11T12:00:00+00:00",
                        "article",
                        "analysis-test-v1",
                        "merit-test-v1",
                        "content-hash-test",
                    ),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )