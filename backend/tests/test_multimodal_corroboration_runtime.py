from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.analysis import adjudication as adjudication_analysis
from app.analysis import multi_evaluator_adjudication
from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)
from app.intelligence.dependencies import (
    record_observation_dependency,
)
from app.intelligence.entities import (
    upsert_canonical_entity,
)
from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)
from app.intelligence.evidence import record_evidence
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)
from app.services import multimodal_adjudication_intake
from app.services import multimodal_adjudication_runtime
from app.services import multimodal_corroboration_runtime as runtime


CLAIM_KEY = (
    "transfer|kepa|chelsea|arsenal|2025"
)
SUBJECT = (
    "transfer|kepa|chelsea|arsenal"
)
NOW = "2026-08-16T12:00:00Z"


class MultimodalCorroborationRuntimeTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )
        self.db_path = (
            Path(self.temp.name)
            / "corroboration.db"
        )

        conn = self.connection_factory()

        try:
            conn.executescript(
                SCHEMA
            )
            conn.commit()
        finally:
            conn.close()

        self.claim = (
            upsert_intelligence_claim(
                canonical_key=CLAIM_KEY,
                subject_key=SUBJECT,
                canonical_text=(
                    "Kepa moves from Chelsea "
                    "to Arsenal."
                ),
                claim_type="transfer",
                seen_at=NOW,
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )
        self.claim_id = (
            self.claim["id"]
        )

        self.sides = []

        specs = [
            {
                "name": "Chelsea",
                "entity_key": (
                    "football|club|chelsea"
                ),
                "role": "origin",
                "url": (
                    "https://www.chelseafc.com/"
                    "en/news/article/kepa-departs"
                ),
            },
            {
                "name": "Arsenal",
                "entity_key": (
                    "football|club|arsenal"
                ),
                "role": "destination",
                "url": (
                    "https://www.arsenal.com/"
                    "news/kepa-signs"
                ),
            },
        ]

        for index, spec in enumerate(
            specs,
            start=1,
        ):
            self.sides.append(
                self.seed_side(
                    index=index,
                    **spec,
                )
            )

    def tearDown(self):
        self.temp.cleanup()

    def connection_factory(self):
        return connect_database(
            self.db_path
        )

    @staticmethod
    def normalize_url(value):
        return (
            str(value or "")
            .strip()
            .lower()
        )

    def domain_resolver(self, value):
        return source_domain_for_url(
            value,
            normalize_url=(
                self.normalize_url
            ),
        )

    def count(self, table):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) "
                    f"FROM {table}"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def rows(
        self,
        sql,
        params=(),
    ):
        conn = self.connection_factory()

        try:
            return [
                dict(row)
                for row in conn.execute(
                    sql,
                    params,
                ).fetchall()
            ]
        finally:
            conn.close()

    def verified_evidence(
        self,
        reference_key,
        subject_key,
    ):
        return record_evidence(
            evidence_type=(
                "machine_reference"
            ),
            subject_key=subject_key,
            observed_at=NOW,
            reference_key=(
                reference_key
            ),
            verification_status=(
                "verified"
            ),
            recorded_at=(
                "2026-08-16T12:00:01Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )["evidence"]

    def seed_revision(
        self,
        *,
        revision_id,
        claim_id,
        adjudication,
        recorded_at,
    ):
        revision = {
            "revision_id": (
                revision_id
            ),
            "claim_id": claim_id,
            "adjudication_sha256": (
                "sha-" + revision_id
            ),
            "adjudication": (
                copy.deepcopy(
                    adjudication
                )
            ),
        }

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO adjudication_state_revisions (
                  id,
                  claim_id,
                  state_version,
                  adjudication_version,
                  adjudication_sha256,
                  as_of,
                  previous_revision_id,
                  trigger_type,
                  trigger_evidence_ids_json,
                  revision_json,
                  recorded_at
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?,
                  NULL, ?, '[]', ?, ?
                )
                """,
                (
                    revision_id,
                    claim_id,
                    (
                        "automated-"
                        "adjudication-state-v1"
                    ),
                    (
                        multi_evaluator_adjudication
                        .MULTI_EVALUATOR_ADJUDICATION_VERSION
                    ),
                    (
                        revision[
                            "adjudication_sha256"
                        ]
                    ),
                    NOW,
                    "evaluator_refresh",
                    json.dumps(
                        revision,
                        sort_keys=True,
                    ),
                    recorded_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return revision

    def persist_adjudication_variant(
        self,
        result,
        *,
        suffix,
    ):
        variant = copy.deepcopy(
            result
        )

        revision_id = (
            str(
                variant[
                    "revision_id"
                ]
            )
            + "-"
            + str(
                suffix
            )
        )

        revision = (
            self.seed_revision(
                revision_id=(
                    revision_id
                ),
                claim_id=(
                    variant[
                        "claim_id"
                    ]
                ),
                adjudication=(
                    variant[
                        "adjudication"
                    ]
                ),
                recorded_at=(
                    "2026-08-16T12:15:00Z"
                ),
            )
        )

        variant[
            "revision_id"
        ] = revision_id

        variant[
            "revision"
        ] = revision

        return variant

    def seed_side(
        self,
        *,
        index,
        name,
        entity_key,
        role,
        url,
    ):
        source = (
            upsert_intelligence_source(
                url=url,
                display_name=name,
                source_type="publisher",
                seen_at=NOW,
                domain_resolver=(
                    self.domain_resolver
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        entity = (
            upsert_canonical_entity(
                entity_key=entity_key,
                entity_type="club",
                canonical_name=name,
                sport_key="football",
                seen_at=NOW,
                connection_factory=(
                    self.connection_factory
                ),
            )["entity"]
        )

        binding_evidence = (
            self.verified_evidence(
                f"binding-{index}",
                (
                    "binding|"
                    + source["id"]
                    + "|"
                    + entity["id"]
                ),
            )
        )

        participant_evidence = (
            self.verified_evidence(
                f"participant-{index}",
                (
                    "participant|"
                    + self.claim_id
                    + "|"
                    + entity["id"]
                ),
            )
        )

        record_verified_source_entity_binding(
            source_id=source["id"],
            entity_id=entity["id"],
            binding_type="official_site",
            evidence_id=(
                binding_evidence["id"]
            ),
            confidence=0.99,
            observed_at=NOW,
            recorded_at=(
                "2026-08-16T12:00:02Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        record_verified_claim_entity_participant(
            claim_id=self.claim_id,
            entity_id=entity["id"],
            participant_role=role,
            evidence_id=(
                participant_evidence["id"]
            ),
            confidence=0.99,
            observed_at=NOW,
            recorded_at=(
                "2026-08-16T12:00:03Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        media_id = (
            f"media-{index}"
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO media_items (
                  id,
                  canonical_url,
                  mode,
                  source_id,
                  reporter_id,
                  title,
                  published_at,
                  latest_content_hash,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (
                  ?, ?, 'social', ?, NULL,
                  ?, ?, ?, ?, ?, '{}'
                )
                """,
                (
                    media_id,
                    url,
                    source["id"],
                    name + " announcement",
                    NOW,
                    f"hash-{index}",
                    NOW,
                    NOW,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        multimodal = record_evidence(
            evidence_type=(
                "multimodal_claim_candidate"
            ),
            subject_key=SUBJECT,
            claim_summary=(
                self.claim[
                    "canonical_text"
                ]
            ),
            canonical_url=url,
            reference_key=(
                f"candidate-{index}"
            ),
            verification_status=(
                "unverified"
            ),
            observed_at=NOW,
            recorded_at=(
                f"2026-08-16T12:0{index}:01Z"
            ),
            normalize_url=(
                self.normalize_url
            ),
            connection_factory=(
                self.connection_factory
            ),
        )["evidence"]

        record_claim_link(
            claim_id=self.claim_id,
            evidence_id=multimodal["id"],
            relationship_type="aligned_to",
            confidence=None,
            observed_at=NOW,
            recorded_at=(
                f"2026-08-16T12:0{index}:02Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        observation = (
            record_source_observation(
                source_id=source["id"],
                media_item_id=media_id,
                subject_key=SUBJECT,
                observation_type=(
                    "multimodal_claim_candidate"
                ),
                status="unresolved",
                claim_summary="",
                provenance_url=url,
                confidence=None,
                observed_at=(
                    f"2026-08-16T12:0{index}:00Z"
                ),
                recorded_at=(
                    f"2026-08-16T12:0{index}:01Z"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )["observation"]
        )

        record_claim_link(
            claim_id=self.claim_id,
            source_observation_id=(
                observation["id"]
            ),
            relationship_type="observed_in",
            confidence=None,
            observed_at=(
                observation["observed_at"]
            ),
            recorded_at=(
                f"2026-08-16T12:0{index}:02Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        judgment = {
            "id": (
                f"stance-{index}"
            ),
            "field": "stance",
            "value": "supports",
            "confidence": 0.92,
            "evaluator_id": (
                "semantic-model-v1"
            ),
            "evaluator_family": (
                "semantic_model"
            ),
            "basis_class": (
                "model_inference"
            ),
            "evidence_ids": [
                multimodal["id"]
            ],
            "training_eligible": False,
        }

        intake = {
            "version": (
                multimodal_adjudication_intake
                .MULTIMODAL_ADJUDICATION_INTAKE_VERSION
            ),
            "status": "ready",
            "claim_id": self.claim_id,
            "media_item_id": media_id,
            "aligned_evidence_ids": [
                multimodal["id"]
            ],
            "source_observation_ids": [
                observation["id"]
            ],
            "judgments_by_field": {
                "stance": [
                    copy.deepcopy(
                        judgment
                    )
                ]
            },
            "policy": {
                "multimodal_evidence_remains_unverified":
                    True,
                "model_judgments_are_not_hard_references":
                    True,
                "verified_authority_requires_database_records":
                    True,
                "adjudication_not_performed":
                    True,
                "adjudication_state_not_persisted":
                    True,
                "establishes_truth":
                    False,
                "establishes_corroboration":
                    False,
                "establishes_independence":
                    False,
                "affects_live_merit":
                    False,
            },
        }

        adjudicated_judgment = {
            key: copy.deepcopy(
                value
            )
            for key, value
            in judgment.items()
            if key not in {
                "field",
                "training_eligible",
            }
        }

        adjudication = {
            "version": (
                multi_evaluator_adjudication
                .MULTI_EVALUATOR_ADJUDICATION_VERSION
            ),
            "claim_id": self.claim_id,
            "fields": {
                "stance": {
                    "judgments": [
                        adjudicated_judgment
                    ],
                },
            },
        }

        revision_id = (
            f"revision-{index}"
        )

        revision = self.seed_revision(
            revision_id=revision_id,
            claim_id=self.claim_id,
            adjudication=adjudication,
            recorded_at=(
                f"2026-08-16T12:0{index}:03Z"
            ),
        )

        result = {
            "version": (
                multimodal_adjudication_runtime
                .MULTIMODAL_ADJUDICATION_RUNTIME_VERSION
            ),
            "status": "persisted",
            "claim_id": self.claim_id,
            "media_item_id": media_id,
            "revision_id": revision_id,
            "revision": revision,
            "adjudication": (
                adjudication
            ),
            "policy": {
                "intake_consumed": True,
                "multimodal_evidence_remains_unverified":
                    True,
                "model_judgments_are_model_assisted":
                    True,
                "hard_authority_revalidated_against_database":
                    True,
                "append_only_history": True,
                "linear_revision_chain": True,
                "idempotent_replay": True,
                "evidence_verification_unchanged":
                    True,
                "training_performed": False,
                "establishes_truth": False,
                "establishes_corroboration":
                    False,
                "establishes_independence":
                    False,
                "affects_live_merit": False,
            },
        }

        return {
            "source": source,
            "entity": entity,
            "role": role,
            "media_id": media_id,
            "evidence": multimodal,
            "observation": observation,
            "intake": intake,
            "adjudication": result,
        }

    def execute(
        self,
        *,
        left_intake=None,
        right_intake=None,
        left_adjudication=None,
        right_adjudication=None,
        verifier=None,
    ):
        kwargs = {}

        if verifier is not None:
            kwargs[
                "independence_verifier"
            ] = verifier

        return (
            runtime
            .execute_multimodal_corroboration(
                claim_id=self.claim_id,
                left_intake=(
                    left_intake
                    or self.sides[0][
                        "intake"
                    ]
                ),
                right_intake=(
                    right_intake
                    or self.sides[1][
                        "intake"
                    ]
                ),
                left_adjudication=(
                    left_adjudication
                    or self.sides[0][
                        "adjudication"
                    ]
                ),
                right_adjudication=(
                    right_adjudication
                    or self.sides[1][
                        "adjudication"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-16T12:20:00Z"
                ),
                **kwargs,
            )
        )

    def support_link_count(self):
        return len(
            self.rows(
                """
                SELECT *
                FROM claim_links
                WHERE claim_id = ?
                  AND relationship_type = 'supports'
                """,
                (
                    self.claim_id,
                ),
            )
        )

    def multimodal_statuses(self):
        return [
            row[
                "verification_status"
            ]
            for row in self.rows(
                """
                SELECT verification_status
                FROM evidence_records
                WHERE evidence_type =
                  'multimodal_claim_candidate'
                ORDER BY id
                """
            )
        ]

    def test_success_certifies_direct_stakeholder_corroboration(
        self,
    ):
        result = self.execute()

        self.assertEqual(
            result["version"],
            runtime
            .MULTIMODAL_CORROBORATION_RUNTIME_VERSION,
        )
        self.assertEqual(
            result["status"],
            (
                "verified_direct_"
                "stakeholder_corroboration"
            ),
        )
        self.assertTrue(
            result[
                "independent_support_established"
            ]
        )
        self.assertTrue(
            result[
                "corroboration_established"
            ]
        )

    def test_success_materializes_two_support_edges(
        self,
    ):
        result = self.execute()

        self.assertEqual(
            result["support_link_count"],
            2,
        )
        self.assertEqual(
            self.support_link_count(),
            2,
        )

    def test_success_persists_verified_independence_assertion(
        self,
    ):
        self.execute()

        rows = self.rows(
            """
            SELECT *
            FROM observation_independence_assertions
            """
        )

        self.assertEqual(
            len(rows),
            1,
        )
        self.assertEqual(
            rows[0][
                "verification_status"
            ],
            "verified",
        )

    def test_success_persists_verified_independence_evidence(
        self,
    ):
        self.execute()

        rows = self.rows(
            """
            SELECT *
            FROM evidence_records
            WHERE evidence_type =
              'direct_stakeholder_independence_reference'
            """
        )

        self.assertEqual(
            len(rows),
            1,
        )
        self.assertEqual(
            rows[0][
                "verification_status"
            ],
            "verified",
        )

    def test_multimodal_candidate_evidence_stays_unverified(
        self,
    ):
        self.execute()

        self.assertEqual(
            self.multimodal_statuses(),
            [
                "unverified",
                "unverified",
            ],
        )

    def test_idempotent_rerun_does_not_duplicate_graph(
        self,
    ):
        first = self.execute()
        counts = {
            "support": (
                self.support_link_count()
            ),
            "assertions": (
                self.count(
                    "observation_independence_assertions"
                )
            ),
            "evidence": len(
                self.rows(
                    """
                    SELECT *
                    FROM evidence_records
                    WHERE evidence_type =
                      'direct_stakeholder_independence_reference'
                    """
                )
            ),
        }

        second = self.execute()

        self.assertTrue(
            first[
                "corroboration_established"
            ]
        )
        self.assertTrue(
            second[
                "corroboration_established"
            ]
        )
        self.assertEqual(
            counts["support"],
            self.support_link_count(),
        )
        self.assertEqual(
            counts["assertions"],
            self.count(
                "observation_independence_assertions"
            ),
        )
        self.assertEqual(
            counts["evidence"],
            len(
                self.rows(
                    """
                    SELECT *
                    FROM evidence_records
                    WHERE evidence_type =
                      'direct_stakeholder_independence_reference'
                    """
                )
            ),
        )

    def test_low_confidence_stance_does_not_create_support(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "confidence"
        ] = 0.70

        adjudication = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        adjudication[
            "adjudication"
        ][
            "fields"
        ][
            "stance"
        ][
            "judgments"
        ][0][
            "confidence"
        ] = 0.70

        adjudication = (
            self.persist_adjudication_variant(
                adjudication,
                suffix="low-confidence",
            )
        )

        result = self.execute(
            left_intake=left,
            left_adjudication=(
                adjudication
            ),
        )

        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )
        self.assertEqual(
            self.support_link_count(),
            1,
        )

    def test_non_supporting_stance_does_not_certify(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "value"
        ] = "contradicts"

        adjudication = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        adjudication[
            "adjudication"
        ][
            "fields"
        ][
            "stance"
        ][
            "judgments"
        ][0][
            "value"
        ] = "contradicts"

        adjudication = (
            self.persist_adjudication_variant(
                adjudication,
                suffix="non-supporting",
            )
        )

        result = self.execute(
            left_intake=left,
            left_adjudication=(
                adjudication
            ),
        )

        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )
        self.assertEqual(
            self.support_link_count(),
            1,
        )

    def test_stance_judgment_must_match_adjudicated_row(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )

        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "confidence"
        ] = 0.99

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_intake=left
            )

    def test_stance_evidence_must_remain_aligned(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "evidence_ids"
        ] = [
            "external-evidence"
        ]

        adjudication = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        adjudication[
            "adjudication"
        ][
            "fields"
        ][
            "stance"
        ][
            "judgments"
        ][0][
            "evidence_ids"
        ] = [
            "external-evidence"
        ]

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_intake=left,
                left_adjudication=(
                    adjudication
                ),
            )

    def test_model_stance_cannot_be_training_eligible(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "training_eligible"
        ] = True

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_model_stance_cannot_claim_hard_basis(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "basis_class"
        ] = (
            "direct_authority_record"
        )

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_boolean_stance_confidence_is_rejected(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "confidence"
        ] = True

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_nonfinite_stance_confidence_is_rejected(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "confidence"
        ] = float("nan")

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_wrong_intake_version_fails_closed(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left["version"] = "wrong"

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_truth_enabling_intake_fails_closed(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left["policy"][
            "establishes_truth"
        ] = True

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_intake=left
            )

    def test_merit_enabling_adjudication_fails_closed(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        left["policy"][
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                left_adjudication=left
            )

    def test_missing_revision_fails_before_writes(
        self,
    ):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                DELETE FROM adjudication_state_revisions
                WHERE id = ?
                """,
                (
                    self.sides[0][
                        "adjudication"
                    ][
                        "revision_id"
                    ],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute()

        self.assertEqual(
            self.support_link_count(),
            0,
        )

    def test_revision_payload_mismatch_fails_before_writes(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        left["revision"][
            "adjudication_sha256"
        ] = "tampered"

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_adjudication=left
            )

        self.assertEqual(
            self.support_link_count(),
            0,
        )

    def test_aligned_evidence_must_still_exist(
        self,
    ):
        evidence_id = (
            self.sides[0][
                "evidence"
            ][
                "id"
            ]
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                DELETE FROM claim_links
                WHERE evidence_id = ?
                """,
                (
                    evidence_id,
                ),
            )
            conn.execute(
                """
                DELETE FROM evidence_records
                WHERE id = ?
                """,
                (
                    evidence_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute()

    def test_aligned_multimodal_evidence_must_remain_unverified(
        self,
    ):
        evidence_id = (
            self.sides[0][
                "evidence"
            ][
                "id"
            ]
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                UPDATE evidence_records
                SET verification_status = 'verified'
                WHERE id = ?
                """,
                (
                    evidence_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute()

    def test_aligned_to_link_must_still_exist(
        self,
    ):
        evidence_id = (
            self.sides[0][
                "evidence"
            ][
                "id"
            ]
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                DELETE FROM claim_links
                WHERE evidence_id = ?
                  AND relationship_type = 'aligned_to'
                """,
                (
                    evidence_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute()

    def test_missing_observed_in_link_fails_closed(
        self,
    ):
        observation_id = (
            self.sides[0][
                "observation"
            ][
                "id"
            ]
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                DELETE FROM claim_links
                WHERE source_observation_id = ?
                  AND relationship_type = 'observed_in'
                """,
                (
                    observation_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute()

    def test_same_media_item_is_rejected(
        self,
    ):
        right_intake = copy.deepcopy(
            self.sides[1]["intake"]
        )
        right_intake[
            "media_item_id"
        ] = (
            self.sides[0][
                "media_id"
            ]
        )

        right_adjudication = copy.deepcopy(
            self.sides[1][
                "adjudication"
            ]
        )
        right_adjudication[
            "media_item_id"
        ] = right_intake[
            "media_item_id"
        ]

        with self.assertRaises(
            runtime
            .CorroborationInputError
        ):
            self.execute(
                right_intake=right_intake,
                right_adjudication=(
                    right_adjudication
                ),
            )

    def test_recorded_cross_dependency_blocks_independence(
        self,
    ):
        left = self.sides[0][
            "observation"
        ]
        right = self.sides[1][
            "observation"
        ]

        record_observation_dependency(
            relationship_type=(
                "derived_from"
            ),
            observed_at=NOW,
            confidence=0.99,
            downstream_source_observation_id=(
                right["id"]
            ),
            upstream_source_observation_id=(
                left["id"]
            ),
            recorded_at=(
                "2026-08-16T12:10:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        result = self.execute()

        self.assertEqual(
            result["status"],
            "recorded_dependency_conflict",
        )
        self.assertFalse(
            result[
                "independent_support_established"
            ]
        )
        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )
        self.assertEqual(
            self.count(
                "observation_independence_assertions"
            ),
            0,
        )

    def test_missing_direct_authority_blocks_independence(
        self,
    ):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                DELETE FROM verified_source_entity_bindings
                WHERE source_id = ?
                """,
                (
                    self.sides[1][
                        "source"
                    ][
                        "id"
                    ],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        result = self.execute()

        self.assertFalse(
            result[
                "independent_support_established"
            ]
        )
        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )

    def test_wrong_transfer_role_pair_blocks_independence(
        self,
    ):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                UPDATE verified_claim_entity_participants
                SET participant_role = 'counterparty'
                WHERE entity_id = ?
                """,
                (
                    self.sides[0][
                        "entity"
                    ][
                        "id"
                    ],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        result = self.execute()

        self.assertFalse(
            result[
                "independent_support_established"
            ]
        )
        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )

    def test_support_edge_metadata_does_not_claim_truth(
        self,
    ):
        self.execute()

        rows = self.rows(
            """
            SELECT metadata_json
            FROM claim_links
            WHERE relationship_type = 'supports'
            """
        )

        self.assertEqual(
            len(rows),
            2,
        )

        for row in rows:
            metadata = json.loads(
                row["metadata_json"]
            )

            self.assertFalse(
                metadata[
                    "establishes_truth"
                ]
            )
            self.assertFalse(
                metadata[
                    "establishes_independence"
                ]
            )
            self.assertFalse(
                metadata[
                    "affects_live_merit"
                ]
            )

    def test_support_confidence_uses_semantic_confidence(
        self,
    ):
        self.execute()

        rows = self.rows(
            """
            SELECT confidence
            FROM claim_links
            WHERE relationship_type = 'supports'
            ORDER BY id
            """
        )

        self.assertEqual(
            [row["confidence"] for row in rows],
            [0.92, 0.92],
        )

    def test_result_never_claims_truth_or_merit(
        self,
    ):
        result = self.execute()

        self.assertFalse(
            result["policy"][
                "establishes_truth"
            ]
        )
        self.assertFalse(
            result["policy"][
                "live_merit_evaluated"
            ]
        )
        self.assertFalse(
            result["policy"][
                "affects_live_merit"
            ]
        )

    def test_result_marks_model_as_not_independence_proof(
        self,
    ):
        result = self.execute()

        self.assertTrue(
            result["policy"][
                "model_output_is_not_independence_proof"
            ]
        )

    def test_support_write_failure_rolls_back_all_support_edges(
        self,
    ):
        original = (
            runtime
            .claim_intelligence
            .record_claim_link
        )
        calls = {
            "count": 0,
        }

        def failing(*args, **kwargs):
            calls["count"] += 1

            if calls["count"] == 2:
                raise RuntimeError(
                    "boom"
                )

            return original(
                *args,
                **kwargs,
            )

        with mock.patch.object(
            runtime
            .claim_intelligence,
            "record_claim_link",
            side_effect=failing,
        ):
            with self.assertRaises(
                RuntimeError
            ):
                self.execute()

        self.assertEqual(
            self.support_link_count(),
            0,
        )
        self.assertEqual(
            self.count(
                "observation_independence_assertions"
            ),
            0,
        )

    def test_verifier_exception_rolls_back_support_edges(
        self,
    ):
        def failing_verifier(
            **kwargs,
        ):
            raise RuntimeError(
                "verifier boom"
            )

        with self.assertRaises(
            RuntimeError
        ):
            self.execute(
                verifier=(
                    failing_verifier
                )
            )

        self.assertEqual(
            self.support_link_count(),
            0,
        )

    def test_invalid_verifier_result_rolls_back_support_edges(
        self,
    ):
        def invalid_verifier(
            **kwargs,
        ):
            return {
                "version": "wrong",
                "persisted": False,
            }

        with self.assertRaises(
            runtime
            .CorroborationIntegrityError
        ):
            self.execute(
                verifier=(
                    invalid_verifier
                )
            )

        self.assertEqual(
            self.support_link_count(),
            0,
        )

    def test_intake_claim_mismatch_is_rejected(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        left["claim_id"] = "other"

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_intake=left
            )

    def test_adjudication_media_mismatch_is_rejected(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        left["media_item_id"] = "other"

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_adjudication=left
            )

    def test_adjudication_revision_identity_mismatch_is_rejected(
        self,
    ):
        left = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )
        left["revision"][
            "revision_id"
        ] = "other"

        with self.assertRaises(
            runtime
            .CorroborationBindingError
        ):
            self.execute(
                left_adjudication=left
            )

    def test_stance_threshold_uses_existing_adjudication_threshold(
        self,
    ):
        self.assertEqual(
            adjudication_analysis
            .HIGH_CONFIDENCE_THRESHOLD,
            0.85,
        )

        left = copy.deepcopy(
            self.sides[0]["intake"]
        )
        adjudication = copy.deepcopy(
            self.sides[0][
                "adjudication"
            ]
        )

        threshold = (
            adjudication_analysis
            .HIGH_CONFIDENCE_THRESHOLD
        )

        left[
            "judgments_by_field"
        ][
            "stance"
        ][0][
            "confidence"
        ] = threshold

        adjudication[
            "adjudication"
        ][
            "fields"
        ][
            "stance"
        ][
            "judgments"
        ][0][
            "confidence"
        ] = threshold

        adjudication = (
            self.persist_adjudication_variant(
                adjudication,
                suffix="threshold",
            )
        )

        result = self.execute(
            left_intake=left,
            left_adjudication=(
                adjudication
            ),
        )

        self.assertTrue(
            result[
                "corroboration_established"
            ]
        )


if __name__ == "__main__":
    unittest.main()
