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


class IntelligenceClaimSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "intelligence-claim-schema.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_table_and_columns_exist(
        self,
    ):
        conn = main.db_conn()

        try:
            table = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = ?
                """,
                (
                    "intelligence_claims",
                ),
            ).fetchone()

            columns = [
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      intelligence_claims
                    )
                    """
                ).fetchall()
            ]
        finally:
            conn.close()

        self.assertIsNotNone(table)

        self.assertEqual(
            columns,
            [
                "id",
                "canonical_key",
                "subject_key",
                "canonical_text",
                "claim_type",
                "first_seen_at",
                "last_seen_at",
                "metadata_json",
            ],
        )

    def test_canonical_key_is_unique(
        self,
    ):
        conn = main.db_conn()

        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id,
                  canonical_key,
                  subject_key,
                  canonical_text,
                  first_seen_at,
                  last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "claim-1",
                    (
                        "transfer|player-a|club-b|"
                        "agreement-reached"
                    ),
                    "transfer|player-a|club-b",
                    (
                        "Club B reached an agreement "
                        "for Player A."
                    ),
                    "2026-08-12T12:00:00+00:00",
                    "2026-08-12T12:00:00+00:00",
                ),
            )

            conn.commit()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id,
                      canonical_key,
                      subject_key,
                      canonical_text,
                      first_seen_at,
                      last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "claim-2",
                        (
                            "transfer|player-a|club-b|"
                            "agreement-reached"
                        ),
                        "transfer|player-a|club-b",
                        (
                            "A differently worded "
                            "description."
                        ),
                        "2026-08-12T12:05:00+00:00",
                        "2026-08-12T12:05:00+00:00",
                    ),
                )
        finally:
            conn.close()

    def test_subject_can_contain_multiple_claims(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = (
                (
                    "claim-agreement",
                    (
                        "transfer|player-a|club-b|"
                        "agreement-reached"
                    ),
                    "transfer|player-a|club-b",
                    "Agreement reached.",
                ),
                (
                    "claim-medical",
                    (
                        "transfer|player-a|club-b|"
                        "medical-scheduled"
                    ),
                    "transfer|player-a|club-b",
                    "Medical scheduled.",
                ),
            )

            for (
                claim_id,
                canonical_key,
                subject_key,
                canonical_text,
            ) in rows:
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id,
                      canonical_key,
                      subject_key,
                      canonical_text,
                      first_seen_at,
                      last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_id,
                        canonical_key,
                        subject_key,
                        canonical_text,
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:00:00+00:00",
                    ),
                )

            conn.commit()

            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM intelligence_claims
                    WHERE subject_key = ?
                    """,
                    (
                        "transfer|player-a|club-b",
                    ),
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            2,
        )

    def test_claim_identity_has_no_truth_judgment_fields(
        self,
    ):
        conn = main.db_conn()

        try:
            columns = {
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      intelligence_claims
                    )
                    """
                ).fetchall()
            }
        finally:
            conn.close()

        forbidden = {
            "status",
            "verification_status",
            "confidence",
            "merit_score",
            "corroborated",
            "independent",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                columns
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
