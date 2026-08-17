from __future__ import annotations

import sys
import unittest

from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app import main
from app.routes import multimodal_admin
from app.services import multimodal_binding_registration as registration
from app.services import multimodal_shadow_api
from app.services import multimodal_shadow_orchestration as orchestration


SUBJECT = {
    "entity_key": "football|club|arsenal",
    "entity_type": "club",
    "canonical_name": "Arsenal",
    "sport_key": "football",
}

LEFT_CAPTURE = {
    "version": "browser-capture-v1",
    "source_url": "https://x.com/one/status/111111",
    "observed_at": "2026-08-17T10:00:00Z",
    "extraction_method": "browser_dom",
    "payload": {
        "platform": "x",
        "surface": "post",
        "container_kind": "post",
        "canonical_url": "https://x.com/one/status/111111",
        "body": "Arsenal update",
    },
    "actor": {
        "handle": "one",
    },
}

RIGHT_CAPTURE = {
    "version": "browser-capture-v1",
    "source_url": "https://x.com/two/status/222222",
    "observed_at": "2026-08-17T10:01:00Z",
    "extraction_method": "browser_dom",
    "payload": {
        "platform": "x",
        "surface": "post",
        "container_kind": "post",
        "canonical_url": "https://x.com/two/status/222222",
        "body": "Arsenal update",
    },
    "actor": {
        "handle": "two",
    },
}


def safe_registration():
    return {
        "version": registration.MULTIMODAL_BINDING_REGISTRATION_VERSION,
        "status": "registered",
        "subject": {
            "entity_id": "entity-1",
            "entity_key": SUBJECT["entity_key"],
            "entity_type": SUBJECT["entity_type"],
            "canonical_name": SUBJECT["canonical_name"],
            "sport_key": SUBJECT["sport_key"],
        },
        "subject_key": SUBJECT["entity_key"],
        "left": {
            "source_id": "source-left",
            "media_item_id": "media-left",
            "story_id": "",
        },
        "right": {
            "source_id": "source-right",
            "media_item_id": "media-right",
            "story_id": "",
        },
        "policy": {
            "subject_record_is_identity_only": True,
            "source_identity_is_deterministic": True,
            "stable_actor_identity_required_for_social": True,
            "source_and_media_persisted_atomically": True,
            "live_release_not_called": True,
            "story_record_created": False,
            "verified_source_entity_binding_created": False,
            "verified_claim_entity_participant_created": False,
            "claim_created": False,
            "observation_created": False,
            "evidence_record_created": False,
            "model_output_used": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "training_eligible": False,
            "affects_live_merit": False,
        },
    }


def safe_shadow():
    return {
        "version": multimodal_shadow_api.MULTIMODAL_SHADOW_API_VERSION,
        "status": "completed_shadow",
        "result": {
            "version": "multimodal-intelligence-runtime-v1",
            "status": "completed_shadow",
            "claim_id": "claim-1",
            "subject_key": SUBJECT["entity_key"],
            "left_media_item_id": "media-left",
            "right_media_item_id": "media-right",
        },
        "policy": {
            "bindings_verified_server_side": True,
            "caller_cannot_set_verification_flags": True,
            "exact_two_media_scope": True,
            "exact_common_claim_required": True,
            "multimodal_evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_independence": True,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


def http_request(admin_key="secret"):
    headers = []

    if admin_key:
        headers.append(
            (
                b"x-sportabase-admin-key",
                admin_key.encode("utf-8"),
            )
        )

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/admin/intelligence/multimodal-shadow-run",
            "raw_path": b"",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


class MultimodalShadowOrchestrationTests(unittest.TestCase):
    def execute(
        self,
        *,
        registration_result=None,
        shadow_result=None,
        registration_runner=None,
        shadow_runner=None,
        gemini_client=object(),
        gemini_generator=lambda **kwargs: None,
        legacy_score=None,
        target_claim_id="",
    ):
        if registration_runner is None:
            registration_runner = mock.Mock(
                return_value=(
                    registration_result
                    if registration_result is not None
                    else safe_registration()
                )
            )

        if shadow_runner is None:
            shadow_runner = mock.Mock(
                return_value=(
                    shadow_result
                    if shadow_result is not None
                    else safe_shadow()
                )
            )

        result = orchestration.execute_multimodal_shadow_orchestration(
            subject=SUBJECT,
            left_capture=LEFT_CAPTURE,
            right_capture=RIGHT_CAPTURE,
            legacy_score=(
                legacy_score
                if legacy_score is not None
                else {"total": 71}
            ),
            target_claim_id=target_claim_id,
            connection_factory=mock.Mock(),
            gemini_client=gemini_client,
            gemini_client_key="client-1",
            gemini_generator=gemini_generator,
            registration_runner=registration_runner,
            shadow_runner=shadow_runner,
        )

        return result, registration_runner, shadow_runner

    def test_version_status_and_claim(self):
        result, _, _ = self.execute()
        self.assertEqual(
            result["version"],
            orchestration.MULTIMODAL_SHADOW_ORCHESTRATION_VERSION,
        )
        self.assertEqual(result["status"], "completed_shadow")
        self.assertEqual(result["claim_id"], "claim-1")

    def test_registration_runs_before_shadow_and_ids_are_server_generated(self):
        calls = []

        def register(**kwargs):
            calls.append("register")
            return safe_registration()

        def shadow(**kwargs):
            calls.append("shadow")
            payload = kwargs["request_payload"]
            self.assertEqual(payload["left"]["source_id"], "source-left")
            self.assertEqual(payload["left"]["media_item_id"], "media-left")
            self.assertEqual(payload["right"]["source_id"], "source-right")
            self.assertEqual(payload["right"]["media_item_id"], "media-right")
            return safe_shadow()

        self.execute(
            registration_runner=register,
            shadow_runner=shadow,
        )
        self.assertEqual(calls, ["register", "shadow"])

    def test_original_captures_are_forwarded_to_shadow(self):
        _, _, shadow = self.execute()
        request_payload = shadow.call_args.kwargs["request_payload"]
        self.assertEqual(request_payload["left"]["capture"], LEFT_CAPTURE)
        self.assertEqual(request_payload["right"]["capture"], RIGHT_CAPTURE)

    def test_target_claim_id_is_forwarded(self):
        _, _, shadow = self.execute(target_claim_id=" claim-9 ")
        payload = shadow.call_args.kwargs["request_payload"]
        self.assertEqual(payload["target_claim_id"], "claim-9")

    def test_legacy_score_is_normalized(self):
        _, _, shadow = self.execute(legacy_score={"total": "71"})
        payload = shadow.call_args.kwargs["request_payload"]
        self.assertEqual(payload["legacy_score"]["total"], 71.0)

    def test_invalid_legacy_score_fails_before_registration(self):
        register = mock.Mock()
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationInputError
        ):
            self.execute(
                registration_runner=register,
                legacy_score={"total": 101},
            )
        register.assert_not_called()

    def test_provider_missing_fails_before_registration(self):
        register = mock.Mock()
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationProviderUnavailable
        ):
            self.execute(
                registration_runner=register,
                gemini_client=None,
            )
        register.assert_not_called()

    def test_generator_missing_fails_before_registration(self):
        register = mock.Mock()
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationProviderUnavailable
        ):
            self.execute(
                registration_runner=register,
                gemini_generator=None,
            )
        register.assert_not_called()

    def test_registration_input_error_maps_to_orchestration_input(self):
        runner = mock.Mock(
            side_effect=registration.MultimodalBindingInputError("bad")
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationInputError
        ):
            self.execute(registration_runner=runner)

    def test_registration_identity_error_maps_to_binding(self):
        runner = mock.Mock(
            side_effect=registration.MultimodalBindingIdentityError("bad")
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationBindingError
        ):
            self.execute(registration_runner=runner)

    def test_registration_persistence_error_is_integrity_error(self):
        runner = mock.Mock(
            side_effect=registration.MultimodalBindingPersistenceError(
                "secret"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ) as captured:
            self.execute(registration_runner=runner)
        self.assertNotIn("secret", str(captured.exception))

    def test_registration_integrity_error_is_generic(self):
        runner = mock.Mock(
            side_effect=registration.MultimodalBindingIntegrityError(
                "secret"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ) as captured:
            self.execute(registration_runner=runner)
        self.assertNotIn("secret", str(captured.exception))

    def test_registration_version_mismatch_fails_closed(self):
        result = safe_registration()
        result["version"] = "wrong"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_status_mismatch_fails_closed(self):
        result = safe_registration()
        result["status"] = "partial"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_subject_mismatch_fails_closed(self):
        result = safe_registration()
        result["subject"]["entity_key"] = "other"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_missing_binding_id_fails_closed(self):
        result = safe_registration()
        result["left"]["source_id"] = ""
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_story_scope_is_rejected(self):
        result = safe_registration()
        result["left"]["story_id"] = "story-1"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_duplicate_media_scope_is_rejected(self):
        result = safe_registration()
        result["right"]["media_item_id"] = "media-left"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_policy_missing_boundary_fails_closed(self):
        result = safe_registration()
        result["policy"]["subject_record_is_identity_only"] = False
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_registration_policy_forbidden_true_fails_closed(self):
        result = safe_registration()
        result["policy"]["affects_live_merit"] = True
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(registration_result=result)

    def test_shadow_input_error_maps_to_orchestration_input(self):
        runner = mock.Mock(
            side_effect=multimodal_shadow_api.MultimodalShadowApiInputError(
                "bad"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationInputError
        ):
            self.execute(shadow_runner=runner)

    def test_shadow_binding_error_maps_to_orchestration_binding(self):
        runner = mock.Mock(
            side_effect=multimodal_shadow_api.MultimodalShadowApiBindingError(
                "bad"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationBindingError
        ):
            self.execute(shadow_runner=runner)

    def test_shadow_provider_error_maps_to_provider_unavailable(self):
        runner = mock.Mock(
            side_effect=(
                multimodal_shadow_api
                .MultimodalShadowApiProviderUnavailable("bad")
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationProviderUnavailable
        ):
            self.execute(shadow_runner=runner)

    def test_shadow_execution_error_maps_to_execution(self):
        runner = mock.Mock(
            side_effect=multimodal_shadow_api.MultimodalShadowApiExecutionError(
                "bad"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationExecutionError
        ):
            self.execute(shadow_runner=runner)

    def test_shadow_integrity_error_is_generic(self):
        runner = mock.Mock(
            side_effect=multimodal_shadow_api.MultimodalShadowApiIntegrityError(
                "secret"
            )
        )
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ) as captured:
            self.execute(shadow_runner=runner)
        self.assertNotIn("secret", str(captured.exception))

    def test_shadow_version_mismatch_fails_closed(self):
        result = safe_shadow()
        result["version"] = "wrong"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_shadow_subject_mismatch_fails_closed(self):
        result = safe_shadow()
        result["result"]["subject_key"] = "other"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_shadow_media_mismatch_fails_closed(self):
        result = safe_shadow()
        result["result"]["left_media_item_id"] = "other"
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_shadow_missing_claim_fails_closed(self):
        result = safe_shadow()
        result["result"]["claim_id"] = ""
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_shadow_policy_missing_boundary_fails_closed(self):
        result = safe_shadow()
        result["policy"]["bindings_verified_server_side"] = False
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_shadow_policy_forbidden_true_fails_closed(self):
        result = safe_shadow()
        result["policy"]["score_effect_applied"] = True
        with self.assertRaises(
            orchestration.MultimodalShadowOrchestrationIntegrityError
        ):
            self.execute(shadow_result=result)

    def test_policy_exposes_partial_registration_semantics(self):
        result, _, _ = self.execute()
        policy = result["policy"]
        self.assertTrue(
            policy["binding_registration_may_persist_if_shadow_fails"]
        )
        self.assertTrue(policy["binding_registration_is_identity_only"])
        self.assertTrue(policy["shadow_adapter_reverifies_bindings"])

    def test_policy_never_claims_truth_authority_independence_or_merit(self):
        result, _, _ = self.execute()
        policy = result["policy"]
        self.assertFalse(policy["establishes_truth"])
        self.assertFalse(policy["establishes_authority"])
        self.assertFalse(policy["establishes_independence"])
        self.assertFalse(policy["affects_live_merit"])
        self.assertFalse(policy["score_effect_applied"])
        self.assertTrue(policy["live_release_not_called"])


class MultimodalShadowRunRouteTests(unittest.TestCase):
    def request_model(self):
        return multimodal_admin.MultimodalShadowRunRequest(
            subject=SUBJECT,
            left_capture=LEFT_CAPTURE,
            right_capture=RIGHT_CAPTURE,
            legacy_score={"total": 71},
            target_claim_id="claim-1",
        )

    def endpoint(
        self,
        *,
        enabled=True,
        admin_guard=None,
        client_factory=None,
        key_resolver=None,
        generator=None,
    ):
        guard = admin_guard or mock.Mock()
        factory = client_factory or mock.Mock(
            return_value=object()
        )
        resolver = key_resolver or mock.Mock(
            return_value="client-1"
        )
        gemini_generator = generator or mock.Mock()

        router = multimodal_admin.build_router(
            enabled,
            guard,
            mock.Mock(),
            factory,
            resolver,
            gemini_generator,
        )

        route = next(
            route
            for route in router.routes
            if route.path == (
                "/admin/intelligence/"
                "multimodal-shadow-run"
            )
        )

        return (
            route.endpoint,
            guard,
            factory,
            resolver,
            gemini_generator,
        )

    def safe_result(self):
        return {
            "version": orchestration.MULTIMODAL_SHADOW_ORCHESTRATION_VERSION,
            "status": "completed_shadow",
            "claim_id": "claim-1",
            "registration": safe_registration(),
            "shadow": safe_shadow(),
            "policy": {
                "affects_live_merit": False,
            },
        }

    def test_request_forbids_binding_ids_and_verification_fields(self):
        payload = {
            "subject": SUBJECT,
            "left_capture": LEFT_CAPTURE,
            "right_capture": RIGHT_CAPTURE,
            "legacy_score": {"total": 71},
            "source_id": "caller-controlled",
            "verified": True,
        }
        with self.assertRaises(ValidationError):
            multimodal_admin.MultimodalShadowRunRequest(**payload)

    def test_disabled_route_returns_404_before_admin_and_provider(self):
        provider = mock.Mock()
        endpoint, guard, _, _, _ = self.endpoint(
            enabled=False,
            client_factory=provider,
        )
        with self.assertRaises(HTTPException) as captured:
            endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 404)
        guard.assert_not_called()
        provider.assert_not_called()

    def test_enabled_route_calls_admin_guard(self):
        endpoint, guard, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            return_value=self.safe_result(),
        ):
            endpoint(self.request_model(), http_request())
        guard.assert_called_once()

    def test_missing_provider_factory_returns_503(self):
        router = multimodal_admin.build_router(
            True,
            mock.Mock(),
            mock.Mock(),
        )
        endpoint = next(
            route.endpoint
            for route in router.routes
            if route.path.endswith("multimodal-shadow-run")
        )
        with self.assertRaises(HTTPException) as captured:
            endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 503)

    def test_provider_factory_failure_returns_503(self):
        endpoint, _, _, _, _ = self.endpoint(
            client_factory=mock.Mock(side_effect=RuntimeError("boom"))
        )
        with self.assertRaises(HTTPException) as captured:
            endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 503)

    def test_route_calls_orchestration_with_server_dependencies(self):
        client = object()
        provider = mock.Mock(return_value=client)
        resolver = mock.Mock(return_value="client-9")
        generator = mock.Mock()
        endpoint, _, _, _, _ = self.endpoint(
            client_factory=provider,
            key_resolver=resolver,
            generator=generator,
        )
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            return_value=self.safe_result(),
        ) as service:
            result = endpoint(self.request_model(), http_request())
        self.assertEqual(result.status, "completed_shadow")
        kwargs = service.call_args.kwargs
        self.assertIs(kwargs["gemini_client"], client)
        self.assertEqual(kwargs["gemini_client_key"], "client-9")
        self.assertIs(kwargs["gemini_generator"], generator)
        self.assertEqual(kwargs["subject"]["entity_key"], SUBJECT["entity_key"])

    def test_input_error_maps_to_422(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            side_effect=(
                orchestration.MultimodalShadowOrchestrationInputError("bad")
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 422)

    def test_binding_error_maps_to_409(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            side_effect=(
                orchestration.MultimodalShadowOrchestrationBindingError("bad")
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 409)

    def test_provider_error_maps_to_503(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            side_effect=(
                orchestration.MultimodalShadowOrchestrationProviderUnavailable(
                    "bad"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 503)

    def test_execution_error_maps_to_409(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            side_effect=(
                orchestration.MultimodalShadowOrchestrationExecutionError("bad")
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 409)

    def test_integrity_error_maps_to_generic_500(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            orchestration,
            "execute_multimodal_shadow_orchestration",
            side_effect=(
                orchestration.MultimodalShadowOrchestrationIntegrityError(
                    "secret"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(self.request_model(), http_request())
        self.assertEqual(captured.exception.status_code, 500)
        self.assertNotIn("secret", str(captured.exception.detail))

    def test_main_openapi_exposes_one_call_shadow_route(self):
        paths = main.app.openapi()["paths"]
        self.assertIn(
            "/admin/intelligence/multimodal-shadow-run",
            paths,
        )

    def test_existing_binding_route_remains_exposed(self):
        paths = main.app.openapi()["paths"]
        self.assertIn(
            "/admin/intelligence/multimodal-bindings",
            paths,
        )

    def test_existing_shadow_route_remains_exposed(self):
        paths = main.app.openapi()["paths"]
        self.assertIn(
            "/admin/intelligence/multimodal-shadow",
            paths,
        )

    def test_main_stays_within_decomposition_budget(self):
        main_path = BACKEND_DIR / "app" / "main.py"
        line_count = len(
            main_path.read_text(encoding="utf-8").splitlines()
        )
        self.assertLessEqual(line_count, 2200)


if __name__ == "__main__":
    unittest.main()
