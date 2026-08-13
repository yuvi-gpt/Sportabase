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


class ClaimLinkSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "claim-link-schema.db"
        )

        main.init_db()

        self.source = (
            main.upsert_intelligence_source(
                url="https://source.example/",
                display_name="Source",
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )
        )

        self.reporter = (
            main.upsert_intelligence_reporter(
                identity_key="reporter-a",
                display_name="Reporter A",
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )
        )

        self.claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|agreement"
                ),
                subject_key="transfer|a|b",
                canonical_text=(
                    "Agreement reached."
                ),
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )
        )

        self.source_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                subject_key="transfer|a|b",
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    "Agreement reached."
                ),
                observed_at=(
                    "2026-08-12T12:05:00+00:00"
                ),
            )["observation"]
        )

        self.reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key="transfer|a|b",
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    "Agreement reached."
                ),
                observed_at=(
                    "2026-08-12T12:06:00+00:00"
                ),
            )["observation"]
        )

        self.evidence = (
            main.record_evidence(
                evidence_type="quote",
                subject_key="transfer|a|b",
                observed_at=(
                    "2026-08-12T12:07:00+00:00"
                ),
                claim_summary=(
                    "Agreement reached."
                ),
                reference_key="quote-1",
            )["evidence"]
        )

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
                    "claim_links",
                ),
            ).fetchone()

            columns = [
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      claim_links
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
                "claim_id",
                "source_observation_id",
                "reporter_observation_id",
                "evidence_id",
                "relationship_type",
                "confidence",
                "observed_at",
                "recorded_at",
                "metadata_json",
            ],
        )

    def test_each_target_shape_is_supported(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = (
                (
                    "claim-link-source",
                    "source_observation_id",
                    self.source_observation["id"],
                ),
                (
                    "claim-link-reporter",
                    "reporter_observation_id",
                    self.reporter_observation["id"],
                ),
                (
                    "claim-link-evidence",
                    "evidence_id",
                    self.evidence["id"],
                ),
            )

            for (
                link_id,
                target_column,
                target_id,
            ) in rows:
                conn.execute(
                    f"""
                    INSERT INTO claim_links (
                      id,
                      claim_id,
                      {target_column},
                      relationship_type,
                      confidence,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        link_id,
                        self.claim["id"],
                        target_id,
                        "aligned_to",
                        0.9,
                        (
                            "2026-08-12"
                            "T12:10:00+00:00"
                        ),
                        (
                            "2026-08-12"
                            "T12:11:00+00:00"
                        ),
                    ),
                )

            conn.commit()

            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM claim_links
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            3,
        )

    def test_exactly_one_target_is_required(
        self,
    ):
        conn = main.db_conn()

        try:
            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO claim_links (
                      id,
                      claim_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-target",
                        self.claim["id"],
                        "aligned_to",
                        (
                            "2026-08-12"
                            "T12:10:00+00:00"
                        ),
                        (
                            "2026-08-12"
                            "T12:11:00+00:00"
                        ),
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO claim_links (
                      id,
                      claim_id,
                      source_observation_id,
                      reporter_observation_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "two-targets",
                        self.claim["id"],
                        self.source_observation["id"],
                        self.reporter_observation["id"],
                        "aligned_to",
                        (
                            "2026-08-12"
                            "T12:10:00+00:00"
                        ),
                        (
                            "2026-08-12"
                            "T12:11:00+00:00"
                        ),
                    ),
                )
        finally:
            conn.close()

    def test_confidence_is_bounded(
        self,
    ):
        conn = main.db_conn()

        try:
            for index, confidence in enumerate(
                (
                    -0.01,
                    1.01,
                )
            ):
                with self.assertRaises(
                    sqlite3.IntegrityError
                ):
                    conn.execute(
                        """
                        INSERT INTO claim_links (
                          id,
                          claim_id,
                          source_observation_id,
                          relationship_type,
                          confidence,
                          observed_at,
                          recorded_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"bad-confidence-{index}",
                            self.claim["id"],
                            self.source_observation[
                                "id"
                            ],
                            "aligned_to",
                            confidence,
                            (
                                "2026-08-12"
                                "T12:10:00+00:00"
                            ),
                            (
                                "2026-08-12"
                                "T12:11:00+00:00"
                            ),
                        ),
                    )

                conn.rollback()
        finally:
            conn.close()

    def test_foreign_keys_are_enforced(
        self,
    ):
        conn = main.db_conn()

        try:
            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO claim_links (
                      id,
                      claim_id,
                      source_observation_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-claim",
                        "missing-claim-id",
                        self.source_observation["id"],
                        "aligned_to",
                        (
                            "2026-08-12"
                            "T12:10:00+00:00"
                        ),
                        (
                            "2026-08-12"
                            "T12:11:00+00:00"
                        ),
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO claim_links (
                      id,
                      claim_id,
                      source_observation_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-target",
                        self.claim["id"],
                        "missing-observation-id",
                        "aligned_to",
                        (
                            "2026-08-12"
                            "T12:10:00+00:00"
                        ),
                        (
                            "2026-08-12"
                            "T12:11:00+00:00"
                        ),
                    ),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
