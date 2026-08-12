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


class EvidenceContextRetrievalTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-context-retrieval-test.db"
        )

        main.init_db()

        self.subject_a = (
            "transfer|player-a|club-b"
        )

        self.subject_b = (
            "transfer|player-a|club-c"
        )

        self.source = (
            main.upsert_intelligence_source(
                url="https://example.com/",
                display_name="Example Sports",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

        self.reporter = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "social|x|reporter-a"
                ),
                display_name="Reporter A",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def seed_subject(
        self,
        *,
        subject_key,
        suffix,
    ):
        source_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                subject_key=subject_key,
                observation_type="report",
                status="unresolved",
                provenance_url=(
                    f"https://example.com/"
                    f"source-{suffix}"
                ),
                confidence=0.7,
                observed_at=(
                    f"2026-08-12T10:0{suffix}:00+00:00"
                ),
            )
        )

        reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key=subject_key,
                observation_type="report",
                status="unresolved",
                provenance_url=(
                    f"https://example.com/"
                    f"reporter-{suffix}"
                ),
                confidence=0.8,
                observed_at=(
                    f"2026-08-12T10:1{suffix}:00+00:00"
                ),
            )
        )

        evidence = main.record_evidence(
            evidence_type="independent_report",
            subject_key=subject_key,
            canonical_url=(
                f"https://example.com/"
                f"evidence-{suffix}"
            ),
            verification_status="unverified",
            observed_at=(
                f"2026-08-12T10:2{suffix}:00+00:00"
            ),
        )

        link = main.record_evidence_link(
            evidence_id=evidence["evidence"]["id"],
            source_id=self.source["id"],
            relationship_type="supports",
            confidence=0.9,
            linked_at=(
                f"2026-08-12T10:3{suffix}:00+00:00"
            ),
        )

        return {
            "source_observation": (
                source_observation["observation"]
            ),
            "reporter_observation": (
                reporter_observation["observation"]
            ),
            "evidence": evidence["evidence"],
            "link": link["link"],
        }

    def test_exact_subject_only_is_loaded(
        self,
    ):
        subject_a_rows = self.seed_subject(
            subject_key=self.subject_a,
            suffix="1",
        )

        self.seed_subject(
            subject_key=self.subject_b,
            suffix="2",
        )

        context = (
            main.load_evidence_context_for_subject(
                subject_key=self.subject_a,
            )
        )

        self.assertEqual(
            context["scope"]["subject_key"],
            self.subject_a,
        )

        self.assertEqual(
            [
                row["id"]
                for row in context[
                    "source_observations"
                ]
            ],
            [
                subject_a_rows[
                    "source_observation"
                ]["id"]
            ],
        )

        self.assertEqual(
            [
                row["id"]
                for row in context[
                    "reporter_observations"
                ]
            ],
            [
                subject_a_rows[
                    "reporter_observation"
                ]["id"]
            ],
        )

        self.assertEqual(
            [
                row["id"]
                for row in context[
                    "evidence_records"
                ]
            ],
            [
                subject_a_rows[
                    "evidence"
                ]["id"]
            ],
        )

        self.assertEqual(
            [
                row["id"]
                for row in context[
                    "evidence_links"
                ]
            ],
            [
                subject_a_rows[
                    "link"
                ]["id"]
            ],
        )

    def test_evidence_link_is_loaded_by_evidence_subject(
        self,
    ):
        seeded = self.seed_subject(
            subject_key=self.subject_a,
            suffix="1",
        )

        context = (
            main.load_evidence_context_for_subject(
                subject_key=self.subject_a,
            )
        )

        self.assertEqual(
            len(context["evidence_links"]),
            1,
        )

        self.assertEqual(
            context["evidence_links"][0][
                "evidence_id"
            ],
            seeded["evidence"]["id"],
        )

        self.assertEqual(
            context["evidence_links"][0][
                "target_type"
            ],
            "source",
        )

        self.assertEqual(
            context["evidence_links"][0][
                "target_id"
            ],
            self.source["id"],
        )

    def test_empty_subject_context_is_stable(
        self,
    ):
        first = (
            main.load_evidence_context_for_subject(
                subject_key=self.subject_a,
            )
        )

        second = (
            main.load_evidence_context_for_subject(
                subject_key=self.subject_a,
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            first["source_observations"],
            [],
        )

        self.assertEqual(
            first["reporter_observations"],
            [],
        )

        self.assertEqual(
            first["evidence_records"],
            [],
        )

        self.assertEqual(
            first["evidence_links"],
            [],
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_subject_key_is_required(
        self,
    ):
        with self.assertRaises(ValueError):
            main.load_evidence_context_for_subject(
                subject_key="",
            )


if __name__ == "__main__":
    unittest.main()
