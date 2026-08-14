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


class EvidenceClaimAlignmentTests(
    unittest.TestCase
):
    def claim_row(
        self,
        *,
        claim_id="claim-1",
        canonical_key="transfer|a|b|agreement",
        canonical_text="Agreement reached.",
    ):
        return {
            "id": claim_id,
            "canonical_key": canonical_key,
            "subject_key": "transfer|a|b",
            "canonical_text": canonical_text,
            "claim_type": "ASSERTION",
            "first_seen_at": "ignored-first",
            "last_seen_at": "ignored-last",
            "metadata_json": '{"ignored":true}',
        }

    def claim_link_row(
        self,
        *,
        link_id="claim-link-1",
        claim_id="claim-1",
        source_observation_id="source-observation-1",
        relationship_type="ALIGNED_TO",
        confidence=0.9,
        observed_at="2026-08-13T10:00:00+00:00",
    ):
        return {
            "id": link_id,
            "claim_id": claim_id,
            "source_observation_id": (
                source_observation_id
            ),
            "reporter_observation_id": None,
            "evidence_id": None,
            "relationship_type": relationship_type,
            "confidence": confidence,
            "observed_at": observed_at,
            "recorded_at": "ignored-recorded",
            "metadata_json": '{"ignored":true}',
        }

    def test_bundle_normalizes_claim_and_link(
        self,
    ):
        claim = self.claim_row(
            canonical_key=(
                "  TRANSFER|A|B|AGREEMENT  "
            ),
            canonical_text=(
                "  Agreement   reached. "
            ),
        )

        link = self.claim_link_row(
            relationship_type=(
                "  ALIGNED_TO  "
            ),
        )

        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[claim],
                claim_links=[link],
            )
        )

        self.assertEqual(
            bundle["claims"],
            [
                {
                    "id": "claim-1",
                    "canonical_key": (
                        "transfer|a|b|agreement"
                    ),
                    "subject_key": (
                        "transfer|a|b"
                    ),
                    "canonical_text": (
                        "Agreement reached."
                    ),
                    "claim_type": "assertion",
                }
            ],
        )

        self.assertEqual(
            bundle["claim_links"],
            [
                {
                    "id": "claim-link-1",
                    "claim_id": "claim-1",
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": (
                        "source-observation-1"
                    ),
                    "relationship_type": (
                        "aligned_to"
                    ),
                    "confidence": 0.9,
                    "observed_at": (
                        "2026-08-13"
                        "T10:00:00+00:00"
                    ),
                }
            ],
        )

    def test_claim_alignment_order_is_stable(
        self,
    ):
        claims = [
            self.claim_row(
                claim_id="claim-1",
            ),
            self.claim_row(
                claim_id="claim-2",
                canonical_key=(
                    "transfer|a|b|terms"
                ),
                canonical_text=(
                    "Terms agreed."
                ),
            ),
        ]

        links = [
            self.claim_link_row(
                link_id="claim-link-1",
                claim_id="claim-1",
                source_observation_id=(
                    "source-observation-1"
                ),
            ),
            self.claim_link_row(
                link_id="claim-link-2",
                claim_id="claim-2",
                source_observation_id=(
                    "source-observation-2"
                ),
            ),
        ]

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=claims,
                claim_links=links,
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=list(
                    reversed(claims)
                ),
                claim_links=list(
                    reversed(links)
                ),
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )

    def test_claim_semantics_change_hash(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[
                    self.claim_row(
                        canonical_text=(
                            "Agreement reached."
                        )
                    )
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[
                    self.claim_row(
                        canonical_text=(
                            "Agreement denied."
                        )
                    )
                ],
            )
        )

        self.assertNotEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )

    def test_operational_fields_do_not_change_hash(
        self,
    ):
        first_claim = self.claim_row()

        second_claim = {
            **first_claim,
            "first_seen_at": "different-first",
            "last_seen_at": "different-last",
            "metadata_json": (
                '{"different":true}'
            ),
        }

        first_link = self.claim_link_row()

        second_link = {
            **first_link,
            "recorded_at": (
                "different-recorded"
            ),
            "metadata_json": (
                '{"different":true}'
            ),
        }

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[first_claim],
                claim_links=[first_link],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[second_claim],
                claim_links=[second_link],
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )


class EvidenceClaimAlignmentRetrievalTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-claim-alignment.db"
        )

        main.init_db()

        self.source = (
            main.upsert_intelligence_source(
                url=(
                    "https://claim-source.example/"
                ),
                display_name="Claim Source",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.media = main.upsert_media_item(
            url=(
                "https://claim-source.example/"
                "selected"
            ),
            mode="article",
            title="Selected article",
            content_hash="selected-content",
            source_id=self.source["id"],
            seen_at=(
                "2026-08-13T10:01:00+00:00"
            ),
        )

        self.other_media = (
            main.upsert_media_item(
                url=(
                    "https://claim-source.example/"
                    "other"
                ),
                mode="article",
                title="Other article",
                content_hash="other-content",
                source_id=self.source["id"],
                seen_at=(
                    "2026-08-13T10:02:00+00:00"
                ),
            )
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_retrieval_is_scoped_to_selected_observation(
        self,
    ):
        selected_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                media_item_id=self.media["id"],
                subject_key="transfer|a|b",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T10:10:00+00:00"
                ),
            )["observation"]
        )

        other_observation = (
            main.record_source_observation(
                source_id=self.source["id"],
                media_item_id=(
                    self.other_media["id"]
                ),
                subject_key="transfer|c|d",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T10:11:00+00:00"
                ),
            )["observation"]
        )

        selected_claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|agreement"
                ),
                subject_key="transfer|a|b",
                canonical_text=(
                    "Agreement reached."
                ),
                seen_at=(
                    "2026-08-13T10:12:00+00:00"
                ),
            )
        )

        other_claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|c|d|agreement"
                ),
                subject_key="transfer|c|d",
                canonical_text=(
                    "Other agreement reached."
                ),
                seen_at=(
                    "2026-08-13T10:13:00+00:00"
                ),
            )
        )

        selected_link = (
            main.record_claim_link(
                claim_id=selected_claim["id"],
                relationship_type=(
                    "aligned_to"
                ),
                source_observation_id=(
                    selected_observation["id"]
                ),
                confidence=0.9,
                observed_at=(
                    "2026-08-13T10:14:00+00:00"
                ),
            )["link"]
        )

        main.record_claim_link(
            claim_id=other_claim["id"],
            relationship_type="aligned_to",
            source_observation_id=(
                other_observation["id"]
            ),
            confidence=0.9,
            observed_at=(
                "2026-08-13T10:15:00+00:00"
            ),
        )

        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            {
                row["id"]
                for row in bundle["claims"]
            },
            {
                selected_claim["id"]
            },
        )

        self.assertEqual(
            {
                row["id"]
                for row in bundle[
                    "claim_links"
                ]
            },
            {
                selected_link["id"]
            },
        )

    def test_retrieval_includes_evidence_alignment(
        self,
    ):
        evidence = main.record_evidence(
            evidence_type="official_statement",
            subject_key="transfer|a|b",
            canonical_url=(
                "https://club.example/"
                "statement"
            ),
            observed_at=(
                "2026-08-13T10:20:00+00:00"
            ),
        )["evidence"]

        main.record_evidence_link(
            evidence_id=evidence["id"],
            media_item_id=self.media["id"],
            relationship_type="supports",
            confidence=0.95,
        )

        claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|official"
                ),
                subject_key="transfer|a|b",
                canonical_text=(
                    "Club officially confirmed "
                    "the agreement."
                ),
                seen_at=(
                    "2026-08-13T10:21:00+00:00"
                ),
            )
        )

        link = main.record_claim_link(
            claim_id=claim["id"],
            relationship_type="aligned_to",
            evidence_id=evidence["id"],
            confidence=0.98,
            observed_at=(
                "2026-08-13T10:22:00+00:00"
            ),
        )["link"]

        bundle = (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=self.media["id"],
            )
        )

        self.assertEqual(
            bundle["claims"][0]["id"],
            claim["id"],
        )

        self.assertEqual(
            bundle["claim_links"][0],
            {
                "id": link["id"],
                "claim_id": claim["id"],
                "target_type": "evidence",
                "target_id": evidence["id"],
                "relationship_type": (
                    "aligned_to"
                ),
                "confidence": 0.98,
                "observed_at": (
                    "2026-08-13"
                    "T10:22:00+00:00"
                ),
            },
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
