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


class ObservationDependencySchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "observation-dependency-schema.db"
        )

        main.init_db()

        self.source_a = (
            main.upsert_intelligence_source(
                url="https://a.example/",
                display_name="Source A",
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.source_b = (
            main.upsert_intelligence_source(
                url="https://b.example/",
                display_name="Source B",
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.reporter_a = (
            main.upsert_intelligence_reporter(
                identity_key="reporter-a",
                display_name="Reporter A",
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.reporter_b = (
            main.upsert_intelligence_reporter(
                identity_key="reporter-b",
                display_name="Reporter B",
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.source_observation = (
            main.record_source_observation(
                source_id=self.source_a["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T11:00:00+00:00"
                ),
            )["observation"]
        )

        self.upstream_source_observation = (
            main.record_source_observation(
                source_id=self.source_b["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T10:30:00+00:00"
                ),
            )["observation"]
        )

        self.reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter_a["id"],
                source_id=self.source_a["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T11:15:00+00:00"
                ),
            )["observation"]
        )

        self.upstream_reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter_b["id"],
                source_id=self.source_b["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T10:45:00+00:00"
                ),
            )["observation"]
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
                    "observation_dependencies",
                ),
            ).fetchone()

            columns = [
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      observation_dependencies
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
                "downstream_source_observation_id",
                "downstream_reporter_observation_id",
                "upstream_source_observation_id",
                "upstream_reporter_observation_id",
                "upstream_source_id",
                "upstream_reporter_id",
                "relationship_type",
                "confidence",
                "observed_at",
                "recorded_at",
                "metadata_json",
            ],
        )

    def test_valid_dependency_targets_are_supported(
        self,
    ):
        conn = main.db_conn()

        try:
            conn.execute(
                """
                INSERT INTO observation_dependencies (
                  id,
                  downstream_source_observation_id,
                  upstream_source_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dependency-source-actor",
                    self.source_observation["id"],
                    self.source_b["id"],
                    "attributed_to",
                    0.9,
                    "2026-08-12T11:20:00+00:00",
                    "2026-08-12T11:21:00+00:00",
                ),
            )

            conn.execute(
                """
                INSERT INTO observation_dependencies (
                  id,
                  downstream_reporter_observation_id,
                  upstream_reporter_observation_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "dependency-reporter-observation",
                    self.reporter_observation["id"],
                    self.upstream_reporter_observation[
                        "id"
                    ],
                    "derived_from",
                    0.8,
                    "2026-08-12T11:25:00+00:00",
                    "2026-08-12T11:26:00+00:00",
                ),
            )

            conn.commit()

            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM observation_dependencies
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            2,
        )

    def test_exactly_one_downstream_and_upstream_are_required(
        self,
    ):
        conn = main.db_conn()

        try:
            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO observation_dependencies (
                      id,
                      upstream_source_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-downstream",
                        self.source_b["id"],
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO observation_dependencies (
                      id,
                      downstream_source_observation_id,
                      downstream_reporter_observation_id,
                      upstream_source_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "two-downstreams",
                        self.source_observation["id"],
                        self.reporter_observation["id"],
                        self.source_b["id"],
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO observation_dependencies (
                      id,
                      downstream_source_observation_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-upstream",
                        self.source_observation["id"],
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO observation_dependencies (
                      id,
                      downstream_source_observation_id,
                      upstream_source_observation_id,
                      upstream_source_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "two-upstreams",
                        self.source_observation["id"],
                        self.upstream_source_observation[
                            "id"
                        ],
                        self.source_b["id"],
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
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
                        INSERT INTO observation_dependencies (
                          id,
                          downstream_source_observation_id,
                          upstream_source_id,
                          relationship_type,
                          confidence,
                          observed_at,
                          recorded_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"bad-confidence-{index}",
                            self.source_observation["id"],
                            self.source_b["id"],
                            "attributed_to",
                            confidence,
                            "2026-08-12T12:00:00+00:00",
                            "2026-08-12T12:01:00+00:00",
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
                    INSERT INTO observation_dependencies (
                      id,
                      downstream_source_observation_id,
                      upstream_source_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-downstream-fk",
                        "missing-observation",
                        self.source_b["id"],
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
                    ),
                )

            conn.rollback()

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO observation_dependencies (
                      id,
                      downstream_source_observation_id,
                      upstream_source_id,
                      relationship_type,
                      observed_at,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "missing-upstream-fk",
                        self.source_observation["id"],
                        "missing-source",
                        "attributed_to",
                        "2026-08-12T12:00:00+00:00",
                        "2026-08-12T12:01:00+00:00",
                    ),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
