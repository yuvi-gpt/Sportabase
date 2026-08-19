from __future__ import annotations

import unittest

from copy import deepcopy

from app.security.cloudflare_policy_audit import (
    CLOUDFLARE_API_ORIGIN,
    CLOUDFLARE_POLICY_AUDIT_VERSION,
    CloudflarePolicyAuditConfig,
    audit_cloudflare_control_room_policy,
    parse_cloudflare_duration_seconds,
)
from app.security.control_room import (
    ControlRoomSecurityMisconfigured,
)


NOW = 2_000_000_000
ACCOUNT = "account123"
APP = "app-123"
AUD = "control-room-audience"
IDP = "google-idp"
OWNER = "owner@example.com"


def _config(**overrides) -> CloudflarePolicyAuditConfig:
    values = {
        "account_id": ACCOUNT,
        "application_id": APP,
        "application_audience": AUD,
        "expected_identity_provider_id": IDP,
        "allowed_emails": (OWNER,),
        "request_timeout_seconds": 7,
        "max_application_session_duration_seconds": 900,
        "max_policy_pages": 3,
    }
    values.update(overrides)
    return CloudflarePolicyAuditConfig(**values)


def _application(**overrides):
    value = {
        "id": APP,
        "name": "Sportabase Control Room",
        "aud": AUD,
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
    }
    value.update(overrides)
    return value


def _idp(**overrides):
    value = {
        "id": IDP,
        "name": "Google",
        "type": "google",
    }
    value.update(overrides)
    return value


def _allow_policy(**overrides):
    value = {
        "id": "policy-allow-owner",
        "name": "Allow owner only",
        "decision": "allow",
        "include": [
            {
                "email": {
                    "email": OWNER,
                }
            }
        ],
        "require": [],
        "exclude": [],
        "session_duration": "15m",
    }
    value.update(overrides)
    return value


def _block_policy(**overrides):
    value = {
        "id": "policy-block-rest",
        "name": "Block rest",
        "decision": "block",
        "include": [{"everyone": {}}],
        "session_duration": "15m",
    }
    value.update(overrides)
    return value


class FakeCloudflareApi:
    def __init__(
        self,
        *,
        application=None,
        identity_provider=None,
        policy_pages=None,
    ):
        self.application = (
            deepcopy(application)
            if application is not None
            else _application()
        )
        self.identity_provider = (
            deepcopy(identity_provider)
            if identity_provider is not None
            else _idp()
        )
        self.policy_pages = (
            deepcopy(policy_pages)
            if policy_pages is not None
            else [[_allow_policy(), _block_policy()]]
        )
        self.calls = []

    def get_json(self, url, api_token, timeout_seconds):
        self.calls.append(
            (url, api_token, timeout_seconds)
        )

        app_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}"
            f"/access/apps/{APP}"
        )
        idp_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}"
            f"/access/identity_providers/{IDP}"
        )

        if url == app_url:
            return {
                "success": True,
                "result": deepcopy(self.application),
            }

        if url == idp_url:
            return {
                "success": True,
                "result": deepcopy(self.identity_provider),
            }

        prefix = app_url + "/policies?per_page=100&page="
        if url.startswith(prefix):
            page = int(url[len(prefix):])
            if page < 1 or page > len(self.policy_pages):
                return {
                    "success": True,
                    "result": [],
                    "result_info": {
                        "total_pages": len(self.policy_pages),
                    },
                }

            return {
                "success": True,
                "result": deepcopy(
                    self.policy_pages[page - 1]
                ),
                "result_info": {
                    "page": page,
                    "total_pages": len(self.policy_pages),
                },
            }

        raise AssertionError(
            "unexpected Cloudflare API URL: " + url
        )


class CloudflarePolicyAuditTests(unittest.TestCase):
    def test_duration_parser_supports_cloudflare_compound_units(self):
        self.assertEqual(
            parse_cloudflare_duration_seconds("0m"),
            0,
        )
        self.assertEqual(
            parse_cloudflare_duration_seconds("15m"),
            900,
        )
        self.assertEqual(
            parse_cloudflare_duration_seconds("1h30m"),
            5400,
        )
        self.assertEqual(
            parse_cloudflare_duration_seconds("500ms"),
            0,
        )

    def test_fractional_seconds_that_do_not_resolve_whole_are_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "whole seconds",
        ):
            parse_cloudflare_duration_seconds("1500ms")

    def test_invalid_duration_is_rejected(self):
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "invalid",
        ):
            parse_cloudflare_duration_seconds("15 minutes")

    def test_happy_path_produces_verified_attestation(self):
        api = FakeCloudflareApi()

        result = audit_cloudflare_control_room_policy(
            config=_config(),
            api_token="read-only-token",
            get_json=api.get_json,
            now_epoch=NOW,
        )

        self.assertEqual(
            result.version,
            CLOUDFLARE_POLICY_AUDIT_VERSION,
        )
        self.assertEqual(result.application_id, APP)
        self.assertEqual(
            result.application_name,
            "Sportabase Control Room",
        )
        self.assertEqual(result.application_audience, AUD)
        self.assertEqual(result.identity_provider_id, IDP)
        self.assertEqual(result.identity_provider_type, "google")
        self.assertEqual(
            result.allow_policy_ids,
            ("policy-allow-owner",),
        )
        self.assertEqual(result.audited_policy_count, 2)

        attestation = result.attestation
        self.assertTrue(attestation.verified)
        self.assertEqual(attestation.verified_at_epoch, NOW)
        self.assertEqual(attestation.application_audience, AUD)
        self.assertEqual(
            attestation.allowed_authenticators,
            ("security_key", "biometrics"),
        )
        self.assertFalse(attestation.mfa_disabled)
        self.assertEqual(
            attestation.mfa_session_duration_seconds,
            0,
        )
        self.assertEqual(
            attestation.source,
            "cloudflare_access_policy_api",
        )

        self.assertEqual(len(api.calls), 3)
        self.assertTrue(
            all(call[1] == "read-only-token" for call in api.calls)
        )
        self.assertTrue(
            all(call[2] == 7 for call in api.calls)
        )

    def test_google_workspace_idp_is_allowed(self):
        api = FakeCloudflareApi(
            identity_provider=_idp(type="google-apps")
        )
        result = audit_cloudflare_control_room_policy(
            config=_config(),
            api_token="token",
            get_json=api.get_json,
            now_epoch=NOW,
        )
        self.assertEqual(
            result.identity_provider_type,
            "google-apps",
        )

    def test_missing_api_token_fails_closed_before_http(self):
        api = FakeCloudflareApi()
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "API token",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="",
                get_json=api.get_json,
                now_epoch=NOW,
            )
        self.assertEqual(api.calls, [])

    def test_invalid_identifier_fails_before_http(self):
        api = FakeCloudflareApi()
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "account id",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(account_id="../evil"),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )
        self.assertEqual(api.calls, [])

    def test_wrong_application_id_fails_closed(self):
        api = FakeCloudflareApi(
            application=_application(id="other-app")
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "application id",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_wrong_application_audience_fails_closed(self):
        api = FakeCloudflareApi(
            application=_application(aud="wrong-audience")
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "audience",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_application_must_allow_only_expected_idp(self):
        api = FakeCloudflareApi(
            application=_application(
                allowed_idps=[IDP, "onetimepin"]
            )
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "only the approved Google IdP",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_identity_provider_must_be_google(self):
        api = FakeCloudflareApi(
            identity_provider=_idp(type="onetimepin")
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "not Google",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_application_session_must_be_short(self):
        api = FakeCloudflareApi(
            application=_application(
                session_duration="1h"
            )
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "session duration",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_application_mfa_is_required(self):
        api = FakeCloudflareApi(
            application=_application(mfa_config=None)
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "MFA configuration is missing",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_application_mfa_cannot_be_disabled(self):
        mfa = deepcopy(_application()["mfa_config"])
        mfa["mfa_disabled"] = True
        api = FakeCloudflareApi(
            application=_application(mfa_config=mfa)
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "MFA is disabled",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_totp_is_rejected_at_application_level(self):
        mfa = deepcopy(_application()["mfa_config"])
        mfa["allowed_authenticators"] = [
            "security_key",
            "totp",
        ]
        api = FakeCloudflareApi(
            application=_application(mfa_config=mfa)
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "non-phishing-resistant",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_mfa_session_reuse_is_rejected(self):
        mfa = deepcopy(_application()["mfa_config"])
        mfa["session_duration"] = "1h"
        api = FakeCloudflareApi(
            application=_application(mfa_config=mfa)
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "every login",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_broad_email_domain_allow_policy_is_rejected(self):
        policy = _allow_policy(
            include=[
                {
                    "email_domain": {
                        "domain": "example.com",
                    }
                }
            ]
        )
        api = FakeCloudflareApi(
            policy_pages=[[policy]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "broad selector",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_everyone_allow_policy_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(
                    include=[{"everyone": {}}]
                )
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "broad selector",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_unapproved_email_allow_policy_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(
                    include=[
                        {
                            "email": {
                                "email": "attacker@example.com",
                            }
                        }
                    ]
                )
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "unapproved email",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_bypass_policy_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(),
                {
                    "id": "bypass",
                    "decision": "bypass",
                    "include": [{"everyone": {}}],
                },
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "bypass or non-user",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_service_auth_policy_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(),
                {
                    "id": "service",
                    "decision": "service_auth",
                    "include": [{"everyone": {}}],
                },
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "bypass or non-user",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_allow_policy_session_must_be_short(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(session_duration="2h")
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "session duration",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_policy_level_totp_override_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(
                    mfa_config={
                        "allowed_authenticators": [
                            "security_key",
                            "totp",
                        ],
                        "mfa_disabled": False,
                        "session_duration": "0m",
                    }
                )
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "non-phishing-resistant",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_policy_level_mfa_disable_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[
                _allow_policy(
                    mfa_config={
                        "allowed_authenticators": [
                            "security_key",
                        ],
                        "mfa_disabled": True,
                        "session_duration": "0m",
                    }
                )
            ]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "MFA is disabled",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_no_allow_policy_is_rejected(self):
        api = FakeCloudflareApi(
            policy_pages=[[_block_policy()]]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "no exact-email allow policy",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_policy_pagination_is_fully_audited(self):
        api = FakeCloudflareApi(
            policy_pages=[
                [_allow_policy()],
                [_block_policy()],
            ]
        )
        result = audit_cloudflare_control_room_policy(
            config=_config(),
            api_token="token",
            get_json=api.get_json,
            now_epoch=NOW,
        )
        self.assertEqual(result.audited_policy_count, 2)
        policy_calls = [
            call
            for call in api.calls
            if "/policies?" in call[0]
        ]
        self.assertEqual(len(policy_calls), 2)

    def test_policy_page_limit_fails_closed(self):
        api = FakeCloudflareApi(
            policy_pages=[
                [_allow_policy()],
                [_block_policy()],
            ]
        )
        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "all policies were inspected",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(max_policy_pages=1),
                api_token="token",
                get_json=api.get_json,
                now_epoch=NOW,
            )

    def test_cloudflare_api_failure_fails_closed(self):
        def failed(url, api_token, timeout_seconds):
            del url, api_token, timeout_seconds
            return {
                "success": False,
                "errors": [{"message": "nope"}],
                "result": None,
            }

        with self.assertRaisesRegex(
            ControlRoomSecurityMisconfigured,
            "reported failure",
        ):
            audit_cloudflare_control_room_policy(
                config=_config(),
                api_token="token",
                get_json=failed,
                now_epoch=NOW,
            )

    def test_result_serialization_never_contains_api_token(self):
        api = FakeCloudflareApi()
        result = audit_cloudflare_control_room_policy(
            config=_config(),
            api_token="TOP-SECRET-TOKEN",
            get_json=api.get_json,
            now_epoch=NOW,
        )
        serialized = str(result.as_dict())
        self.assertNotIn("TOP-SECRET-TOKEN", serialized)


if __name__ == "__main__":
    unittest.main()
