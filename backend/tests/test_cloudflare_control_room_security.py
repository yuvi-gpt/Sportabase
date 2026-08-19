from __future__ import annotations

import unittest

from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.control_room_admin import build_router
from app.security.cloudflare_access import (
    CloudflareAccessVerifierConfig,
)
from app.security.cloudflare_control_room import (
    CLOUDFLARE_CONTROL_ROOM_ASSURANCE_VERSION,
    CloudflareIndependentMfaAssurancePolicy,
    CloudflareIndependentMfaAttestation,
    build_attested_independent_mfa_assurance_resolver,
    build_cloudflare_control_room_guard,
    normalize_cloudflare_authenticators,
    validate_independent_mfa_attestation,
    validate_independent_mfa_assurance_policy,
)
from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomSecurityMisconfigured,
    ControlRoomSecurityPolicy,
)


NOW = 2_000_000_000
TEAM = "https://team.cloudflareaccess.com"
AUDIENCE = "control-room-audience"
OWNER = "owner@example.com"


def _attestation(**overrides) -> CloudflareIndependentMfaAttestation:
    values = {
        "verified": True,
        "verified_at_epoch": NOW - 30,
        "application_audience": AUDIENCE,
        "allowed_authenticators": (
            "security_key",
            "biometrics",
        ),
        "mfa_disabled": False,
        "mfa_session_duration_seconds": 0,
        "source": "cloudflare_access_policy_api",
    }
    values.update(overrides)
    return CloudflareIndependentMfaAttestation(**values)


def _assurance_policy(**overrides) -> CloudflareIndependentMfaAssurancePolicy:
    values = {
        "max_attestation_age_seconds": 300,
        "max_application_token_lifetime_seconds": 900,
        "clock_skew_seconds": 60,
        "require_every_login": True,
    }
    values.update(overrides)
    return CloudflareIndependentMfaAssurancePolicy(**values)


def _authorization_policy(**overrides) -> ControlRoomSecurityPolicy:
    values = {
        "enabled": True,
        "allowed_emails": (OWNER,),
        "expected_issuer": TEAM,
        "expected_audience": AUDIENCE,
        "minimum_auth_strength": "phishing_resistant",
        "max_session_age_seconds": 900,
        "clock_skew_seconds": 60,
    }
    values.update(overrides)
    return ControlRoomSecurityPolicy(**values)


class StaticJwksClient:
    key = None
    observed_urls: list[str] = []

    def __init__(self, url: str):
        self.observed_urls.append(url)

    def get_signing_key_from_jwt(self, encoded: str):
        del encoded
        return SimpleNamespace(key=self.key)


class CloudflareControlRoomSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        StaticJwksClient.key = cls.private_key.public_key()

    def setUp(self):
        StaticJwksClient.observed_urls = []

    def _claims(self, **overrides):
        values = {
            "type": "app",
            "aud": [AUDIENCE],
            "email": OWNER,
            "exp": NOW + 600,
            "iat": NOW - 60,
            "nbf": NOW - 60,
            "iss": TEAM,
            "sub": "owner-123",
        }
        values.update(overrides)
        return values

    def _token(self, *, key=None, **claim_overrides):
        signing_key = key or self.private_key
        return jwt.encode(
            self._claims(**claim_overrides),
            signing_key,
            algorithm="RS256",
            headers={
                "kid": "control-room-test-key",
                "typ": "JWT",
            },
        )

    def _guard(self, **overrides):
        values = {
            "verifier_config": CloudflareAccessVerifierConfig(
                team_domain=TEAM,
                audience=AUDIENCE,
                clock_skew_seconds=60,
            ),
            "authorization_policy": _authorization_policy(),
            "mfa_attestation": _attestation(),
            "assurance_policy": _assurance_policy(),
            "jwks_client_factory": StaticJwksClient,
            "now_epoch_resolver": lambda: NOW,
        }
        values.update(overrides)
        return build_cloudflare_control_room_guard(**values)

    def _client(self, guard=None):
        app = FastAPI()
        app.include_router(
            build_router(
                require_control_room=guard or self._guard(),
            )
        )
        return TestClient(app)

    def test_version_is_stable(self):
        self.assertEqual(
            CLOUDFLARE_CONTROL_ROOM_ASSURANCE_VERSION,
            "sportabase-cloudflare-control-room-assurance-v1",
        )

    def test_authenticator_normalization_is_deduplicated(self):
        self.assertEqual(
            normalize_cloudflare_authenticators(
                (
                    " Security_Key ",
                    "security_key",
                    "BIOMETRICS",
                    "",
                )
            ),
            (
                "security_key",
                "biometrics",
            ),
        )

    def test_verified_phishing_resistant_attestation_passes(self):
        authenticators = validate_independent_mfa_attestation(
            _attestation(),
            expected_audience=AUDIENCE,
            policy=_assurance_policy(),
            now_epoch=NOW,
        )
        self.assertEqual(
            authenticators,
            ("security_key", "biometrics"),
        )

    def test_unverified_attestation_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "has not been verified",
        ):
            validate_independent_mfa_attestation(
                _attestation(verified=False),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_wrong_attestation_audience_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "audience",
        ):
            validate_independent_mfa_attestation(
                _attestation(application_audience="other-app"),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_disabled_mfa_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "disabled",
        ):
            validate_independent_mfa_attestation(
                _attestation(mfa_disabled=True),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_totp_is_rejected_for_control_room(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "non-phishing-resistant",
        ):
            validate_independent_mfa_attestation(
                _attestation(
                    allowed_authenticators=(
                        "security_key",
                        "totp",
                    )
                ),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_empty_authenticator_set_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "no allowed authenticators",
        ):
            validate_independent_mfa_attestation(
                _attestation(allowed_authenticators=()),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_nonzero_mfa_session_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "require every login",
        ):
            validate_independent_mfa_attestation(
                _attestation(mfa_session_duration_seconds=60),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_stale_attestation_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "stale",
        ):
            validate_independent_mfa_attestation(
                _attestation(verified_at_epoch=NOW - 361),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_future_attestation_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "future",
        ):
            validate_independent_mfa_attestation(
                _attestation(verified_at_epoch=NOW + 61),
                expected_audience=AUDIENCE,
                policy=_assurance_policy(),
                now_epoch=NOW,
            )

    def test_assurance_policy_requires_every_login(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "every login",
        ):
            validate_independent_mfa_assurance_policy(
                _assurance_policy(require_every_login=False)
            )

    def test_assurance_policy_rejects_nonpositive_attestation_age(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "attestation age",
        ):
            validate_independent_mfa_assurance_policy(
                _assurance_policy(max_attestation_age_seconds=0)
            )

    def test_assurance_policy_rejects_nonpositive_token_lifetime(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "token lifetime",
        ):
            validate_independent_mfa_assurance_policy(
                _assurance_policy(
                    max_application_token_lifetime_seconds=0
                )
            )

    def test_missing_signed_amr_can_use_verified_independent_mfa(self):
        resolver = build_attested_independent_mfa_assurance_resolver(
            attestation=_attestation(),
            expected_audience=AUDIENCE,
            policy=_assurance_policy(),
            now_epoch_resolver=lambda: NOW,
        )

        assurance = resolver(self._claims())

        self.assertEqual(
            assurance.authenticated_at_epoch,
            NOW - 60,
        )
        self.assertEqual(
            assurance.auth_strength,
            "phishing_resistant",
        )
        self.assertEqual(
            assurance.auth_methods,
            (
                "cloudflare_independent_mfa",
                "security_key",
                "biometrics",
            ),
        )

    def test_signed_amr_is_preserved_as_additional_evidence(self):
        resolver = build_attested_independent_mfa_assurance_resolver(
            attestation=_attestation(
                allowed_authenticators=("security_key",)
            ),
            expected_audience=AUDIENCE,
            policy=_assurance_policy(),
            now_epoch_resolver=lambda: NOW,
        )

        assurance = resolver(
            self._claims(
                amr=["hwk"],
                auth_time=NOW - 90,
            )
        )

        self.assertEqual(
            assurance.auth_methods,
            (
                "cloudflare_independent_mfa",
                "security_key",
                "hwk",
            ),
        )
        self.assertEqual(
            assurance.authenticated_at_epoch,
            NOW - 60,
        )

    def test_long_lived_application_token_is_denied(self):
        resolver = build_attested_independent_mfa_assurance_resolver(
            attestation=_attestation(),
            expected_audience=AUDIENCE,
            policy=_assurance_policy(
                max_application_token_lifetime_seconds=900
            ),
            now_epoch_resolver=lambda: NOW,
        )

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "lifetime exceeds",
        ):
            resolver(
                self._claims(
                    iat=NOW - 60,
                    exp=NOW + 900,
                )
            )

    def test_invalid_application_token_lifetime_is_denied(self):
        resolver = build_attested_independent_mfa_assurance_resolver(
            attestation=_attestation(),
            expected_audience=AUDIENCE,
            policy=_assurance_policy(),
            now_epoch_resolver=lambda: NOW,
        )

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "lifetime is invalid",
        ):
            resolver(
                self._claims(
                    iat=NOW,
                    exp=NOW,
                )
            )

    def test_full_route_allows_exact_owner_with_attested_mfa(self):
        response = self._client().get(
            "/admin/control-room/session",
            headers={
                "Cf-Access-Jwt-Assertion": self._token(),
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(
            payload["principal"]["email"],
            OWNER,
        )
        self.assertEqual(
            payload["principal"]["auth_strength"],
            "phishing_resistant",
        )
        self.assertIn(
            "cloudflare_independent_mfa",
            payload["principal"]["auth_methods"],
        )
        self.assertEqual(
            StaticJwksClient.observed_urls,
            [TEAM + "/cdn-cgi/access/certs"],
        )

    def test_full_route_denies_non_allowlisted_email(self):
        response = self._client().get(
            "/admin/control-room/session",
            headers={
                "Cf-Access-Jwt-Assertion": self._token(
                    email="attacker@example.com"
                ),
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_full_route_denies_forged_token(self):
        attacker_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        response = self._client().get(
            "/admin/control-room/session",
            headers={
                "Cf-Access-Jwt-Assertion": self._token(
                    key=attacker_key
                ),
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_full_route_denies_missing_token(self):
        response = self._client().get(
            "/admin/control-room/session"
        )
        self.assertEqual(response.status_code, 403)

    def test_full_route_fails_closed_when_attestation_is_stale(self):
        guard = self._guard(
            mfa_attestation=_attestation(
                verified_at_epoch=NOW - 361
            )
        )
        response = self._client(guard).get(
            "/admin/control-room/session",
            headers={
                "Cf-Access-Jwt-Assertion": self._token(),
            },
        )
        self.assertEqual(response.status_code, 503)

    def test_full_route_denies_token_lifetime_over_bound(self):
        response = self._client().get(
            "/admin/control-room/session",
            headers={
                "Cf-Access-Jwt-Assertion": self._token(
                    iat=NOW - 60,
                    exp=NOW + 900,
                ),
            },
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
