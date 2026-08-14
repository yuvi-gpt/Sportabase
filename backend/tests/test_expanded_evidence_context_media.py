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


class ExpandedEvidenceContextMediaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "expanded-media-context-test.db"
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
            content_hash="expanded-media-content",
            source_id=self.source["id"],
            reporter_id=self.reporter["id"],
            seen_at=(
                "2026-08-12T10:00:00+00:00"
            ),
        )

        self.story = (
            main.upsert_intelligence_story(
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
        )

        self.other_story = (
            main.upsert_intelligence_story(
                canonical_key=(
                    "transfer|player-c|club-d"
                ),
                canonical_title=(
                    "Player C to Club D"
                ),
                seen_at=(
                    "2026-08-12T09:05:00+00:00"
                ),
            )
        )

        main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="reports",
            confidence=0.8,
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_media_and_linked_story_context_are_loaded(
        self,
    ):
        media_source_observation = (
            main.record_source_observation(
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

        story_source_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                story_id=self.story["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="follow_up",
                status="developing",
                observed_at=(
                    "2026-08-12T10:15:00+00:00"
                ),
            )["observation"]
        )

        media_reporter_observation = (
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
                    "2026-08-12T10:20:00+00:00"
                ),
            )["observation"]
        )

        story_reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                story_id=self.story["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="follow_up",
                status="developing",
                observed_at=(
                    "2026-08-12T10:25:00+00:00"
                ),
            )["observation"]
        )

        media_evidence = main.record_evidence(
            evidence_type="independent_report",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="MEDIA-EVIDENCE",
            verification_status="unverified",
            observed_at=(
                "2026-08-12T11:00:00+00:00"
            ),
        )["evidence"]

        story_evidence = main.record_evidence(
            evidence_type="official_statement",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="STORY-EVIDENCE",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:05:00+00:00"
            ),
        )["evidence"]

        media_link = main.record_evidence_link(
            evidence_id=media_evidence["id"],
            media_item_id=self.media["id"],
            relationship_type="supports",
            confidence=0.7,
        )["link"]

        story_link = main.record_evidence_link(
            evidence_id=story_evidence["id"],
            story_id=self.story["id"],
            relationship_type="supports",
            confidence=0.95,
        )["link"]

        context = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            context["scope"]["media_item_id"],
            self.media["id"],
        )

        self.assertEqual(
            context["expansion"]["policy"],
            main.MEDIA_EVIDENCE_CONTEXT_POLICY_VERSION,
        )

        self.assertEqual(
            context["expansion"]["story_links"],
            [
                {
                    "story_id": self.story["id"],
                    "relationship_type": "reports",
                    "confidence": 0.8,
                }
            ],
        )

        self.assertEqual(
            {
                row["id"]
                for row in context[
                    "source_observations"
                ]
            },
            {
                media_source_observation["id"],
                story_source_observation["id"],
            },
        )

        self.assertEqual(
            {
                row["id"]
                for row in context[
                    "reporter_observations"
                ]
            },
            {
                media_reporter_observation["id"],
                story_reporter_observation["id"],
            },
        )

        self.assertEqual(
            {
                row["id"]
                for row in context[
                    "evidence_records"
                ]
            },
            {
                media_evidence["id"],
                story_evidence["id"],
            },
        )

        self.assertEqual(
            {
                row["id"]
                for row in context[
                    "evidence_links"
                ]
            },
            {
                media_link["id"],
                story_link["id"],
            },
        )

    def test_unrelated_and_identity_evidence_do_not_leak(
        self,
    ):
        source_evidence = main.record_evidence(
            evidence_type="source_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="SOURCE-EVIDENCE",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:00:00+00:00"
            ),
        )["evidence"]

        reporter_evidence = main.record_evidence(
            evidence_type="reporter_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="REPORTER-EVIDENCE",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:05:00+00:00"
            ),
        )["evidence"]

        subject_only_evidence = main.record_evidence(
            evidence_type="historical_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            reference_key="SUBJECT-ONLY-EVIDENCE",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:10:00+00:00"
            ),
        )["evidence"]

        unrelated_story_evidence = (
            main.record_evidence(
                evidence_type="official_statement",
                subject_key=(
                    "transfer|player-c|club-d"
                ),
                reference_key=(
                    "UNRELATED-STORY-EVIDENCE"
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-12T11:15:00+00:00"
                ),
            )["evidence"]
        )

        main.record_evidence_link(
            evidence_id=source_evidence["id"],
            source_id=self.source["id"],
            relationship_type="supports",
            confidence=0.9,
        )

        main.record_evidence_link(
            evidence_id=reporter_evidence["id"],
            reporter_id=self.reporter["id"],
            relationship_type="supports",
            confidence=0.9,
        )

        main.record_evidence_link(
            evidence_id=unrelated_story_evidence["id"],
            story_id=self.other_story["id"],
            relationship_type="supports",
            confidence=0.9,
        )

        context = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        evidence_ids = {
            row["id"]
            for row in context[
                "evidence_records"
            ]
        }

        self.assertNotIn(
            source_evidence["id"],
            evidence_ids,
        )

        self.assertNotIn(
            reporter_evidence["id"],
            evidence_ids,
        )

        self.assertNotIn(
            subject_only_evidence["id"],
            evidence_ids,
        )

        self.assertNotIn(
            unrelated_story_evidence["id"],
            evidence_ids,
        )

        self.assertEqual(
            context["evidence_records"],
            [],
        )

        self.assertEqual(
            context["evidence_links"],
            [],
        )

    def test_story_edge_changes_context_hash(
        self,
    ):
        first = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        first_hash = (
            main.evidence_context_hash(
                first
            )
        )

        main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="corroborates",
            confidence=0.95,
        )

        second = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        second_hash = (
            main.evidence_context_hash(
                second
            )
        )

        self.assertNotEqual(
            first_hash,
            second_hash,
        )

        self.assertEqual(
            second["expansion"]["story_links"],
            [
                {
                    "story_id": self.story["id"],
                    "relationship_type": (
                        "corroborates"
                    ),
                    "confidence": 0.95,
                }
            ],
        )

    def test_expanded_hash_helper_matches_context(
        self,
    ):
        context = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        expected_hash = (
            main.evidence_context_hash(
                context
            )
        )

        actual_hash = (
            main.expanded_evidence_context_hash_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            actual_hash,
            expected_hash,
        )

    def test_same_expanded_context_is_stable(
        self,
    ):
        first = (
            main.load_expanded_evidence_context_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        second = (
            main.load_expanded_evidence_context_for_media_item(
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

    def test_media_item_id_is_required(
        self,
    ):
        with self.assertRaises(ValueError):
            main.load_expanded_evidence_context_for_media_item(
                media_item_id="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
