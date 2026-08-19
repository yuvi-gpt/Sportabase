from __future__ import annotations

import unittest

from app.security.control_room import (
    CONTROL_ROOM_SECURITY_VERSION,
    ControlRoomAccessDenied,
    ControlRoomSecurityMisconfigured,
    ControlRoomSecurityPolicy,
    VerifiedControlRoomIdentity,
    authorize_control_room_identity,
    normalize_email_allowlist,
    validate_control_room_policy,
)


NOW = 2_000_000_000


def _policy(**overrides) -> ControlRoomSecurityPolicy:
    values = {
        "enabled": True,
        "allowed_emails": ("owner@example.com",),
        "expected_issuer": "https://access.example.com",
        "expected_audience": "control-room-audience",
        "minimum_auth_strength": "phishing_resistant",
        "max_session_age_seconds": 3600,
        "clock_skew_seconds": 60,
    }
    values.update(overrides)
    return ControlRoomSecurityPolicy(**values)


def _identity(**overrides) -> VerifiedControlRoomIdentity:
    values = {
        "token_verified": True,
        "subject": "user-123",
        "email": "owner@example.com",
        "issuer": "https://access.example.com",
        "audiences": ("control-room-audience",),
        "issued_at_epoch": NOW - 600,
        "authenticated_at_epoch": NOW - 600,
        "expires_at_epoch": NOW + 1800,
        "auth_strength": "phishing_resistant",
        "auth_methods": ("passkey", "webauthn"),
    }
    values.update(overrides)
    return VerifiedControlRoomIdentity(**values)


class ControlRoomSecurityTests(unittest.TestCase):
    def test_email_allowlist_is_normalized_and_deduplicated(self):
        self.assertEqual(
            normalize_email_allowlist(
                (
                    " Owner@Example.com ",
                    "owner@example.com",
                    "SECOND@example.com",
                    "",
                )
            ),
            (
                "owner@example.com",
                "second@example.com",
            ),
        )

    def test_valid_phishing_resistant_identity_is_authorized(self):
        principal = authorize_control_room_identity(
            _identity(email=" OWNER@EXAMPLE.COM "),
            policy=_policy(),
            now_epoch=NOW,
        )

        self.assertEqual(principal.version, CONTROL_ROOM_SECURITY_VERSION)
        self.assertEqual(principal.subject, "user-123")
        self.assertEqual(principal.email, "owner@example.com")
        self.assertEqual(principal.audience, "control-room-audience")
        self.assertEqual(principal.auth_strength, "phishing_resistant")
        self.assertEqual(principal.auth_methods, ("passkey", "webauthn"))

    def test_disabled_control_room_denies_access(self):
        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "disabled",
        ):
            authorize_control_room_identity(
                _identity(),
                policy=_policy(enabled=False),
                now_epoch=NOW,
            )

    def test_unverified_token_is_denied(self):
        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "cryptographically verified",
        ):
            authorize_control_room_identity(
                _identity(token_verified=False),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_missing_subject_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "subject"):
            authorize_control_room_identity(
                _identity(subject=""),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_missing_email_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "email"):
            authorize_control_room_identity(
                _identity(email=""),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_non_allowlisted_email_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "allowlisted"):
            authorize_control_room_identity(
                _identity(email="attacker@example.com"),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_similar_email_is_not_treated_as_allowlisted(self):
        with self.assertRaises(ControlRoomAccessDenied):
            authorize_control_room_identity(
                _identity(email="owner@example.com.attacker.test"),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_wrong_issuer_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "issuer"):
            authorize_control_room_identity(
                _identity(issuer="https://evil.example"),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_wrong_audience_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "audience"):
            authorize_control_room_identity(
                _identity(audiences=("another-app",)),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_expected_audience_can_be_one_of_multiple_claim_values(self):
        principal = authorize_control_room_identity(
            _identity(
                audiences=(
                    "another-app",
                    "control-room-audience",
                )
            ),
            policy=_policy(),
            now_epoch=NOW,
        )
        self.assertEqual(principal.audience, "control-room-audience")

    def test_expired_token_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "expired"):
            authorize_control_room_identity(
                _identity(expires_at_epoch=NOW - 61),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_token_issued_too_far_in_future_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "issued in the future"):
            authorize_control_room_identity(
                _identity(issued_at_epoch=NOW + 61),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_authentication_time_too_far_in_future_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "authentication time"):
            authorize_control_room_identity(
                _identity(authenticated_at_epoch=NOW + 61),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_invalid_token_lifetime_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "lifetime"):
            authorize_control_room_identity(
                _identity(
                    issued_at_epoch=NOW - 60,
                    expires_at_epoch=NOW - 60,
                ),
                policy=_policy(),
                now_epoch=NOW - 60,
            )

    def test_missing_token_timestamp_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "timestamps"):
            authorize_control_room_identity(
                _identity(authenticated_at_epoch=0),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_stale_authentication_is_denied(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "too old"):
            authorize_control_room_identity(
                _identity(authenticated_at_epoch=NOW - 3661),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_mfa_is_insufficient_when_phishing_resistant_is_required(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "stronger"):
            authorize_control_room_identity(
                _identity(auth_strength="mfa"),
                policy=_policy(),
                now_epoch=NOW,
            )

    def test_policy_can_require_mfa_without_requiring_phishing_resistance(self):
        principal = authorize_control_room_identity(
            _identity(auth_strength="mfa"),
            policy=_policy(minimum_auth_strength="mfa"),
            now_epoch=NOW,
        )
        self.assertEqual(principal.auth_strength, "mfa")

    def test_fresh_auth_override_supports_future_step_up_routes(self):
        with self.assertRaisesRegex(ControlRoomAccessDenied, "too old"):
            authorize_control_room_identity(
                _identity(authenticated_at_epoch=NOW - 361),
                policy=_policy(),
                now_epoch=NOW,
                max_auth_age_seconds=300,
            )

    def test_empty_allowlist_is_misconfiguration_when_enabled(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "allowlisted email",
        ):
            validate_control_room_policy(
                _policy(allowed_emails=())
            )

    def test_missing_issuer_is_misconfiguration(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "issuer",
        ):
            validate_control_room_policy(
                _policy(expected_issuer="")
            )

    def test_missing_audience_is_misconfiguration(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "audience",
        ):
            validate_control_room_policy(
                _policy(expected_audience="")
            )

    def test_nonpositive_session_age_is_misconfiguration(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "session age",
        ):
            validate_control_room_policy(
                _policy(max_session_age_seconds=0)
            )

    def test_negative_clock_skew_is_misconfiguration(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "clock skew",
        ):
            validate_control_room_policy(
                _policy(clock_skew_seconds=-1)
            )

    def test_nonpositive_step_up_age_is_misconfiguration(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "age limit",
        ):
            authorize_control_room_identity(
                _identity(),
                policy=_policy(),
                now_epoch=NOW,
                max_auth_age_seconds=0,
            )

    def test_disabled_policy_does_not_require_provider_configuration(self):
        validate_control_room_policy(
            _policy(
                enabled=False,
                allowed_emails=(),
                expected_issuer="",
                expected_audience="",
            )
        )


if __name__ == "__main__":
    unittest.main()
