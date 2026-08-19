from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.composition import compose_application
from app.routes.control_room_admin import (
    CONTROL_ROOM_ROUTE_VERSION,
    build_router,
)
from app.security.control_room import (
    CONTROL_ROOM_SECURITY_VERSION,
    ControlRoomAccessDenied,
    ControlRoomPrincipal,
    ControlRoomSecurityMisconfigured,
)


NOW = 2_000_000_000


def _principal() -> ControlRoomPrincipal:
    return ControlRoomPrincipal(
        version=CONTROL_ROOM_SECURITY_VERSION,
        subject="owner-123",
        email="owner@example.com",
        email_verified=True,
        issuer="https://access.example.com",
        audience="control-room-audience",
        auth_strength="phishing_resistant",
        auth_methods=("passkey", "webauthn"),
        authenticated_at_epoch=NOW - 60,
        expires_at_epoch=NOW + 1800,
    )


def _client(require_control_room=None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_router(
            require_control_room=require_control_room,
        )
    )
    return TestClient(app)


class ControlRoomAdminRouteTests(unittest.TestCase):
    def test_default_route_is_fail_closed_when_guard_is_unconfigured(self):
        response = _client().get("/admin/control-room/session")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Control Room identity verification is not configured."
                )
            },
        )

    def test_authorized_principal_can_reach_session_route(self):
        calls = []

        def guard(request):
            calls.append(request.url.path)
            return _principal()

        response = _client(guard).get("/admin/control-room/session")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ["/admin/control-room/session"])

        payload = response.json()
        self.assertEqual(payload["version"], CONTROL_ROOM_ROUTE_VERSION)
        self.assertIs(payload["authenticated"], True)
        self.assertEqual(payload["principal"]["email"], "owner@example.com")
        self.assertIs(payload["principal"]["email_verified"], True)
        self.assertEqual(
            payload["principal"]["auth_strength"],
            "phishing_resistant",
        )
        self.assertEqual(
            payload["principal"]["auth_methods"],
            ["passkey", "webauthn"],
        )

    def test_access_denied_from_guard_becomes_403(self):
        def guard(request):
            del request
            raise ControlRoomAccessDenied("no")

        response = _client(guard).get("/admin/control-room/session")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Control Room access denied."},
        )

    def test_security_misconfiguration_from_guard_becomes_503(self):
        def guard(request):
            del request
            raise ControlRoomSecurityMisconfigured("missing provider")

        response = _client(guard).get("/admin/control-room/session")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Control Room security is not configured."},
        )

    def test_invalid_guard_return_is_fail_closed(self):
        response = _client(lambda request: None).get(
            "/admin/control-room/session"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Control Room authorization did not produce a principal."
                )
            },
        )

    def test_namespace_does_not_expose_shorter_alias(self):
        response = _client(lambda request: _principal()).get(
            "/admin/control-room"
        )
        self.assertEqual(response.status_code, 404)

    def test_composition_mounts_control_room_namespace(self):
        app = FastAPI()

        with patch(
            "app.application.composition.browser_capture_automation."
            "register_browser_capture_automation_lifecycle"
        ):
            compose_application(
                app=app,
                health_handler=lambda: {"ok": True},
                ingest_handler=lambda: None,
                stories_handler=lambda: [],
                resolve_content_handler=lambda req: None,
                browser_capture_handler=lambda req: None,
                analyze_video_handler=lambda req, request: None,
                analyze_handler=lambda req, request: None,
                usage_summary_handler=lambda request, days: {},
                multimodal_shadow_api_enabled=False,
                require_admin=lambda request: None,
                connection_factory=lambda: None,
                gemini_client_factory=lambda: None,
                request_client_key_resolver=lambda request: "test",
                gemini_generator=lambda **kwargs: None,
                analysis_version="test-analysis",
                scoring_version="test-scoring",
                control_room_guard=lambda request: _principal(),
            )

        paths = {
            route.path
            for route in app.routes
            if hasattr(route, "path")
        }

        self.assertIn("/admin/control-room/session", paths)

    def test_composition_defaults_to_fail_closed_control_room_guard(self):
        app = FastAPI()

        with patch(
            "app.application.composition.browser_capture_automation."
            "register_browser_capture_automation_lifecycle"
        ):
            compose_application(
                app=app,
                health_handler=lambda: {"ok": True},
                ingest_handler=lambda: None,
                stories_handler=lambda: [],
                resolve_content_handler=lambda req: None,
                browser_capture_handler=lambda req: None,
                analyze_video_handler=lambda req, request: None,
                analyze_handler=lambda req, request: None,
                usage_summary_handler=lambda request, days: {},
                multimodal_shadow_api_enabled=False,
                require_admin=lambda request: None,
                connection_factory=lambda: None,
                gemini_client_factory=lambda: None,
                request_client_key_resolver=lambda request: "test",
                gemini_generator=lambda **kwargs: None,
                analysis_version="test-analysis",
                scoring_version="test-scoring",
            )

        response = TestClient(app).get("/admin/control-room/session")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
