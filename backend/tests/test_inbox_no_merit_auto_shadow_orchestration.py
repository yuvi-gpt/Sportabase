from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path
from unittest import mock


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]


from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.services import browser_capture_automation as automation
from app.services import browser_capture_inbox
from app.services import inbox_auto_shadow_orchestration as auto_shadow
from app.services import inbox_candidate_shadow_orchestration as candidate_shadow
from app.services import inbox_no_merit_auto_shadow_orchestration as no_merit
from app.services import multimodal_intelligence_runtime as runtime
from app.services import multimodal_shadow_api


OBSERVED = "2026-08-17T13:10:00Z"


def x_capture(
    *,
    status_id="100",
    body="Arsenal agree transfer terms with Player One.",
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://x.com/reporter/status/"
            + status_id
        ),
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "x",
            "surface": "post",
            "container_kind": "post",
            "canonical_url": (
                "https://x.com/reporter/status/"
                + status_id
            ),
            "body": body,
        },
        "actor": {
            "handle": "reporter",
            "profile_url": "https://x.com/reporter",
        },
    }


def youtube_capture():
    return {
        "version": "browser-capture-v1",
        "source_url": "https://www.youtube.com/watch?v=abc123xyz00",
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom+youtube_transcript",
        "payload": {
            "platform": "youtube",
            "surface": "video",
            "container_kind": "video",
            "canonical_url": "https://www.youtube.com/watch?v=abc123xyz00",
            "title": "Transfer update",
            "body": "Arsenal agree transfer terms with Player One.",
        },
        "actor": {
            "handle": "channel_one",
            "profile_url": "https://www.youtube.com/@channel_one",
        },
    }


def web_capture():
    return {
        "version": "browser-capture-v1",
        "source_url": "https://example.com/story",
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom+article_extractor",
        "payload": {
            "platform": "web",
            "surface": "article",
            "container_kind": "article",
            "canonical_url": "https://example.com/story",
            "title": "Transfer update",
            "body": "Arsenal agree transfer terms with Player One.",
        },
        "actor": {},
    }


def loaded_capture(
    capture,
    *,
    record_id="bci_anchor",
):
    payload = capture["payload"]
    return {
        "version": browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION,
        "status": "loaded",
        "capture_record_id": record_id,
        "capture_hash": "hash",
        "canonical_url": payload["canonical_url"],
        "platform": payload["platform"],
        "platform_surface": payload["surface"],
        "normalized_item_id": "item",
        "normalized_content_hash": "content",
        "observed_at": capture["observed_at"],
        "capture": capture,
        "policy": {
            "record_is_untrusted": True,
            "integrity_rechecked_on_load": True,
            "affects_live_merit": False,
        },
    }


def safe_selection(
    *,
    anchor="bci_anchor",
    candidate="bci_peer",
    subject="entity_arsenal",
):
    return {
        "version": auto_shadow.MULTIMODAL_INBOX_AUTO_SELECTION_VERSION,
        "status": "selected",
        "anchor_capture_record_id": anchor,
        "candidate_capture_record_id": candidate,
        "subject_entity_id": subject,
        "candidate_score": 0.75,
        "candidate_reasons": ["shared_exact_entity"],
        "shared_entity_ids": [subject],
        "eligible_candidate_count": 1,
        "rejected_candidate_count": 0,
        "rejected_candidates": [],
        "policy": {
            "automatic_selection_is_candidate_routing_only": True,
            "automatic_selection_requires_exactly_one_eligible_candidate": True,
            "eligible_candidate_requires_exactly_one_shared_entity": True,
            "candidate_score_is_not_a_truth_confidence": True,
            "candidate_score_is_not_an_authority_confidence": True,
            "candidate_score_is_not_an_independence_confidence": True,
            "discovery_gate_is_read_only": True,
            "selected_subject_is_exact_entity_candidate_only": True,
            "selected_subject_is_not_verified_by_auto_selection": True,
            "affects_live_merit": False,
        },
    }


def safe_candidate_shadow(
    *,
    anchor="bci_anchor",
    candidate="bci_peer",
    subject="entity_arsenal",
):
    return {
        "version": candidate_shadow.MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION,
        "status": "completed_shadow",
        "claim_id": "claim_arsenal_transfer",
        "anchor_capture_record_id": anchor,
        "candidate_capture_record_id": candidate,
        "subject_entity_id": subject,
        "subject": {},
        "discovery_gate": {},
        "orchestration": {},
        "policy": {
            "candidate_must_be_currently_discovered": True,
            "discovery_gate_is_read_only": True,
            "discovery_score_is_ranking_only": True,
            "discovery_does_not_establish_same_claim": True,
            "subject_entity_must_be_shared_exact_candidate": True,
            "shared_entity_candidate_does_not_verify_subject": True,
            "subject_descriptor_loaded_server_side": True,
            "caller_cannot_supply_subject_descriptor": True,
            "caller_cannot_supply_binding_ids": True,
            "downstream_exact_common_claim_required": True,
            "capture_integrity_rechecked_downstream": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_independence": True,
            "live_merit_shadow_only": True,
            "merit_baseline_mode": "not_applicable",
            "merit_baseline_available": False,
            "merit_shadow_evaluated": False,
            "synthetic_merit_baseline_used": False,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


def safe_no_merit_result(anchor="bci_anchor"):
    return {
        "version": no_merit.MULTIMODAL_INBOX_NO_MERIT_AUTO_SHADOW_VERSION,
        "status": "completed_shadow",
        "claim_id": "claim_arsenal_transfer",
        "anchor_capture_record_id": anchor,
        "selected_candidate_capture_record_id": "bci_peer",
        "selected_subject_entity_id": "entity_arsenal",
        "baseline_resolution": {
            "mode": "not_applicable",
            "reason": "no_legacy_merit_baseline_for_non_article",
            "legacy_score": None,
            "synthetic_merit_baseline_used": False,
        },
        "automatic_selection": {},
        "orchestration": {},
        "policy": {
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "merit_baseline_mode": "not_applicable",
            "merit_baseline_available": False,
            "merit_shadow_evaluated": False,
            "synthetic_merit_baseline_used": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class MeritBaselineModeTests(unittest.TestCase):
    def test_legacy_mode_constant(self):
        self.assertEqual(
            runtime.MERIT_BASELINE_MODE_LEGACY,
            "legacy_merit",
        )

    def test_not_applicable_mode_constant(self):
        self.assertEqual(
            runtime.MERIT_BASELINE_MODE_NOT_APPLICABLE,
            "not_applicable",
        )

    def test_no_merit_shadow_version(self):
        self.assertEqual(
            runtime.NO_MERIT_BASELINE_SHADOW_VERSION,
            "multimodal-no-merit-baseline-v1",
        )

    def test_legacy_baseline_requires_mapping(self):
        with self.assertRaises(
            runtime.MultimodalPipelineInputError
        ):
            runtime._normalize_merit_baseline(
                legacy_score=None,
                merit_baseline_mode="legacy_merit",
            )

    def test_legacy_baseline_is_copied(self):
        raw = {"total": 55, "nested": {"x": 1}}
        mode, score = runtime._normalize_merit_baseline(
            legacy_score=raw,
            merit_baseline_mode="legacy_merit",
        )
        self.assertEqual(mode, "legacy_merit")
        self.assertEqual(score, raw)
        self.assertIsNot(score, raw)
        self.assertIsNot(score["nested"], raw["nested"])

    def test_no_merit_mode_requires_none(self):
        with self.assertRaises(
            runtime.MultimodalPipelineInputError
        ):
            runtime._normalize_merit_baseline(
                legacy_score={"total": 0},
                merit_baseline_mode="not_applicable",
            )

    def test_no_merit_mode_returns_none(self):
        mode, score = runtime._normalize_merit_baseline(
            legacy_score=None,
            merit_baseline_mode="not_applicable",
        )
        self.assertEqual(mode, "not_applicable")
        self.assertIsNone(score)

    def test_unknown_baseline_mode_rejected(self):
        with self.assertRaises(
            runtime.MultimodalPipelineInputError
        ):
            runtime._normalize_merit_baseline(
                legacy_score=None,
                merit_baseline_mode="made_up",
            )

    def test_no_merit_shadow_has_no_live_score(self):
        result = runtime._no_merit_shadow_result(
            claim_id="claim_1"
        )
        self.assertIsNone(result["live_score"])

    def test_no_merit_shadow_is_not_applicable(self):
        result = runtime._no_merit_shadow_result(
            claim_id="claim_1"
        )
        self.assertEqual(result["status"], "not_applicable")

    def test_no_merit_shadow_does_not_call_shadow_runner(self):
        result = runtime._no_merit_shadow_result(
            claim_id="claim_1"
        )
        self.assertFalse(
            result["policy"]["shadow_runner_called"]
        )

    def test_no_merit_shadow_never_uses_synthetic_baseline(self):
        result = runtime._no_merit_shadow_result(
            claim_id="claim_1"
        )
        self.assertFalse(
            result["policy"]["synthetic_merit_baseline_used"]
        )

    def test_no_merit_shadow_never_affects_live_merit(self):
        result = runtime._no_merit_shadow_result(
            claim_id="claim_1"
        )
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )

    def test_api_defaults_to_legacy_mode(self):
        parts = multimodal_shadow_api._request_parts({
            "subject_key": "football|club|arsenal",
            "left": {
                "capture": {"x": 1},
                "source_id": "s1",
                "media_item_id": "m1",
            },
            "right": {
                "capture": {"x": 2},
                "source_id": "s2",
                "media_item_id": "m2",
            },
            "legacy_score": {"total": 50},
        })
        self.assertEqual(
            parts["merit_baseline_mode"],
            "legacy_merit",
        )

    def test_api_accepts_internal_no_merit_mode(self):
        parts = multimodal_shadow_api._request_parts({
            "subject_key": "football|club|arsenal",
            "left": {
                "capture": {"x": 1},
                "source_id": "s1",
                "media_item_id": "m1",
            },
            "right": {
                "capture": {"x": 2},
                "source_id": "s2",
                "media_item_id": "m2",
            },
            "legacy_score": None,
            "merit_baseline_mode": "not_applicable",
        })
        self.assertEqual(
            parts["merit_baseline_mode"],
            "not_applicable",
        )
        self.assertIsNone(parts["legacy_score"])

    def test_api_rejects_synthetic_score_in_no_merit_mode(self):
        with self.assertRaises(
            multimodal_shadow_api.MultimodalShadowApiInputError
        ):
            multimodal_shadow_api._request_parts({
                "subject_key": "football|club|arsenal",
                "left": {
                    "capture": {"x": 1},
                    "source_id": "s1",
                    "media_item_id": "m1",
                },
                "right": {
                    "capture": {"x": 2},
                    "source_id": "s2",
                    "media_item_id": "m2",
                },
                "legacy_score": {"total": 0},
                "merit_baseline_mode": "not_applicable",
            })

    def test_api_rejects_unknown_baseline_mode(self):
        with self.assertRaises(
            multimodal_shadow_api.MultimodalShadowApiInputError
        ):
            multimodal_shadow_api._request_parts({
                "subject_key": "football|club|arsenal",
                "left": {
                    "capture": {"x": 1},
                    "source_id": "s1",
                    "media_item_id": "m1",
                },
                "right": {
                    "capture": {"x": 2},
                    "source_id": "s2",
                    "media_item_id": "m2",
                },
                "legacy_score": None,
                "merit_baseline_mode": "unknown",
            })


class NoMeritAnchorScopeTests(unittest.TestCase):
    def loader(self, capture):
        return lambda **kwargs: loaded_capture(
            capture,
            record_id=kwargs["capture_record_id"],
        )

    def test_x_is_supported(self):
        result = no_merit._load_anchor_scope(
            anchor_capture_record_id="bci_anchor",
            connection_factory=object(),
            capture_loader=self.loader(x_capture()),
        )
        self.assertEqual(result["platform"], "x")

    def test_youtube_is_supported(self):
        result = no_merit._load_anchor_scope(
            anchor_capture_record_id="bci_anchor",
            connection_factory=object(),
            capture_loader=self.loader(youtube_capture()),
        )
        self.assertEqual(result["platform"], "youtube")

    def test_web_article_is_rejected(self):
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowInputError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=self.loader(web_capture()),
            )

    def test_unknown_platform_is_rejected(self):
        capture = x_capture()
        capture["payload"]["platform"] = "unknown"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowInputError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=self.loader(capture),
            )

    def test_platform_mismatch_is_integrity_error(self):
        loaded = loaded_capture(x_capture())
        loaded["platform"] = "youtube"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )

    def test_surface_mismatch_is_integrity_error(self):
        loaded = loaded_capture(x_capture())
        loaded["platform_surface"] = "video"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )

    def test_untrusted_policy_is_required(self):
        loaded = loaded_capture(x_capture())
        loaded["policy"]["record_is_untrusted"] = False
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )

    def test_integrity_recheck_policy_is_required(self):
        loaded = loaded_capture(x_capture())
        loaded["policy"]["integrity_rechecked_on_load"] = False
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )

    def test_capture_may_not_affect_merit(self):
        loaded = loaded_capture(x_capture())
        loaded["policy"]["affects_live_merit"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )

    def test_record_id_scope_is_rechecked(self):
        loaded = loaded_capture(x_capture())
        loaded["capture_record_id"] = "other"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._load_anchor_scope(
                anchor_capture_record_id="bci_anchor",
                connection_factory=object(),
                capture_loader=lambda **kwargs: loaded,
            )


class AutoSelectionContractTests(unittest.TestCase):
    def test_selection_version_is_v1(self):
        self.assertEqual(
            auto_shadow.MULTIMODAL_INBOX_AUTO_SELECTION_VERSION,
            "multimodal-inbox-auto-selection-v1",
        )

    def test_safe_selection_validates(self):
        result = no_merit._validate_selection(
            safe_selection(),
            anchor_capture_record_id="bci_anchor",
        )
        self.assertEqual(
            result["candidate_capture_record_id"],
            "bci_peer",
        )

    def test_selection_version_mismatch_fails(self):
        result = safe_selection()
        result["version"] = "wrong"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_anchor_mismatch_fails(self):
        result = safe_selection(anchor="wrong")
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_candidate_required(self):
        result = safe_selection()
        result["candidate_capture_record_id"] = ""
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_subject_required(self):
        result = safe_selection()
        result["subject_entity_id"] = ""
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_cannot_select_anchor_itself(self):
        result = safe_selection(candidate="bci_anchor")
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_policy_must_remain_candidate_only(self):
        result = safe_selection()
        result["policy"][
            "automatic_selection_is_candidate_routing_only"
        ] = False
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )

    def test_selection_never_affects_merit(self):
        result = safe_selection()
        result["policy"]["affects_live_merit"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_selection(
                result,
                anchor_capture_record_id="bci_anchor",
            )


class NoMeritCandidateContractTests(unittest.TestCase):
    def test_safe_candidate_shadow_validates(self):
        result = no_merit._validate_candidate_shadow(
            safe_candidate_shadow(),
            anchor_capture_record_id="bci_anchor",
            candidate_capture_record_id="bci_peer",
            subject_entity_id="entity_arsenal",
        )
        self.assertEqual(
            result["claim_id"],
            "claim_arsenal_transfer",
        )

    def test_candidate_requires_no_merit_mode(self):
        result = safe_candidate_shadow()
        result["policy"]["merit_baseline_mode"] = "legacy_merit"
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )

    def test_candidate_may_not_have_baseline(self):
        result = safe_candidate_shadow()
        result["policy"]["merit_baseline_available"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )

    def test_candidate_may_not_evaluate_merit_shadow(self):
        result = safe_candidate_shadow()
        result["policy"]["merit_shadow_evaluated"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )

    def test_candidate_may_not_use_synthetic_baseline(self):
        result = safe_candidate_shadow()
        result["policy"]["synthetic_merit_baseline_used"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )

    def test_candidate_scope_is_rechecked(self):
        result = safe_candidate_shadow(candidate="wrong")
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )

    def test_candidate_truth_must_remain_false(self):
        result = safe_candidate_shadow()
        result["policy"]["establishes_truth"] = True
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError
        ):
            no_merit._validate_candidate_shadow(
                result,
                anchor_capture_record_id="bci_anchor",
                candidate_capture_record_id="bci_peer",
                subject_entity_id="entity_arsenal",
            )


class NoMeritExecutionTests(unittest.TestCase):
    def execute(self, **overrides):
        kwargs = {
            "anchor_capture_record_id": "bci_anchor",
            "connection_factory": object(),
            "gemini_client": object(),
            "gemini_client_key": "test",
            "gemini_generator": lambda *args, **kwargs: {},
            "capture_loader": (
                lambda **kwargs: loaded_capture(
                    x_capture(),
                    record_id=kwargs["capture_record_id"],
                )
            ),
            "selection_runner": (
                lambda **kwargs: safe_selection(
                    anchor=kwargs["anchor_capture_record_id"]
                )
            ),
            "candidate_shadow_runner": (
                lambda **kwargs: safe_candidate_shadow(
                    anchor=kwargs["anchor_capture_record_id"],
                    candidate=kwargs["candidate_capture_record_id"],
                    subject=kwargs["subject_entity_id"],
                )
            ),
        }
        kwargs.update(overrides)
        return no_merit.execute_multimodal_inbox_no_merit_auto_shadow(
            **kwargs
        )

    def test_successful_execution_has_no_merit_baseline(self):
        result = self.execute()
        self.assertEqual(
            result["baseline_resolution"]["mode"],
            "not_applicable",
        )
        self.assertIsNone(
            result["baseline_resolution"]["legacy_score"]
        )

    def test_successful_execution_marks_synthetic_false(self):
        result = self.execute()
        self.assertFalse(
            result["baseline_resolution"][
                "synthetic_merit_baseline_used"
            ]
        )

    def test_successful_execution_preserves_claim(self):
        result = self.execute()
        self.assertEqual(
            result["claim_id"],
            "claim_arsenal_transfer",
        )

    def test_successful_execution_preserves_selection(self):
        result = self.execute()
        self.assertEqual(
            result["selected_candidate_capture_record_id"],
            "bci_peer",
        )
        self.assertEqual(
            result["selected_subject_entity_id"],
            "entity_arsenal",
        )

    def test_candidate_runner_receives_none_legacy_score(self):
        runner = mock.Mock(
            side_effect=lambda **kwargs: safe_candidate_shadow(
                anchor=kwargs["anchor_capture_record_id"],
                candidate=kwargs["candidate_capture_record_id"],
                subject=kwargs["subject_entity_id"],
            )
        )
        self.execute(candidate_shadow_runner=runner)
        self.assertIsNone(
            runner.call_args.kwargs["legacy_score"]
        )

    def test_candidate_runner_receives_not_applicable_mode(self):
        runner = mock.Mock(
            side_effect=lambda **kwargs: safe_candidate_shadow(
                anchor=kwargs["anchor_capture_record_id"],
                candidate=kwargs["candidate_capture_record_id"],
                subject=kwargs["subject_entity_id"],
            )
        )
        self.execute(candidate_shadow_runner=runner)
        self.assertEqual(
            runner.call_args.kwargs["merit_baseline_mode"],
            "not_applicable",
        )

    def test_article_anchor_is_rejected(self):
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowInputError
        ):
            self.execute(
                capture_loader=(
                    lambda **kwargs: loaded_capture(
                        web_capture(),
                        record_id=kwargs["capture_record_id"],
                    )
                )
            )

    def test_missing_gemini_client_is_provider_error(self):
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowProviderUnavailable
        ):
            self.execute(gemini_client=None)

    def test_missing_generator_is_provider_error(self):
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowProviderUnavailable
        ):
            self.execute(gemini_generator=None)

    def test_selection_not_ready_maps_to_not_ready(self):
        def fail(**kwargs):
            raise auto_shadow.MultimodalInboxAutoShadowSelectionError(
                "ambiguous"
            )
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowNotReady
        ):
            self.execute(selection_runner=fail)

    def test_candidate_binding_not_ready_maps_to_not_ready(self):
        def fail(**kwargs):
            raise candidate_shadow.MultimodalInboxCandidateShadowBindingError(
                "changed"
            )
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowNotReady
        ):
            self.execute(candidate_shadow_runner=fail)

    def test_candidate_provider_error_maps_to_provider(self):
        def fail(**kwargs):
            raise candidate_shadow.MultimodalInboxCandidateShadowProviderUnavailable(
                "down"
            )
        with self.assertRaises(
            no_merit.MultimodalInboxNoMeritAutoShadowProviderUnavailable
        ):
            self.execute(candidate_shadow_runner=fail)

    def test_no_merit_policy_never_affects_live_merit(self):
        result = self.execute()
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )

    def test_video_scores_are_explicitly_not_reinterpreted(self):
        result = self.execute()
        self.assertTrue(
            result["policy"][
                "video_component_scores_not_reinterpreted_as_merit"
            ]
        )


class AutomationDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "dispatch.db"
        conn = connect_database(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
        self.factory = lambda: connect_database(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def enabled_env(self, key, default=None):
        values = {
            automation.BROWSER_CAPTURE_AUTOMATION_FLAG: "1",
            automation.BROWSER_CAPTURE_AUTOMATION_MAX_ATTEMPTS: "4",
        }
        return values.get(key, default)

    def store(self, capture):
        return browser_capture_inbox.store_browser_capture(
            raw_capture=capture,
            connection_factory=self.factory,
            now_provider=lambda: "2026-08-17T13:11:00Z",
        )

    def enqueue_claim(self, capture):
        stored = self.store(capture)
        automation.enqueue_browser_capture_job(
            capture_record_id=stored["capture_record_id"],
            analysis_version="a1",
            scoring_version="s1",
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        job = automation.claim_next_browser_capture_job(
            worker_id="worker",
            analysis_version="a1",
            scoring_version="s1",
            connection_factory=self.factory,
            lease_seconds=30,
            now_provider=lambda: 1000,
        )
        return stored, job

    def test_article_anchor_mode(self):
        stored = self.store(web_capture())
        mode = automation._automation_anchor_mode(
            capture_record_id=stored["capture_record_id"],
            connection_factory=self.factory,
        )
        self.assertEqual(mode, "article_history_merit")

    def test_social_anchor_mode(self):
        stored = self.store(x_capture())
        mode = automation._automation_anchor_mode(
            capture_record_id=stored["capture_record_id"],
            connection_factory=self.factory,
        )
        self.assertEqual(mode, "non_article_no_merit")

    def test_youtube_anchor_mode(self):
        stored = self.store(youtube_capture())
        mode = automation._automation_anchor_mode(
            capture_record_id=stored["capture_record_id"],
            connection_factory=self.factory,
        )
        self.assertEqual(mode, "non_article_no_merit")

    def test_social_enqueue_is_persistent(self):
        stored = self.store(x_capture())
        result = automation.enqueue_browser_capture_job(
            capture_record_id=stored["capture_record_id"],
            analysis_version="a1",
            scoring_version="s1",
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "enqueued")

    def test_non_article_worker_uses_non_article_runner(self):
        stored, job = self.enqueue_claim(x_capture())
        article_runner = mock.Mock()
        non_article_runner = mock.Mock(
            return_value=safe_no_merit_result(
                stored["capture_record_id"]
            )
        )
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda *args, **kwargs: {},
            runner=article_runner,
            non_article_runner=non_article_runner,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["execution_mode"],
            "non_article_no_merit",
        )
        article_runner.assert_not_called()
        non_article_runner.assert_called_once()

    def test_article_worker_does_not_use_non_article_runner(self):
        stored, job = self.enqueue_claim(web_capture())
        history_result = {
            "version": (
                automation.inbox_history_auto_shadow_orchestration
                .MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION
            ),
            "status": "completed_shadow",
            "claim_id": "claim",
            "anchor_capture_record_id": stored["capture_record_id"],
            "selected_candidate_capture_record_id": "peer",
            "selected_subject_entity_id": "entity",
            "baseline_resolution": {"legacy_total": 50},
            "policy": {
                "live_merit_shadow_only": True,
                "live_release_not_called": True,
                "score_effect_applied": False,
                "establishes_truth": False,
                "establishes_authority": False,
                "establishes_independence": False,
                "affects_live_merit": False,
            },
        }
        article_runner = mock.Mock(return_value=history_result)
        non_article_runner = mock.Mock()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda *args, **kwargs: {},
            runner=article_runner,
            non_article_runner=non_article_runner,
            now_provider=lambda: 1001,
        )
        self.assertEqual(
            result["execution_mode"],
            "article_history_merit",
        )
        article_runner.assert_called_once()
        non_article_runner.assert_not_called()

    def test_non_article_not_ready_retries(self):
        _, job = self.enqueue_claim(x_capture())
        def fail(**kwargs):
            raise no_merit.MultimodalInboxNoMeritAutoShadowNotReady(
                "peer not ready"
            )
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda *args, **kwargs: {},
            non_article_runner=fail,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "retry_scheduled")

    def test_non_article_integrity_failure_is_terminal(self):
        _, job = self.enqueue_claim(x_capture())
        def fail(**kwargs):
            raise no_merit.MultimodalInboxNoMeritAutoShadowIntegrityError(
                "bad"
            )
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda *args, **kwargs: {},
            non_article_runner=fail,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "failed")

    def test_no_merit_result_policy_is_validated(self):
        stored, job = self.enqueue_claim(x_capture())
        result_payload = safe_no_merit_result(
            stored["capture_record_id"]
        )
        result_payload["policy"][
            "synthetic_merit_baseline_used"
        ] = True
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda *args, **kwargs: {},
            non_article_runner=lambda **kwargs: result_payload,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "failed")

    def test_result_summary_keeps_no_merit_baseline_resolution(self):
        result = automation._result_summary(
            safe_no_merit_result()
        )
        self.assertEqual(
            result["baseline_resolution"]["mode"],
            "not_applicable",
        )

    def test_queue_policy_no_longer_claims_article_only(self):
        stored = self.store(x_capture())
        result = automation.enqueue_browser_capture_job(
            capture_record_id=stored["capture_record_id"],
            analysis_version="a1",
            scoring_version="s1",
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertFalse(
            result["policy"]["article_anchor_only"]
        )
        self.assertTrue(
            result["policy"]["article_and_non_article_supported"]
        )


if __name__ == "__main__":
    unittest.main()
