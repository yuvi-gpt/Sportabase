from __future__ import annotations

import unittest

from fastapi import Request

from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomSecurityMisconfigured,
)
from app.security.control_room_origin import (
    CONTROL_ROOM_ORIGIN_PROVENANCE_HEADER,
    CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION,
    protect_control_room_guard_with_origin_provenance,
    validate_origin_provenance_secret,
    verify_control_room_origin_provenance,
)


SECRET = "A" * 44
OTHER_SECRET = "B" * 44


def _request(*values: str) -> Request:
    headers = [
        (
            CONTROL_ROOM_ORIGIN_PROVENANCE_HEADER.lower().encode("ascii"),
            value.encode("ascii"),
        )
        for value in values
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/admin/control-room/session",
            "raw_path": b"/admin/control-room/session",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )


class ControlRoomOriginProvenanceTests(unittest.TestCase):
    def test_version_is_v1(self):
        self.assertEqual(
            CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION,
            "sportabase-control-room-origin-provenance-v1",
        )

    def test_secure_secret_is_accepted(self):
        self.assertEqual(
            validate_origin_provenance_secret(SECRET),
            SECRET,
        )

    def test_missing_or_short_expected_secret_fails_closed(self):
        expected_message = (
            "Control Room origin provenance secret is not configured securely."
        )
        for value in ("", "short"):
            with self.subTest(value=value):
                with self.assertRaises(
                    ControlRoomSecurityMisconfigured
                ) as caught:
                    validate_origin_provenance_secret(value)
                self.assertEqual(str(caught.exception), expected_message)

    def test_exact_single_header_is_required(self):
        verify_control_room_origin_provenance(
            _request(SECRET),
            expected_secret=SECRET,
        )

        for request in (
            _request(),
            _request(OTHER_SECRET),
            _request(SECRET, SECRET),
        ):
            with self.subTest(headers=request.scope["headers"]):
                with self.assertRaises(ControlRoomAccessDenied):
                    verify_control_room_origin_provenance(
                        request,
                        expected_secret=SECRET,
                    )

    def test_denial_never_contains_secret_material(self):
        with self.assertRaises(ControlRoomAccessDenied) as caught:
            verify_control_room_origin_provenance(
                _request(OTHER_SECRET),
                expected_secret=SECRET,
            )
        message = str(caught.exception)
        self.assertNotIn(SECRET, message)
        self.assertNotIn(OTHER_SECRET, message)

    def test_wrapper_rejects_direct_origin_before_inner_guard(self):
        calls = []

        def inner(request):
            calls.append(request.url.path)
            return object()

        guard = protect_control_room_guard_with_origin_provenance(
            inner_guard=inner,
            expected_secret=SECRET,
        )

        with self.assertRaises(ControlRoomAccessDenied):
            guard(_request())
        self.assertEqual(calls, [])

        result = guard(_request(SECRET))
        self.assertIsNotNone(result)
        self.assertEqual(calls, ["/admin/control-room/session"])

    def test_wrapper_preserves_nonsecret_operational_hooks(self):
        def inner(request):
            del request
            return object()

        inner.runtime_version = "runtime-v1"
        inner.clear_policy_cache = lambda: None

        guard = protect_control_room_guard_with_origin_provenance(
            inner_guard=inner,
            expected_secret=SECRET,
        )

        self.assertEqual(guard.runtime_version, "runtime-v1")
        self.assertTrue(callable(guard.clear_policy_cache))
        self.assertEqual(
            guard.origin_provenance_version,
            CONTROL_ROOM_ORIGIN_PROVENANCE_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
