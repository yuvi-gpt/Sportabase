import tempfile
import unittest
import socket
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_evolution import reconcile_claim_evolution
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.claims.repository import record_claim_link
from app.intelligence.homepage_storylines import build_homepage_storylines
from app.routes import intelligence_admin
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


T0 = "2026-08-20T10:00:00+00:00"
T1 = "2026-08-21T10:00:00+00:00"
T2 = "2026-08-22T10:00:00+00:00"
SUBJECT = "football|player|one"


class HomepageStorylinesTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "homepage.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            for suffix in ("one", "two", "three"):
                conn.execute(
                    """INSERT INTO intelligence_sources
                    (id,source_key,display_name,source_type,canonical_domain,
                     first_seen_at,last_seen_at,metadata_json)
                    VALUES (?,?,?,'publisher',?,?,?,'{}')""",
                    ("source-" + suffix, "source|" + suffix, suffix.title(),
                     suffix + ".test", T0, T2),
                )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate(state, *, subject=SUBJECT, destination="club|arsenal", event_type="transfer", facets=None):
        roles = {"destination": destination}
        if event_type == "injury":
            roles = {}
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": subject,
            "event_type": event_type,
            "state": state,
            "negated": False,
            "roles": roles,
            "facets": facets or {},
        }

    def report(self, suffix, *, subject=SUBJECT, source="one", observed=T0, published=None):
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO media_items
                (id,canonical_url,mode,source_id,title,published_at,
                 latest_content_hash,first_seen_at,last_seen_at,metadata_json)
                VALUES (?,?, 'article',?,?,?,?,?,?, '{}')""",
                ("media-" + suffix, "https://example.test/" + suffix,
                 "source-" + source, "Report " + suffix, published,
                 "hash-" + suffix, observed, observed),
            )
            conn.execute(
                """INSERT INTO source_observations
                (id,source_id,media_item_id,subject_key,observation_type,status,
                 observed_at,recorded_at,metadata_json)
                VALUES (?,?,?,?, 'report','reported',?,?, '{}')""",
                ("observation-" + suffix, "source-" + source,
                 "media-" + suffix, subject, observed, T2),
            )
            conn.commit()
        finally:
            conn.close()
        return "observation-" + suffix

    def claim(self, state, suffix, *, subject=SUBJECT, destination="club|arsenal", observed=T0, published=None, text=None, event_type="transfer", facets=None):
        observation = self.report(
            suffix, subject=subject,
            source={"a": "one", "b": "two", "c": "three"}.get(suffix, "one"),
            observed=observed, published=published,
        )
        result = materialize_canonical_claim(
            candidate=self.candidate(state, subject=subject, destination=destination, event_type=event_type, facets=facets),
            claim_text=("Claim " + suffix if text is None else text),
            observed_at=observed,
            source_observation_id=observation,
            relationship_type="reports",
            connection_factory=self.factory,
        )
        claim_id = result["claim"]["id"]
        story = materialize_canonical_claim_story(
            claim_id=claim_id, connection_factory=self.factory
        )
        return claim_id, story["story_id"], observation

    def build(self, **kwargs):
        return build_homepage_storylines(connection_factory=self.factory, **kwargs)

    def add_verified_independence(self, left, right, suffix="one"):
        conn = self.factory()
        try:
            conn.execute("INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,verification_status,observed_at,recorded_at,metadata_json) VALUES (?,?, 'independent_report',?,'verified',?,?,'{}')", ("ind-evidence-" + suffix, "ind-" + suffix, SUBJECT, T1, T1))
            conn.execute("INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES (?,?,?,?,'verified',?,?,'{}')", ("ind-" + suffix, left, right, "ind-evidence-" + suffix, T1, T1))
            conn.commit()
        finally:
            conn.close()

    def add_evolution_link(self, link_id, predecessor, successor, family_key, relationship="progresses_to"):
        conn = self.factory()
        try:
            conn.execute("INSERT INTO claim_evolution_links (id,predecessor_claim_id,successor_claim_id,subject_key,family_key,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?,?,?,?,?,?,?,?, '{}')", (link_id, predecessor, successor, SUBJECT, family_key, relationship, T2, T2))
            conn.commit()
        finally:
            conn.close()

    def test_valid_component_preserves_claims_stories_and_root_identity(self):
        first, first_story, _ = self.claim("interest", "a", observed=T0)
        second, second_story, _ = self.claim("negotiating", "b", observed=T1)
        third, third_story, _ = self.claim("completed", "c", observed=T2)
        reconcile_claim_evolution(claim_id=third, connection_factory=self.factory)
        result = self.build()
        self.assertEqual(len(result["storylines"]), 1)
        card = result["storylines"][0]
        self.assertEqual(card["storyline_kind"], "evolution_component")
        self.assertEqual(card["storyline_id"], "homepage-storyline-v1|evolution-root|" + first)
        self.assertEqual({row["claim_id"] for row in card["claims"]}, {first, second, third})
        self.assertEqual({row["story_id"] for row in card["exact_stories"]}, {first_story, second_story, third_story})
        self.assertEqual(card["evolution_transition_count"], 2)
        self.assertEqual(card["current_state"], "completed")
        self.assertEqual(card["previous_state"], "negotiating")
        self.assertEqual(card["terminal_state"], "completed")

    def test_singleton_and_same_subject_claims_do_not_merge(self):
        first, story, _ = self.claim("interest", "a")
        second, _, _ = self.claim("injured", "b", observed=T1, event_type="injury", facets={"episode_key": "episode-1"})
        cards = self.build()["storylines"]
        self.assertEqual(len(cards), 2)
        by_claim = {card["current_claim_id"]: card for card in cards}
        self.assertEqual(by_claim[first]["storyline_id"], "homepage-storyline-v1|exact-story|" + story)
        self.assertEqual(by_claim[second]["storyline_kind"], "singleton")

    def test_disconnected_same_family_transfer_claims_stay_separate(self):
        self.claim("interest", "a", observed=T0)
        self.claim("completed", "b", observed=T1)
        self.assertEqual(len(self.build()["storylines"]), 2)

    def test_different_destination_families_do_not_merge(self):
        self.claim("interest", "a", destination="club|arsenal")
        self.claim("negotiating", "b", destination="club|chelsea", observed=T1)
        self.assertEqual(len(self.build()["storylines"]), 2)

    def test_deterministic_title_and_mechanical_fallback(self):
        first, _, _ = self.claim("interest", "a", text="Earlier title")
        second, _, _ = self.claim("negotiating", "b", observed=T1, text="Latest title")
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        self.assertEqual(self.build()["storylines"][0]["title"], "Latest title")
        conn = self.factory()
        try:
            conn.execute("UPDATE intelligence_claims SET canonical_text='' WHERE id=?", (second,))
            conn.execute("UPDATE intelligence_stories SET canonical_title='' WHERE canonical_key LIKE ?", ("%" + second,))
            conn.commit()
        finally:
            conn.close()
        fallback = self.build()["storylines"][0]["title"]
        self.assertIn("Transfer Negotiating", fallback)
        self.assertTrue(first)

    def test_media_dedup_source_semantics_and_representative_selection(self):
        claim_id, _, first_observation = self.claim("interest", "a", published=T0)
        second_observation = self.report("later", source="two", observed=T1, published=T2)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second_observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        card = self.build()["storylines"][0]
        self.assertEqual(card["report_count"], 2)
        self.assertEqual(card["distinct_source_count"], 2)
        self.assertFalse(card["verified_independent_reporting_present"])
        self.assertEqual(card["representative_media"]["media_item_id"], "media-later")
        self.assertEqual(card["first_appearance_at"], T0)
        self.assertEqual(card["latest_activity_at"], T2)
        self.assertTrue(first_observation)

    def test_verified_independence_and_dependency_conflict(self):
        claim_id, _, first = self.claim("interest", "a")
        second = self.report("independent", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.add_verified_independence(first, second)
        card = self.build()["storylines"][0]
        self.assertTrue(card["verified_independent_reporting_present"])
        conn = self.factory()
        try:
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('dep',?,?,'derived_from',?,?,'{}')", (second, first, T1, T1))
            conn.commit()
        finally:
            conn.close()
        card = self.build()["storylines"][0]
        self.assertFalse(card["verified_independent_reporting_present"])
        self.assertTrue(card["known_dependency_present"])

    def test_contradiction_and_adjudication_correction_are_separate(self):
        first, _, _ = self.claim("completed", "a", observed=T0)
        observation = self.report("denied", source="two", observed=T1)
        candidate = self.candidate("completed")
        candidate["negated"] = True
        result = materialize_canonical_claim(candidate=candidate, claim_text="Denied", observed_at=T1, source_observation_id=observation, relationship_type="reports", connection_factory=self.factory)
        second = result["claim"]["id"]
        materialize_canonical_claim_story(claim_id=second, connection_factory=self.factory)
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("INSERT INTO adjudication_state_revisions (id,claim_id,state_version,adjudication_version,adjudication_sha256,as_of,trigger_type,trigger_evidence_ids_json,revision_json,recorded_at) VALUES ('rev-a',?,'v','v','a',?,'initial_evaluation','[]','{}',?)", (first, T0, T2))
            conn.execute("INSERT INTO adjudication_state_revisions (id,claim_id,state_version,adjudication_version,adjudication_sha256,as_of,previous_revision_id,trigger_type,trigger_evidence_ids_json,revision_json,recorded_at) VALUES ('rev-b',?,'v','v','b',?,'rev-a','canonical_outcome','[]','{}',?)", (first, T2, T2))
            conn.execute("INSERT INTO automatic_correction_events (id,claim_id,field,signature,previous_revision_id,current_revision_id,event_version,event_json,recorded_at) VALUES ('correction',?,'stance','s','rev-a','rev-b','v','{}',?)", (first, T2))
            conn.commit()
        finally:
            conn.close()
        card = self.build()["storylines"][0]
        self.assertTrue(card["contradiction_present"])
        self.assertTrue(card["adjudication_correction_present"])

    def test_shared_verified_entity_does_not_group_storylines(self):
        first, _, _ = self.claim("interest", "a")
        second, _, _ = self.claim("injured", "b", observed=T1, event_type="injury", facets={"episode_key": "injury-one"})
        conn = self.factory()
        try:
            conn.execute("INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,verification_status,observed_at,recorded_at,metadata_json) VALUES ('entity-evidence','entity-evidence','official_statement',?,'verified',?,?,'{}')", (SUBJECT, T1, T1))
            conn.execute("INSERT INTO canonical_entities (id,entity_key,entity_type,sport_key,canonical_name,first_seen_at,last_seen_at,metadata_json) VALUES ('entity-one',?,'player','football','Player One',?,?,'{}')", (SUBJECT, T0, T1))
            for index, claim_id in enumerate((first, second)):
                conn.execute("INSERT INTO verified_claim_entity_participants (id,claim_id,entity_id,participant_role,evidence_id,verification_status,confidence,observed_at,recorded_at,metadata_json) VALUES (?,?, 'entity-one','subject','entity-evidence','verified',0.99,?,?,'{}')", ("participant-" + str(index), claim_id, T1, T1))
            conn.commit()
        finally:
            conn.close()
        cards = self.build()["storylines"]
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(card["entities"][0]["entity_id"] == "entity-one" for card in cards))

    def test_verified_equivalent_legacy_claim_adds_reports_without_duplicate_card(self):
        canonical, _, _ = self.claim("interest", "a")
        legacy_observation = self.report("legacy", source="two", observed=T1)
        conn = self.factory()
        try:
            conn.execute("INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-claim','legacy-key',?,'Legacy','assertion',?,?,'{}')", (SUBJECT, T0, T1))
            conn.execute("INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-claim',?,?,'verified_equivalent','test',?,?,'{}')", (canonical, SUBJECT, T0, T1))
            conn.commit()
        finally:
            conn.close()
        record_claim_link(claim_id="legacy-claim", relationship_type="reports", observed_at=T1, source_observation_id=legacy_observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=canonical, connection_factory=self.factory)
        cards = self.build()["storylines"]
        self.assertEqual(len(cards), 1)
        self.assertEqual([row["claim_id"] for row in cards[0]["claims"]], [canonical])
        self.assertEqual(cards[0]["report_count"], 2)

    def test_source_and_reporter_observations_for_same_media_count_once(self):
        claim_id, _, _ = self.claim("interest", "a")
        conn = self.factory()
        try:
            conn.execute("INSERT INTO intelligence_reporters (id,identity_key,display_name,first_seen_at,last_seen_at,metadata_json) VALUES ('reporter-one','reporter|one','Reporter One',?,?,'{}')", (T0, T1))
            conn.execute("INSERT INTO reporter_observations (id,reporter_id,source_id,media_item_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('reporter-observation','reporter-one','source-one','media-a',?,'report','reported',?,?,'{}')", (SUBJECT, T0, T1))
            conn.commit()
        finally:
            conn.close()
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T0, reporter_observation_id="reporter-observation", connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        card = self.build()["storylines"][0]
        self.assertEqual(card["report_count"], 1)
        self.assertEqual(card["representative_media"]["media_item_id"], "media-a")

    def test_same_media_reporting_two_component_claims_counts_once(self):
        first, _, observation = self.claim("interest", "a", observed=T0)
        second_result = materialize_canonical_claim(candidate=self.candidate("negotiating"), claim_text="Second", observed_at=T1, connection_factory=self.factory)
        second = second_result["claim"]["id"]
        materialize_canonical_claim_story(claim_id=second, connection_factory=self.factory)
        record_claim_link(claim_id=second, relationship_type="reports", observed_at=T1, source_observation_id=observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=second, connection_factory=self.factory)
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        card = self.build()["storylines"][0]
        self.assertEqual({row["claim_id"] for row in card["claims"]}, {first, second})
        self.assertEqual(card["report_count"], 1)
        self.assertEqual(card["distinct_source_count"], 1)

    def test_ambiguous_actor_dependency_blocks_independence_without_dependency(self):
        claim_id, _, first = self.claim("interest", "a")
        same_actor = self.report("same-actor", source="one", observed=T1)
        candidate = self.report("candidate", source="two", observed=T2)
        for observation in (same_actor, candidate):
            record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.add_verified_independence(first, candidate, "ambiguous")
        conn = self.factory()
        try:
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('ambiguous-dependency',?,'source-one','derived_from',?,?,'{}')", (candidate, T2, T2))
            conn.commit()
        finally:
            conn.close()
        card = self.build()["storylines"][0]
        self.assertFalse(card["known_dependency_present"])
        self.assertFalse(card["verified_independent_reporting_present"])

    def test_malformed_potential_dependency_blocks_independence_without_dependency(self):
        claim_id, _, first = self.claim("interest", "a")
        candidate = self.report("candidate", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=candidate, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.add_verified_independence(first, candidate, "malformed")
        conn = self.factory()
        try:
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('malformed-dependency',?,?,'derived_from',?,?,'not-json')", (candidate, first, T1, T1))
            conn.commit()
        finally:
            conn.close()
        card = self.build()["storylines"][0]
        self.assertFalse(card["known_dependency_present"])
        self.assertFalse(card["verified_independent_reporting_present"])

    def test_cycle_fails_closed_and_route_returns_conflict(self):
        first, _, _ = self.claim("interest", "a", observed=T0)
        second, _, _ = self.claim("negotiating", "b", observed=T1)
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        conn = self.factory()
        try:
            family = conn.execute("SELECT family_key FROM claim_evolution_links LIMIT 1").fetchone()[0]
        finally:
            conn.close()
        self.add_evolution_link("reverse-link", second, first, family)
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()
        app = FastAPI()
        app.include_router(intelligence_admin.build_router(require_admin=lambda request: None, connection_factory=self.factory))
        self.assertEqual(TestClient(app).get("/admin/intelligence/homepage-storylines").status_code, 409)

    def test_multiple_root_component_fails_closed(self):
        first, _, _ = self.claim("interest", "a", observed=T0)
        second, _, _ = self.claim("approach", "b", observed=T1)
        third, _, _ = self.claim("negotiating", "c", observed=T2)
        reconcile_claim_evolution(claim_id=third, connection_factory=self.factory)
        conn = self.factory()
        try:
            family = conn.execute("SELECT family_key FROM claim_evolution_links LIMIT 1").fetchone()[0]
            conn.execute("DELETE FROM claim_evolution_links")
            conn.commit()
        finally:
            conn.close()
        self.add_evolution_link("root-one", first, third, family)
        self.add_evolution_link("root-two", second, third, family)
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()

    def test_exact_story_corruption_fails_closed(self):
        claim_id, _, _ = self.claim("interest", "a")
        conn = self.factory()
        try:
            conn.execute("UPDATE intelligence_stories SET metadata_json='{}'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()
        self.assertTrue(claim_id)

    def test_identity_mapping_chain_fails_closed(self):
        canonical, _, _ = self.claim("interest", "a")
        conn = self.factory()
        try:
            for claim_id in ("legacy-one", "legacy-two"):
                conn.execute("INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,'Legacy','assertion',?,?,'{}')", (claim_id, claim_id + "-key", SUBJECT, T0, T1))
            conn.execute("INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-one',?,?,'verified_equivalent','test',?,?,'{}')", (canonical, SUBJECT, T0, T1))
            conn.execute("INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-two','legacy-one',?,'verified_equivalent','test',?,?,'{}')", (SUBJECT, T0, T1))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()

    def test_equal_time_cards_use_storyline_id_tie_break(self):
        self.claim("interest", "a", subject="football|player|one", observed=T0, published=T0)
        self.claim("interest", "b", subject="football|player|two", observed=T0, published=T0)
        cards = self.build()["storylines"]
        self.assertEqual([card["storyline_id"] for card in cards], sorted(card["storyline_id"] for card in cards))

    def test_malformed_cursors_are_client_errors(self):
        self.claim("interest", "a")
        app = FastAPI()
        app.include_router(intelligence_admin.build_router(require_admin=lambda request: None, connection_factory=self.factory))
        client = TestClient(app)
        self.assertEqual(client.get("/admin/intelligence/homepage-storylines?cursor=not-base64").status_code, 422)
        import base64
        import json
        malformed_time = base64.urlsafe_b64encode(json.dumps(["bad-time", T0, "homepage-storyline-v1|exact-story|id"]).encode()).decode().rstrip("=")
        malformed_id = base64.urlsafe_b64encode(json.dumps([T0, T0, "wrong|id"]).encode()).decode().rstrip("=")
        self.assertEqual(client.get("/admin/intelligence/homepage-storylines", params={"cursor": malformed_time}).status_code, 422)
        self.assertEqual(client.get("/admin/intelligence/homepage-storylines", params={"cursor": malformed_id}).status_code, 422)

    def test_query_count_is_bounded_across_more_storyline_cards(self):
        self.claim("interest", "a", subject="football|player|one")
        counts = []
        def counting_factory():
            conn = self.factory()
            conn.set_trace_callback(lambda statement: counts.append(statement) if statement.lstrip().upper().startswith("SELECT") else None)
            return conn
        build_homepage_storylines(connection_factory=counting_factory)
        one_card_queries = len(counts)
        for index in range(2, 7):
            self.claim("interest", "bulk-" + str(index), subject="football|player|" + str(index), observed=T0)
        counts.clear()
        result = build_homepage_storylines(connection_factory=counting_factory)
        self.assertEqual(len(result["storylines"]), 6)
        self.assertLessEqual(len(counts), one_card_queries + 2)

    def test_ordering_limit_cursor_and_policy(self):
        self.claim("interest", "a", observed=T0)
        self.claim("interest", "b", subject="football|player|two", observed=T2)
        first = self.build(limit=1)
        self.assertTrue(first["pagination"]["has_more"])
        second = self.build(limit=1, cursor=first["pagination"]["next_cursor"])
        self.assertNotEqual(first["storylines"][0]["storyline_id"], second["storylines"][0]["storyline_id"])
        policy = first["policy"]
        self.assertFalse(policy["provider_call_performed"])
        self.assertFalse(policy["read_path_performs_writes"])
        self.assertTrue(policy["family_key_alone_does_not_define_storyline"])

    def test_fail_closed_dangling_cross_subject_cycle_and_exact_story_corruption(self):
        first, _, _ = self.claim("interest", "a", observed=T0)
        second, _, _ = self.claim("negotiating", "b", observed=T1)
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("UPDATE claim_evolution_links SET successor_claim_id='missing'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()
        conn = self.factory()
        try:
            conn.execute("UPDATE claim_evolution_links SET successor_claim_id=?, predecessor_claim_id=?", (second, first))
            conn.execute("UPDATE intelligence_claims SET subject_key='other' WHERE id=?", (second,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build()

    def test_route_validation_integrity_read_only_and_no_reconciliation(self):
        claim_id, _, _ = self.claim("interest", "a")
        app = FastAPI()
        app.include_router(intelligence_admin.build_router(require_admin=lambda request: None, connection_factory=self.factory))
        client = TestClient(app)
        with (
            patch("app.intelligence.claim_evolution.reconcile_claim_evolution") as reconcile,
            patch("app.ai.generation.generate_gemini_content", side_effect=AssertionError("provider call")) as provider,
            patch.object(socket, "create_connection", side_effect=AssertionError("network call")) as network,
        ):
            response = client.get("/admin/intelligence/homepage-storylines")
        self.assertEqual(response.status_code, 200)
        reconcile.assert_not_called()
        provider.assert_not_called()
        network.assert_not_called()
        self.assertEqual(client.get("/admin/intelligence/homepage-storylines?limit=201").status_code, 422)
        conn = self.factory()
        try:
            conn.execute("DELETE FROM story_claim_links WHERE claim_id=?", (claim_id,))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(client.get("/admin/intelligence/homepage-storylines").status_code, 409)


if __name__ == "__main__":
    unittest.main()
