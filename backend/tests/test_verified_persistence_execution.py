from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from app.intelligence import claims as claims
from app.intelligence import evidence as evidence
from app.models import content
from app.models import intelligence_bridge as models
from app.services import verified_persistence_execution as runtime

OBSERVED = "2026-08-16T12:00:00Z"
SUBJECT = "club|arsenal"
SOURCE = "source-1"
MEDIA = "media-1"
STORY = "story-1"
UPSTREAM_SOURCE = "source-upstream"


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE canonical_entities (
 id TEXT PRIMARY KEY,
 entity_key TEXT NOT NULL UNIQUE
);

CREATE TABLE intelligence_sources (
 id TEXT PRIMARY KEY,
 source_key TEXT NOT NULL UNIQUE
);

CREATE TABLE intelligence_reporters (
 id TEXT PRIMARY KEY,
 identity_key TEXT NOT NULL UNIQUE
);

CREATE TABLE media_items (
 id TEXT PRIMARY KEY,
 canonical_url TEXT NOT NULL UNIQUE,
 mode TEXT NOT NULL,
 source_id TEXT,
 reporter_id TEXT,
 title TEXT NOT NULL DEFAULT '',
 published_at TEXT,
 latest_content_hash TEXT NOT NULL,
 first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(source_id)
   REFERENCES intelligence_sources(id),
 FOREIGN KEY(reporter_id)
   REFERENCES intelligence_reporters(id)
);

CREATE TABLE intelligence_stories (
 id TEXT PRIMARY KEY,
 canonical_key TEXT NOT NULL UNIQUE,
 canonical_title TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'developing',
 first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL,
 metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE story_media_links (
 story_id TEXT NOT NULL,
 media_item_id TEXT NOT NULL,
 relationship_type TEXT NOT NULL DEFAULT 'reports',
 confidence REAL NOT NULL DEFAULT 0.0,
 linked_at TEXT NOT NULL,
 PRIMARY KEY(story_id, media_item_id),
 FOREIGN KEY(story_id)
   REFERENCES intelligence_stories(id),
 FOREIGN KEY(media_item_id)
   REFERENCES media_items(id)
);

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
 metadata_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(source_id)
   REFERENCES intelligence_sources(id),
 FOREIGN KEY(media_item_id)
   REFERENCES media_items(id),
 FOREIGN KEY(story_id)
   REFERENCES intelligence_stories(id)
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
 metadata_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(claim_id)
   REFERENCES intelligence_claims(id),
 FOREIGN KEY(source_observation_id)
   REFERENCES source_observations(id),
 FOREIGN KEY(evidence_id)
   REFERENCES evidence_records(id)
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
 metadata_json TEXT NOT NULL DEFAULT '{}',
 FOREIGN KEY(downstream_source_observation_id)
   REFERENCES source_observations(id),
 FOREIGN KEY(upstream_source_observation_id)
   REFERENCES source_observations(id),
 FOREIGN KEY(upstream_source_id)
   REFERENCES intelligence_sources(id),
 FOREIGN KEY(upstream_reporter_id)
   REFERENCES intelligence_reporters(id)
);
"""


def evidence_id(kwargs):
    key = (
        evidence
        .evidence_key_for_record(
            evidence_type=(
                kwargs[
                    "evidence_type"
                ]
            ),
            subject_key=(
                kwargs[
                    "subject_key"
                ]
            ),
            observed_at=(
                kwargs[
                    "observed_at"
                ]
            ),
            canonical_url=(
                kwargs.get(
                    "canonical_url",
                    "",
                )
            ),
            reference_key=(
                kwargs.get(
                    "reference_key",
                    "",
                )
            ),
            verification_status=(
                kwargs.get(
                    "verification_status",
                    "unverified",
                )
            ),
            normalize_url=(
                lambda value: value
            ),
        )
    )

    return hashlib.sha256(
        (
            "evidence|"
            + key
        ).encode()
    ).hexdigest()


def proposal(
    operation,
    kwargs,
    deterministic_id="",
):
    return (
        models.PersistenceProposal(
            operation=operation,
            readiness="ready",
            deterministic_id=(
                deterministic_id
            ),
            blocked_reasons=[],
            kwargs=kwargs,
        )
    )


def candidate(index=1):
    text = (
        "Arsenal completed signing "
        + str(index)
        + "."
    )

    canonical_key = (
        "multimodal|"
        + SUBJECT
        + "|claim-"
        + str(index)
    )

    claim_id = (
        claims
        .claim_id_for_canonical_key(
            canonical_key
        )
    )

    ev_kwargs = {
        "evidence_type":
            "multimodal_claim_candidate",
        "subject_key":
            SUBJECT,
        "observed_at":
            OBSERVED,
        "claim_summary":
            text,
        "canonical_url":
            "https://example.com/post",
        "reference_key":
            "candidate:"
            + str(index),
        "verification_status":
            "unverified",
        "published_at":
            None,
        "metadata": {
            "training_eligible":
                False,
            "establishes_truth":
                False,
            "establishes_independence":
                False,
            "affects_live_merit":
                False,
        },
    }

    ev_id = evidence_id(
        ev_kwargs
    )

    link_kwargs = {
        "claim_id":
            claim_id,
        "relationship_type":
            "aligned_to",
        "observed_at":
            OBSERVED,
        "confidence":
            None,
        "evidence_id":
            ev_id,
        "metadata": {
            "establishes_truth":
                False,
            "affects_live_merit":
                False,
        },
    }

    link_id = (
        claims
        .claim_link_id_for_record(
            claim_id=claim_id,
            relationship_type=(
                "aligned_to"
            ),
            observed_at=(
                OBSERVED
            ),
            confidence=None,
            evidence_id=(
                ev_id
            ),
        )
    )

    obs_kwargs = {
        "source_id":
            SOURCE,
        "subject_key":
            SUBJECT,
        "observation_type":
            "report",
        "observed_at":
            OBSERVED,
        "status":
            "unresolved",
        "claim_summary":
            text,
        "provenance_url":
            "https://example.com/post",
        "confidence":
            None,
        "media_item_id":
            MEDIA,
        "story_id":
            STORY,
        "metadata": {
            "interpretation_confidence":
                0.82,
            "establishes_truth":
                False,
            "establishes_independence":
                False,
            "affects_live_merit":
                False,
        },
    }

    return (
        models
        .CandidateBridgeRecord(
            candidate_id=(
                "candidate:"
                + str(index)
            ),
            canonical_text=text,
            interpretation_confidence=(
                0.82
            ),
            source_artifacts=[],
            source_validation_errors=[],
            claim=proposal(
                "upsert_intelligence_claim",
                {
                    "canonical_key":
                        canonical_key,
                    "subject_key":
                        SUBJECT,
                    "canonical_text":
                        text,
                    "claim_type":
                        "multimodal_candidate",
                    "metadata": {
                        "establishes_truth":
                            False,
                    },
                    "seen_at":
                        OBSERVED,
                },
                claim_id,
            ),
            evidence=proposal(
                "record_evidence",
                ev_kwargs,
                ev_id,
            ),
            claim_link=proposal(
                "record_claim_link",
                link_kwargs,
                link_id,
            ),
            source_observation=(
                proposal(
                    "record_source_observation",
                    obs_kwargs,
                )
            ),
            policy={
                "training_eligible":
                    False,
                "establishes_truth":
                    False,
                "establishes_independence":
                    False,
                "affects_live_merit":
                    False,
            },
        )
    )


def bindings():
    return (
        models.BridgeBindings(
            subject_key=SUBJECT,
            source_id=SOURCE,
            source_record_verified=True,
            media_item_id=MEDIA,
            media_item_record_verified=True,
            story_id=STORY,
            story_record_verified=True,
            upstream_targets_by_item_id={},
        )
    )


def plan(
    candidates=None,
    dependencies=None,
):
    return (
        models
        .ItemIntelligenceBridgePlan(
            item_id="web:item",
            subject_key=SUBJECT,
            subject_resolution_status=(
                "explicit_binding"
            ),
            source_candidate={},
            candidates=(
                candidates
                or [
                    candidate()
                ]
            ),
            dependency_constraints=(
                dependencies
                or []
            ),
            independence_status=(
                "unknown"
            ),
            policy={
                "bridge_runtime_version": (
                    "multimodal-intelligence-bridge-runtime-v1"
                ),
                "dry_run_only":
                    True,
                "training_eligible":
                    False,
                "establishes_truth":
                    False,
                "establishes_independence":
                    False,
                "affects_live_merit":
                    False,
            },
        )
    )


def relationship(
    kind="repost_of",
):
    return (
        content
        .ContentRelationship(
            relationship_id="rel:1",
            source_item_id="web:item",
            target_item_id="upstream:item",
            relationship_type=kind,
            provenance=(
                content
                .ProvenanceRecord(
                    source_url=(
                        "https://example.com/post"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    extraction_method=(
                        "browser_dom"
                    ),
                    content_hash=(
                        "rel-hash"
                    ),
                )
            ),
        )
    )


def dep_constraint(
    kind="repost_of",
):
    mapped = (
        "attributed_to"
        if kind == "quote_of"
        else "derived_from"
    )

    return (
        models
        .DependencyConstraint(
            relationship_id="rel:1",
            relationship_type=kind,
            source_item_id="web:item",
            target_item_id="upstream:item",
            persistence_relationship_type=(
                mapped
            ),
            independence_status=(
                "blocked_by_explicit_dependency"
            ),
            persistence_proposal=(
                models
                .PersistenceProposal(
                    operation=(
                        "record_observation_dependency"
                    ),
                    readiness="blocked",
                    deterministic_id="",
                    blocked_reasons=[
                        "downstream_source_observation_not_bound"
                    ],
                    kwargs={},
                )
            ),
            policy={
                "explicit_dependency_blocks_independence":
                    True,
                "establishes_truth":
                    False,
                "affects_live_merit":
                    False,
            },
        )
    )


class VerifiedPersistenceTests(
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
            / "test.db"
        )

        conn = sqlite3.connect(
            self.db
        )

        conn.executescript(
            SCHEMA
        )

        conn.execute(
            """
            INSERT INTO canonical_entities
            VALUES (?, ?)
            """,
            (
                "entity-1",
                SUBJECT,
            ),
        )

        conn.execute(
            """
            INSERT INTO intelligence_sources
            VALUES (?, ?)
            """,
            (
                SOURCE,
                "publisher|example.com",
            ),
        )

        conn.execute(
            """
            INSERT INTO intelligence_sources
            VALUES (?, ?)
            """,
            (
                UPSTREAM_SOURCE,
                "publisher|upstream",
            ),
        )

        conn.execute(
            """
            INSERT INTO media_items
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                MEDIA,
                "https://example.com/post",
                "web",
                SOURCE,
                None,
                "",
                None,
                "hash",
                OBSERVED,
                OBSERVED,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO intelligence_stories
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                STORY,
                "story-key",
                "Story",
                "developing",
                OBSERVED,
                OBSERVED,
                "{}",
            ),
        )

        conn.execute(
            """
            INSERT INTO story_media_links
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                STORY,
                MEDIA,
                "reports",
                1.0,
                OBSERVED,
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

        conn.execute(
            "PRAGMA foreign_keys=ON"
        )

        return conn

    def count(self, table):
        conn = self.factory()

        value = conn.execute(
            "SELECT COUNT(*) FROM "
            + table
        ).fetchone()[0]

        conn.close()

        return value

    def execute(
        self,
        p=None,
        b=None,
        rels=(),
    ):
        return (
            runtime
            .execute_verified_persistence(
                plan=(
                    p
                    or plan()
                ),
                bindings=(
                    b
                    or bindings()
                ),
                relationships=rels,
                connection_factory=(
                    self.factory
                ),
            )
        )

    def test_success_persists_atomic_candidate_graph(self):
        result = self.execute()

        self.assertEqual(
            result[
                "candidate_count"
            ],
            1,
        )

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            0,
        )

    def test_evidence_remains_unverified(self):
        self.execute()

        conn = self.factory()

        status = conn.execute(
            """
            SELECT verification_status
            FROM evidence_records
            """
        ).fetchone()[0]

        conn.close()

        self.assertEqual(
            status,
            "unverified",
        )

    def test_observation_confidence_remains_null(self):
        self.execute()

        conn = self.factory()

        value = conn.execute(
            """
            SELECT confidence
            FROM source_observations
            """
        ).fetchone()[0]

        conn.close()

        self.assertIsNone(
            value
        )

    def test_idempotent_rerun(self):
        self.execute()
        self.execute()

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

    def test_two_candidates_share_neutral_observation(self):
        self.execute(
            plan([
                candidate(1),
                candidate(2),
            ])
        )

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            4,
        )

    def test_missing_subject_row_fails_before_writes(self):
        conn = self.factory()

        conn.execute(
            """
            DELETE FROM canonical_entities
            """
        )

        conn.commit()
        conn.close()

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute()

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            0,
        )

    def test_missing_source_row_fails_before_writes(self):
        conn = self.factory()

        conn.execute(
            """
            DELETE FROM story_media_links
            """
        )

        conn.execute(
            """
            DELETE FROM media_items
            """
        )

        conn.execute(
            """
            DELETE FROM intelligence_sources
            WHERE id = ?
            """,
            (
                SOURCE,
            ),
        )

        conn.commit()
        conn.close()

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute()

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            0,
        )

    def test_media_source_mismatch_fails(self):
        conn = self.factory()

        conn.execute(
            """
            UPDATE media_items
            SET source_id = ?
            """,
            (
                UPSTREAM_SOURCE,
            ),
        )

        conn.commit()
        conn.close()

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute()

    def test_missing_story_media_link_fails(self):
        conn = self.factory()

        conn.execute(
            """
            DELETE FROM story_media_links
            """
        )

        conn.commit()
        conn.close()

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute()

    def test_false_source_verified_flag_fails(self):
        b = bindings()
        b.source_record_verified = False

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute(
                b=b
            )

    def test_false_media_verified_flag_fails(self):
        b = bindings()
        b.media_item_record_verified = False

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute(
                b=b
            )

    def test_false_story_verified_flag_fails(self):
        b = bindings()
        b.story_record_verified = False

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute(
                b=b
            )

    def test_blocked_proposal_fails(self):
        p = plan()

        p.candidates[
            0
        ].claim.readiness = (
            "blocked"
        )

        p.candidates[
            0
        ].claim.blocked_reasons = [
            "x"
        ]

        with self.assertRaises(
            runtime
            .ProposalBlockedError
        ):
            self.execute(
                p=p
            )

    def test_verified_evidence_is_rejected(self):
        p = plan()

        p.candidates[
            0
        ].evidence.kwargs[
            "verification_status"
        ] = "verified"

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_tampered_claim_identity_is_rejected(self):
        p = plan()

        p.candidates[
            0
        ].claim.deterministic_id = (
            "wrong"
        )

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_tampered_evidence_identity_is_rejected(self):
        p = plan()

        p.candidates[
            0
        ].evidence.deterministic_id = (
            "wrong"
        )

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_tampered_link_identity_is_rejected(self):
        p = plan()

        p.candidates[
            0
        ].claim_link.deterministic_id = (
            "wrong"
        )

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_merit_policy_true_is_rejected(self):
        p = plan()

        p.policy[
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_truth_policy_true_is_rejected(self):
        p = plan()

        p.candidates[
            0
        ].policy[
            "establishes_truth"
        ] = True

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_non_dry_run_plan_is_rejected(self):
        p = plan()

        p.policy[
            "dry_run_only"
        ] = False

        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                p=p
            )

    def test_no_candidates_is_rejected(self):
        p = plan()

        p.candidates = []

        with self.assertRaises(
            runtime
            .ProposalBlockedError
        ):
            self.execute(
                p=p
            )

    def test_explicit_dependency_persists_after_observation(self):
        b = bindings()

        b.upstream_targets_by_item_id = {
            "upstream:item": {
                "record_verified":
                    True,
                "upstream_source_id":
                    UPSTREAM_SOURCE,
            }
        }

        p = plan(
            dependencies=[
                dep_constraint(
                    "repost_of"
                )
            ]
        )

        self.execute(
            p=p,
            b=b,
            rels=[
                relationship(
                    "repost_of"
                )
            ],
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            1,
        )

        conn = self.factory()

        row = conn.execute(
            """
            SELECT
              relationship_type,
              upstream_source_id
            FROM observation_dependencies
            """
        ).fetchone()

        conn.close()

        self.assertEqual(
            tuple(row),
            (
                "derived_from",
                UPSTREAM_SOURCE,
            ),
        )

    def test_quote_dependency_maps_to_attributed_to(self):
        b = bindings()

        b.upstream_targets_by_item_id = {
            "upstream:item": {
                "record_verified":
                    True,
                "upstream_source_id":
                    UPSTREAM_SOURCE,
            }
        }

        p = plan(
            dependencies=[
                dep_constraint(
                    "quote_of"
                )
            ]
        )

        self.execute(
            p=p,
            b=b,
            rels=[
                relationship(
                    "quote_of"
                )
            ],
        )

        conn = self.factory()

        value = conn.execute(
            """
            SELECT relationship_type
            FROM observation_dependencies
            """
        ).fetchone()[0]

        conn.close()

        self.assertEqual(
            value,
            "attributed_to",
        )

    def test_missing_upstream_dependency_target_rolls_back(self):
        p = plan(
            dependencies=[
                dep_constraint(
                    "repost_of"
                )
            ]
        )

        with self.assertRaises(
            runtime
            .BindingVerificationError
        ):
            self.execute(
                p=p,
                rels=[
                    relationship(
                        "repost_of"
                    )
                ],
            )

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            0,
        )

    def test_omitted_explicit_dependency_is_rejected(self):
        with self.assertRaises(
            runtime
            .IntegrityVerificationError
        ):
            self.execute(
                rels=[
                    relationship(
                        "repost_of"
                    )
                ]
            )

    def test_transaction_rolls_back_mid_write_failure(self):
        with mock.patch.object(
            runtime
            .claim_intelligence,
            "record_claim_link",
            side_effect=(
                RuntimeError(
                    "boom"
                )
            ),
        ):
            with self.assertRaises(
                RuntimeError
            ):
                self.execute()

        self.assertEqual(
            self.count(
                "intelligence_claims"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            0,
        )

    def test_result_policy_never_claims_truth_or_merit(self):
        result = self.execute()

        self.assertFalse(
            result[
                "policy"
            ][
                "establishes_truth"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "establishes_independence"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "affects_live_merit"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "adjudication_performed"
            ]
        )


if __name__ == "__main__":
    unittest.main()
