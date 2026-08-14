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


class SnapshotContextSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "context-schema-test.db"
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def identity_columns(self):
        conn = main.db_conn()

        try:
            columns = conn.execute(
                """
                PRAGMA index_info(
                  idx_analysis_snapshots_identity
                )
                """
            ).fetchall()

            return [
                str(row["name"])
                for row in columns
            ]
        finally:
            conn.close()

    def test_fresh_database_has_context_identity(
        self,
    ):
        main.init_db()

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
            "context_hash",
            column_names,
        )

        self.assertEqual(
            self.identity_columns(),
            [
                "media_item_id",
                "mode",
                "content_hash",
                "context_hash",
                "analysis_version",
                "scoring_version",
            ],
        )

    def test_old_database_migrates_in_place(
        self,
    ):
        conn = sqlite3.connect(
            str(main.DB_PATH)
        )

        try:
            conn.executescript(
                """
                CREATE TABLE analysis_snapshots (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  media_item_id TEXT NOT NULL,
                  story_id TEXT,
                  analyzed_at TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  analysis_version TEXT NOT NULL,
                  scoring_version TEXT NOT NULL DEFAULT '',
                  content_hash TEXT NOT NULL,
                  merit_score INTEGER,
                  evidence_score INTEGER,
                  logic_score INTEGER,
                  badge TEXT NOT NULL DEFAULT '',
                  verdict TEXT NOT NULL DEFAULT '',
                  article_type TEXT NOT NULL DEFAULT '',
                  score_components_json TEXT NOT NULL DEFAULT '{}',
                  score_calculation_json TEXT NOT NULL DEFAULT '{}',
                  reasons_json TEXT NOT NULL DEFAULT '[]',
                  response_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE UNIQUE INDEX
                idx_analysis_snapshots_identity
                ON analysis_snapshots(
                  media_item_id,
                  mode,
                  content_hash,
                  analysis_version,
                  scoring_version
                );
                """
            )

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
                    "legacy-media",
                    "2026-08-11T12:00:00+00:00",
                    "article",
                    "analysis-v1",
                    "merit-v1",
                    "content-v1",
                ),
            )

            conn.commit()
        finally:
            conn.close()

        main.init_db()

        conn = main.db_conn()

        try:
            row = conn.execute(
                """
                SELECT context_hash
                FROM analysis_snapshots
                WHERE media_item_id = ?
                """,
                (
                    "legacy-media",
                ),
            ).fetchone()

            self.assertIsNotNone(
                row
            )

            self.assertEqual(
                str(row["context_hash"]),
                "",
            )

            conn.execute(
                """
                INSERT INTO analysis_snapshots (
                  media_item_id,
                  analyzed_at,
                  mode,
                  analysis_version,
                  scoring_version,
                  content_hash,
                  context_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-media",
                    "2026-08-11T13:00:00+00:00",
                    "article",
                    "analysis-v1",
                    "merit-v1",
                    "content-v1",
                    "evidence-context-v2",
                ),
            )

            conn.commit()

            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM analysis_snapshots
                    WHERE media_item_id = ?
                    """,
                    (
                        "legacy-media",
                    ),
                ).fetchone()[0]
            )

            self.assertEqual(
                count,
                2,
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
                      content_hash,
                      context_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-media",
                        "2026-08-11T14:00:00+00:00",
                        "article",
                        "analysis-v1",
                        "merit-v1",
                        "content-v1",
                        "",
                    ),
                )

        finally:
            conn.close()

        self.assertEqual(
            self.identity_columns(),
            [
                "media_item_id",
                "mode",
                "content_hash",
                "context_hash",
                "analysis_version",
                "scoring_version",
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )