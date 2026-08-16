from __future__ import annotations

import copy
import math
import tempfile
from pathlib import Path
import unittest

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.services import multimodal_adjudication_intake
from app.services import multimodal_adjudication_runtime as runtime


CLAIM_ID = "claim-mm-1"
MEDIA_ID = "media-mm-1"
SOURCE_ID = "source-mm-1"
SUBJECT = "club|arsenal"
EVIDENCE_ID = "evidence-mm-1"
URL = "https://example.com/post"
AS_OF = "2026-08-16T18:00:00Z"
RECORDED = "2026-08-16T18:01:00Z"


def model_judgments():
    evaluator_id = "claim-observation-semantic-model"
    evaluator_family = "observation_semantic_model"

    values = {
        "source_role": "publisher",
        "authority_class": "none",
        "reliability_class": "unknown",
        "provenance_class": "attributed_reporting",
        "stance": "supports",
        "independence_status": "unknown",
    }

    return {
        field: [
            {
                "id": f"model:{field}",
                "field": field,
                "value": value,
                "confidence": 0.90,
                "evaluator_id": evaluator_id,
                "evaluator_family": evaluator_family,
                "basis_class": "model_inference",
                "evidence_ids": [EVIDENCE_ID],
                "training_eligible": False,
            }
        ]
        for field, value in values.items()
    }


def base_intake():
    return {
        "version": (
            multimodal_adjudication_intake
            .MULTIMODAL_ADJUDICATION_INTAKE_VERSION
        ),
        "status": "ready",
        "claim_id": CLAIM_ID,
        "media_item_id": MEDIA_ID,
        "subject_key": SUBJECT,
        "source_ids": [SOURCE_ID],
        "aligned_evidence_ids": [EVIDENCE_ID],
        "source_observation_ids": ["observation-mm-1"],
        "authority_matches": [],
        "evidence_analysis_bundle": {
            "version": "evidence-analysis-v5",
        },
        "judgments_by_field": model_judgments(),
        "policy": {
            "multimodal_evidence_remains_unverified": True,
            "model_judgments_are_not_hard_references": True,
            "verified_authority_requires_database_records": True,
            "absence_of_dependency_does_not_establish_independence": True,
            "different_domains_do_not_establish_independence": True,
            "adjudication_not_performed": True,
            "adjudication_state_not_persisted": True,
            "training_eligibility_not_changed_by_model": True,
            "establishes_truth": False,
            "establishes_corroboration": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class MultimodalAdjudicationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.temp_dir.name)
            / "multimodal-adjudication.db"
        )

        initialize_database(
            self.connection_factory,
            SCHEMA,
        )

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id,
                  source_key,
                  display_name,
                  source_type,
                  canonical_domain,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    SOURCE_ID,
                    "publisher|example.com",
                    "Example",
                    "publisher",
                    "example.com",
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    MEDIA_ID,
                    URL,
                    "web",
                    SOURCE_ID,
                    None,
                    "",
                    None,
                    "hash-mm-1",
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id,
                  canonical_key,
                  subject_key,
                  canonical_text,
                  claim_type,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    CLAIM_ID,
                    "multimodal|club|arsenal|runtime",
                    SUBJECT,
                    "Arsenal completed the signing.",
                    "multimodal_candidate",
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.execute(
                """
                INSERT INTO evidence_records (
                  id,
                  evidence_key,
                  evidence_type,
                  subject_key,
                  claim_summary,
                  canonical_url,
                  reference_key,
                  verification_status,
                  published_at,
                  observed_at,
                  recorded_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    EVIDENCE_ID,
                    "evidence-key-mm-1",
                    "multimodal_claim_candidate",
                    SUBJECT,
                    "Arsenal completed the signing.",
                    URL,
                    "candidate:mm-1",
                    "unverified",
                    None,
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.execute(
                """
                INSERT INTO claim_links (
                  id,
                  claim_id,
                  source_observation_id,
                  reporter_observation_id,
                  evidence_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "claim-link-mm-1",
                    CLAIM_ID,
                    None,
                    None,
                    EVIDENCE_ID,
                    "aligned_to",
                    None,
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.commit()

        finally:
            conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def connection_factory(self):
        return connect_database(
            self.db_path
        )

    def execute(
        self,
        intake=None,
        *,
        as_of=AS_OF,
    ):
        return runtime.execute_multimodal_adjudication(
            intake=(
                intake
                if intake is not None
                else base_intake()
            ),
            as_of=as_of,
            recorded_at=None,
            connection_factory=(
                self.connection_factory
            ),
        )

    def count(self, table):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def evidence_status(self, evidence_id=EVIDENCE_ID):
        conn = self.connection_factory()

        try:
            row = conn.execute(
                """
                SELECT verification_status
                FROM evidence_records
                WHERE id = ?
                """,
                (evidence_id,),
            ).fetchone()

            return row[0]
        finally:
            conn.close()

    def seed_hard_authority(
        self,
        *,
        participant_role="subject",
        confidence=0.99,
    ):
        source_evidence = "evidence-source-control"
        participant_evidence = "evidence-claim-participant"
        entity_id = "entity-arsenal"

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id,
                  entity_key,
                  entity_type,
                  sport_key,
                  canonical_name,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    SUBJECT,
                    "club",
                    "football",
                    "Arsenal",
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            for evidence_id, key in (
                (
                    source_evidence,
                    "verified-source-control",
                ),
                (
                    participant_evidence,
                    "verified-claim-participant",
                ),
            ):
                conn.execute(
                    """
                    INSERT INTO evidence_records (
                      id,
                      evidence_key,
                      evidence_type,
                      subject_key,
                      claim_summary,
                      canonical_url,
                      reference_key,
                      verification_status,
                      published_at,
                      observed_at,
                      recorded_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        key,
                        "canonical_fact",
                        SUBJECT,
                        "",
                        "",
                        key,
                        "verified",
                        None,
                        AS_OF,
                        AS_OF,
                        "{}",
                    ),
                )

            conn.execute(
                """
                INSERT INTO verified_source_entity_bindings (
                  id,
                  source_id,
                  entity_id,
                  binding_type,
                  evidence_id,
                  verification_status,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-binding-1",
                    SOURCE_ID,
                    entity_id,
                    "official_account",
                    source_evidence,
                    "verified",
                    confidence,
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.execute(
                """
                INSERT INTO verified_claim_entity_participants (
                  id,
                  claim_id,
                  entity_id,
                  participant_role,
                  evidence_id,
                  verification_status,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "participant-1",
                    CLAIM_ID,
                    entity_id,
                    participant_role,
                    participant_evidence,
                    "verified",
                    confidence,
                    AS_OF,
                    AS_OF,
                    "{}",
                ),
            )

            conn.commit()

        finally:
            conn.close()

        if participant_role in {
            "governing_body",
            "competition",
        }:
            source_role = "official_institution"
            authority_class = "institutional"
        else:
            source_role = "primary_stakeholder"
            authority_class = "direct"

        intake = base_intake()

        intake["authority_matches"] = [
            {
                "source_binding_id": "source-binding-1",
                "source_id": SOURCE_ID,
                "entity_id": entity_id,
                "binding_type": "official_account",
                "source_binding_evidence_id": source_evidence,
                "source_binding_confidence": confidence,
                "source_binding_observed_at": AS_OF,
                "participant_id": "participant-1",
                "participant_role": participant_role,
                "participant_evidence_id": participant_evidence,
                "participant_confidence": confidence,
                "participant_observed_at": AS_OF,
                "resolved_source_role": source_role,
                "resolved_authority_class": authority_class,
                "hard_reference_confidence": confidence,
            }
        ]

        identity = "source-binding-1:participant-1"

        for field, value in (
            (
                "source_role",
                source_role,
            ),
            (
                "authority_class",
                authority_class,
            ),
        ):
            intake["judgments_by_field"][field].append(
                {
                    "id": (
                        "verified-authority:"
                        + CLAIM_ID
                        + ":"
                        + field
                        + ":"
                        + identity
                    ),
                    "field": field,
                    "value": value,
                    "confidence": confidence,
                    "evaluator_id": (
                        "verified-source-claim-entity-match"
                    ),
                    "evaluator_family": (
                        "verified_authority_record"
                    ),
                    "basis_class": (
                        "direct_authority_record"
                    ),
                    "evidence_ids": [
                        participant_evidence,
                        source_evidence,
                    ],
                    "training_eligible": True,
                }
            )

        return intake

    def test_initial_run_persists_one_revision(self):
        result = self.execute()

        self.assertEqual(
            result["status"],
            "persisted",
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )

    def test_initial_trigger_is_initial_evaluation(self):
        result = self.execute()

        self.assertEqual(
            result["trigger_type"],
            "initial_evaluation",
        )

    def test_identical_rerun_is_replayed(self):
        first = self.execute()
        second = self.execute()

        self.assertEqual(
            first["revision_id"],
            second["revision_id"],
        )

        self.assertEqual(
            second["status"],
            "replayed",
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )

    def test_later_as_of_creates_evaluator_refresh_revision(self):
        first = self.execute()

        second = self.execute(
            as_of="2026-08-16T19:00:00Z",
        )

        self.assertNotEqual(
            first["revision_id"],
            second["revision_id"],
        )

        self.assertEqual(
            second["trigger_type"],
            "evaluator_refresh",
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            2,
        )

    def test_multimodal_evidence_remains_unverified(self):
        self.execute()

        self.assertEqual(
            self.evidence_status(),
            "unverified",
        )

    def test_model_judgments_form_one_model_assisted_run(self):
        result = self.execute()

        self.assertEqual(
            result["model_run_count"],
            1,
        )

        self.assertEqual(
            result["hard_reference_run_count"],
            0,
        )

    def test_model_only_fields_do_not_become_auto_gold(self):
        result = self.execute()

        self.assertEqual(
            result["summary"][
                "auto_gold_fields"
            ],
            [],
        )

    def test_result_policy_never_establishes_truth(self):
        result = self.execute()

        self.assertFalse(
            result["policy"][
                "establishes_truth"
            ]
        )

    def test_result_policy_never_establishes_corroboration(self):
        result = self.execute()

        self.assertFalse(
            result["policy"][
                "establishes_corroboration"
            ]
        )

    def test_result_policy_never_establishes_independence(self):
        result = self.execute()

        self.assertFalse(
            result["policy"][
                "establishes_independence"
            ]
        )

    def test_result_policy_never_affects_live_merit(self):
        result = self.execute()

        self.assertFalse(
            result["policy"][
                "affects_live_merit"
            ]
        )

    def test_wrong_intake_version_fails_closed(self):
        intake = base_intake()
        intake["version"] = "wrong"

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_non_ready_intake_fails_closed(self):
        intake = base_intake()
        intake["status"] = "blocked"

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_missing_required_intake_policy_fails_closed(self):
        intake = base_intake()
        intake["policy"][
            "model_judgments_are_not_hard_references"
        ] = False

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_truth_enabling_intake_policy_fails_closed(self):
        intake = base_intake()
        intake["policy"][
            "establishes_truth"
        ] = True

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_empty_aligned_evidence_fails_closed(self):
        intake = base_intake()
        intake["aligned_evidence_ids"] = []

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_missing_claim_fails_before_history_write(self):
        conn = self.connection_factory()

        try:
            conn.execute(
                "DELETE FROM claim_links"
            )
            conn.execute(
                "DELETE FROM intelligence_claims"
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationEvidenceValidationError
        ):
            self.execute()

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            0,
        )

    def test_missing_media_fails_before_history_write(self):
        conn = self.connection_factory()

        try:
            conn.execute(
                "DELETE FROM media_items"
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationEvidenceValidationError
        ):
            self.execute()

    def test_missing_evidence_fails_closed(self):
        conn = self.connection_factory()

        try:
            conn.execute(
                "DELETE FROM claim_links"
            )
            conn.execute(
                "DELETE FROM evidence_records"
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationEvidenceValidationError
        ):
            self.execute()

    def test_missing_aligned_to_link_fails_closed(self):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                UPDATE claim_links
                SET relationship_type = 'observed_in'
                WHERE evidence_id = ?
                """,
                (EVIDENCE_ID,),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationEvidenceValidationError
        ):
            self.execute()

    def test_verified_multimodal_candidate_is_rejected(self):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                UPDATE evidence_records
                SET verification_status = 'verified'
                WHERE id = ?
                """,
                (EVIDENCE_ID,),
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationEvidenceValidationError
        ):
            self.execute()

    def test_unknown_judgment_field_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "outcome_status"
        ] = []

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_judgment_bucket_mismatch_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["field"] = "source_role"

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_duplicate_judgment_id_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["id"] = (
            intake[
                "judgments_by_field"
            ][
                "source_role"
            ][0]["id"]
        )

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_model_hard_reference_basis_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["basis_class"] = (
            "direct_authority_record"
        )

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_model_training_eligibility_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["training_eligible"] = True

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_model_external_evidence_reference_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["evidence_ids"] = [
            "outside-evidence"
        ]

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_model_cannot_establish_independence(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "independence_status"
        ][0]["value"] = "established"

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_boolean_confidence_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["confidence"] = True

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_nonfinite_confidence_is_rejected(self):
        intake = base_intake()
        intake["judgments_by_field"][
            "stance"
        ][0]["confidence"] = math.nan

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_hard_judgment_without_authority_match_is_rejected(self):
        intake = base_intake()

        intake["judgments_by_field"][
            "authority_class"
        ].append({
            "id": (
                "verified-authority:"
                + CLAIM_ID
                + ":authority_class:x:y"
            ),
            "field": "authority_class",
            "value": "direct",
            "confidence": 0.99,
            "evaluator_id": (
                "verified-source-claim-entity-match"
            ),
            "evaluator_family": (
                "verified_authority_record"
            ),
            "basis_class": (
                "direct_authority_record"
            ),
            "evidence_ids": [],
            "training_eligible": True,
        })

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_verified_hard_authority_creates_machine_verified_runs(self):
        intake = self.seed_hard_authority()

        result = self.execute(
            intake
        )

        self.assertEqual(
            result["hard_reference_run_count"],
            2,
        )

    def test_verified_hard_authority_can_auto_gold_authority_class(self):
        intake = self.seed_hard_authority()

        result = self.execute(
            intake
        )

        self.assertIn(
            "authority_class",
            result["summary"][
                "auto_gold_fields"
            ],
        )

        self.assertEqual(
            result["adjudication"][
                "fields"
            ][
                "authority_class"
            ][
                "effective"
            ][
                "value"
            ],
            "direct",
        )

    def test_official_institution_maps_to_institutional_authority(self):
        intake = self.seed_hard_authority(
            participant_role=(
                "governing_body"
            )
        )

        result = self.execute(
            intake
        )

        self.assertEqual(
            result["adjudication"][
                "fields"
            ][
                "authority_class"
            ][
                "effective"
            ][
                "value"
            ],
            "institutional",
        )

    def test_hard_reference_underlying_evidence_must_stay_verified(self):
        intake = self.seed_hard_authority()

        conn = self.connection_factory()

        try:
            conn.execute(
                """
                UPDATE evidence_records
                SET verification_status = 'unverified'
                WHERE id = 'evidence-source-control'
                """
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_hard_reference_confidence_tampering_is_rejected(self):
        intake = self.seed_hard_authority()

        intake["judgments_by_field"][
            "authority_class"
        ][1]["confidence"] = 0.95

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_hard_reference_wrong_source_is_rejected(self):
        intake = self.seed_hard_authority()
        intake["source_ids"] = [
            "different-source"
        ]

        with self.assertRaises(
            runtime.AdjudicationAuthorityValidationError
        ):
            self.execute(intake)

    def test_same_model_evaluator_cannot_vote_twice_on_one_field(self):
        intake = base_intake()

        duplicate = copy.deepcopy(
            intake[
                "judgments_by_field"
            ][
                "stance"
            ][0]
        )

        duplicate["id"] = "model:stance:second"

        intake["judgments_by_field"][
            "stance"
        ].append(
            duplicate
        )

        with self.assertRaises(
            runtime.AdjudicationIntakeValidationError
        ):
            self.execute(intake)

    def test_distinct_model_evaluator_creates_second_run(self):
        intake = base_intake()

        second = copy.deepcopy(
            intake[
                "judgments_by_field"
            ][
                "stance"
            ][0]
        )

        second["id"] = "second-model:stance"
        second["evaluator_id"] = "second-model"
        second["evaluator_family"] = "second-family"

        intake["judgments_by_field"][
            "stance"
        ].append(
            second
        )

        result = self.execute(
            intake
        )

        self.assertEqual(
            result["model_run_count"],
            2,
        )

    def test_latest_revision_matches_returned_revision(self):
        result = self.execute()

        conn = self.connection_factory()

        try:
            row = conn.execute(
                """
                SELECT id
                FROM adjudication_state_revisions
                WHERE claim_id = ?
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
                """,
                (CLAIM_ID,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            row[0],
            result["revision_id"],
        )

    def test_runtime_does_not_create_independence_assertions(self):
        before = self.count(
            "observation_independence_assertions"
        )

        self.execute()

        after = self.count(
            "observation_independence_assertions"
        )

        self.assertEqual(
            before,
            after,
        )

    def test_runtime_does_not_mutate_aligned_evidence_status(self):
        before = self.evidence_status()

        result = self.execute()

        after = self.evidence_status()

        self.assertEqual(
            before,
            after,
        )

        self.assertEqual(
            result[
                "evidence_verification_statuses"
            ][EVIDENCE_ID],
            "unverified",
        )


if __name__ == "__main__":
    unittest.main()
