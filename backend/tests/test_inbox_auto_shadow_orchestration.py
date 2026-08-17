from __future__ import annotations

import math
import sys
import unittest

from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError


BACKEND = Path(__file__).resolve().parents[1]

if str(BACKEND) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND),
    )


from app.routes import inbox_auto_shadow_admin
from app.services import inbox_auto_shadow_orchestration as auto
from app.services import inbox_candidate_discovery
from app.services import inbox_candidate_shadow_orchestration


ANCHOR_ID = "capture-anchor"
CANDIDATE_ID = "capture-candidate"
SUBJECT_ID = "entity-arsenal"


def safe_discovery_policy():
    return {
        "read_only_discovery": True,
        "inbox_records_remain_untrusted": True,
        "entity_candidates_do_not_verify_subject": True,
        "deterministic_score_is_ranking_only": True,
        "candidate_discovery_does_not_establish_corroboration": True,
        "creates_claim": False,
        "creates_evidence": False,
        "creates_verified_binding": False,
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_independence": False,
        "affects_live_merit": False,
    }


def safe_candidate_policy():
    return {
        "candidate_only": True,
        "same_story_not_established": True,
        "same_claim_not_established": True,
        "subject_not_verified": True,
        "independence_not_established": True,
        "corroboration_not_established": True,
        "affects_live_merit": False,
    }


def candidate(
    candidate_id=CANDIDATE_ID,
    *,
    shared=None,
    score=0.72,
):
    if shared is None:
        shared = [SUBJECT_ID]

    return {
        "capture_record_id": candidate_id,
        "candidate_score": score,
        "candidate_reasons": [
            "shared_text_tokens",
            "shared_exact_entity_candidates",
        ],
        "signals": {
            "shared_entity_ids": list(shared),
        },
        "policy": safe_candidate_policy(),
    }


def discovery_result(
    candidates=None,
    *,
    anchor_id=ANCHOR_ID,
):
    if candidates is None:
        candidates = [candidate()]

    return {
        "version": (
            inbox_candidate_discovery
            .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        ),
        "status": (
            "candidates_available"
            if candidates
            else "no_candidates"
        ),
        "anchor_capture_record_id": anchor_id,
        "anchor": {},
        "pair_candidates": candidates,
        "load_failures": [],
        "counts": {},
        "policy": safe_discovery_policy(),
    }


def safe_candidate_shadow_policy():
    return {
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
        "binding_ids_generated_server_side": True,
        "shadow_adapter_reverifies_bindings": True,
        "live_merit_shadow_only": True,
        "live_release_not_called": True,
        "score_effect_applied": False,
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_independence": False,
        "affects_live_merit": False,
    }


def candidate_shadow_result(
    *,
    anchor_id=ANCHOR_ID,
    candidate_id=CANDIDATE_ID,
    subject_id=SUBJECT_ID,
):
    return {
        "version": (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": "claim-123",
        "anchor_capture_record_id": anchor_id,
        "candidate_capture_record_id": candidate_id,
        "subject_entity_id": subject_id,
        "subject": {},
        "discovery_gate": {},
        "orchestration": {},
        "policy": safe_candidate_shadow_policy(),
    }


class Recorder:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.value


def execute(
    *,
    discovery=None,
    shadow=None,
    **overrides,
):
    if discovery is None:
        discovery = discovery_result()

    if shadow is None:
        shadow = candidate_shadow_result()

    discovery_runner = Recorder(discovery)
    shadow_runner = Recorder(shadow)

    kwargs = {
        "anchor_capture_record_id": ANCHOR_ID,
        "legacy_score": {"total": 61},
        "target_claim_id": "",
        "scan_limit": 100,
        "max_candidates": 12,
        "connection_factory": lambda: object(),
        "gemini_client": object(),
        "gemini_client_key": "client-1",
        "gemini_generator": lambda **kwargs: None,
        "discovery_runner": discovery_runner,
        "candidate_shadow_runner": shadow_runner,
    }
    kwargs.update(overrides)

    result = auto.execute_multimodal_inbox_auto_shadow(
        **kwargs
    )

    return result, discovery_runner, shadow_runner


def route_endpoint(router):
    matches = [
        route.endpoint
        for route in router.routes
        if getattr(route, "path", "")
        == (
            "/admin/intelligence/"
            "multimodal-inbox-auto-shadow-run"
        )
    ]

    if len(matches) != 1:
        raise AssertionError(
            "Expected exactly one #27 route."
        )

    return matches[0]


def build_route(
    *,
    enabled=True,
    admin=None,
    client_factory=None,
    client_key=None,
    generator=None,
):
    if admin is None:
        admin = lambda request: None

    if client_factory is None:
        client_factory = lambda: object()

    if client_key is None:
        client_key = lambda request: "route-client"

    if generator is None:
        generator = lambda **kwargs: None

    router = inbox_auto_shadow_admin.build_router(
        enabled=enabled,
        require_admin=admin,
        connection_factory=lambda: object(),
        gemini_client_factory=client_factory,
        request_client_key_resolver=client_key,
        gemini_generator=generator,
    )

    return route_endpoint(router)


def request_model(**overrides):
    payload = {
        "anchor_capture_record_id": ANCHOR_ID,
        "legacy_score": {"total": 61},
        "target_claim_id": "",
        "scan_limit": 100,
        "max_candidates": 12,
    }
    payload.update(overrides)

    return (
        inbox_auto_shadow_admin
        .MultimodalInboxAutoShadowRequest(
            **payload
        )
    )


class AutoShadowInputTests(unittest.TestCase):
    def test_version_constant(self):
        self.assertEqual(
            auto.MULTIMODAL_INBOX_AUTO_SHADOW_VERSION,
            "multimodal-inbox-auto-shadow-v1",
        )

    def test_anchor_required(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(
                anchor_capture_record_id=" "
            )

    def test_anchor_length_bounded(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(
                anchor_capture_record_id="x" * 257
            )

    def test_legacy_score_must_be_mapping(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(
                legacy_score=[]
            )

    def test_scan_limit_rejects_bool(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(scan_limit=True)

    def test_scan_limit_lower_bound(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(scan_limit=0)

    def test_scan_limit_upper_bound(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(scan_limit=501)

    def test_candidate_limit_rejects_bool(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(max_candidates=False)

    def test_candidate_limit_lower_bound(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(max_candidates=0)

    def test_candidate_limit_upper_bound(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(max_candidates=51)

    def test_connection_factory_required(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(connection_factory=None)

    def test_gemini_client_required(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowProviderUnavailable
        ):
            execute(gemini_client=None)

    def test_gemini_generator_required(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowProviderUnavailable
        ):
            execute(gemini_generator=None)


class AutoSelectionTests(unittest.TestCase):
    def test_discovery_semantics_are_disabled(self):
        _, discovery_runner, _ = execute()

        self.assertEqual(
            discovery_runner.calls[0][
                "semantic_assessments"
            ],
            0,
        )
        self.assertIsNone(
            discovery_runner.calls[0][
                "gemini_client"
            ]
        )

    def test_discovery_uses_requested_scan_limits(self):
        _, discovery_runner, _ = execute(
            scan_limit=222,
            max_candidates=17,
        )

        call = discovery_runner.calls[0]
        self.assertEqual(call["scan_limit"], 222)
        self.assertEqual(call["max_candidates"], 17)

    def test_no_candidates_fails_closed(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowSelectionError
        ):
            execute(
                discovery=discovery_result([])
            )

    def test_no_shared_entity_is_not_auto_eligible(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowSelectionError
        ):
            execute(
                discovery=discovery_result([
                    candidate(shared=[]),
                ])
            )

    def test_multiple_shared_entities_are_not_auto_eligible(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowSelectionError
        ):
            execute(
                discovery=discovery_result([
                    candidate(
                        shared=[
                            SUBJECT_ID,
                            "entity-player",
                        ]
                    ),
                ])
            )

    def test_single_eligible_candidate_is_selected(self):
        result, _, shadow_runner = execute()

        self.assertEqual(
            result[
                "selected_candidate_capture_record_id"
            ],
            CANDIDATE_ID,
        )
        self.assertEqual(
            result[
                "selected_subject_entity_id"
            ],
            SUBJECT_ID,
        )
        self.assertEqual(
            len(shadow_runner.calls),
            1,
        )

    def test_multiple_eligible_candidates_are_ambiguous(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowSelectionError
        ):
            execute(
                discovery=discovery_result([
                    candidate(
                        "capture-1",
                        shared=[SUBJECT_ID],
                    ),
                    candidate(
                        "capture-2",
                        shared=[SUBJECT_ID],
                    ),
                ])
            )

    def test_ineligible_candidates_do_not_block_one_unique_eligible(self):
        discovery = discovery_result([
            candidate(
                "capture-no-entity",
                shared=[],
            ),
            candidate(
                CANDIDATE_ID,
                shared=[SUBJECT_ID],
            ),
            candidate(
                "capture-many-entities",
                shared=[
                    SUBJECT_ID,
                    "entity-other",
                ],
            ),
        ])

        result, _, _ = execute(
            discovery=discovery
        )

        selection = result[
            "automatic_selection"
        ]

        self.assertEqual(
            selection["eligible_candidate_count"],
            1,
        )
        self.assertEqual(
            selection["rejected_candidate_count"],
            2,
        )

    def test_duplicate_candidate_ids_are_integrity_failure(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([
                    candidate(CANDIDATE_ID),
                    candidate(CANDIDATE_ID),
                ])
            )

    def test_non_mapping_candidate_is_integrity_failure(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([
                    "bad-candidate"
                ])
            )

    def test_missing_candidate_id_is_integrity_failure(self):
        row = candidate()
        row.pop("capture_record_id")

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_missing_candidate_policy_is_integrity_failure(self):
        row = candidate()
        row.pop("policy")

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_candidate_same_claim_must_remain_unestablished(self):
        row = candidate()
        row["policy"][
            "same_claim_not_established"
        ] = False

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_candidate_live_merit_effect_is_rejected(self):
        row = candidate()
        row["policy"][
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_missing_signals_is_integrity_failure(self):
        row = candidate()
        row.pop("signals")

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_shared_entity_ids_must_be_list(self):
        row = candidate()
        row["signals"][
            "shared_entity_ids"
        ] = SUBJECT_ID

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([row])
            )

    def test_bool_candidate_score_is_rejected(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([
                    candidate(score=True),
                ])
            )

    def test_numeric_string_candidate_score_is_normalized(self):
        result, _, _ = execute(
            discovery=discovery_result([
                candidate(score="0.72"),
            ])
        )

        self.assertEqual(
            result[
                "automatic_selection"
            ]["candidate_score"],
            0.72,
        )

    def test_nan_candidate_score_is_rejected(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([
                    candidate(score=math.nan),
                ])
            )

    def test_candidate_score_above_one_is_rejected(self):
        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery=discovery_result([
                    candidate(score=1.01),
                ])
            )

    def test_duplicate_shared_entity_values_dedupe_safely(self):
        result, _, _ = execute(
            discovery=discovery_result([
                candidate(
                    shared=[
                        SUBJECT_ID,
                        SUBJECT_ID,
                        " ",
                    ]
                ),
            ])
        )

        self.assertEqual(
            result[
                "selected_subject_entity_id"
            ],
            SUBJECT_ID,
        )


class DownstreamDelegationTests(unittest.TestCase):
    def test_selected_candidate_is_sent_to_locked_26(self):
        _, _, shadow_runner = execute()

        call = shadow_runner.calls[0]
        self.assertEqual(
            call[
                "candidate_capture_record_id"
            ],
            CANDIDATE_ID,
        )

    def test_selected_subject_is_sent_to_locked_26(self):
        _, _, shadow_runner = execute()

        self.assertEqual(
            shadow_runner.calls[0][
                "subject_entity_id"
            ],
            SUBJECT_ID,
        )

    def test_anchor_is_sent_to_locked_26(self):
        _, _, shadow_runner = execute()

        self.assertEqual(
            shadow_runner.calls[0][
                "anchor_capture_record_id"
            ],
            ANCHOR_ID,
        )

    def test_target_claim_id_is_preserved(self):
        _, _, shadow_runner = execute(
            target_claim_id="claim-target"
        )

        self.assertEqual(
            shadow_runner.calls[0][
                "target_claim_id"
            ],
            "claim-target",
        )

    def test_client_key_is_normalized(self):
        _, _, shadow_runner = execute(
            gemini_client_key="  "
        )

        self.assertEqual(
            shadow_runner.calls[0][
                "gemini_client_key"
            ],
            "anonymous",
        )

    def test_legacy_score_is_forwarded(self):
        score = {"total": 44}
        _, _, shadow_runner = execute(
            legacy_score=score
        )

        self.assertEqual(
            shadow_runner.calls[0][
                "legacy_score"
            ],
            score,
        )

    def test_scan_limits_are_reused_downstream(self):
        _, _, shadow_runner = execute(
            scan_limit=300,
            max_candidates=21,
        )

        call = shadow_runner.calls[0]
        self.assertEqual(
            call["scan_limit"],
            300,
        )
        self.assertEqual(
            call["max_candidates"],
            21,
        )


class DownstreamIntegrityTests(unittest.TestCase):
    def test_shadow_version_mismatch_rejected(self):
        shadow = candidate_shadow_result()
        shadow["version"] = "bad"

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_status_mismatch_rejected(self):
        shadow = candidate_shadow_result()
        shadow["status"] = "failed"

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_anchor_scope_mismatch_rejected(self):
        shadow = candidate_shadow_result(
            anchor_id="other"
        )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_candidate_scope_mismatch_rejected(self):
        shadow = candidate_shadow_result(
            candidate_id="other"
        )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_subject_scope_mismatch_rejected(self):
        shadow = candidate_shadow_result(
            subject_id="other"
        )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_claim_id_required(self):
        shadow = candidate_shadow_result()
        shadow["claim_id"] = ""

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_policy_required(self):
        shadow = candidate_shadow_result()
        shadow.pop("policy")

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_must_revalidate_candidate(self):
        shadow = candidate_shadow_result()
        shadow["policy"][
            "candidate_must_be_currently_discovered"
        ] = False

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)

    def test_shadow_live_merit_effect_rejected(self):
        shadow = candidate_shadow_result()
        shadow["policy"][
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(shadow=shadow)


class ErrorTranslationTests(unittest.TestCase):
    def test_discovery_input_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryInputError(
                    "bad"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(
                discovery_runner=runner
            )

    def test_discovery_not_found_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryNotFoundError(
                    "missing"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowDiscoveryError
        ):
            execute(
                discovery_runner=runner
            )

    def test_discovery_lookup_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryLookupError(
                    "db"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowExecutionError
        ):
            execute(
                discovery_runner=runner
            )

    def test_discovery_integrity_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_discovery
                .InboxCandidateDiscoveryIntegrityError(
                    "integrity"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                discovery_runner=runner
            )

    def test_candidate_shadow_input_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowInputError(
                    "bad"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowInputError
        ):
            execute(
                candidate_shadow_runner=runner
            )

    def test_candidate_shadow_discovery_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowDiscoveryError(
                    "stale"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowDiscoveryError
        ):
            execute(
                candidate_shadow_runner=runner
            )

    def test_candidate_shadow_binding_error_becomes_selection_error(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowBindingError(
                    "subject changed"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowSelectionError
        ):
            execute(
                candidate_shadow_runner=runner
            )

    def test_candidate_shadow_provider_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowProviderUnavailable(
                    "provider"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowProviderUnavailable
        ):
            execute(
                candidate_shadow_runner=runner
            )

    def test_candidate_shadow_execution_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowExecutionError(
                    "execution"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowExecutionError
        ):
            execute(
                candidate_shadow_runner=runner
            )

    def test_candidate_shadow_integrity_error_translated(self):
        def runner(**kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowIntegrityError(
                    "integrity"
                )
            )

        with self.assertRaises(
            auto.MultimodalInboxAutoShadowIntegrityError
        ):
            execute(
                candidate_shadow_runner=runner
            )


class ResultPolicyTests(unittest.TestCase):
    def test_result_claim_id_preserved(self):
        result, _, _ = execute()

        self.assertEqual(
            result["claim_id"],
            "claim-123",
        )

    def test_result_selection_mode_is_explicit(self):
        result, _, _ = execute()

        self.assertEqual(
            result[
                "automatic_selection"
            ]["selection_mode"],
            "single_unambiguous_discovery_candidate",
        )

    def test_candidate_score_is_not_truth_confidence(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "candidate_score_is_not_a_truth_confidence"
            ]
        )

    def test_auto_selection_does_not_verify_subject(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "selected_subject_is_not_verified_by_auto_selection"
            ]
        )

    def test_downstream_exact_common_claim_remains_required(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "downstream_exact_common_claim_required"
            ]
        )

    def test_live_merit_remains_shadow_only(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "live_merit_shadow_only"
            ]
        )
        self.assertFalse(
            result["policy"][
                "affects_live_merit"
            ]
        )

    def test_caller_candidate_id_is_forbidden_by_policy(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "caller_cannot_supply_candidate_capture_id"
            ]
        )

    def test_caller_subject_id_is_forbidden_by_policy(self):
        result, _, _ = execute()

        self.assertTrue(
            result["policy"][
                "caller_cannot_supply_subject_entity_id"
            ]
        )


class RouteModelTests(unittest.TestCase):
    def test_request_accepts_minimal_auto_input(self):
        req = request_model()
        self.assertEqual(
            req.anchor_capture_record_id,
            ANCHOR_ID,
        )

    def test_request_forbids_candidate_capture_id(self):
        with self.assertRaises(ValidationError):
            request_model(
                candidate_capture_record_id=CANDIDATE_ID
            )

    def test_request_forbids_subject_entity_id(self):
        with self.assertRaises(ValidationError):
            request_model(
                subject_entity_id=SUBJECT_ID
            )

    def test_request_forbids_subject_descriptor(self):
        with self.assertRaises(ValidationError):
            request_model(
                subject={
                    "entity_key": "club:arsenal"
                }
            )

    def test_request_forbids_source_id(self):
        with self.assertRaises(ValidationError):
            request_model(source_id="source-1")

    def test_request_forbids_media_item_id(self):
        with self.assertRaises(ValidationError):
            request_model(media_item_id="media-1")

    def test_route_is_registered(self):
        endpoint = build_route()
        self.assertTrue(callable(endpoint))

    def test_disabled_route_returns_404_before_service(self):
        endpoint = build_route(enabled=False)

        with self.assertRaises(HTTPException) as ctx:
            endpoint(
                request_model(),
                object(),
            )

        self.assertEqual(
            ctx.exception.status_code,
            404,
        )

    def test_admin_guard_is_called(self):
        calls = []

        def admin(request):
            calls.append(request)

        endpoint = build_route(admin=admin)

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            return_value={
                "version": auto.MULTIMODAL_INBOX_AUTO_SHADOW_VERSION,
                "status": "completed_shadow",
                "claim_id": "claim-123",
                "anchor_capture_record_id": ANCHOR_ID,
                "selected_candidate_capture_record_id": CANDIDATE_ID,
                "selected_subject_entity_id": SUBJECT_ID,
                "automatic_selection": {},
                "orchestration": {},
                "policy": {},
            },
        ):
            request = object()
            endpoint(
                request_model(),
                request,
            )

        self.assertEqual(calls, [request])

    def test_missing_client_factory_returns_503(self):
        router = inbox_auto_shadow_admin.build_router(
            enabled=True,
            require_admin=lambda request: None,
            connection_factory=lambda: object(),
            gemini_client_factory=None,
            request_client_key_resolver=None,
            gemini_generator=lambda **kwargs: None,
        )

        endpoint = route_endpoint(router)

        with self.assertRaises(HTTPException) as ctx:
            endpoint(
                request_model(),
                object(),
            )

        self.assertEqual(ctx.exception.status_code, 503)

    def test_client_factory_failure_returns_503(self):
        def factory():
            raise RuntimeError("down")

        endpoint = build_route(
            client_factory=factory
        )

        with self.assertRaises(HTTPException) as ctx:
            endpoint(
                request_model(),
                object(),
            )

        self.assertEqual(ctx.exception.status_code, 503)

    def test_missing_generator_returns_503(self):
        router = inbox_auto_shadow_admin.build_router(
            enabled=True,
            require_admin=lambda request: None,
            connection_factory=lambda: object(),
            gemini_client_factory=lambda: object(),
            request_client_key_resolver=None,
            gemini_generator=None,
        )
        endpoint = route_endpoint(router)

        with self.assertRaises(HTTPException) as ctx:
            endpoint(
                request_model(),
                object(),
            )

        self.assertEqual(ctx.exception.status_code, 503)

    def test_route_passes_client_key(self):
        endpoint = build_route(
            client_key=lambda request: "abc"
        )

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            return_value={
                "version": auto.MULTIMODAL_INBOX_AUTO_SHADOW_VERSION,
                "status": "completed_shadow",
                "claim_id": "claim-123",
                "anchor_capture_record_id": ANCHOR_ID,
                "selected_candidate_capture_record_id": CANDIDATE_ID,
                "selected_subject_entity_id": SUBJECT_ID,
                "automatic_selection": {},
                "orchestration": {},
                "policy": {},
            },
        ) as runner:
            endpoint(
                request_model(),
                object(),
            )

        self.assertEqual(
            runner.call_args.kwargs[
                "gemini_client_key"
            ],
            "abc",
        )

    def test_route_maps_input_error_to_422(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowInputError(
                    "bad"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 422)

    def test_route_maps_discovery_error_to_409(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowDiscoveryError(
                    "stale"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_route_maps_selection_error_to_409(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowSelectionError(
                    "ambiguous"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_route_maps_provider_error_to_503(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowProviderUnavailable(
                    "provider"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 503)

    def test_route_maps_execution_error_to_409(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowExecutionError(
                    "execution"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_route_maps_integrity_error_to_generic_500(self):
        endpoint = build_route()

        with mock.patch.object(
            inbox_auto_shadow_admin
            .inbox_auto_shadow_orchestration,
            "execute_multimodal_inbox_auto_shadow",
            side_effect=(
                auto.MultimodalInboxAutoShadowIntegrityError(
                    "secret detail"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                endpoint(
                    request_model(),
                    object(),
                )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertNotIn(
            "secret detail",
            str(ctx.exception.detail),
        )


if __name__ == "__main__":
    unittest.main()
