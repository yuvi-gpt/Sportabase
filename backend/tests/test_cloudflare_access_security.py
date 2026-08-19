from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request

from app.security.cloudflare_access import (
    CLOUDFLARE_ACCESS_JWT_ALGORITHM,
    CLOUDFLARE_ACCESS_JWT_HEADER,
    CloudflareAccessVerifierConfig,
    auth_strength_from_amr,
    cloudflare_access_certs_url,
    normalize_auth_methods,
    normalize_cloudflare_team_domain,
    verify_cloudflare_access_request,
    verify_cloudflare_access_token,
)
from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomSecurityMisconfigured,
    ControlRoomSecurityPolicy,
    authorize_control_room_identity,
)


TEAM_DOMAIN = "https://team.cloudflareaccess.com"
AUDIENCE = "control-room-audience"

_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_OTHER_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)


def _config(**overrides) -> CloudflareAccessVerifierConfig:
    values = {
        "team_domain": TEAM_DOMAIN,
        "audience": AUDIENCE,
        "clock_skew_seconds": 5,
    }
    values.update(overrides)
    return CloudflareAccessVerifierConfig(**values)


def _claims(**overrides):
    now = int(time.time())
    values = {
        "type": "app",
        "aud": [AUDIENCE],
        "email": "owner@example.com",
        "exp": now + 600,
        "iat": now - 60,
        "nbf": now - 60,
        "iss": TEAM_DOMAIN,
        "sub": "user-123",
        "auth_time": now - 120,
        "amr": ["hwk"],
    }
    values.update(overrides)
    return values


def _token(
    *,
    claims=None,
    key=_PRIVATE_KEY,
    algorithm=CLOUDFLARE_ACCESS_JWT_ALGORITHM,
    headers=None,
):
    token_headers = {
        "kid": "test-key",
        "typ": "JWT",
    }
    if headers:
        token_headers.update(headers)

    return jwt.encode(
        claims or _claims(),
        key,
        algorithm=algorithm,
        headers=token_headers,
    )


class _StaticJwksClient:
    def __init__(self, url, key=_PUBLIC_KEY):
        self.url = url
        self.key = key

    def get_signing_key_from_jwt(self, token):
        del token
        return SimpleNamespace(key=self.key)


def _static_jwks_factory(url):
    return _StaticJwksClient(url)


def _request_with_token(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/admin/control-room/session",
            "raw_path": b"/admin/control-room/session",
            "query_string": b"",
            "headers": [
                (
                    CLOUDFLARE_ACCESS_JWT_HEADER.encode("ascii"),
                    token.encode("utf-8"),
                )
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )


class CloudflareAccessSecurityTests(unittest.TestCase):
    def test_team_domain_is_normalized_and_certs_url_is_bounded(self):
        self.assertEqual(
            normalize_cloudflare_team_domain(
                "https://TEAM.cloudflareaccess.com/"
            ),
            TEAM_DOMAIN,
        )
        self.assertEqual(
            cloudflare_access_certs_url(TEAM_DOMAIN),
            TEAM_DOMAIN + "/cdn-cgi/access/certs",
        )

    def test_non_cloudflare_jwks_origin_is_rejected(self):
        for value in (
            "http://team.cloudflareaccess.com",
            "https://evil.example",
            "https://team.cloudflareaccess.com.evil.example",
            "https://team.cloudflareaccess.com/path",
            "https://user@team.cloudflareaccess.com",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ControlRoomSecurityMisconfigured):
                    normalize_cloudflare_team_domain(value)

    def test_valid_rs256_user_token_is_cryptographically_verified(self):
        observed_urls = []

        def factory(url):
            observed_urls.append(url)
            return _StaticJwksClient(url)

        identity = verify_cloudflare_access_token(
            _token(),
            config=_config(),
            jwks_client_factory=factory,
        )

        self.assertTrue(identity.token_verified)
        self.assertEqual(identity.subject, "user-123")
        self.assertEqual(identity.email, "owner@example.com")
        self.assertTrue(identity.email_verified)
        self.assertEqual(identity.issuer, TEAM_DOMAIN)
        self.assertEqual(identity.audiences, (AUDIENCE,))
        self.assertEqual(identity.auth_strength, "phishing_resistant")
        self.assertEqual(identity.auth_methods, ("hwk",))
        self.assertGreater(identity.authenticated_at_epoch, 0)
        self.assertEqual(
            observed_urls,
            [TEAM_DOMAIN + "/cdn-cgi/access/certs"],
        )

    def test_verified_identity_satisfies_sportabase_policy_when_assurance_exists(self):
        identity = verify_cloudflare_access_token(
            _token(),
            config=_config(),
            jwks_client_factory=_static_jwks_factory,
        )

        principal = authorize_control_room_identity(
            identity,
            policy=ControlRoomSecurityPolicy(
                enabled=True,
                allowed_emails=("owner@example.com",),
                expected_issuer=TEAM_DOMAIN,
                expected_audience=AUDIENCE,
                minimum_auth_strength="phishing_resistant",
                max_session_age_seconds=3600,
                clock_skew_seconds=60,
            ),
        )

        self.assertEqual(principal.email, "owner@example.com")
        self.assertEqual(principal.auth_strength, "phishing_resistant")

    def test_request_verifier_reads_only_access_assertion_header(self):
        identity = verify_cloudflare_access_request(
            _request_with_token(_token()),
            config=_config(),
            jwks_client_factory=_static_jwks_factory,
        )
        self.assertEqual(identity.subject, "user-123")

    def test_missing_access_assertion_header_is_denied(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "query_string": b"",
                "headers": [],
            }
        )
        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "missing",
        ):
            verify_cloudflare_access_request(
                request,
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_wrong_signature_is_denied(self):
        encoded = _token(key=_OTHER_PRIVATE_KEY)
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                encoded,
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_algorithm_confusion_is_denied_before_jwks_lookup(self):
        called = []

        def factory(url):
            called.append(url)
            return _StaticJwksClient(url)

        encoded = jwt.encode(
            _claims(),
            "not-an-rsa-key",
            algorithm="HS256",
            headers={"kid": "test-key"},
        )

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "algorithm",
        ):
            verify_cloudflare_access_token(
                encoded,
                config=_config(),
                jwks_client_factory=factory,
            )

        self.assertEqual(called, [])

    def test_missing_kid_is_denied_before_jwks_lookup(self):
        encoded = jwt.encode(
            _claims(),
            _PRIVATE_KEY,
            algorithm="RS256",
            headers={"typ": "JWT"},
        )

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "key id",
        ):
            verify_cloudflare_access_token(
                encoded,
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_wrong_audience_is_denied(self):
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                _token(),
                config=_config(audience="another-app"),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_wrong_issuer_is_denied(self):
        encoded = _token(
            claims=_claims(
                iss="https://other.cloudflareaccess.com"
            )
        )
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                encoded,
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_expired_token_is_denied(self):
        now = int(time.time())
        encoded = _token(
            claims=_claims(
                iat=now - 120,
                nbf=now - 120,
                exp=now - 30,
                auth_time=now - 120,
            )
        )
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                encoded,
                config=_config(clock_skew_seconds=0),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_future_not_before_token_is_denied(self):
        now = int(time.time())
        encoded = _token(
            claims=_claims(
                iat=now,
                nbf=now + 120,
                exp=now + 600,
                auth_time=now,
            )
        )
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                encoded,
                config=_config(clock_skew_seconds=0),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_missing_email_is_denied(self):
        claims = _claims()
        claims.pop("email")
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                _token(claims=claims),
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_service_token_shape_is_denied(self):
        claims = _claims(sub="")
        claims.pop("email")
        claims.pop("auth_time")
        claims.pop("amr")
        with self.assertRaises(ControlRoomAccessDenied):
            verify_cloudflare_access_token(
                _token(claims=claims),
                config=_config(),
                jwks_client_factory=_static_jwks_factory,
            )

    def test_missing_auth_time_stays_fail_closed(self):
        claims = _claims()
        claims.pop("auth_time")
        identity = verify_cloudflare_access_token(
            _token(claims=claims),
            config=_config(),
            jwks_client_factory=_static_jwks_factory,
        )

        self.assertEqual(identity.authenticated_at_epoch, 0)

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "timestamps",
        ):
            authorize_control_room_identity(
                identity,
                policy=ControlRoomSecurityPolicy(
                    enabled=True,
                    allowed_emails=("owner@example.com",),
                    expected_issuer=TEAM_DOMAIN,
                    expected_audience=AUDIENCE,
                    minimum_auth_strength="phishing_resistant",
                ),
            )

    def test_missing_amr_stays_unknown_and_cannot_satisfy_strong_policy(self):
        claims = _claims()
        claims.pop("amr")
        identity = verify_cloudflare_access_token(
            _token(claims=claims),
            config=_config(),
            jwks_client_factory=_static_jwks_factory,
        )

        self.assertEqual(identity.auth_strength, "unknown")
        self.assertEqual(identity.auth_methods, ())

        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "stronger",
        ):
            authorize_control_room_identity(
                identity,
                policy=ControlRoomSecurityPolicy(
                    enabled=True,
                    allowed_emails=("owner@example.com",),
                    expected_issuer=TEAM_DOMAIN,
                    expected_audience=AUDIENCE,
                    minimum_auth_strength="phishing_resistant",
                ),
            )

    def test_amr_strength_mapping_is_conservative(self):
        self.assertEqual(
            auth_strength_from_amr(
                normalize_auth_methods(["pwd", "hwk"])
            ),
            "phishing_resistant",
        )
        self.assertEqual(
            auth_strength_from_amr(
                normalize_auth_methods(["pwd", "otp"])
            ),
            "mfa",
        )
        self.assertEqual(
            auth_strength_from_amr(
                normalize_auth_methods(["pwd"])
            ),
            "single_factor",
        )
        self.assertEqual(
            auth_strength_from_amr(
                normalize_auth_methods(["unknown-method"])
            ),
            "unknown",
        )

    def test_empty_audience_is_configuration_error(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "audience",
        ):
            verify_cloudflare_access_token(
                _token(),
                config=_config(audience=""),
                jwks_client_factory=_static_jwks_factory,
            )


if __name__ == "__main__":
    unittest.main()
