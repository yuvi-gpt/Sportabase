from __future__ import annotations

import json
import socket
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.claims.repository import record_claim_link
from app.intelligence.reporting_coverage import build_claim_reporting_coverage
from app.routes import intelligence_admin
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


NOW = "2026-08-31T10:00:00+00:00"
SUBJECT = "player|one"


class ReportingCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "coverage.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            self._source(conn, "source-1", "publisher|example.com", "Example")
            self._reporter(conn, "reporter-1", "reporter|one", "Reporter One")
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

    @staticmethod
    def _source(
        conn,
        source_id,
        source_key,
        name,
        *,
        source_type="publisher",
        domain="example.com",
        metadata=None,
    ):
        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id, source_key, display_name, source_type, canonical_domain,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_key,
                name,
                source_type,
                domain,
                NOW,
                NOW,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    @staticmethod
    def _reporter(conn, reporter_id, identity_key, name):
        conn.execute(
            """
            INSERT INTO intelligence_reporters (
              id, identity_key, display_name, first_seen_at, last_seen_at,
              metadata_json
            ) VALUES (?, ?, ?, ?, ?, '{}')
            """,
            (reporter_id, identity_key, name, NOW, NOW),
        )

    def observation(
        self,
        suffix,
        *,
        source_id="source-1",
        reporter_id=None,
        direct_reporter_id=None,
        subject=SUBJECT,
        observed_at=NOW,
        published_at=None,
        mode="article",
        with_media=True,
    ):
        media_id = "media-" + suffix
        observation_id = "observation-" + suffix
        conn = self.factory()
        try:
            if with_media:
                conn.execute(
                    """
                    INSERT INTO media_items (
                      id, canonical_url, mode, source_id, reporter_id, title,
                      published_at, latest_content_hash, first_seen_at,
                      last_seen_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
                    """,
                    (
                        media_id,
                        "https://media.example/" + suffix,
                        mode,
                        source_id,
                        direct_reporter_id,
                        "Title " + suffix,
                        published_at,
                        "hash-" + suffix,
                        NOW,
                        NOW,
                    ),
                )
            if reporter_id:
                conn.execute(
                    """
                    INSERT INTO reporter_observations (
                      id, reporter_id, source_id, media_item_id, subject_key,
                      observation_type, status, observed_at, recorded_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, ?, 'report', 'reported', ?, ?, '{}')
                    """,
                    (
                        observation_id,
                        reporter_id,
                        source_id,
                        media_id if with_media else None,
                        subject,
                        observed_at,
                        NOW,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO source_observations (
                      id, source_id, media_item_id, subject_key,
                      observation_type, status, observed_at, recorded_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, 'report', 'reported', ?, ?, '{}')
                    """,
                    (
                        observation_id,
                        source_id or "source-1",
                        media_id if with_media else None,
                        subject,
                        observed_at,
                        NOW,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        return observation_id, media_id

    def canonical_claim(self, observation_id, *, candidate=None):
        result = materialize_canonical_claim(
            candidate=candidate or self.candidate(),
            claim_text="Player One completed a move to Arsenal",
            observed_at=NOW,
            connection_factory=self.factory,
            source_observation_id=observation_id,
            relationship_type="reports",
        )
        return result["claim"]["id"]

    def link(
        self,
        claim_id,
        observation_id,
        *,
        relationship="reports",
        reporter=False,
        observed_at=NOW,
    ):
        return record_claim_link(
            claim_id=claim_id,
            relationship_type=relationship,
            observed_at=observed_at,
            reporter_observation_id=observation_id if reporter else None,
            source_observation_id=None if reporter else observation_id,
            connection_factory=self.factory,
        )

    def materialize_story(self, claim_id):
        return materialize_canonical_claim_story(
            claim_id=claim_id,
            connection_factory=self.factory,
        )

    def coverage(self, claim_id):
        return build_claim_reporting_coverage(
            canonical_claim_id=claim_id,
            connection_factory=self.factory,
        )

    def basic_graph(self):
        observation_id, media_id = self.observation("base")
        claim_id = self.canonical_claim(observation_id)
        story = self.materialize_story(claim_id)
        return claim_id, story["story_id"], media_id

    def test_one_canonical_claim_one_report_contract(self):
        claim_id, story_id, media_id = self.basic_graph()
        result = self.coverage(claim_id)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["canonical_claim"]["id"], claim_id)
        self.assertEqual(result["story"]["id"], story_id)
        self.assertEqual(result["coverage"]["media_items"], 1)
        self.assertEqual(result["media"][0]["media_item_id"], media_id)
        self.assertEqual(result["coverage"]["first_observed_at"], NOW)
        self.assertFalse(result["policy"]["establishes_independence"])

    def test_multiple_media_same_source_and_distinct_sources(self):
        first, _ = self.observation("one")
        claim_id = self.canonical_claim(first)
        second, _ = self.observation("two")
        self.link(claim_id, second)
        conn = self.factory()
        try:
            self._source(
                conn,
                "source-2",
                "publisher|other.example",
                "Other",
                domain="other.example",
            )
            conn.commit()
        finally:
            conn.close()
        third, _ = self.observation("three", source_id="source-2")
        self.link(claim_id, third)
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(result["coverage"]["media_items"], 3)
        self.assertEqual(result["coverage"]["distinct_sources"], 2)

    def test_source_and_reporter_paths_dedupe_one_media(self):
        source_observation, media_id = self.observation("shared")
        claim_id = self.canonical_claim(source_observation)
        reporter_observation = "observation-shared-reporter"
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO reporter_observations (
                  id, reporter_id, source_id, media_item_id, subject_key,
                  observation_type, status, observed_at, recorded_at,
                  metadata_json
                ) VALUES (?, 'reporter-1', 'source-1', ?, ?, 'report',
                          'reported', ?, ?, '{}')
                """,
                (reporter_observation, media_id, SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.link(claim_id, reporter_observation, reporter=True)
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(result["coverage"]["media_items"], 1)
        self.assertEqual(result["coverage"]["distinct_reporters"], 1)

    def test_multiple_and_direct_reporters_are_deduplicated_and_sorted(self):
        conn = self.factory()
        try:
            self._reporter(conn, "reporter-2", "reporter|two", "Alpha Reporter")
            conn.commit()
        finally:
            conn.close()
        source_observation, media_id = self.observation(
            "authors", direct_reporter_id="reporter-1"
        )
        claim_id = self.canonical_claim(source_observation)
        for reporter_id in ("reporter-1", "reporter-2"):
            observation_id = "observation-authors-" + reporter_id
            conn = self.factory()
            try:
                conn.execute(
                    """
                    INSERT INTO reporter_observations (
                      id, reporter_id, source_id, media_item_id, subject_key,
                      observation_type, observed_at, recorded_at, metadata_json
                    ) VALUES (?, ?, 'source-1', ?, ?, 'report', ?, ?, '{}')
                    """,
                    (observation_id, reporter_id, media_id, SUBJECT, NOW, NOW),
                )
                conn.commit()
            finally:
                conn.close()
            self.link(claim_id, observation_id, reporter=True)
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(result["coverage"]["distinct_reporters"], 2)
        self.assertEqual(
            [item["reporter_id"] for item in result["media"][0]["reporters"]],
            ["reporter-2", "reporter-1"],
        )

    def test_missing_reporter_and_missing_publication_source_are_normal(self):
        observation_id, _ = self.observation("missing-reporter")
        claim_id = self.canonical_claim(observation_id)
        conn = self.factory()
        try:
            conn.execute("UPDATE media_items SET source_id = NULL")
            conn.commit()
        finally:
            conn.close()
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(result["coverage"]["media_items"], 1)
        self.assertEqual(result["coverage"]["distinct_sources"], 0)
        self.assertEqual(result["coverage"]["distinct_reporters"], 0)
        self.assertIsNone(result["media"][0]["source"])

    def test_replay_does_not_duplicate_media(self):
        observation_id, _ = self.observation("replay")
        claim_id = self.canonical_claim(observation_id)
        first = self.link(claim_id, observation_id)
        second = self.link(claim_id, observation_id)
        self.assertFalse(first["created"])
        self.assertFalse(second["created"])
        self.materialize_story(claim_id)
        self.materialize_story(claim_id)
        self.assertEqual(self.coverage(claim_id)["coverage"]["media_items"], 1)

    def test_every_non_reports_relationship_and_evidence_are_excluded(self):
        valid, valid_media = self.observation("valid")
        claim_id = self.canonical_claim(valid)
        excluded_media = []
        for relationship in (
            "supports",
            "context",
            "contradicts",
            "aligned_to",
            "refutes",
            "confirms",
            "corroborates",
        ):
            observation_id, media_id = self.observation("excluded-" + relationship)
            excluded_media.append(media_id)
            self.link(claim_id, observation_id, relationship=relationship)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO evidence_records (
                  id, evidence_key, evidence_type, subject_key, observed_at,
                  recorded_at, metadata_json
                ) VALUES ('evidence-1', 'evidence-key-1', 'document', ?, ?, ?, '{}')
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        record_claim_link(
            claim_id=claim_id,
            relationship_type="reports",
            observed_at=NOW,
            evidence_id="evidence-1",
            connection_factory=self.factory,
        )
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual([item["media_item_id"] for item in result["media"]], [valid_media])
        self.assertTrue(set(excluded_media).isdisjoint(
            item["media_item_id"] for item in result["media"]
        ))

    def test_shared_subject_and_different_canonical_claim_do_not_leak(self):
        first, first_media = self.observation("claim-one")
        first_claim = self.canonical_claim(first)
        second, second_media = self.observation("claim-two")
        second_claim = self.canonical_claim(
            second,
            candidate=self.candidate(state="agreed"),
        )
        self.assertNotEqual(first_claim, second_claim)
        self.materialize_story(first_claim)
        self.materialize_story(second_claim)
        self.assertEqual(
            [item["media_item_id"] for item in self.coverage(first_claim)["media"]],
            [first_media],
        )
        self.assertNotEqual(first_media, second_media)

    def test_verified_legacy_equivalent_claim_contributes(self):
        canonical_observation, canonical_media = self.observation("canonical")
        claim_id = self.canonical_claim(canonical_observation)
        legacy_observation, legacy_media = self.observation("legacy")
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES ('legacy-claim', 'legacy-key', ?, 'Legacy', 'assertion',
                          ?, ?, '{}')
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO claim_identity_mappings (
                  production_claim_id, canonical_claim_id, subject_key,
                  mapping_status, mapping_basis, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES ('legacy-claim', ?, ?, 'verified_equivalent', 'test',
                          ?, ?, '{}')
                """,
                (claim_id, SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.link("legacy-claim", legacy_observation)
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(
            {item["media_item_id"] for item in result["media"]},
            {canonical_media, legacy_media},
        )

    def test_malformed_mapping_and_mapping_chain_fail_closed(self):
        observation_id, _ = self.observation("mapping")
        claim_id = self.canonical_claim(observation_id)
        conn = self.factory()
        try:
            for legacy_id in ("legacy-a", "legacy-b"):
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id, canonical_key, subject_key, canonical_text, claim_type,
                      first_seen_at, last_seen_at, metadata_json
                    ) VALUES (?, ?, ?, '', 'assertion', ?, ?, '{}')
                    """,
                    (legacy_id, "key-" + legacy_id, SUBJECT, NOW, NOW),
                )
            conn.execute(
                """
                INSERT INTO claim_identity_mappings VALUES (
                  'legacy-a', ?, ?, 'verified_equivalent', 'test', ?, ?, '{}'
                )
                """,
                (claim_id, SUBJECT, NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO claim_identity_mappings VALUES (
                  'legacy-b', 'legacy-a', ?, 'verified_equivalent', 'test', ?, ?, '{}'
                )
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.materialize_story(claim_id)
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.coverage(claim_id)

    def test_canonical_claim_cannot_be_redirected(self):
        observation_id, _ = self.observation("redirect")
        claim_id = self.canonical_claim(observation_id)
        other_observation, _ = self.observation("redirect-other")
        other_claim = self.canonical_claim(
            other_observation,
            candidate=self.candidate(state="agreed"),
        )
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO claim_identity_mappings VALUES (
                  ?, ?, ?, 'verified_equivalent', 'test', ?, ?, '{}'
                )
                """,
                (claim_id, other_claim, SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.materialize_story(claim_id)
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.coverage(claim_id)

    def test_story_is_reused_and_conflicting_provenance_fails_closed(self):
        claim_id, story_id, _ = self.basic_graph()
        self.assertEqual(self.coverage(claim_id)["story"]["id"], story_id)
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE intelligence_stories SET metadata_json = '{}' WHERE id = ?",
                (story_id,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.coverage(claim_id)

    def test_conflicting_story_media_semantics_and_graph_set_fail_closed(self):
        claim_id, story_id, _ = self.basic_graph()
        conn = self.factory()
        try:
            conn.execute(
                """
                UPDATE story_media_links
                SET relationship_type = 'reports'
                WHERE story_id = ?
                """,
                (story_id,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.coverage(claim_id)

    def test_media_order_and_timestamp_aggregation_are_semantic(self):
        later, _ = self.observation(
            "later",
            observed_at="2026-08-31T12:00:00+00:00",
            published_at="2026-08-01T00:00:00+00:00",
        )
        claim_id = self.canonical_claim(later)
        early_b, media_b = self.observation(
            "b",
            observed_at="2026-08-31T09:00:00+00:00",
            published_at="2026-08-30T00:00:00+00:00",
        )
        early_a, media_a = self.observation(
            "a",
            observed_at="2026-08-31T09:00:00+00:00",
            published_at=None,
        )
        self.link(claim_id, early_b, observed_at="2026-08-31T09:00:00+00:00")
        self.link(claim_id, early_a, observed_at="2026-08-31T09:00:00+00:00")
        self.materialize_story(claim_id)
        result = self.coverage(claim_id)
        self.assertEqual(result["media"][0]["media_item_id"], media_b)
        self.assertEqual(result["media"][1]["media_item_id"], media_a)
        self.assertEqual(result["coverage"]["first_observed_at"], "2026-08-31T09:00:00+00:00")
        self.assertEqual(result["coverage"]["last_observed_at"], "2026-08-31T12:00:00+00:00")

    def test_one_media_observation_min_max_and_published_time_not_substituted(self):
        first, media_id = self.observation(
            "timestamps",
            observed_at="2026-08-31T10:00:00+00:00",
            published_at="2020-01-01T00:00:00+00:00",
        )
        claim_id = self.canonical_claim(first)
        second_id = "observation-timestamps-second"
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, media_item_id, subject_key, observation_type,
                  observed_at, recorded_at, metadata_json
                ) VALUES (?, 'source-1', ?, ?, 'report', ?, ?, '{}')
                """,
                (second_id, media_id, SUBJECT, "2026-08-31T13:00:00+00:00", NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.link(claim_id, second_id, observed_at="2026-08-31T13:00:00+00:00")
        self.materialize_story(claim_id)
        item = self.coverage(claim_id)["media"][0]
        self.assertEqual(item["reporting_first_observed_at"], NOW)
        self.assertEqual(item["reporting_last_observed_at"], "2026-08-31T13:00:00+00:00")

    def test_malformed_or_naive_observation_timestamp_fails_closed(self):
        for index, timestamp in enumerate(("bad-time", "2026-08-31T10:00:00")):
            with self.subTest(timestamp=timestamp):
                observation_id, _ = self.observation(
                    "bad-time-" + str(index), observed_at=timestamp
                )
                claim_id = self.canonical_claim(observation_id)
                self.materialize_story(claim_id)
                with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
                    self.coverage(claim_id)

    def test_channel_source_uses_persisted_actor_identity_not_domain(self):
        conn = self.factory()
        try:
            self._source(
                conn,
                "channel-1",
                "channel|youtube|platform_actor_id|UC123",
                "Cricket Channel",
                source_type="channel",
                domain="youtube.com",
                metadata={"identity_basis": "platform_actor_id", "identity_value": "UC123"},
            )
            conn.commit()
        finally:
            conn.close()
        observation_id, _ = self.observation(
            "video", source_id="channel-1", mode="multimodal_capture"
        )
        claim_id = self.canonical_claim(observation_id)
        self.materialize_story(claim_id)
        source = self.coverage(claim_id)["media"][0]["source"]
        self.assertEqual(source["source_id"], "channel-1")
        self.assertEqual(source["source_type"], "channel")
        self.assertNotEqual(source["source_id"], source["canonical_domain"])

    def test_dependency_records_do_not_change_coverage(self):
        first, _ = self.observation("dependency-one")
        claim_id = self.canonical_claim(first)
        second, _ = self.observation("dependency-two")
        self.link(claim_id, second)
        self.materialize_story(claim_id)
        before = self.coverage(claim_id)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO observation_dependencies (
                  id, downstream_source_observation_id, upstream_source_observation_id,
                  relationship_type, observed_at, recorded_at, metadata_json
                ) VALUES ('dependency-1', ?, ?, 'derived_from', ?, ?, '{}')
                """,
                (second, first, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        after = self.coverage(claim_id)
        self.assertEqual(before, after)

    def test_read_service_performs_no_writes_and_no_network_calls(self):
        claim_id, _, _ = self.basic_graph()
        before = self.db_path.read_bytes()
        with patch.object(socket, "create_connection", side_effect=AssertionError):
            result = self.coverage(claim_id)
        after = self.db_path.read_bytes()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(before, after)

    def test_missing_and_noncanonical_claim_handling(self):
        self.assertEqual(self.coverage("missing")["status"], "not_found")
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES ('legacy-only', 'legacy-only-key', ?, '', 'assertion',
                          ?, ?, '{}')
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.coverage("legacy-only")

    def test_route_success_missing_and_noncanonical_handling(self):
        claim_id, _, _ = self.basic_graph()
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES ('not-canonical', 'not-canonical-key', ?, '',
                          'assertion', ?, ?, '{}')
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        guarded = []

        def require_admin(request):
            guarded.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)
        success = client.get(
            f"/admin/intelligence/claims/{claim_id}/reporting-coverage"
        )
        missing = client.get(
            "/admin/intelligence/claims/missing/reporting-coverage"
        )
        invalid = client.get(
            "/admin/intelligence/claims/not-canonical/reporting-coverage"
        )
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()["coverage"]["media_items"], 1)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 409)
        self.assertEqual(len(guarded), 3)


if __name__ == "__main__":
    unittest.main()
