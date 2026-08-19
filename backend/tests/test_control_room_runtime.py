from __future__ import annotations

import time
import unittest

from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request

from app.security.cloudflare_policy_audit import (
    CLOUDFLARE_API_ORIGIN,
)
from app.security.control_room import (
    ControlRoomAccessDenied,
    ControlRoomSecurityMisconfigured,
)
from app.security.control_room_runtime import (
    CONTROL_ROOM_RUNTIME_VERSION,
    ControlRoomPolicyAttestationCache,
    ControlRoomRuntimeConfig,
    build_control_room_runtime_guard,
    build_default_control_room_guard,
    validate_control_room_runtime_config,
)


TEAM = "https://team.cloudflareaccess.com"
ACCOUNT = "account123"
APP = "app-123"
AUDIENCE = "control-room-audience"
IDP = "google-idp"
OWNER = "owner@example.com"
SECRET = "TOP-SECRET-READ-ONLY-TOKEN"


def _config(**overrides) -> ControlRoomRuntimeConfig:
    values = {
        "enabled": True,
        "team_domain": TEAM,
        "account_id": ACCOUNT,
        "application_id": APP,
        "application_audience": AUDIENCE,
        "identity_provider_id": IDP,
        "allowed_emails": (OWNER,),
        "policy_audit_api_token": SECRET,
        "policy_cache_ttl_seconds": 240,
        "request_timeout_seconds": 7,
        "max_session_duration_seconds": 900,
        "max_policy_pages": 3,
        "clock_skew_seconds": 60,
    }
    values.update(overrides)
    return ControlRoomRuntimeConfig(**values)


def _request(token: str) -> Request:
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
                    b"cf-access-jwt-assertion",
                    token.encode("utf-8"),
                )
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )


class FakePolicyApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.fail = False

    def __call__(
        self,
        url: str,
        api_token: str,
        timeout_seconds: int,
    ):
        self.calls.append(
            (url, api_token, timeout_seconds)
        )
        if self.fail:
            return {
                "success": False,
                "errors": [{"message": "unavailable"}],
                "result": None,
            }

        app_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}"
            f"/access/apps/{APP}"
        )
        idp_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}"
            f"/access/identity_providers/{IDP}"
        )
        policy_url = (
            app_url
            + "/policies?per_page=100&page=1"
        )

        if url == app_url:
            return {
                "success": True,
                "result": {
                    "id": APP,
                    "name": "Sportabase Control Room",
                    "aud": AUDIENCE,
                    "allowed_idps": [IDP],
                    "session_duration": "15m",
                    "mfa_config": {
                        "allowed_authenticators": [
                            "security_key",
                            "biometrics",
                        ],
                        "mfa_disabled": False,
                        "session_duration": "0m",
                    },
                },
            }

        if url == idp_url:
            return {
                "success": True,
                "result": {
                    "id": IDP,
                    "name": "Google",
                    "type": "google",
                },
            }

        if url == policy_url:
            return {
                "success": True,
                "result": [
                    {
                        "id": "owner-only",
                        "decision": "allow",
                        "include": [
                            {
                                "email": {
                                    "email": OWNER,
                                }
                            }
                        ],
                        "session_duration": "15m",
                    },
                    {
                        "id": "block-rest",
                        "decision": "block",
                        "include": [{"everyone": {}}],
                    },
                ],
                "result_info": {
                    "page": 1,
                    "total_pages": 1,
                },
            }

        raise AssertionError(
            "unexpected Cloudflare API URL: " + url
        )


class StaticJwksFactory:
    def __init__(self, public_key) -> None:
        self.public_key = public_key
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        public_key = self.public_key

        class Client:
            def get_signing_key_from_jwt(self, encoded):
                del encoded
                return SimpleNamespace(key=public_key)

        return Client()


def _signed_token(
    private_key,
    *,
    email: str = OWNER,
    now_epoch: int | None = None,
) -> str:
    current = (
        int(time.time())
        if now_epoch is None
        else int(now_epoch)
    )
    return jwt.encode(
        {
            "type": "app",
            "aud": [AUDIENCE],
            "email": email,
            "exp": current + 600,
            "iat": current - 30,
            "nbf": current - 30,
            "iss": TEAM,
            "sub": "owner-subject",
        },
        private_key,
        algorithm="RS256",
        headers={
            "kid": "offline-runtime-key",
            "typ": "JWT",
        },
    )


class ControlRoomRuntimeTests(unittest.TestCase):
    def test_secret_is_redacted_from_runtime_config_repr(self):
        value = repr(_config())
        self.assertNotIn(SECRET, value)
        self.assertNotIn(
            "TOP-SECRET",
            value,
        )

    def test_default_guard_build_is_network_side_effect_free(self):
        guard = build_default_control_room_guard()
        self.assertTrue(callable(guard))
        self.assertEqual(
            getattr(guard, "runtime_version"),
            CONTROL_ROOM_RUNTIME_VERSION,
        )

    def test_disabled_runtime_fails_closed(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "disabled",
        ):
            validate_control_room_runtime_config(
                _config(enabled=False)
            )

    def test_cache_ttl_cannot_exceed_attestation_window(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "1 and 300",
        ):
            validate_control_room_runtime_config(
                _config(policy_cache_ttl_seconds=301)
            )

    def test_session_window_is_capped_at_fifteen_minutes(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "1 and 900",
        ):
            validate_control_room_runtime_config(
                _config(max_session_duration_seconds=901)
            )

    def test_policy_cache_reuses_fresh_audit_and_refreshes_after_ttl(self):
        now = [2_000_000_000]
        api = FakePolicyApi()
        cache = ControlRoomPolicyAttestationCache(
            config=_config(),
            get_json=api,
            now_epoch_resolver=lambda: now[0],
        )

        first = cache.get_result()
        self.assertTrue(first.attestation.verified)
        self.assertEqual(len(api.calls), 3)
        self.assertTrue(
            all(call[1] == SECRET for call in api.calls)
        )

        second = cache.get_result()
        self.assertIs(first, second)
        self.assertEqual(len(api.calls), 3)

        now[0] += 239
        third = cache.get_result()
        self.assertIs(first, third)
        self.assertEqual(len(api.calls), 3)

        now[0] += 2
        refreshed = cache.get_result()
        self.assertIsNot(first, refreshed)
        self.assertEqual(len(api.calls), 6)
        self.assertEqual(
            refreshed.attestation.verified_at_epoch,
            now[0],
        )

    def test_stale_policy_is_not_used_when_refresh_fails(self):
        now = [2_000_000_000]
        api = FakePolicyApi()
        cache = ControlRoomPolicyAttestationCache(
            config=_config(),
            get_json=api,
            now_epoch_resolver=lambda: now[0],
        )
        cache.get_result()
        self.assertEqual(len(api.calls), 3)

        now[0] += 241
        api.fail = True
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "reported failure",
        ):
            cache.get_result()

        self.assertEqual(len(api.calls), 4)

    def test_malformed_token_never_touches_policy_audit_secret(self):
        api = FakePolicyApi()
        guard = build_control_room_runtime_guard(
            config=_config(),
            policy_audit_get_json=api,
        )

        with self.assertRaises(ControlRoomAccessDenied):
            guard(_request("not-a-jwt"))

        self.assertEqual(api.calls, [])

    def test_valid_owner_gets_phishing_resistant_principal(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        jwks = StaticJwksFactory(
            private_key.public_key()
        )
        api = FakePolicyApi()
        guard = build_control_room_runtime_guard(
            config=_config(),
            policy_audit_get_json=api,
            jwks_client_factory=jwks,
        )

        token = _signed_token(private_key)
        principal = guard(_request(token))

        self.assertEqual(principal.email, OWNER)
        self.assertEqual(
            principal.auth_strength,
            "phishing_resistant",
        )
        self.assertIn(
            "cloudflare_independent_mfa",
            principal.auth_methods,
        )
        self.assertIn(
            "security_key",
            principal.auth_methods,
        )
        self.assertIn(
            "biometrics",
            principal.auth_methods,
        )
        self.assertEqual(len(api.calls), 3)
        self.assertEqual(
            jwks.urls,
            [TEAM + "/cdn-cgi/access/certs"],
        )

        # A second valid request re-verifies the caller token but does not
        # re-use the privileged Cloudflare policy API token while the audited
        # policy attestation is still fresh.
        again = guard(_request(token))
        self.assertEqual(again.email, OWNER)
        self.assertEqual(len(api.calls), 3)
        self.assertEqual(len(jwks.urls), 2)

    def test_signed_unapproved_email_is_denied(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        jwks = StaticJwksFactory(
            private_key.public_key()
        )
        api = FakePolicyApi()
        guard = build_control_room_runtime_guard(
            config=_config(),
            policy_audit_get_json=api,
            jwks_client_factory=jwks,
        )

        token = _signed_token(
            private_key,
            email="attacker@example.com",
        )
        with self.assertRaisesRegex(
            ControlRoomAccessDenied,
            "allowlisted",
        ):
            guard(_request(token))

        self.assertEqual(len(api.calls), 3)


if __name__ == "__main__":
    unittest.main()
