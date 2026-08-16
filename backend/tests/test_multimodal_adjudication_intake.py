from __future__ import annotations

import copy
import sqlite3
import tempfile
from pathlib import Path
import unittest

from app.analysis import evidence as evidence_analysis
from app.analysis import observation_semantics
from app.services import multimodal_adjudication_intake as intake


CLAIM_ID = "claim-1"
MEDIA_ID = "media-1"
SOURCE_ID = "source-1"
SUBJECT = "club|arsenal"
EVIDENCE_ID = "evidence-1"
OBSERVATION_ID = "observation-1"
URL = "https://example.com/post"
NOW = "2026-08-16T12:00:00Z"


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE intelligence_claims (
  id TEXT PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE,
  subject_key TEXT NOT NULL,
  canonical_text TEXT NOT NULL DEFAULT '',
  claim_type TEXT NOT NULL DEFAULT 'assertion',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE media_items (
  id TEXT PRIMARY KEY
);

CREATE TABLE story_media_links (
  story_id TEXT NOT NULL,
  media_item_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  confidence REAL
);

CREATE TABLE evidence_records (
  id TEXT PRIMARY KEY,
  evidence_key TEXT NOT NULL UNIQUE,
  evidence_type TEXT NOT NULL,
  subject_key TEXT NOT NULL,
  claim_summary TEXT NOT NULL DEFAULT '',
  canonical_url TEXT NOT NULL DEFAULT '',
  reference_key TEXT NOT NULL DEFAULT '',
  verification_status TEXT NOT NULL DEFAULT 'unverified',
  published_at TEXT,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE source_observations (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  media_item_id TEXT,
  story_id TEXT,
  subject_key TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unresolved',
  claim_summary TEXT NOT NULL DEFAULT '',
  provenance_url TEXT NOT NULL DEFAULT '',
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE reporter_observations (
  id TEXT PRIMARY KEY,
  reporter_id TEXT NOT NULL,
  source_id TEXT,
  media_item_id TEXT,
  story_id TEXT,
  subject_key TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unresolved',
  claim_summary TEXT NOT NULL DEFAULT '',
  provenance_url TEXT NOT NULL DEFAULT '',
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE claim_links (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  source_observation_id TEXT,
  reporter_observation_id TEXT,
  evidence_id TEXT,
  relationship_type TEXT NOT NULL,
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE evidence_links (
  id TEXT PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  media_item_id TEXT,
  story_id TEXT,
  source_id TEXT,
  reporter_id TEXT,
  relationship_type TEXT NOT NULL,
  confidence REAL,
  linked_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE observation_dependencies (
  id TEXT PRIMARY KEY,
  downstream_source_observation_id TEXT,
  downstream_reporter_observation_id TEXT,
  upstream_source_observation_id TEXT,
  upstream_reporter_observation_id TEXT,
  upstream_source_id TEXT,
  upstream_reporter_id TEXT,
  relationship_type TEXT NOT NULL,
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE observation_independence_assertions (
  id TEXT PRIMARY KEY,
  observation_a_source_observation_id TEXT,
  observation_a_reporter_observation_id TEXT,
  observation_b_source_observation_id TEXT,
  observation_b_reporter_observation_id TEXT,
  provenance_evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE verified_source_entity_bindings (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  binding_type TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  confidence REAL NOT NULL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE verified_claim_entity_participants (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  participant_role TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  confidence REAL NOT NULL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
"""


def semantic(
    *,
    claim_id=CLAIM_ID,
    source_url=URL,
    relevance="same_claim",
):
    return (
        observation_semantics
        .normalize_claim_observation_semantics(
            {
                "claim_relevance":
                    relevance,
                "source_role":
                    "publisher",
                "authority_class":
                    "none",
                "reliability_class":
                    "unknown",
                "provenance_class":
                    "attributed_reporting",
                "stance":
                    "supports",
                "dependency_status":
                    "no_explicit_dependency_detected",
                "dependency_targets":
                    [],
                "field_evidence":
                    ["source text"],
                "source_role_confidence":
                    0.8,
                "authority_confidence":
                    0.8,
                "reliability_confidence":
                    0.8,
                "provenance_confidence":
                    0.8,
                "stance_confidence":
                    0.8,
                "dependency_confidence":
                    0.7,
            },
            claim_id=claim_id,
            source_url=source_url,
        )
    )


class MultimodalAdjudicationIntakeTests(
    unittest.TestCase
):
    def setUp(self):
        self.tmp = (
            tempfile
            .TemporaryDirectory()
        )

        self.db = (
            Path(
                self.tmp.name
            )
            / "intake.db"
        )

        conn = sqlite3.connect(
            self.db
        )

        conn.executescript(
            SCHEMA
        )

        conn.execute(
            """
            INSERT INTO intelligence_claims
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                CLAIM_ID,
                "multimodal|club|arsenal|claim",
                SUBJECT,
                "Arsenal completed the signing.",
                "multimodal_candidate",
                NOW,
                NOW,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO media_items
            VALUES (?)
            """,
            (
                MEDIA_ID,
            ),
        )

        conn.execute(
            """
            INSERT INTO story_media_links
            VALUES (?, ?, ?, ?)
            """,
            (
                "story-1",
                MEDIA_ID,
                "reports",
                1.0,
            ),
        )

        conn.execute(
            """
            INSERT INTO evidence_records
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                EVIDENCE_ID,
                "evidence-key-1",
                "multimodal_claim_candidate",
                SUBJECT,
                "Arsenal completed the signing.",
                URL,
                "candidate:1",
                "unverified",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO source_observations
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                OBSERVATION_ID,
                SOURCE_ID,
                MEDIA_ID,
                "story-1",
                SUBJECT,
                "multimodal_claim_candidate",
                "unresolved",
                "",
                URL,
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO claim_links
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "link-evidence",
                CLAIM_ID,
                None,
                None,
                EVIDENCE_ID,
                "aligned_to",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO claim_links
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "link-observation",
                CLAIM_ID,
                OBSERVATION_ID,
                None,
                None,
                "observed_in",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self):
        conn = sqlite3.connect(
            self.db
        )

        conn.row_factory = (
            sqlite3.Row
        )

        return conn

    def build(
        self,
        result=None,
        *,
        aligned_evidence_ids=None,
        source_observation_ids=None,
    ):
        return (
            intake
            .build_multimodal_adjudication_intake(
                claim_id=CLAIM_ID,
                media_item_id=MEDIA_ID,
                semantic_result=(
                    result
                    or semantic()
                ),
                aligned_evidence_ids=(
                    aligned_evidence_ids
                ),
                source_observation_ids=(
                    source_observation_ids
                ),
                connection_factory=(
                    self.factory
                ),
            )
        )

    def execute(
        self,
        sql,
        args=(),
    ):
        conn = self.factory()
        conn.execute(
            sql,
            args,
        )
        conn.commit()
        conn.close()

    def count(
        self,
        table,
    ):
        conn = self.factory()
        value = conn.execute(
            "SELECT COUNT(*) FROM "
            + table
        ).fetchone()[0]
        conn.close()
        return value

    def test_ready_intake_builds_evidence_analysis_v5(self):
        result = self.build()

        self.assertEqual(
            result["status"],
            "ready",
        )

        self.assertEqual(
            result[
                "evidence_analysis_bundle"
            ][
                "version"
            ],
            evidence_analysis
            .EVIDENCE_ANALYSIS_BUNDLE_VERSION,
        )

    def test_multimodal_evidence_remains_unverified(self):
        result = self.build()

        records = result[
            "evidence_analysis_bundle"
        ][
            "evidence_records"
        ]

        self.assertEqual(
            records[0][
                "verification_status"
            ],
            "unverified",
        )

    def test_model_judgments_are_attached_to_aligned_evidence(self):
        result = self.build()

        judgment = result[
            "judgments_by_field"
        ][
            "stance"
        ][0]

        self.assertEqual(
            judgment[
                "evidence_ids"
            ],
            [
                EVIDENCE_ID
            ],
        )

        self.assertEqual(
            judgment[
                "basis_class"
            ],
            "model_inference",
        )

        self.assertFalse(
            judgment[
                "training_eligible"
            ]
        )

    def test_no_authority_records_means_no_hard_reference(self):
        result = self.build()

        rows = result[
            "judgments_by_field"
        ][
            "authority_class"
        ]

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0][
                "basis_class"
            ],
            "model_inference",
        )

    def test_missing_claim_fails_closed(self):
        self.execute(
            """
            DELETE FROM intelligence_claims
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_missing_media_fails_closed(self):
        self.execute(
            """
            DELETE FROM media_items
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_missing_aligned_evidence_fails_closed(self):
        self.execute(
            """
            DELETE FROM claim_links
            WHERE evidence_id IS NOT NULL
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_missing_observed_in_fails_closed(self):
        self.execute(
            """
            DELETE FROM claim_links
            WHERE source_observation_id IS NOT NULL
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_verified_multimodal_candidate_is_rejected(self):
        self.execute(
            """
            UPDATE evidence_records
            SET verification_status = 'verified'
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_evidence_subject_mismatch_is_rejected(self):
        self.execute(
            """
            UPDATE evidence_records
            SET subject_key = 'club|chelsea'
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_observation_subject_mismatch_is_rejected(self):
        self.execute(
            """
            UPDATE source_observations
            SET subject_key = 'club|chelsea'
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_observation_media_mismatch_is_rejected(self):
        self.execute(
            """
            UPDATE source_observations
            SET media_item_id = 'media-elsewhere'
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_resolved_multimodal_observation_is_rejected(self):
        self.execute(
            """
            UPDATE source_observations
            SET status = 'confirmed'
            """
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_semantic_claim_mismatch_is_rejected(self):
        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                semantic(
                    claim_id="another-claim"
                )
            )

    def test_semantic_source_url_mismatch_is_rejected(self):
        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                semantic(
                    source_url=(
                        "https://elsewhere.example/post"
                    )
                )
            )

    def test_non_same_claim_semantics_are_rejected(self):
        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                semantic(
                    relevance="related_claim"
                )
            )

    def test_missing_semantic_policy_boundary_is_rejected(self):
        value = semantic()

        value[
            "policy"
        ][
            "model_does_not_establish_truth"
        ] = False

        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                value
            )

    def test_model_cannot_claim_hard_reference_basis(self):
        value = semantic()

        value[
            "field_judgments"
        ][0][
            "basis_class"
        ] = (
            "direct_authority_record"
        )

        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                value
            )

    def test_duplicate_semantic_judgment_ids_are_rejected(self):
        value = semantic()

        value[
            "field_judgments"
        ].append(
            copy.deepcopy(
                value[
                    "field_judgments"
                ][0]
            )
        )

        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                value
            )

    def test_boolean_semantic_confidence_is_rejected(self):
        value = semantic()

        value[
            "field_judgments"
        ][0][
            "confidence"
        ] = True

        with self.assertRaises(
            intake
            .IntakeSemanticError
        ):
            self.build(
                value
            )

    def test_explicit_dependency_enters_evidence_bundle(self):
        self.execute(
            """
            INSERT INTO observation_dependencies
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "dep-1",
                OBSERVATION_ID,
                None,
                None,
                None,
                "source-upstream",
                None,
                "derived_from",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        result = self.build()

        rows = result[
            "evidence_analysis_bundle"
        ][
            "observation_dependencies"
        ]

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0][
                "relationship_type"
            ],
            "derived_from",
        )

    def _verified_authority(
        self,
        participant_role,
        *,
        confidence=0.98,
        binding_evidence_status="verified",
    ):
        self.execute(
            """
            INSERT INTO evidence_records
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "binding-evidence",
                "binding-evidence-key",
                "official_binding",
                SUBJECT,
                "",
                URL,
                "binding",
                binding_evidence_status,
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            """
            INSERT INTO evidence_records
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "participant-evidence",
                "participant-evidence-key",
                "participant_binding",
                SUBJECT,
                "",
                URL,
                "participant",
                "verified",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            """
            INSERT INTO verified_source_entity_bindings
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "source-binding-1",
                SOURCE_ID,
                "entity-1",
                "official_account",
                "binding-evidence",
                "verified",
                confidence,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            """
            INSERT INTO verified_claim_entity_participants
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "participant-1",
                CLAIM_ID,
                "entity-1",
                participant_role,
                "participant-evidence",
                "verified",
                confidence,
                NOW,
                NOW,
                "{}",
            ),
        )

    def test_verified_stakeholder_match_adds_direct_authority_reference(self):
        self._verified_authority(
            "subject"
        )

        result = self.build()

        hard = [
            row
            for row in result[
                "judgments_by_field"
            ][
                "authority_class"
            ]
            if row[
                "basis_class"
            ]
            == "direct_authority_record"
        ]

        self.assertEqual(
            len(hard),
            1,
        )

        self.assertEqual(
            hard[0][
                "value"
            ],
            "direct",
        )

        self.assertGreaterEqual(
            hard[0][
                "confidence"
            ],
            0.95,
        )

    def test_verified_governing_body_match_adds_institutional_reference(self):
        self._verified_authority(
            "governing_body"
        )

        result = self.build()

        hard = [
            row
            for row in result[
                "judgments_by_field"
            ][
                "authority_class"
            ]
            if row[
                "basis_class"
            ]
            == "direct_authority_record"
        ]

        self.assertEqual(
            hard[0][
                "value"
            ],
            "institutional",
        )

    def test_unverified_binding_evidence_cannot_create_hard_reference(self):
        self._verified_authority(
            "subject",
            binding_evidence_status=(
                "unverified"
            ),
        )

        result = self.build()

        hard = [
            row
            for row in result[
                "judgments_by_field"
            ][
                "authority_class"
            ]
            if row[
                "basis_class"
            ]
            == "direct_authority_record"
        ]

        self.assertEqual(
            hard,
            [],
        )

    def test_low_confidence_verified_binding_is_rejected(self):
        self._verified_authority(
            "subject",
            confidence=0.90,
        )

        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build()

    def test_intake_does_not_write_database(self):
        before = {
            table: self.count(
                table
            )
            for table in (
                "intelligence_claims",
                "evidence_records",
                "source_observations",
                "claim_links",
                "observation_dependencies",
            )
        }

        self.build()

        after = {
            table: self.count(
                table
            )
            for table in before
        }

        self.assertEqual(
            before,
            after,
        )

    def test_intake_policy_does_not_claim_truth_independence_or_merit(self):
        result = self.build()

        policy = result[
            "policy"
        ]

        self.assertFalse(
            policy[
                "establishes_truth"
            ]
        )

        self.assertFalse(
            policy[
                "establishes_corroboration"
            ]
        )

        self.assertFalse(
            policy[
                "establishes_independence"
            ]
        )

        self.assertFalse(
            policy[
                "affects_live_merit"
            ]
        )

        self.assertTrue(
            policy[
                "adjudication_not_performed"
            ]
        )

    def _seed_second_claim_media_observation(
        self,
    ):
        second_url = (
            "https://other.example/post"
        )

        self.execute(
            '''
            INSERT INTO media_items
            VALUES (?)
            ''',
            (
                "media-2",
            ),
        )

        self.execute(
            '''
            INSERT INTO evidence_records
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "evidence-2",
                "evidence-key-2",
                "multimodal_claim_candidate",
                SUBJECT,
                "Arsenal completed the signing.",
                second_url,
                "candidate:2",
                "unverified",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            '''
            INSERT INTO source_observations
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "observation-2",
                "source-2",
                "media-2",
                None,
                SUBJECT,
                "multimodal_claim_candidate",
                "unresolved",
                "",
                second_url,
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            '''
            INSERT INTO claim_links
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "link-evidence-2",
                CLAIM_ID,
                None,
                None,
                "evidence-2",
                "aligned_to",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

        self.execute(
            '''
            INSERT INTO claim_links
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                "link-observation-2",
                CLAIM_ID,
                "observation-2",
                None,
                None,
                "observed_in",
                None,
                NOW,
                NOW,
                "{}",
            ),
        )

    def test_explicit_candidate_scope_allows_same_claim_on_multiple_media(
        self,
    ):
        self._seed_second_claim_media_observation()

        result = self.build(
            aligned_evidence_ids=[
                EVIDENCE_ID
            ],
            source_observation_ids=[
                OBSERVATION_ID
            ],
        )

        self.assertEqual(
            result[
                "aligned_evidence_ids"
            ],
            [
                EVIDENCE_ID
            ],
        )

        self.assertEqual(
            result[
                "source_observation_ids"
            ],
            [
                OBSERVATION_ID
            ],
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "explicit_persistence_scope_applied"
            ]
        )

        claim_links = result[
            "evidence_analysis_bundle"
        ][
            "claim_links"
        ]

        self.assertEqual(
            {
                row["id"]
                for row in claim_links
            },
            {
                "link-evidence",
                "link-observation",
            },
        )

    def test_explicit_candidate_scope_must_reference_claim_links(
        self,
    ):
        with self.assertRaises(
            intake
            .IntakeBindingError
        ):
            self.build(
                aligned_evidence_ids=[
                    "not-linked-evidence"
                ],
                source_observation_ids=[
                    OBSERVATION_ID
                ],
            )

    def test_explicit_candidate_scope_arguments_must_be_supplied_together(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.build(
                aligned_evidence_ids=[
                    EVIDENCE_ID
                ],
            )

    def test_intake_is_deterministic(self):
        first = self.build()
        second = self.build()

        self.assertEqual(
            first,
            second,
        )


if __name__ == "__main__":
    unittest.main()
