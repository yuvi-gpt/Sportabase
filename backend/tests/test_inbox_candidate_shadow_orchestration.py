from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.routes import inbox_candidate_shadow_admin
from app.services import inbox_candidate_discovery
from app.services import inbox_candidate_shadow_orchestration
from app.services import multimodal_inbox_shadow_orchestration


class CandidateShadowServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.temp_dir.name)
            / "candidate-shadow.db"
        )

        conn = self.connection_factory()

        try:
            conn.executescript(
                """
                CREATE TABLE canonical_entities (
                  id TEXT PRIMARY KEY,
                  entity_key TEXT NOT NULL,
                  entity_type TEXT NOT NULL,
                  sport_key TEXT NOT NULL DEFAULT '',
                  canonical_name TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id,
                  entity_key,
                  entity_type,
                  sport_key,
                  canonical_name
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "entity-1",
                    "football|club|arsenal",
                    "club",
                    "football",
                    "Arsenal",
                ),
            )

            conn.commit()
        finally:
            conn.close()

        self.discovery_calls = []
        self.shadow_calls = []

    def tearDown(self):
        self.temp_dir.cleanup()

    def connection_factory(self):
        conn = sqlite3.connect(
            self.db_path
        )
        conn.row_factory = sqlite3.Row
        return conn

    def entity_candidate(
        self,
        entity_id="entity-1",
    ):
        return {
            "id": entity_id,
            "entity_key": (
                "football|club|arsenal"
            ),
            "entity_type": "club",
            "sport_key": "football",
            "canonical_name": "Arsenal",
            "matching_mentions": [],
            "policy": {
                "exact_text_candidate_only": True,
                "alias_match_does_not_verify_subject": True,
                "alias_match_does_not_establish_authority": True,
            },
        }

    def discovery_policy(self):
        return {
            "read_only_discovery": True,
            "inbox_records_remain_untrusted": True,
            "anchor_capture_text_is_not_a_verified_claim": True,
            "entity_matching_is_exact_alias_or_canonical_name_only": True,
            "entity_candidates_do_not_verify_subject": True,
            "deterministic_score_is_ranking_only": True,
            "semantic_same_claim_is_candidate_only": True,
            "semantic_stance_does_not_establish_truth": True,
            "semantic_dependency_does_not_establish_independence": True,
            "candidate_discovery_does_not_establish_corroboration": True,
            "manual_or_later_verified_selection_required": True,
            "creates_entity": False,
            "creates_alias": False,
            "creates_source": False,
            "creates_media_item": False,
            "creates_story": False,
            "creates_claim": False,
            "creates_observation": False,
            "creates_evidence": False,
            "creates_verified_binding": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        }

    def candidate_policy(self):
        return {
            "candidate_only": True,
            "same_story_not_established": True,
            "same_claim_not_established": True,
            "subject_not_verified": True,
            "independence_not_established": True,
            "corroboration_not_established": True,
            "affects_live_merit": False,
        }

    def discovery(self, **overrides):
        candidate = {
            "capture_record_id": "candidate-1",
            "canonical_url": (
                "https://example.com/candidate"
            ),
            "platform": "web",
            "platform_surface": "article",
            "observed_at": "2026-08-17T10:01:00Z",
            "title": "Candidate",
            "candidate_score": 0.91,
            "signals": {
                "lexical_score": 0.8,
                "entity_score": 1.0,
                "time_score": 0.9,
                "time_distance_hours": 1.0,
                "shared_token_count": 5,
                "shared_tokens": [
                    "arsenal",
                    "transfer",
                ],
                "shared_entity_ids": [
                    "entity-1"
                ],
                "identical_normalized_content": False,
            },
            "entity_candidates": [
                self.entity_candidate()
            ],
            "candidate_reasons": [
                "shared_text_tokens",
                "shared_exact_entity_candidates",
            ],
            "semantic": {
                "status": "not_assessed",
                "assessment": None,
            },
            "policy": self.candidate_policy(),
        }

        result = {
            "version": (
                inbox_candidate_discovery
                .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
            ),
            "status": "candidates_available",
            "anchor_capture_record_id": "anchor-1",
            "anchor": {
                "canonical_url": (
                    "https://example.com/anchor"
                ),
                "platform": "web",
                "platform_surface": "article",
                "observed_at": "2026-08-17T10:00:00Z",
                "title": "Anchor",
                "entity_candidates": [
                    self.entity_candidate()
                ],
            },
            "pair_candidates": [candidate],
            "load_failures": [],
            "counts": {},
            "policy": self.discovery_policy(),
        }

        result.update(overrides)
        return result

    def shadow_policy(self):
        return {
            "admin_endpoint_uses_stored_capture_ids_only": True,
            "raw_capture_not_accepted_by_admin_endpoint": True,
            "inbox_records_remain_untrusted": True,
            "capture_integrity_rechecked_before_orchestration": True,
            "inbox_lookup_is_read_only": True,
            "subject_is_admin_supplied": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
            "evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_independence": True,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        }

    def shadow(self, **overrides):
        result = {
            "version": (
                multimodal_inbox_shadow_orchestration
                .MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
            ),
            "status": "completed_shadow",
            "claim_id": "claim-1",
            "left_capture_record_id": "anchor-1",
            "right_capture_record_id": "candidate-1",
            "orchestration": {
                "status": "completed_shadow"
            },
            "policy": self.shadow_policy(),
        }
        result.update(overrides)
        return result

    def discovery_runner(self, **kwargs):
        self.discovery_calls.append(kwargs)
        return self.discovery()

    def shadow_runner(self, **kwargs):
        self.shadow_calls.append(kwargs)
        return self.shadow()

    def run_service(
        self,
        *,
        discovery_runner=None,
        shadow_runner=None,
        **overrides,
    ):
        kwargs = {
            "anchor_capture_record_id": "anchor-1",
            "candidate_capture_record_id": "candidate-1",
            "subject_entity_id": "entity-1",
            "legacy_score": {"total": 72},
            "target_claim_id": "",
            "scan_limit": 100,
            "max_candidates": 12,
            "connection_factory": self.connection_factory,
            "gemini_client": object(),
            "gemini_client_key": "client-1",
            "gemini_generator": lambda **_kwargs: None,
            "discovery_runner": (
                discovery_runner
                or self.discovery_runner
            ),
            "shadow_runner": (
                shadow_runner
                or self.shadow_runner
            ),
        }
        kwargs.update(overrides)

        return (
            inbox_candidate_shadow_orchestration
            .execute_multimodal_inbox_candidate_shadow(
                **kwargs
            )
        )

    def test_version(self):
        result = self.run_service()
        self.assertEqual(
            result["version"],
            "multimodal-inbox-candidate-shadow-v1",
        )

    def test_completed_shadow_status(self):
        result = self.run_service()
        self.assertEqual(
            result["status"],
            "completed_shadow",
        )
        self.assertEqual(
            result["claim_id"],
            "claim-1",
        )

    def test_pair_scope_is_preserved(self):
        result = self.run_service()
        self.assertEqual(
            result["anchor_capture_record_id"],
            "anchor-1",
        )
        self.assertEqual(
            result["candidate_capture_record_id"],
            "candidate-1",
        )

    def test_subject_descriptor_is_loaded_server_side(self):
        result = self.run_service()
        self.assertEqual(
            result["subject"],
            {
                "entity_key": "football|club|arsenal",
                "entity_type": "club",
                "canonical_name": "Arsenal",
                "sport_key": "football",
            },
        )

    def test_subject_entity_id_is_preserved(self):
        result = self.run_service()
        self.assertEqual(
            result["subject_entity_id"],
            "entity-1",
        )

    def test_discovery_gate_exposes_ranking_only(self):
        result = self.run_service()
        gate = result["discovery_gate"]
        self.assertEqual(
            gate["candidate_score"],
            0.91,
        )
        self.assertEqual(
            gate["shared_entity_ids"],
            ["entity-1"],
        )
        self.assertIn(
            "shared_text_tokens",
            gate["candidate_reasons"],
        )

    def test_discovery_semantics_are_disabled_for_gate(self):
        self.run_service()
        call = self.discovery_calls[0]
        self.assertEqual(
            call["semantic_assessments"],
            0,
        )
        self.assertIsNone(
            call["gemini_client"]
        )
        self.assertIsNone(
            call["gemini_generator"]
        )

    def test_discovery_receives_bounded_scan_parameters(self):
        self.run_service(
            scan_limit=77,
            max_candidates=9,
        )
        call = self.discovery_calls[0]
        self.assertEqual(
            call["scan_limit"],
            77,
        )
        self.assertEqual(
            call["max_candidates"],
            9,
        )

    def test_shadow_receives_server_loaded_subject(self):
        self.run_service()
        subject = self.shadow_calls[0][
            "subject"
        ]
        self.assertEqual(
            subject["canonical_name"],
            "Arsenal",
        )
        self.assertNotIn(
            "id",
            subject,
        )

    def test_shadow_receives_selected_pair(self):
        self.run_service()
        call = self.shadow_calls[0]
        self.assertEqual(
            call["left_capture_record_id"],
            "anchor-1",
        )
        self.assertEqual(
            call["right_capture_record_id"],
            "candidate-1",
        )

    def test_shadow_receives_legacy_score(self):
        score = {"total": 61}
        self.run_service(
            legacy_score=score
        )
        self.assertEqual(
            self.shadow_calls[0]["legacy_score"],
            score,
        )

    def test_client_key_is_normalized(self):
        self.run_service(
            gemini_client_key="   "
        )
        self.assertEqual(
            self.shadow_calls[0][
                "gemini_client_key"
            ],
            "anonymous",
        )

    def test_target_claim_id_is_normalized(self):
        self.run_service(
            target_claim_id="  claim-x  "
        )
        self.assertEqual(
            self.shadow_calls[0][
                "target_claim_id"
            ],
            "claim-x",
        )

    def test_missing_anchor_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                anchor_capture_record_id=""
            )

    def test_missing_candidate_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                candidate_capture_record_id=""
            )

    def test_same_capture_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                candidate_capture_record_id=(
                    "anchor-1"
                )
            )

    def test_missing_subject_id_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                subject_entity_id=""
            )

    def test_long_capture_id_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                anchor_capture_record_id=(
                    "x" * 257
                )
            )

    def test_long_subject_id_is_rejected(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                subject_entity_id=(
                    "x" * 257
                )
            )

    def test_scan_limit_is_bounded(self):
        for value in (0, 501, True):
            with self.subTest(value=value):
                with self.assertRaises(
                    inbox_candidate_shadow_orchestration
                    .MultimodalInboxCandidateShadowInputError
                ):
                    self.run_service(
                        scan_limit=value
                    )

    def test_candidate_limit_is_bounded(self):
        for value in (0, 51, True):
            with self.subTest(value=value):
                with self.assertRaises(
                    inbox_candidate_shadow_orchestration
                    .MultimodalInboxCandidateShadowInputError
                ):
                    self.run_service(
                        max_candidates=value
                    )

    def test_legacy_score_must_be_mapping(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                legacy_score=[]
            )

    def test_connection_factory_is_required(self):
        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                connection_factory=None
            )

    def test_selected_candidate_must_be_current(self):
        def discovery(**_kwargs):
            return self.discovery(
                pair_candidates=[]
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowDiscoveryError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_duplicate_selected_candidate_fails_integrity(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result["pair_candidates"].append(
                dict(
                    result[
                        "pair_candidates"
                    ][0]
                )
            )
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_version_is_rechecked(self):
        def discovery(**_kwargs):
            return self.discovery(
                version="wrong"
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_anchor_scope_is_rechecked(self):
        def discovery(**_kwargs):
            return self.discovery(
                anchor_capture_record_id=(
                    "other"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_status_is_rechecked(self):
        def discovery(**_kwargs):
            return self.discovery(
                status="trusted"
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_policy_is_required(self):
        def discovery(**_kwargs):
            return self.discovery(
                policy={}
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_forbidden_policy_fails(self):
        def discovery(**_kwargs):
            policy = self.discovery_policy()
            policy["establishes_truth"] = True
            return self.discovery(
                policy=policy
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_candidate_policy_is_rechecked(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result[
                "pair_candidates"
            ][0]["policy"] = {}
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_candidate_live_merit_effect_fails(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result[
                "pair_candidates"
            ][0]["policy"][
                "affects_live_merit"
            ] = True
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_candidate_signals_are_required(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result[
                "pair_candidates"
            ][0]["signals"] = None
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_subject_must_appear_in_anchor_candidates(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result["anchor"][
                "entity_candidates"
            ] = []
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_subject_must_appear_in_candidate_entities(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result[
                "pair_candidates"
            ][0][
                "entity_candidates"
            ] = []
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_subject_must_be_in_shared_signal(self):
        def discovery(**_kwargs):
            result = self.discovery()
            result[
                "pair_candidates"
            ][0]["signals"][
                "shared_entity_ids"
            ] = []
            return result

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_missing_canonical_subject_fails_binding(self):
        conn = self.connection_factory()
        try:
            conn.execute(
                "DELETE FROM canonical_entities"
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ):
            self.run_service()

    def test_incomplete_canonical_subject_fails_integrity(self):
        conn = self.connection_factory()
        try:
            conn.execute(
                """
                UPDATE canonical_entities
                SET canonical_name = ''
                WHERE id = 'entity-1'
                """
            )
            conn.commit()
        finally:
            conn.close()

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service()

    def test_discovery_input_error_maps(self):
        def discovery(**_kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryInputError(
                    "bad input"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_not_found_maps(self):
        def discovery(**_kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryNotFoundError(
                    "missing"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowDiscoveryError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_lookup_error_maps(self):
        def discovery(**_kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryLookupError(
                    "db down"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowExecutionError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_discovery_integrity_error_maps(self):
        def discovery(**_kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryIntegrityError(
                    "bad capture"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                discovery_runner=discovery
            )

    def test_shadow_input_error_maps(self):
        def shadow(**_kwargs):
            raise (
                multimodal_inbox_shadow_orchestration
                .MultimodalInboxShadowInputError(
                    "bad shadow input"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_binding_error_maps(self):
        def shadow(**_kwargs):
            raise (
                multimodal_inbox_shadow_orchestration
                .MultimodalInboxShadowBindingError(
                    "bad binding"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_provider_error_maps(self):
        def shadow(**_kwargs):
            raise (
                multimodal_inbox_shadow_orchestration
                .MultimodalInboxShadowProviderUnavailable(
                    "provider"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowProviderUnavailable
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_execution_error_maps(self):
        def shadow(**_kwargs):
            raise (
                multimodal_inbox_shadow_orchestration
                .MultimodalInboxShadowExecutionError(
                    "execution"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowExecutionError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_integrity_error_maps(self):
        def shadow(**_kwargs):
            raise (
                multimodal_inbox_shadow_orchestration
                .MultimodalInboxShadowIntegrityError(
                    "integrity"
                )
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_version_is_rechecked(self):
        def shadow(**_kwargs):
            return self.shadow(
                version="wrong"
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_pair_scope_is_rechecked(self):
        def shadow(**_kwargs):
            return self.shadow(
                right_capture_record_id="other"
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_claim_id_is_required(self):
        def shadow(**_kwargs):
            return self.shadow(
                claim_id=""
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_policy_is_rechecked(self):
        def shadow(**_kwargs):
            return self.shadow(
                policy={}
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_shadow_forbidden_policy_fails(self):
        def shadow(**_kwargs):
            policy = self.shadow_policy()
            policy["affects_live_merit"] = True
            return self.shadow(
                policy=policy
            )

        with self.assertRaises(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ):
            self.run_service(
                shadow_runner=shadow
            )

    def test_output_policy_keeps_discovery_as_gate_only(self):
        result = self.run_service()
        policy = result["policy"]
        self.assertTrue(
            policy[
                "candidate_must_be_currently_discovered"
            ]
        )
        self.assertTrue(
            policy[
                "discovery_score_is_ranking_only"
            ]
        )
        self.assertTrue(
            policy[
                "discovery_does_not_establish_same_claim"
            ]
        )

    def test_output_policy_requires_shared_exact_subject(self):
        policy = self.run_service()[
            "policy"
        ]
        self.assertTrue(
            policy[
                "subject_entity_must_be_shared_exact_candidate"
            ]
        )
        self.assertTrue(
            policy[
                "shared_entity_candidate_does_not_verify_subject"
            ]
        )
        self.assertTrue(
            policy[
                "subject_descriptor_loaded_server_side"
            ]
        )

    def test_output_policy_preserves_shadow_only(self):
        policy = self.run_service()[
            "policy"
        ]
        self.assertTrue(
            policy[
                "downstream_exact_common_claim_required"
            ]
        )
        self.assertTrue(
            policy[
                "live_merit_shadow_only"
            ]
        )
        self.assertFalse(
            policy["establishes_truth"]
        )
        self.assertFalse(
            policy["establishes_authority"]
        )
        self.assertFalse(
            policy["establishes_independence"]
        )
        self.assertFalse(
            policy["affects_live_merit"]
        )


class CandidateShadowRouteTests(
    unittest.TestCase
):
    def request_payload(self, **overrides):
        value = {
            "anchor_capture_record_id": "anchor-1",
            "candidate_capture_record_id": "candidate-1",
            "subject_entity_id": "entity-1",
            "legacy_score": {"total": 72},
            "target_claim_id": "",
            "scan_limit": 100,
            "max_candidates": 12,
        }
        value.update(overrides)
        return value

    def service_result(self):
        return {
            "version": (
                inbox_candidate_shadow_orchestration
                .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
            ),
            "status": "completed_shadow",
            "claim_id": "claim-1",
            "anchor_capture_record_id": "anchor-1",
            "candidate_capture_record_id": "candidate-1",
            "subject_entity_id": "entity-1",
            "subject": {},
            "discovery_gate": {},
            "orchestration": {},
            "policy": {},
        }

    def router(
        self,
        *,
        enabled=True,
        require_admin=None,
        client_factory=None,
        key_resolver=None,
        generator=None,
    ):
        if require_admin is None:
            require_admin = lambda _request: None

        if client_factory is None:
            client_factory = lambda: object()

        if key_resolver is None:
            key_resolver = (
                lambda _request: "client-1"
            )

        if generator is None:
            generator = lambda **_kwargs: None

        return (
            inbox_candidate_shadow_admin
            .build_router(
                enabled=enabled,
                require_admin=require_admin,
                connection_factory=(
                    lambda: None
                ),
                gemini_client_factory=(
                    client_factory
                ),
                request_client_key_resolver=(
                    key_resolver
                ),
                gemini_generator=generator,
            )
        )

    def endpoint(self, router):
        expected = (
            "/admin/intelligence/"
            "multimodal-inbox-candidate-shadow-run"
        )

        matches = [
            route
            for route in router.routes
            if getattr(
                route,
                "path",
                "",
            ) == expected
        ]

        self.assertEqual(
            len(matches),
            1,
        )

        return matches[0].endpoint

    def request_model(self, **overrides):
        return (
            inbox_candidate_shadow_admin
            .MultimodalInboxCandidateShadowRequest(
                **self.request_payload(
                    **overrides
                )
            )
        )

    def test_request_forbids_subject_descriptor(self):
        with self.assertRaises(
            ValidationError
        ):
            self.request_model(
                subject={
                    "entity_key": "x"
                }
            )

    def test_request_forbids_binding_ids(self):
        for field in (
            "source_id",
            "media_item_id",
            "story_id",
            "verified",
        ):
            with self.subTest(field=field):
                with self.assertRaises(
                    ValidationError
                ):
                    self.request_model(
                        **{field: "x"}
                    )

    def test_request_bounds_scan_limit(self):
        with self.assertRaises(
            ValidationError
        ):
            self.request_model(
                scan_limit=501
            )

    def test_request_bounds_candidate_limit(self):
        with self.assertRaises(
            ValidationError
        ):
            self.request_model(
                max_candidates=51
            )

    def test_route_is_registered(self):
        router = self.router()
        self.endpoint(router)

    def test_disabled_route_is_404_before_admin(self):
        admin_calls = []
        router = self.router(
            enabled=False,
            require_admin=(
                lambda request:
                admin_calls.append(request)
            ),
        )
        endpoint = self.endpoint(router)

        with self.assertRaises(
            HTTPException
        ) as context:
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            context.exception.status_code,
            404,
        )
        self.assertEqual(
            admin_calls,
            [],
        )

    def test_enabled_route_requires_admin(self):
        marker = object()
        admin_calls = []
        router = self.router(
            require_admin=(
                lambda request:
                admin_calls.append(request)
            ),
        )
        endpoint = self.endpoint(router)

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            return_value=self.service_result(),
        ):
            endpoint(
                self.request_model(),
                marker,
            )

        self.assertEqual(
            admin_calls,
            [marker],
        )

    def test_missing_client_factory_is_503(self):
        router = (
            inbox_candidate_shadow_admin
            .build_router(
                enabled=True,
                require_admin=(
                    lambda _request: None
                ),
                connection_factory=(
                    lambda: None
                ),
                gemini_client_factory=None,
                request_client_key_resolver=None,
                gemini_generator=(
                    lambda **_kwargs: None
                ),
            )
        )
        endpoint = self.endpoint(router)

        with self.assertRaises(
            HTTPException
        ) as context:
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            context.exception.status_code,
            503,
        )

    def test_none_client_is_503(self):
        router = self.router(
            client_factory=lambda: None
        )
        endpoint = self.endpoint(router)

        with self.assertRaises(
            HTTPException
        ) as context:
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            context.exception.status_code,
            503,
        )

    def test_client_factory_failure_is_503(self):
        def client_factory():
            raise RuntimeError("down")

        router = self.router(
            client_factory=client_factory
        )
        endpoint = self.endpoint(router)

        with self.assertRaises(
            HTTPException
        ) as context:
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            context.exception.status_code,
            503,
        )

    def test_missing_generator_is_503(self):
        router = (
            inbox_candidate_shadow_admin
            .build_router(
                enabled=True,
                require_admin=(
                    lambda _request: None
                ),
                connection_factory=(
                    lambda: None
                ),
                gemini_client_factory=(
                    lambda: object()
                ),
                request_client_key_resolver=None,
                gemini_generator=None,
            )
        )
        endpoint = self.endpoint(router)

        with self.assertRaises(
            HTTPException
        ) as context:
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            context.exception.status_code,
            503,
        )

    def test_route_delegates_exact_request_fields(self):
        router = self.router()
        endpoint = self.endpoint(router)
        calls = []

        def execute(**kwargs):
            calls.append(kwargs)
            return self.service_result()

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            side_effect=execute,
        ):
            response = endpoint(
                self.request_model(
                    scan_limit=80,
                    max_candidates=7,
                    target_claim_id="claim-x",
                ),
                object(),
            )

        self.assertEqual(
            response.status,
            "completed_shadow",
        )
        self.assertEqual(
            calls[0][
                "anchor_capture_record_id"
            ],
            "anchor-1",
        )
        self.assertEqual(
            calls[0][
                "candidate_capture_record_id"
            ],
            "candidate-1",
        )
        self.assertEqual(
            calls[0]["subject_entity_id"],
            "entity-1",
        )
        self.assertEqual(
            calls[0]["scan_limit"],
            80,
        )
        self.assertEqual(
            calls[0]["max_candidates"],
            7,
        )
        self.assertEqual(
            calls[0]["target_claim_id"],
            "claim-x",
        )

    def test_route_passes_client_key(self):
        router = self.router(
            key_resolver=(
                lambda _request: "resolved-client"
            )
        )
        endpoint = self.endpoint(router)
        calls = []

        def execute(**kwargs):
            calls.append(kwargs)
            return self.service_result()

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            side_effect=execute,
        ):
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            calls[0]["gemini_client_key"],
            "resolved-client",
        )

    def test_route_defaults_client_key(self):
        router = (
            inbox_candidate_shadow_admin
            .build_router(
                enabled=True,
                require_admin=(
                    lambda _request: None
                ),
                connection_factory=(
                    lambda: None
                ),
                gemini_client_factory=(
                    lambda: object()
                ),
                request_client_key_resolver=None,
                gemini_generator=(
                    lambda **_kwargs: None
                ),
            )
        )
        endpoint = self.endpoint(router)
        calls = []

        def execute(**kwargs):
            calls.append(kwargs)
            return self.service_result()

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            side_effect=execute,
        ):
            endpoint(
                self.request_model(),
                object(),
            )

        self.assertEqual(
            calls[0]["gemini_client_key"],
            "anonymous",
        )

    def assert_http_mapping(
        self,
        error,
        expected_status,
    ):
        router = self.router()
        endpoint = self.endpoint(router)

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            side_effect=error,
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                endpoint(
                    self.request_model(),
                    object(),
                )

        self.assertEqual(
            context.exception.status_code,
            expected_status,
        )

    def test_input_error_maps_422(self):
        self.assert_http_mapping(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError(
                "bad input"
            ),
            422,
        )

    def test_discovery_error_maps_409(self):
        self.assert_http_mapping(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowDiscoveryError(
                "not current"
            ),
            409,
        )

    def test_binding_error_maps_409(self):
        self.assert_http_mapping(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError(
                "bad subject"
            ),
            409,
        )

    def test_provider_error_maps_503(self):
        self.assert_http_mapping(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowProviderUnavailable(
                "provider"
            ),
            503,
        )

    def test_execution_error_maps_409(self):
        self.assert_http_mapping(
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowExecutionError(
                "execution"
            ),
            409,
        )

    def test_integrity_error_maps_generic_500(self):
        router = self.router()
        endpoint = self.endpoint(router)

        with mock.patch.object(
            inbox_candidate_shadow_orchestration,
            "execute_multimodal_inbox_candidate_shadow",
            side_effect=(
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowIntegrityError(
                    "secret detail"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                endpoint(
                    self.request_model(),
                    object(),
                )

        self.assertEqual(
            context.exception.status_code,
            500,
        )
        self.assertNotIn(
            "secret detail",
            str(context.exception.detail),
        )


if __name__ == "__main__":
    unittest.main()
