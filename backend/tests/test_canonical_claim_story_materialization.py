from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import (
    ClaimMaterializationConflictError,
    materialize_canonical_claim,
)
from app.intelligence.stories import story_id_for_canonical_key
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


NOW = "2026-08-31T10:00:00+00:00"
SUBJECT = "player|one"


class CanonicalClaimStoryMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "test.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type, canonical_domain,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES ('source-1', 'publisher|example.com', 'Example',
                          'publisher', 'example.com', ?, ?, '{}')
                """,
                (NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO intelligence_reporters (
                  id, identity_key, display_name, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES ('reporter-1', 'reporter|one', 'Reporter One', ?, ?, '{}')
                """,
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate(**changes):
        value = {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {"destination": "club|arsenal"},
            "facets": {},
        }
        value.update(changes)
        return value

    def observation(self, suffix, *, subject=SUBJECT, reporter=False):
        media_id = "media-" + suffix
        observation_id = "observation-" + suffix
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO media_items (
                  id, canonical_url, mode, source_id, title, latest_content_hash,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, 'article', 'source-1', ?, ?, ?, ?, '{}')
                """,
                (media_id, "https://example.com/" + suffix, suffix, suffix, NOW, NOW),
            )
            if reporter:
                conn.execute(
                    """
                    INSERT INTO reporter_observations (
                      id, reporter_id, source_id, media_item_id, subject_key,
                      observation_type, claim_summary, observed_at, recorded_at,
                      metadata_json
                    ) VALUES (?, 'reporter-1', 'source-1', ?, ?, 'report', ?, ?, ?, '{}')
                    """,
                    (observation_id, media_id, subject, suffix, NOW, NOW),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO source_observations (
                      id, source_id, media_item_id, subject_key, observation_type,
                      claim_summary, observed_at, recorded_at, metadata_json
                    ) VALUES (?, 'source-1', ?, ?, 'report', ?, ?, ?, '{}')
                    """,
                    (observation_id, media_id, subject, suffix, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        return observation_id, media_id

    def materialize(self, candidate, text, observation_id=None):
        return materialize_canonical_claim(
            candidate=candidate,
            claim_text=text,
            observed_at=NOW,
            connection_factory=self.factory,
            source_observation_id=observation_id,
        )

    def counts(self):
        conn = self.factory()
        try:
            return tuple(
                int(conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0])
                for table in (
                    "intelligence_stories",
                    "story_claim_links",
                    "story_media_links",
                )
            )
        finally:
            conn.close()

    def insert_legacy_claim(self, conn, claim_id, *, subject=SUBJECT):
        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, 'legacy', 'multimodal_candidate', ?, ?, '{}')
            """,
            (claim_id, "legacy-key-" + claim_id, subject, NOW, NOW),
        )

    def insert_mapping(
        self,
        conn,
        production_id,
        canonical_id,
        *,
        subject=SUBJECT,
        status="verified_equivalent",
    ):
        conn.execute(
            """
            INSERT INTO claim_identity_mappings (
              production_claim_id, canonical_claim_id, subject_key,
              mapping_status, mapping_basis, first_seen_at, last_seen_at,
              metadata_json
            ) VALUES (?, ?, ?, ?, 'test', ?, ?, '{}')
            """,
            (production_id, canonical_id, subject, status, NOW, NOW),
        )

    def story_identity(self, claim_id):
        canonical_key = "multimodal-exact-claim-v1|claim:" + claim_id
        return canonical_key, story_id_for_canonical_key(canonical_key)

    def test_different_wording_converges_and_replay_is_idempotent(self):
        left_observation, left_media = self.observation("left")
        right_observation, right_media = self.observation("right")
        first = self.materialize(
            self.candidate(), "Player One has joined Arsenal", left_observation
        )
        second = self.materialize(
            self.candidate(), "Arsenal complete Player One signing", right_observation
        )

        one = materialize_canonical_claim_story(
            claim_id=first["claim"]["id"], connection_factory=self.factory
        )
        two = materialize_canonical_claim_story(
            claim_id=second["claim"]["id"], connection_factory=self.factory
        )

        self.assertEqual(one["story_id"], two["story_id"])
        self.assertEqual(two["media_item_ids"], [left_media, right_media])
        self.assertEqual(self.counts(), (1, 1, 2))

    def test_material_identity_differences_never_cluster_by_shared_subject(self):
        variants = [
            self.candidate(
                event_type="contract",
                state="signed",
                roles={"organization": "club|arsenal"},
            ),
            self.candidate(state="interest"),
            self.candidate(negated=True),
            self.candidate(roles={"destination": "club|chelsea"}),
        ]
        story_ids = set()
        base = self.materialize(self.candidate(), "base")
        story_ids.add(materialize_canonical_claim_story(
            claim_id=base["claim"]["id"], connection_factory=self.factory
        )["story_id"])
        for index, candidate in enumerate(variants):
            with self.subTest(index=index):
                claim = self.materialize(candidate, "variant")
                story_ids.add(materialize_canonical_claim_story(
                    claim_id=claim["claim"]["id"], connection_factory=self.factory
                )["story_id"])
        self.assertEqual(len(story_ids), 5)
        self.assertEqual(self.counts()[:2], (5, 5))

    def test_sparse_then_richer_uses_existing_comparison_policy(self):
        sparse = self.materialize(self.candidate(), "sparse")
        richer = self.materialize(
            self.candidate(facets={"effective_period": "2026"}), "richer"
        )
        self.assertEqual(sparse["claim"]["id"], richer["claim"]["id"])
        story = materialize_canonical_claim_story(
            claim_id=richer["claim"]["id"], connection_factory=self.factory
        )
        self.assertEqual(story["canonical_claim_id"], sparse["claim"]["id"])

        with self.assertRaises(ClaimMaterializationConflictError):
            self.materialize(
                self.candidate(facets={"effective_period": "2027"}), "conflict"
            )
        self.assertEqual(self.counts()[:2], (1, 1))

    def test_verified_legacy_mappings_converge_and_contribute_linked_media(self):
        canonical = self.materialize(self.candidate(), "canonical")
        canonical_id = canonical["claim"]["id"]
        observations = [self.observation("legacy-" + str(index)) for index in (1, 2)]
        expected_media = [item[1] for item in observations]
        conn = self.factory()
        try:
            for index, (observation_id, _media_id) in zip((1, 2), observations):
                legacy_id = "legacy-" + str(index)
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id, canonical_key, subject_key, canonical_text, claim_type,
                      first_seen_at, last_seen_at, metadata_json
                    ) VALUES (?, ?, ?, 'legacy', 'multimodal_candidate', ?, ?, '{}')
                    """,
                    (legacy_id, "legacy-key-" + str(index), SUBJECT, NOW, NOW),
                )
                conn.execute(
                    """
                    INSERT INTO claim_identity_mappings (
                      production_claim_id, canonical_claim_id, subject_key,
                      mapping_status, mapping_basis, first_seen_at, last_seen_at,
                      metadata_json
                    ) VALUES (?, ?, ?, 'verified_equivalent', 'test', ?, ?, '{}')
                    """,
                    (legacy_id, canonical_id, SUBJECT, NOW, NOW),
                )
                conn.execute(
                    """
                    INSERT INTO claim_links (
                      id, claim_id, source_observation_id, relationship_type,
                      observed_at, recorded_at, metadata_json
                    ) VALUES (?, ?, ?, 'reports', ?, ?, '{}')
                    """,
                    ("link-" + str(index), legacy_id, observation_id, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()

        first = materialize_canonical_claim_story(
            claim_id="legacy-1", connection_factory=self.factory
        )
        second = materialize_canonical_claim_story(
            claim_id="legacy-2", connection_factory=self.factory
        )
        self.assertEqual(first["story_id"], second["story_id"])
        self.assertEqual(second["canonical_claim_id"], canonical_id)
        self.assertEqual(second["media_item_ids"], expected_media)
        self.assertEqual(self.counts(), (1, 1, 2))

    def test_invalid_observation_reference_rolls_back_entire_graph(self):
        claim = self.materialize(self.candidate(), "claim")
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                """
                INSERT INTO claim_links (
                  id, claim_id, source_observation_id, relationship_type,
                  observed_at, recorded_at, metadata_json
                ) VALUES ('dangling', ?, 'missing', 'reports', ?, ?, '{}')
                """,
                (claim["claim"]["id"], NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim["claim"]["id"], connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_mapping_must_be_verified_and_subject_consistent(self):
        canonical = self.materialize(self.candidate(), "canonical")["claim"]["id"]
        conn = self.factory()
        try:
            self.insert_legacy_claim(conn, "legacy-unverified")
            conn.execute("PRAGMA ignore_check_constraints = ON")
            self.insert_mapping(
                conn,
                "legacy-unverified",
                canonical,
                status="pending",
            )
            self.insert_legacy_claim(conn, "legacy-wrong-subject")
            self.insert_mapping(
                conn,
                "legacy-wrong-subject",
                canonical,
                subject="player|other",
            )
            conn.commit()
        finally:
            conn.close()

        for claim_id in ("legacy-unverified", "legacy-wrong-subject"):
            with self.subTest(claim_id=claim_id):
                with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
                    materialize_canonical_claim_story(
                        claim_id=claim_id, connection_factory=self.factory
                    )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_mapping_chains_and_cycles_fail_closed(self):
        canonical = self.materialize(self.candidate(), "canonical")["claim"]["id"]
        conn = self.factory()
        try:
            for claim_id in ("chain-a", "chain-b", "cycle-a", "cycle-b"):
                self.insert_legacy_claim(conn, claim_id)
            self.insert_mapping(conn, "chain-a", "chain-b")
            self.insert_mapping(conn, "chain-b", canonical)
            self.insert_mapping(conn, "cycle-a", "cycle-b")
            self.insert_mapping(conn, "cycle-b", "cycle-a")
            conn.commit()
        finally:
            conn.close()

        for claim_id in ("chain-a", "cycle-a"):
            with self.subTest(claim_id=claim_id):
                with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
                    materialize_canonical_claim_story(
                        claim_id=claim_id, connection_factory=self.factory
                    )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_mapping_cannot_redirect_valid_canonical_claim(self):
        first = self.materialize(self.candidate(), "first")["claim"]["id"]
        second = self.materialize(
            self.candidate(state="interest"), "second"
        )["claim"]["id"]
        conn = self.factory()
        try:
            self.insert_mapping(conn, first, second)
            conn.commit()
        finally:
            conn.close()

        result = materialize_canonical_claim_story(
            claim_id=first, connection_factory=self.factory
        )
        self.assertEqual(result["canonical_claim_id"], first)
        self.assertEqual(result["canonical_key"], self.story_identity(first)[0])

    def test_source_and_reporter_reports_are_members_but_other_links_are_not(self):
        source_observation, source_media = self.observation("valid-source")
        reporter_observation, reporter_media = self.observation(
            "valid-reporter", reporter=True
        )
        unrelated_observation, _unrelated_media = self.observation("unrelated")
        claim = self.materialize(
            self.candidate(), "source", source_observation
        )["claim"]["id"]
        materialize_canonical_claim(
            candidate=self.candidate(),
            claim_text="reporter",
            observed_at=NOW,
            connection_factory=self.factory,
            reporter_observation_id=reporter_observation,
            relationship_type="reports",
        )
        self.materialize(
            self.candidate(), "not membership", unrelated_observation
        )
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE claim_links SET relationship_type = 'supports' "
                "WHERE source_observation_id = ?",
                (unrelated_observation,),
            )
            conn.commit()
        finally:
            conn.close()

        result = materialize_canonical_claim_story(
            claim_id=claim, connection_factory=self.factory
        )
        self.assertEqual(result["media_item_ids"], [reporter_media, source_media])

    def test_evidence_only_link_does_not_create_media_membership(self):
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO evidence_records (
                  id, evidence_key, evidence_type, subject_key, observed_at,
                  recorded_at, metadata_json
                ) VALUES ('evidence-1', 'evidence|1', 'document', ?, ?, ?, '{}')
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        claim = materialize_canonical_claim(
            candidate=self.candidate(),
            claim_text="evidence",
            observed_at=NOW,
            connection_factory=self.factory,
            evidence_id="evidence-1",
            relationship_type="supports",
        )["claim"]["id"]
        result = materialize_canonical_claim_story(
            claim_id=claim, connection_factory=self.factory
        )
        self.assertEqual(result["media_item_ids"], [])
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_observation_subject_mismatch_fails_closed(self):
        observation_id, _media_id = self.observation(
            "wrong-subject", subject="player|other"
        )
        claim = self.materialize(
            self.candidate(), "claim", observation_id
        )["claim"]["id"]
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_missing_media_reference_rolls_back_entire_graph(self):
        observation_id, media_id = self.observation("missing-media")
        claim = self.materialize(
            self.candidate(), "claim", observation_id
        )["claim"]["id"]
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM media_items WHERE id = ?", (media_id,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_media_from_other_claim_and_ambiguous_entities_does_not_leak(self):
        other_observation, _other_media = self.observation("other-claim")
        base = self.materialize(self.candidate(), "base")["claim"]["id"]
        self.materialize(
            self.candidate(roles={"destination": "club|chelsea"}),
            "other",
            other_observation,
        )
        conn = self.factory()
        try:
            for index in (1, 2):
                conn.execute(
                    """
                    INSERT INTO canonical_entities (
                      id, entity_key, entity_type, canonical_name,
                      first_seen_at, last_seen_at, metadata_json
                    ) VALUES (?, ?, 'club', 'United', ?, ?, '{}')
                    """,
                    ("entity-" + str(index), "club|united-" + str(index), NOW, NOW),
                )
                conn.execute(
                    """
                    INSERT INTO entity_aliases (
                      id, entity_id, alias_text, normalized_alias, alias_type,
                      first_seen_at, last_seen_at, metadata_json
                    ) VALUES (?, ?, 'United', 'united', 'short_name', ?, ?, '{}')
                    """,
                    ("alias-" + str(index), "entity-" + str(index), NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        result = materialize_canonical_claim_story(
            claim_id=base, connection_factory=self.factory
        )
        self.assertEqual(result["media_item_ids"], [])

    def test_core_fixture_context_produces_separate_stories(self):
        first = self.materialize(
            self.candidate(
                event_type="match_result",
                state="won",
                roles={},
                facets={"event_key": "fixture|one"},
            ),
            "fixture one",
        )
        second = self.materialize(
            self.candidate(
                event_type="match_result",
                state="won",
                roles={},
                facets={"event_key": "fixture|two"},
            ),
            "fixture two",
        )
        stories = {
            materialize_canonical_claim_story(
                claim_id=value["claim"]["id"], connection_factory=self.factory
            )["story_id"]
            for value in (first, second)
        }
        self.assertEqual(len(stories), 2)

    def test_structured_identity_markers_and_fingerprints_are_validated(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        conn = self.factory()
        try:
            row = conn.execute(
                "SELECT metadata_json FROM intelligence_claims WHERE id = ?",
                (claim,),
            ).fetchone()
            metadata = json.loads(row[0])
            metadata["core_fingerprint"] = "stale"
            conn.execute(
                "UPDATE intelligence_claims SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata), claim),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_malformed_structured_metadata_is_rejected(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        conn = self.factory()
        try:
            row = conn.execute(
                "SELECT metadata_json FROM intelligence_claims WHERE id = ?",
                (claim,),
            ).fetchone()
            metadata = json.loads(row[0])
            metadata["structured_claim"]["event_type"] = "unsupported-event"
            conn.execute(
                "UPDATE intelligence_claims SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata), claim),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_compatible_multimodal_story_metadata_and_subject_entity_are_preserved(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        canonical_key, story_id = self.story_identity(claim)
        metadata = {
            "materialization_version": "story-claim-graph-materialization-v1",
            "materialization_basis": "downstream_exact_common_claim_id",
            "claim_id": claim,
            "subject_key": SUBJECT,
            "subject_entity_id": "entity-player-one",
            "multimodal_marker": "preserve-me",
        }
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id, canonical_key, canonical_title, status, first_seen_at,
                  last_seen_at, metadata_json
                ) VALUES (?, ?, 'Existing', 'developing', ?, ?, ?)
                """,
                (story_id, canonical_key, NOW, NOW, json.dumps(metadata)),
            )
            conn.commit()
        finally:
            conn.close()

        materialize_canonical_claim_story(
            claim_id=claim,
            connection_factory=self.factory,
            now_provider=lambda: "2026-08-31T11:00:00+00:00",
        )
        conn = self.factory()
        try:
            stored = conn.execute(
                "SELECT metadata_json FROM intelligence_stories WHERE id = ?",
                (story_id,),
            ).fetchone()
        finally:
            conn.close()
        result = json.loads(stored[0])
        self.assertEqual(result["subject_entity_id"], "entity-player-one")
        self.assertEqual(result["multimodal_marker"], "preserve-me")
        self.assertEqual(
            result["materialization_version"],
            "story-claim-graph-materialization-v1",
        )
        self.assertEqual(
            result["story_claim_graph_materialization_version"],
            "story-claim-graph-materialization-v1",
        )
        self.assertEqual(
            result["canonical_claim_story_materialization_version"],
            "canonical-claim-story-materialization-v1",
        )

    def test_inconsistent_existing_story_metadata_fails_without_mutation(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        canonical_key, story_id = self.story_identity(claim)
        original = json.dumps({"claim_id": "another-claim", "subject_key": SUBJECT})
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id, canonical_key, canonical_title, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, 'Existing', ?, ?, ?)
                """,
                (story_id, canonical_key, NOW, NOW, original),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        conn = self.factory()
        try:
            stored = conn.execute(
                "SELECT metadata_json FROM intelligence_stories WHERE id = ?",
                (story_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(stored, original)
        self.assertEqual(self.counts(), (1, 0, 0))

    def test_conflicting_existing_story_claim_edge_fails_closed(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        other = self.materialize(
            self.candidate(state="interest"), "other"
        )["claim"]["id"]
        canonical_key, story_id = self.story_identity(claim)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id, canonical_key, canonical_title, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, 'Existing', ?, ?, '{}')
                """,
                (story_id, canonical_key, NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO story_claim_links (
                  story_id, claim_id, relationship_type, link_basis, linked_at,
                  metadata_json
                ) VALUES (?, ?, 'exact_claim_group',
                          'downstream_exact_common_claim_id', ?, '{}')
                """,
                (story_id, other, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            materialize_canonical_claim_story(
                claim_id=claim, connection_factory=self.factory
            )
        self.assertEqual(self.counts(), (1, 1, 0))

    def test_replay_with_earlier_time_keeps_last_seen_monotonic(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        materialize_canonical_claim_story(
            claim_id=claim,
            connection_factory=self.factory,
            now_provider=lambda: "2026-08-31T12:00:00+00:00",
        )
        materialize_canonical_claim_story(
            claim_id=claim,
            connection_factory=self.factory,
            now_provider=lambda: "2026-08-31T11:00:00+00:00",
        )
        conn = self.factory()
        try:
            last_seen = conn.execute(
                "SELECT last_seen_at FROM intelligence_stories"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(last_seen, "2026-08-31T12:00:00+00:00")

    def test_preexisting_connection_transaction_is_not_rolled_back_or_closed(self):
        claim = self.materialize(self.candidate(), "claim")["claim"]["id"]
        conn = self.factory()
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE intelligence_claims SET canonical_text = 'uncommitted' WHERE id = ?",
            (claim,),
        )
        try:
            with self.assertRaises(Exception):
                materialize_canonical_claim_story(
                    claim_id=claim, connection_factory=lambda: conn
                )
            self.assertTrue(conn.in_transaction)
            self.assertEqual(
                conn.execute(
                    "SELECT canonical_text FROM intelligence_claims WHERE id = ?",
                    (claim,),
                ).fetchone()[0],
                "uncommitted",
            )
        finally:
            conn.rollback()
            conn.close()


if __name__ == "__main__":
    unittest.main()
