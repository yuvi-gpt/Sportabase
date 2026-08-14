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


class EvidenceContextMediaRetrievalTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "media-context-retrieval-test.db"
        )

        main.init_db()

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

        self.media = main.upsert_media_item(
            url=(
                "https://example.com/"
                "player-a-club-b"
            ),
            mode="article",
            title=(
                "Player A linked with Club B"
            ),
            content_hash="media-content-a",
            source_id=self.source["id"],
            reporter_id=self.reporter["id"],
            seen_at=(
                "2026-08-12T09:30:00+00:00"
            ),
        )

        self.other_media = main.upsert_media_item(
            url=(
                "https://example.com/"
                "player-c-club-d"
            ),
            mode="article",
            title=(
                "Player C linked with Club D"
            ),
            content_hash="media-content-b",
            source_id=self.source["id"],
            reporter_id=self.reporter["id"],
            seen_at=(
                "2026-08-12T09:35:00+00:00"
            ),
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_exact_media_item_only_is_loaded(
        self,
    ):
        source_match = (
            main.record_source_observation(
                source_id=self.source["id"],
                media_item_id=self.media["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )["observation"]
        )

        main.record_source_observation(
            source_id=self.source["id"],
            media_item_id=self.other_media["id"],
            subject_key=(
                "transfer|player-c|club-d"
            ),
            observation_type="report",
            status="unresolved",
            observed_at=(
                "2026-08-12T10:05:00+00:00"
            ),
        )

        reporter_match = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                media_item_id=self.media["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T10:10:00+00:00"
                ),
            )["observation"]
        )

        main.record_reporter_observation(
            reporter_id=self.reporter["id"],
            source_id=self.source["id"],
            media_item_id=self.other_media["id"],
            subject_key=(
                "transfer|player-c|club-d"
            ),
            observation_type="report",
            status="unresolved",
            observed_at=(
                "2026-08-12T10:15:00+00:00"
            ),
        )

        evidence_match = main.record_evidence(
            evidence_type="independent_report",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="MEDIA-A-EVIDENCE",
            verification_status="unverified",
            observed_at=(
                "2026-08-12T11:00:00+00:00"
            ),
        )["evidence"]

        evidence_other = main.record_evidence(
            evidence_type="independent_report",
            subject_key=(
                "transfer|player-c|club-d"
            ),
            reference_key="MEDIA-B-EVIDENCE",
            verification_status="unverified",
            observed_at=(
                "2026-08-12T11:05:00+00:00"
            ),
        )["evidence"]

        link_match = main.record_evidence_link(
            evidence_id=evidence_match["id"],
            media_item_id=self.media["id"],
            relationship_type="supports",
            confidence=0.8,
        )["link"]

        main.record_evidence_link(
            evidence_id=evidence_other["id"],
            media_item_id=self.other_media["id"],
            relationship_type="supports",
            confidence=0.8,
        )

        context = (
            main.load_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            context["scope"]["media_item_id"],
            self.media["id"],
        )

        self.assertEqual(
            [
                row["id"]
                for row in context[
                    "source_observations"
                ]
            ],
            [
                source_match["id"],
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
                reporter_match["id"],
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
                evidence_match["id"],
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
                link_match["id"],
            ],
        )

    def test_story_evidence_is_not_implicitly_loaded(
        self,
    ):
        story = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-b"
            ),
            canonical_title=(
                "Player A to Club B"
            ),
            seen_at=(
                "2026-08-12T09:00:00+00:00"
            ),
        )

        main.link_media_item_to_story(
            story_id=story["id"],
            media_item_id=self.media["id"],
            relationship_type="reports",
            confidence=0.8,
        )

        evidence = main.record_evidence(
            evidence_type="official_statement",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="STORY-ONLY-EVIDENCE",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:00:00+00:00"
            ),
        )["evidence"]

        main.record_evidence_link(
            evidence_id=evidence["id"],
            story_id=story["id"],
            relationship_type="supports",
            confidence=0.95,
        )

        context = (
            main.load_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            context["evidence_records"],
            [],
        )

        self.assertEqual(
            context["evidence_links"],
            [],
        )

    def test_empty_media_context_is_stable(
        self,
    ):
        first = (
            main.load_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        second = (
            main.load_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

        self.assertEqual(
            first["scope"]["media_item_id"],
            self.media["id"],
        )

    def test_media_item_id_is_required(
        self,
    ):
        with self.assertRaises(ValueError):
            main.load_evidence_context_for_media_item(
                media_item_id="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
