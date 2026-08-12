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


class ObservationDependencyPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "observation-dependency-persistence.db"
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

        self.source_observation_a = (
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

        self.source_observation_b = (
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

        self.reporter_observation_a = (
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

        self.reporter_observation_b = (
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

    def record_default(
        self,
        **overrides,
    ):
        arguments = {
            "downstream_source_observation_id":
                self.source_observation_a["id"],
            "upstream_source_id":
                self.source_b["id"],
            "relationship_type":
                "attributed_to",
            "confidence": 0.9,
            "observed_at":
                "2026-08-12T11:20:00+00:00",
        }

        arguments.update(
            overrides
        )

        return (
            main.record_observation_dependency(
                **arguments
            )
        )

    def test_identical_dependency_is_idempotent(
        self,
    ):
        first = self.record_default(
            recorded_at=(
                "2026-08-12T11:21:00+00:00"
            ),
            metadata={
                "capture": "first",
            },
        )

        second = self.record_default(
            recorded_at=(
                "2026-08-12T11:30:00+00:00"
            ),
            metadata={
                "capture": "second",
            },
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["dependency"]["id"],
            second["dependency"]["id"],
        )

        conn = main.db_conn()

        try:
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
            1,
        )

    def test_relationship_type_is_normalized_and_changes_identity(
        self,
    ):
        first = self.record_default(
            relationship_type=" ATTRIBUTED_TO "
        )

        second = self.record_default(
            relationship_type="derived_from"
        )

        self.assertEqual(
            first["dependency"][
                "relationship_type"
            ],
            "attributed_to",
        )

        self.assertNotEqual(
            first["dependency"]["id"],
            second["dependency"]["id"],
        )

    def test_confidence_change_is_append_only(
        self,
    ):
        first = self.record_default(
            confidence=0.7
        )

        second = self.record_default(
            confidence=0.9
        )

        self.assertNotEqual(
            first["dependency"]["id"],
            second["dependency"]["id"],
        )

    def test_observed_time_change_is_append_only(
        self,
    ):
        first = self.record_default(
            observed_at=(
                "2026-08-12T11:20:00+00:00"
            )
        )

        second = self.record_default(
            observed_at=(
                "2026-08-12T11:21:00+00:00"
            )
        )

        self.assertNotEqual(
            first["dependency"]["id"],
            second["dependency"]["id"],
        )

    def test_all_target_shapes_are_supported(
        self,
    ):
        records = [
            main.record_observation_dependency(
                downstream_source_observation_id=(
                    self.source_observation_a["id"]
                ),
                upstream_source_observation_id=(
                    self.source_observation_b["id"]
                ),
                relationship_type="derived_from",
                observed_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            ),
            main.record_observation_dependency(
                downstream_source_observation_id=(
                    self.source_observation_a["id"]
                ),
                upstream_reporter_observation_id=(
                    self.reporter_observation_b["id"]
                ),
                relationship_type="attributed_to",
                observed_at=(
                    "2026-08-12T12:01:00+00:00"
                ),
            ),
            main.record_observation_dependency(
                downstream_reporter_observation_id=(
                    self.reporter_observation_a["id"]
                ),
                upstream_source_id=(
                    self.source_b["id"]
                ),
                relationship_type="attributed_to",
                observed_at=(
                    "2026-08-12T12:02:00+00:00"
                ),
            ),
            main.record_observation_dependency(
                downstream_reporter_observation_id=(
                    self.reporter_observation_a["id"]
                ),
                upstream_reporter_id=(
                    self.reporter_b["id"]
                ),
                relationship_type="attributed_to",
                observed_at=(
                    "2026-08-12T12:03:00+00:00"
                ),
            ),
        ]

        self.assertTrue(
            all(
                record["created"]
                for record in records
            )
        )

        self.assertEqual(
            len(
                {
                    record["dependency"]["id"]
                    for record in records
                }
            ),
            4,
        )

    def test_target_cardinality_is_validated_before_database(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.record_observation_dependency(
                upstream_source_id=(
                    self.source_b["id"]
                ),
                relationship_type="attributed_to",
                observed_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )

        with self.assertRaises(
            ValueError
        ):
            main.record_observation_dependency(
                downstream_source_observation_id=(
                    self.source_observation_a["id"]
                ),
                upstream_source_id=(
                    self.source_b["id"]
                ),
                upstream_reporter_id=(
                    self.reporter_b["id"]
                ),
                relationship_type="attributed_to",
                observed_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )

    def test_confidence_is_validated_before_database(
        self,
    ):
        for confidence in (
            "bad",
            -0.01,
            1.01,
        ):
            with self.assertRaises(
                ValueError
            ):
                self.record_default(
                    confidence=confidence
                )

    def test_required_semantic_fields_are_enforced(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                relationship_type=""
            )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                observed_at=""
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
