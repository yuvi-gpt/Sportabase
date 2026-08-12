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


class EvidenceAnalysisRetrievalTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-analysis-retrieval.db"
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
            content_hash=(
                "analysis-retrieval-content"
            ),
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

    def test_media_and_story_claim_text_is_loaded(
        self,
    ):
        media_evidence = main.record_evidence(
            evidence_type="independent_report",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "The player is considering "
                "a move to Club B."
            ),
            reference_key="MEDIA-CLAIM",
            verification_status="unverified",
            observed_at=(
                "2026-08-12T10:10:00+00:00"
            ),
        )["evidence"]

        story_evidence = main.record_evidence(
            evidence_type="official_statement",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Club B officially confirmed "
                "an agreement."
            ),
            canonical_url=(
                "https://club-b.example/"
                "official-statement"
            ),
            verification_status="verified",
            observed_at=(
                "2026-08-12T10:20:00+00:00"
            ),
        )["evidence"]

        main.record_evidence_link(
            evidence_id=media_evidence["id"],
            media_item_id=self.media["id"],
            relationship_type="supports",
            confidence=0.7,
        )

        main.record_evidence_link(
            evidence_id=story_evidence["id"],
            story_id=self.story["id"],
            relationship_type="confirms",
            confidence=0.95,
        )

        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        claims = {
            row["claim_summary"]
            for row in bundle[
                "evidence_records"
            ]
        }

        self.assertEqual(
            claims,
            {
                (
                    "The player is considering "
                    "a move to Club B."
                ),
                (
                    "Club B officially confirmed "
                    "an agreement."
                ),
            },
        )

        self.assertEqual(
            bundle["story_links"],
            [
                {
                    "story_id": self.story["id"],
                    "relationship_type": "reports",
                    "confidence": 0.8,
                }
            ],
        )

    def test_observation_claim_text_is_loaded(
        self,
    ):
        source_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                story_id=self.story["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="follow_up",
                status="developing",
                claim_summary=(
                    "Example Sports says talks "
                    "have accelerated."
                ),
                provenance_url=(
                    "https://example.com/follow-up"
                ),
                confidence=0.75,
                observed_at=(
                    "2026-08-12T10:30:00+00:00"
                ),
            )["observation"]
        )

        reporter_observation = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                media_item_id=self.media["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    "Reporter A says personal "
                    "terms are being discussed."
                ),
                provenance_url=(
                    "https://example.com/reporter"
                ),
                confidence=0.65,
                observed_at=(
                    "2026-08-12T10:35:00+00:00"
                ),
            )["observation"]
        )

        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            bundle[
                "source_observations"
            ][0]["id"],
            source_observation["id"],
        )

        self.assertEqual(
            bundle[
                "source_observations"
            ][0]["claim_summary"],
            (
                "Example Sports says talks "
                "have accelerated."
            ),
        )

        self.assertEqual(
            bundle[
                "reporter_observations"
            ][0]["id"],
            reporter_observation["id"],
        )

        self.assertEqual(
            bundle[
                "reporter_observations"
            ][0]["claim_summary"],
            (
                "Reporter A says personal "
                "terms are being discussed."
            ),
        )

    def test_unrelated_identity_evidence_does_not_leak(
        self,
    ):
        source_evidence = main.record_evidence(
            evidence_type="historical_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Unrelated source-wide history."
            ),
            reference_key="SOURCE-HISTORY",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:00:00+00:00"
            ),
        )["evidence"]

        reporter_evidence = main.record_evidence(
            evidence_type="historical_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Unrelated reporter-wide history."
            ),
            reference_key="REPORTER-HISTORY",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:05:00+00:00"
            ),
        )["evidence"]

        subject_only = main.record_evidence(
            evidence_type="historical_record",
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Unlinked subject-only history."
            ),
            reference_key="SUBJECT-HISTORY",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:10:00+00:00"
            ),
        )["evidence"]

        unrelated_story = main.record_evidence(
            evidence_type="official_statement",
            subject_key=(
                "transfer|player-c|club-d"
            ),
            claim_summary=(
                "Club D confirmed Player C."
            ),
            reference_key="OTHER-STORY",
            verification_status="verified",
            observed_at=(
                "2026-08-12T11:15:00+00:00"
            ),
        )["evidence"]

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
            evidence_id=unrelated_story["id"],
            story_id=self.other_story["id"],
            relationship_type="supports",
            confidence=0.9,
        )

        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        loaded_ids = {
            row["id"]
            for row in bundle[
                "evidence_records"
            ]
        }

        self.assertNotIn(
            source_evidence["id"],
            loaded_ids,
        )

        self.assertNotIn(
            reporter_evidence["id"],
            loaded_ids,
        )

        self.assertNotIn(
            subject_only["id"],
            loaded_ids,
        )

        self.assertNotIn(
            unrelated_story["id"],
            loaded_ids,
        )

        self.assertEqual(
            bundle["evidence_records"],
            [],
        )

    def test_empty_bundle_is_stable(
        self,
    ):
        first = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        second = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            first["version"],
            main.EVIDENCE_ANALYSIS_BUNDLE_VERSION,
        )

    def test_state_helper_matches_bundle_hash(
        self,
    ):
        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        state = (
            main.load_evidence_analysis_state_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            state["bundle"],
            bundle,
        )

        self.assertEqual(
            state["context_hash"],
            main.evidence_analysis_bundle_hash(
                bundle
            ),
        )

    def test_media_item_id_is_required(
        self,
    ):
        with self.assertRaises(ValueError):
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
