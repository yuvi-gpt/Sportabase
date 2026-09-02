from __future__ import annotations

import json
import tempfile
import unittest
import socket
from unittest.mock import patch

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.source_profiles import (
    build_reporter_profile,
    build_source_profile,
)
from app.routes.intelligence_admin import build_router
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
)


T0 = "2026-08-01T10:00:00+00:00"
T1 = "2026-08-02T10:00:00+00:00"
T2 = "2026-08-03T10:00:00+00:00"
SUBJECT = "player|one"


class SourceProfileTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "profiles.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            conn.executemany(
                "INSERT INTO intelligence_sources (id,source_key,display_name,source_type,canonical_domain,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,'publisher',?,?,?,'{}')",
                [
                    ("source-a", "publisher|a.example", "Outlet A", "a.example", T0, T2),
                    ("source-b", "publisher|b.example", "Outlet B", "b.example", T0, T2),
                ],
            )
            conn.executemany(
                "INSERT INTO intelligence_reporters (id,identity_key,display_name,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,?,?,'{}')",
                [
                    ("reporter-a", "reporter a", "Reporter A", T0, T2),
                    ("reporter-b", "reporter b", "Reporter B", T0, T2),
                ],
            )
            conn.executemany(
                "INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,published_at,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES (?,?, 'article',?,?,?,?,?,?,?,'{}')",
                [
                    ("media-a", "https://a.example/one", "source-a", "reporter-a", "One", T0, "h1", T0, T2),
                    ("media-b", "https://b.example/two", "source-b", "reporter-b", "Two", None, "h2", T0, T2),
                ],
            )
            structured = json.dumps({"structured_claim": {
                "version": "canonical-claim-contract-v1",
                "subject_key": SUBJECT,
                "event_type": "transfer",
                "state": "completed",
                "negated": False,
                "roles": {"destination": "club|arsenal"},
                "facets": {},
            }})
            conn.executemany(
                "INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,?,?,?,?,?)",
                [
                    ("legacy", "legacy-key", SUBJECT, "legacy", "assertion", T0, T2, "{}"),
                    ("canonical", "canonical-key", SUBJECT, "canonical", "assertion", T0, T2, structured),
                    ("claim-two", "claim-two-key", SUBJECT, "two", "assertion", T0, T2, "{}"),
                ],
            )
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy','canonical',?,'verified_equivalent','structured_identity',?,?,'{}')",
                (SUBJECT, T0, T2),
            )
            conn.execute(
                "INSERT INTO intelligence_stories (id,canonical_key,canonical_title,status,first_seen_at,last_seen_at,metadata_json) VALUES ('story-a','story-key','Story','developing',?,?, '{}')",
                (T0, T2),
            )
            conn.executemany(
                "INSERT INTO story_claim_links (story_id,claim_id,relationship_type,link_basis,linked_at,metadata_json) VALUES ('story-a',?,'exact_claim_group','downstream_exact_common_claim_id',?,'{}')",
                [("legacy", T0), ("claim-two", T0)],
            )
            conn.execute(
                "INSERT INTO canonical_entities (id,entity_key,entity_type,sport_key,canonical_name,first_seen_at,last_seen_at,metadata_json) VALUES ('entity-a','player|one','player','football','Player One',?,?, '{}')",
                (T0, T2),
            )
            conn.execute(
                "INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,canonical_url,reference_key,verification_status,observed_at,recorded_at,metadata_json) VALUES ('evidence-a','evidence-key','document',?,'','evidence-ref','verified',?,?,'{}')",
                (SUBJECT, T0, T0),
            )
            conn.execute(
                "INSERT INTO verified_claim_entity_participants (id,claim_id,entity_id,participant_role,evidence_id,verification_status,confidence,observed_at,recorded_at,metadata_json) VALUES ('participant','canonical','entity-a','subject','evidence-a','verified',1.0,?,?,'{}')",
                (T0, T0),
            )
            conn.executemany(
                "INSERT INTO source_observations (id,source_id,media_item_id,story_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?,?,?,?,?,'report','unresolved',?,?,'{}')",
                [
                    ("source-obs-a", "source-a", "media-a", "story-a", SUBJECT, T0, T0),
                    ("source-obs-b", "source-b", "media-b", None, SUBJECT, T1, T1),
                ],
            )
            conn.execute(
                "INSERT INTO reporter_observations (id,reporter_id,source_id,media_item_id,story_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('reporter-obs-a','reporter-a','source-a','media-a','story-a',?,'report','unresolved',?,?, '{}')",
                (SUBJECT, T0, T0),
            )
            conn.executemany(
                "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?,?,?,?,?,?,'{}')",
                [
                    ("link-report", "legacy", "source-obs-a", "reports", T0, T0),
                    ("link-support", "legacy", "source-obs-a", "supports", T0, T0),
                    ("link-contradict", "claim-two", "source-obs-a", "contradicts", T1, T1),
                    ("link-align", "claim-two", "source-obs-a", "aligned_to", T1, T1),
                    ("link-unknown", "claim-two", "source-obs-a", "mentions", T1, T1),
                ],
            )
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,reporter_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('reporter-link','legacy','reporter-obs-a','reports',?,?, '{}')",
                (T0, T0),
            )
            conn.execute(
                "INSERT INTO claim_evolution_links (id,predecessor_claim_id,successor_claim_id,subject_key,family_key,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('evolution','legacy','claim-two',?,'family-a','progresses_to',?,?, '{}')",
                (SUBJECT, T1, T1),
            )
            conn.execute(
                "INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('dependency','source-obs-a','source-obs-b','attributed_to',?,?, '{}')",
                (T1, T1),
            )
            conn.execute(
                "INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES ('ind-conflict','source-obs-a','source-obs-b','evidence-a','verified',?,?, '{}')",
                (T1, T1),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def test_source_profile_counts_semantics_coverage_and_conflict(self):
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)

        self.assertEqual(result["version"], "source-profile-v1")
        self.assertEqual(result["actor"]["canonical_key"], "publisher|a.example")
        self.assertEqual(result["actor"]["canonical_domain"], "a.example")
        summary = result["summary"]
        self.assertEqual(summary["observations_recorded"], 1)
        self.assertEqual(summary["media_items_reported"], 1)
        self.assertEqual(summary["claim_report_relationships"], 1)
        self.assertEqual(summary["claim_support_relationships"], 1)
        self.assertEqual(summary["claim_contradiction_relationships"], 1)
        self.assertEqual(summary["claim_alignment_relationships"], 1)
        self.assertEqual(summary["exact_claims_reported"], 2)
        self.assertEqual(summary["canonical_claims_reported"], 2)
        self.assertEqual(summary["exact_stories_reported"], 1)
        self.assertEqual(summary["evolution_families_touched"], 1)
        self.assertEqual(summary["known_dependency_observations"], 1)
        self.assertEqual(summary["verified_independent_observations"], 0)
        self.assertEqual(summary["verified_independence_pairs"], 0)
        self.assertEqual(result["coverage"]["sample_size_status"], "limited")
        self.assertEqual(result["coverage"]["sports"][0]["sport_key"], "football")
        self.assertEqual(result["coverage"]["event_types"][0]["event_type"], "transfer")
        self.assertEqual(result["dependency_context"]["relationship_counts"], {"attributed_to": 1})
        self.assertEqual(len(result["independence_context"]["conflicts"]), 1)
        self.assertTrue(any(row["type"] == "unrecognized_claim_relationship" for row in result["anomalies"]))
        forbidden = {"accuracy", "reliability_score", "trust_score", "hit_rate", "original_reporting"}
        self.assertTrue(forbidden.isdisjoint(json.dumps(result).lower().split('"')))

    def test_reporter_identity_association_and_recent_activity(self):
        result = build_reporter_profile(reporter_id="reporter-a", connection_factory=self.factory)

        self.assertEqual(result["actor"]["canonical_key"], "reporter a")
        self.assertNotIn("source_type", result["actor"])
        self.assertEqual(result["associations"]["observed_sources"][0]["id"], "source-a")
        recent = result["recent_activity"]
        self.assertFalse(recent["has_more"])
        self.assertEqual(recent["items"][0]["time_basis"], "published_at")
        self.assertTrue(result["policy"]["observed_reporting_association_does_not_establish_employment"])

    def test_verified_pair_counts_observations_separately_from_pairs(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute(
                "INSERT INTO observation_independence_assertions (id,observation_a_reporter_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES ('ind-two','reporter-obs-a','source-obs-b','evidence-a','verified',?,?, '{}')",
                (T2, T2),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["verified_independent_observations"], 1)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 1)
        self.assertEqual(result["independence_context"]["counterpart_actors"], [{"actor_type": "source", "actor_id": "source-b"}])

    def test_mapping_chain_fails_closed(self):
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('canonical','claim-two',?,'verified_equivalent','bad-chain',?,?,'{}')",
                (SUBJECT, T0, T2),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(StoryClaimGraphMaterializationIntegrityError, "chained|legacy"):
            build_source_profile(source_id="source-a", connection_factory=self.factory)

    def test_mapping_corruption_variants_fail_closed(self):
        mutations = {
            "unverified mapping": "UPDATE claim_identity_mappings SET mapping_status='unverified' WHERE production_claim_id='legacy'",
            "wrong subject": "UPDATE claim_identity_mappings SET subject_key='wrong' WHERE production_claim_id='legacy'",
            "malformed metadata": "UPDATE claim_identity_mappings SET metadata_json='[]' WHERE production_claim_id='legacy'",
            "missing target": "UPDATE claim_identity_mappings SET canonical_claim_id='missing' WHERE production_claim_id='legacy'",
            "self mapping": "UPDATE claim_identity_mappings SET canonical_claim_id='legacy' WHERE production_claim_id='legacy'",
        }
        for label, sql in mutations.items():
            with self.subTest(label=label):
                conn = self.factory()
                try:
                    conn.execute("PRAGMA foreign_keys=OFF")
                    conn.execute("PRAGMA ignore_check_constraints=ON")
                    conn.execute(sql)
                    conn.commit()
                finally:
                    conn.close()
                with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
                    build_source_profile(source_id="source-a", connection_factory=self.factory)
                conn = self.factory()
                try:
                    conn.execute("DELETE FROM claim_identity_mappings")
                    conn.execute(
                        "INSERT INTO claim_identity_mappings VALUES ('legacy','canonical',?,'verified_equivalent','structured_identity',?,?, '{}')",
                        (SUBJECT, T0, T2),
                    )
                    conn.commit()
                finally:
                    conn.close()

    def test_mapping_cycle_fails_closed(self):
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO claim_identity_mappings VALUES ('canonical','legacy',?,'verified_equivalent','cycle',?,?, '{}')",
                (SUBJECT, T0, T2),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_source_profile(source_id="source-a", connection_factory=self.factory)

    def test_malformed_structured_canonical_identity_fails_closed(self):
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE intelligence_claims SET metadata_json=? WHERE id='canonical'",
                (json.dumps({"structured_claim": {"event_type": "invented"}}),),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(StoryClaimGraphMaterializationIntegrityError, "Structured"):
            build_source_profile(source_id="source-a", connection_factory=self.factory)

    def test_unqualified_independence_variants_are_excluded(self):
        cases = ("unverified_assertion", "unverified_evidence", "same_source", "bad_assertion_metadata", "bad_assertion_time", "bad_evidence_metadata", "bad_evidence_time", "wrong_subject")
        for case in cases:
            with self.subTest(case=case):
                conn = self.factory()
                try:
                    conn.execute("DELETE FROM observation_dependencies")
                    if case == "unverified_assertion":
                        conn.execute("UPDATE observation_independence_assertions SET verification_status='unverified'")
                    elif case == "unverified_evidence":
                        conn.execute("UPDATE evidence_records SET verification_status='unverified'")
                    elif case == "same_source":
                        conn.execute("UPDATE source_observations SET source_id='source-a' WHERE id='source-obs-b'")
                    elif case == "bad_assertion_metadata":
                        conn.execute("UPDATE observation_independence_assertions SET metadata_json='[]'")
                    elif case == "bad_assertion_time":
                        conn.execute("UPDATE observation_independence_assertions SET observed_at='not-time'")
                    elif case == "bad_evidence_metadata":
                        conn.execute("UPDATE evidence_records SET metadata_json='[]'")
                    elif case == "bad_evidence_time":
                        conn.execute("UPDATE evidence_records SET recorded_at='not-time'")
                    elif case == "wrong_subject":
                        conn.execute("UPDATE evidence_records SET subject_key='wrong'")
                    conn.commit()
                finally:
                    conn.close()
                result = build_source_profile(source_id="source-a", connection_factory=self.factory)
                self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
                self.assertEqual(result["summary"]["verified_independent_observations"], 0)
                conn = self.factory()
                try:
                    conn.execute("UPDATE observation_independence_assertions SET verification_status='verified',metadata_json='{}',observed_at=?", (T1,))
                    conn.execute("UPDATE evidence_records SET verification_status='verified',metadata_json='{}',recorded_at=?,subject_key=?", (T0, SUBJECT))
                    conn.execute("UPDATE source_observations SET source_id='source-b' WHERE id='source-obs-b'")
                    conn.commit()
                finally:
                    conn.close()

    def test_missing_independence_endpoint_is_excluded(self):
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("UPDATE observation_independence_assertions SET observation_b_source_observation_id='missing'")
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 0)

    def test_unresolved_actor_dependency_blocks_independence(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("INSERT INTO intelligence_sources VALUES ('source-c','publisher|c.example','C','publisher','c.example',NULL,NULL,?,?, '{}')", (T0, T2))
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('actor-dep','source-obs-a','source-c','derived_from',?,?, '{}')", (T1, T1))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["known_dependency_observations"], 1)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
        self.assertTrue(any(row["type"] == "unresolved_actor_dependency" for row in result["anomalies"]))

    def test_dangling_dependency_target_is_excluded_and_blocks(self):
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('dangling-dep','source-obs-a','missing','derived_from',?,?, '{}')", (T1, T1))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["known_dependency_observations"], 0)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
        self.assertTrue(any(row["type"] == "dangling_dependency_target" for row in result["anomalies"]))

    def test_intermediate_dependency_cycle_blocks_independence(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("INSERT INTO intelligence_sources VALUES ('source-c','publisher|c.example','C','publisher','c.example',NULL,NULL,?,?, '{}')", (T0, T2))
            conn.execute("INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('source-obs-c','source-c',?,'report','unresolved',?,?, '{}')", (SUBJECT, T1, T1))
            rows = [
                ("cycle-a", "source-obs-a", "source-obs-b"),
                ("cycle-b", "source-obs-b", "source-obs-c"),
                ("cycle-c", "source-obs-c", "source-obs-a"),
            ]
            conn.executemany("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?,?,?,'derived_from',?,?, '{}')", [(a, b, c, T1, T1) for a, b, c in rows])
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
        self.assertTrue(any(row["type"] == "dependency_cycle" for row in result["anomalies"]))

    def test_malformed_dependency_does_not_count_and_blocks(self):
        conn = self.factory()
        try:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,downstream_reporter_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('bad-dep','source-obs-a','reporter-obs-a','source-obs-b','attributed_to',?,?, '{}')", (T1, T1))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["known_dependency_observations"], 0)
        self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
        self.assertTrue(any(row["type"] == "malformed_dependency" for row in result["anomalies"]))

    def test_all_malformed_dependency_cardinalities_block_independence(self):
        inserts = {
            "no-upstream": "INSERT INTO observation_dependencies (id,downstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('bad-dep','source-obs-a','attributed_to',?,?, '{}')",
            "multiple-upstream": "INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,upstream_source_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('bad-dep','source-obs-a','source-obs-b','source-b','attributed_to',?,?, '{}')",
            "multiple-downstream": "INSERT INTO observation_dependencies (id,downstream_source_observation_id,downstream_reporter_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('bad-dep','source-obs-a','reporter-obs-a','source-obs-b','attributed_to',?,?, '{}')",
        }
        for label, sql in inserts.items():
            with self.subTest(label=label):
                conn = self.factory()
                try:
                    conn.execute("PRAGMA ignore_check_constraints=ON")
                    conn.execute("DELETE FROM observation_dependencies")
                    conn.execute(sql, (T1, T1))
                    conn.commit()
                finally:
                    conn.close()
                result = build_source_profile(source_id="source-a", connection_factory=self.factory)
                self.assertEqual(result["summary"]["known_dependency_observations"], 0)
                self.assertEqual(result["summary"]["verified_independence_pairs"], 0)
                self.assertTrue(any(row["type"] == "malformed_dependency" for row in result["anomalies"]))

    def test_independence_is_not_transitive(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM observation_dependencies")
            conn.execute("INSERT INTO intelligence_sources VALUES ('source-c','publisher|c.example','C','publisher','c.example',NULL,NULL,?,?, '{}')", (T0, T2))
            conn.execute("INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('source-obs-c','source-c',?,'report','unresolved',?,?, '{}')", (SUBJECT, T2, T2))
            conn.execute("UPDATE observation_independence_assertions SET id='pair-a-b'")
            conn.execute("INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES ('pair-b-c','source-obs-b','source-obs-c','evidence-a','verified',?,?, '{}')", (T2, T2))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual([row["assertion_id"] for row in result["independence_context"]["qualified_pairs"]], ["pair-a-b"])
        self.assertEqual(result["summary"]["verified_independence_pairs"], 1)

    def test_association_mismatch_is_not_reintroduced_or_counted_as_media(self):
        conn = self.factory()
        try:
            conn.execute("UPDATE reporter_observations SET source_id='source-b' WHERE id='reporter-obs-a'")
            conn.commit()
        finally:
            conn.close()
        result = build_reporter_profile(reporter_id="reporter-a", connection_factory=self.factory)
        self.assertEqual(result["associations"]["observed_sources"], [])
        self.assertEqual(result["summary"]["media_items_reported"], 0)
        self.assertTrue(any(row["type"] == "actor_association_mismatch" for row in result["anomalies"]))

    def test_both_association_paths_dedupe_and_media_only_paths_are_preserved(self):
        conn = self.factory()
        try:
            conn.executemany(
                "INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,published_at,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,'article',?,?,?,? ,?,?,?,'{}')",
                [
                    ("media-reporter-only", "https://b.example/by-a", "source-b", "reporter-a", "By A", T1, "h3", T1, T2),
                    ("media-source-only", "https://a.example/by-b", "source-a", "reporter-b", "By B", T1, "h4", T1, T2),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        reporter = build_reporter_profile(reporter_id="reporter-a", connection_factory=self.factory)
        reporter_associations = {row["id"]: row for row in reporter["associations"]["observed_sources"]}
        self.assertEqual(set(reporter_associations), {"source-a", "source-b"})
        self.assertEqual(reporter_associations["source-a"]["media_items_reported"], 1)
        source = build_source_profile(source_id="source-a", connection_factory=self.factory)
        source_associations = {row["id"]: row for row in source["associations"]["observed_reporters"]}
        self.assertEqual(set(source_associations), {"reporter-a", "reporter-b"})
        self.assertEqual(source_associations["reporter-a"]["media_items_reported"], 1)

    def test_source_association_conflict_is_excluded_and_not_reintroduced(self):
        conn = self.factory()
        try:
            conn.execute("UPDATE media_items SET reporter_id='reporter-b' WHERE id='media-a'")
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(result["associations"]["observed_reporters"], [])
        self.assertEqual(result["summary"]["media_items_reported"], 0)
        self.assertTrue(any(row["type"] == "actor_association_mismatch" for row in result["anomalies"]))

    def test_source_association_source_identity_conflict_is_excluded(self):
        conn = self.factory()
        try:
            conn.execute("INSERT INTO intelligence_sources VALUES ('source-other','publisher|other.example','Other','publisher','other.example',NULL,NULL,?,?, '{}')", (T0, T2))
            conn.execute("INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,published_at,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES ('conflicting-media','https://other.example/conflict','article','source-other','reporter-b','Conflict',?,'conflict-hash',?,?, '{}')", (T1, T1, T2))
            conn.execute("INSERT INTO reporter_observations (id,reporter_id,source_id,media_item_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('conflicting-reporter-observation','reporter-b','source-a','conflicting-media',?,'report','unresolved',?,?, '{}')", (SUBJECT, T1, T1))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        associations = {row["id"]: row for row in result["associations"]["observed_reporters"]}
        self.assertNotIn("reporter-b", associations)
        self.assertEqual(result["summary"]["media_items_reported"], 1)
        self.assertTrue(any(
            row["type"] == "actor_association_mismatch"
            and row["stable_id"] == "conflicting-reporter-observation"
            for row in result["anomalies"]
        ))

    def test_sample_boundary_and_observed_time_fallback(self):
        conn = self.factory()
        try:
            conn.executemany(
                "INSERT INTO reporter_observations (id,reporter_id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?, 'reporter-a','source-a',?,'report','unresolved',?,?, '{}')",
                [(f"extra-{index}", SUBJECT, T2, T2) for index in range(3)],
            )
            conn.commit()
        finally:
            conn.close()
        result = build_reporter_profile(reporter_id="reporter-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["observations_recorded"], 4)
        self.assertEqual(result["coverage"]["sample_size_status"], "limited")
        conn = self.factory()
        try:
            conn.execute("INSERT INTO reporter_observations (id,reporter_id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('extra-3','reporter-a','source-a',?,'report','unresolved',?,?, '{}')", (SUBJECT, T2, T2))
            conn.commit()
        finally:
            conn.close()
        result = build_reporter_profile(reporter_id="reporter-a", connection_factory=self.factory)
        self.assertEqual(result["summary"]["observations_recorded"], 5)
        self.assertEqual(result["coverage"]["sample_size_status"], "sufficient_for_descriptive_counts")
        fallback = [row for row in result["recent_activity"]["items"] if row["observation_id"].startswith("extra-")]
        self.assertTrue(all(row["time_basis"] == "observed_at" for row in fallback))

    def test_missing_actor_and_deterministic_read_only_bounded_queries(self):
        self.assertEqual(build_source_profile(source_id="missing", connection_factory=self.factory)["status"], "not_found")
        conn = self.factory()
        try:
            conn.execute("INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,published_at,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES ('det-media','https://a.example/deterministic','article','source-a','reporter-b','Deterministic',?,'det-hash',?,?,'{}')", (T2, T2, T2))
            conn.execute("INSERT INTO source_observations (id,source_id,media_item_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('det-observation','source-a','det-media',?,'report','unresolved',?,?, '{}')", (SUBJECT, T2, T2))
            conn.execute("INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('det-safe','source-a',?,'report','unresolved',?,?, '{}')", (SUBJECT, T2, T2))
            conn.execute("INSERT INTO intelligence_sources VALUES ('source-c','publisher|c.example','C','publisher','c.example',NULL,NULL,?,?, '{}')", (T0, T2))
            conn.execute("INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('det-counterpart','source-c',?,'report','unresolved',?,?, '{}')", (SUBJECT, T2, T2))
            conn.execute("INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('det-link','claim-two','det-observation','reports',?,?, '{}')", (T2, T2))
            conn.executemany("INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES (?,'det-safe',?,'evidence-a','verified',?,?, '{}')", [("det-independent-b", "source-obs-b", T2, T2), ("det-independent-c", "det-counterpart", T2, T2)])
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('det-malformed','det-observation','derived_from',?,?, '{}')", (T2, T2))
            conn.commit()
        finally:
            conn.close()
        statements = []

        def traced_factory():
            conn = connect_database(self.db_path)
            conn.set_trace_callback(statements.append)
            return conn

        with patch.object(socket, "socket", side_effect=AssertionError("network access")):
            first = build_source_profile(source_id="source-a", connection_factory=traced_factory)
        first_count = len(statements)
        self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")) for sql in statements))
        second = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first["associations"]["observed_reporters"]), 2)
        self.assertGreaterEqual(len(first["dependency_context"]["upstream"]), 1)
        self.assertGreaterEqual(len(first["anomalies"]), 2)
        self.assertEqual(first["summary"]["verified_independence_pairs"], 2)
        self.assertGreaterEqual(len(first["recent_activity"]["items"]), 2)
        self.assertLess(first_count, 30)

    def test_query_growth_is_not_linear_and_mapping_targets_are_bulk_loaded(self):
        def trace_count():
            statements = []
            def factory():
                conn = connect_database(self.db_path)
                conn.set_trace_callback(statements.append)
                return conn
            build_source_profile(source_id="source-a", connection_factory=factory)
            return statements

        small = trace_count()
        candidate = {
            "version": "canonical-claim-contract-v1", "subject_key": SUBJECT,
            "event_type": "transfer", "state": "completed", "negated": False,
            "roles": {"destination": "club|arsenal"}, "facets": {},
        }
        conn = self.factory()
        try:
            for index in range(40):
                legacy, canonical, observation = f"bulk-legacy-{index}", f"bulk-canonical-{index}", f"bulk-observation-{index}"
                media_id = f"bulk-media-{index}"
                conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,'','assertion',?,?, '{}')", (legacy, "key-" + legacy, SUBJECT, T0, T2))
                conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,'','assertion',?,?,?)", (canonical, "key-" + canonical, SUBJECT, T0, T2, json.dumps({"structured_claim": candidate})))
                conn.execute("INSERT INTO claim_identity_mappings VALUES (?,?,?,'verified_equivalent','bulk',?,?, '{}')", (legacy, canonical, SUBJECT, T0, T2))
                conn.execute("INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,published_at,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,'article','source-a','reporter-b','bulk',?,?,?,?,'{}')", (media_id, f"https://a.example/{index}", T1, f"bulk-hash-{index}", T1, T2))
                conn.execute("INSERT INTO source_observations (id,source_id,media_item_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?,'source-a',?,?, 'report','unresolved',?,?, '{}')", (observation, media_id, SUBJECT, T1, T1))
                conn.execute("INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?,?,?,'reports',?,?, '{}')", ("bulk-link-" + str(index), legacy, observation, T1, T1))
            conn.commit()
        finally:
            conn.close()
        large = trace_count()
        self.assertLessEqual(len(large) - len(small), 3)
        normalized = [" ".join(sql.lower().split()) for sql in large]
        self.assertFalse(any("from intelligence_claims where id =" in sql for sql in normalized))
        self.assertFalse(any("select * from media_items where source_id=" in sql or "select * from media_items where reporter_id=" in sql for sql in normalized))
        self.assertFalse(any("select cl.*" in sql and "join source_observations" in sql for sql in normalized))

    def test_actor_metadata_is_bounded(self):
        conn = self.factory()
        try:
            conn.execute("UPDATE intelligence_sources SET metadata_json=? WHERE id='source-a'", (json.dumps({"oversized": "x" * 17000}),))
            conn.commit()
        finally:
            conn.close()
        result = build_source_profile(source_id="source-a", connection_factory=self.factory)
        self.assertNotIn("metadata", result["actor"])
        self.assertTrue(any(row["type"] == "malformed_actor_metadata" for row in result["anomalies"]))

    def test_admin_routes_are_protected_and_translate_missing_and_conflict(self):
        calls = []

        def guard(request):
            calls.append(request.url.path)

        app = FastAPI()
        app.include_router(build_router(require_admin=guard, connection_factory=self.factory))
        client = TestClient(app)
        response = client.get("/admin/intelligence/sources/source-a/profile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/admin/intelligence/sources/source-a/profile"])
        self.assertEqual(client.get("/admin/intelligence/reporters/missing/profile").status_code, 404)
        self.assertEqual(client.get("/admin/intelligence/reporters/reporter-a/profile").status_code, 200)
        self.assertEqual(client.get("/admin/intelligence/sources/" + "x" * 129 + "/profile").status_code, 422)

        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('canonical','claim-two',?,'verified_equivalent','bad-chain',?,?,'{}')",
                (SUBJECT, T0, T2),
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(client.get("/admin/intelligence/sources/source-a/profile").status_code, 409)

        denied = FastAPI()
        def deny(_request):
            raise HTTPException(status_code=403, detail="denied")
        denied.include_router(build_router(require_admin=deny, connection_factory=self.factory))
        self.assertEqual(TestClient(denied).get("/admin/intelligence/sources/source-a/profile").status_code, 403)


if __name__ == "__main__":
    unittest.main()
