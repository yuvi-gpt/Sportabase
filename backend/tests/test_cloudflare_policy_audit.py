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
from app.security.control_room import ControlRoomSecurityMisconfigured


NOW = 2_000_000_000
ACCOUNT = "account123"
APP = "app-123"
AUD = "control-room-audience"
IDP = "google-idp"
OWNER = "owner@example.com"


def _config(**overrides):
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
            "allowed_authenticators": ["security_key", "biometrics"],
            "mfa_disabled": False,
            "session_duration": "0m",
        },
    }
    value.update(overrides)
    return value


def _idp(**overrides):
    value = {"id": IDP, "name": "Google", "type": "google"}
    value.update(overrides)
    return value


def _allow_policy(**overrides):
    value = {
        "id": "policy-allow-owner",
        "name": "Allow owner only",
        "decision": "allow",
        "include": [{"email": {"email": OWNER}}],
        "require": [],
        "exclude": [],
        "session_duration": "15m",
    }
    value.update(overrides)
    return value


def _block_policy():
    return {
        "id": "policy-block-rest",
        "name": "Block rest",
        "decision": "block",
        "include": [{"everyone": {}}],
        "session_duration": "15m",
    }


class FakeCloudflareApi:
    def __init__(self, *, application=None, identity_provider=None, pages=None):
        self.application = deepcopy(application or _application())
        self.identity_provider = deepcopy(identity_provider or _idp())
        self.pages = deepcopy(pages or [[_allow_policy(), _block_policy()]])
        self.calls = []

    def get_json(self, url, api_token, timeout_seconds):
        self.calls.append((url, api_token, timeout_seconds))
        app_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}/access/apps/{APP}"
        )
        idp_url = (
            f"{CLOUDFLARE_API_ORIGIN}/accounts/{ACCOUNT}"
            f"/access/identity_providers/{IDP}"
        )

        if url == app_url:
            return {"success": True, "result": deepcopy(self.application)}
        if url == idp_url:
            return {"success": True, "result": deepcopy(self.identity_provider)}

        prefix = app_url + "/policies?per_page=100&page="
        if url.startswith(prefix):
            page = int(url[len(prefix):])
            result = self.pages[page - 1] if page <= len(self.pages) else []
            return {
                "success": True,
                "result": deepcopy(result),
                "result_info": {
                    "page": page,
                    "total_pages": len(self.pages),
                },
            }

        raise AssertionError("unexpected Cloudflare URL: " + url)


def _audit(api, *, config=None, token="read-only-token"):
    return audit_cloudflare_control_room_policy(
        config=config or _config(),
        api_token=token,
        get_json=api.get_json,
        now_epoch=NOW,
    )


class CloudflarePolicyAuditTests(unittest.TestCase):
    def assertAuditDenied(self, api, pattern, *, config=None, token="token"):
        with self.assertRaisesRegex(ControlRoomSecurityMisconfigured, pattern):
            _audit(api, config=config, token=token)

    def test_duration_parser_is_strict_and_supports_compound_units(self):
        self.assertEqual(parse_cloudflare_duration_seconds("0m"), 0)
        self.assertEqual(parse_cloudflare_duration_seconds("15m"), 900)
        self.assertEqual(parse_cloudflare_duration_seconds("1h30m"), 5400)
        self.assertEqual(parse_cloudflare_duration_seconds("1000ms"), 1)
        with self.assertRaisesRegex(ControlRoomSecurityMisconfigured, "whole seconds"):
            parse_cloudflare_duration_seconds("1500ms")
        with self.assertRaisesRegex(ControlRoomSecurityMisconfigured, "invalid"):
            parse_cloudflare_duration_seconds("15 minutes")

    def test_happy_path_issues_verified_secret_free_attestation(self):
        api = FakeCloudflareApi()
        result = _audit(api, token="TOP-SECRET-TOKEN")

        self.assertEqual(result.version, CLOUDFLARE_POLICY_AUDIT_VERSION)
        self.assertEqual(result.application_id, APP)
        self.assertEqual(result.application_audience, AUD)
        self.assertEqual(result.identity_provider_id, IDP)
        self.assertEqual(result.identity_provider_type, "google")
        self.assertEqual(result.allow_policy_ids, ("policy-allow-owner",))
        self.assertEqual(result.audited_policy_count, 2)
        self.assertTrue(result.attestation.verified)
        self.assertEqual(result.attestation.verified_at_epoch, NOW)
        self.assertEqual(
            result.attestation.allowed_authenticators,
            ("security_key", "biometrics"),
        )
        self.assertEqual(result.attestation.mfa_session_duration_seconds, 0)
        self.assertNotIn("TOP-SECRET-TOKEN", str(result.as_dict()))
        self.assertEqual(len(api.calls), 3)
        self.assertTrue(all(call[2] == 7 for call in api.calls))

    def test_google_workspace_idp_is_also_accepted(self):
        result = _audit(
            FakeCloudflareApi(identity_provider=_idp(type="google-apps"))
        )
        self.assertEqual(result.identity_provider_type, "google-apps")

    def test_missing_token_or_unsafe_identifier_fails_before_http(self):
        api = FakeCloudflareApi()
        self.assertAuditDenied(api, "API token", token="")
        self.assertEqual(api.calls, [])

        api = FakeCloudflareApi()
        self.assertAuditDenied(
            api,
            "account id",
            config=_config(account_id="../evil"),
        )
        self.assertEqual(api.calls, [])

    def test_application_identity_and_audience_are_pinned(self):
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(id="other-app")),
            "application id",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(aud="wrong")),
            "audience",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(
                application=_application(allowed_idps=[IDP, "another-idp"])
            ),
            "only the approved Google IdP",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(identity_provider=_idp(type="onetimepin")),
            "not Google",
        )

    def test_application_session_and_mfa_must_be_strict(self):
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(session_duration="1h")),
            "session duration",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(mfa_config=None)),
            "MFA configuration is missing",
        )

        disabled = deepcopy(_application()["mfa_config"])
        disabled["mfa_disabled"] = True
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(mfa_config=disabled)),
            "MFA is disabled",
        )

        weak = deepcopy(_application()["mfa_config"])
        weak["allowed_authenticators"] = ["security_key", "totp"]
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(mfa_config=weak)),
            "non-phishing-resistant",
        )

        reusable = deepcopy(_application()["mfa_config"])
        reusable["session_duration"] = "1h"
        self.assertAuditDenied(
            FakeCloudflareApi(application=_application(mfa_config=reusable)),
            "every login",
        )

    def test_allow_policy_must_use_only_exact_approved_email_selectors(self):
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[
                    _allow_policy(
                        include=[{"email_domain": {"domain": "example.com"}}]
                    )
                ]]
            ),
            "broad selector",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[_allow_policy(include=[{"everyone": {}}])]]
            ),
            "broad selector",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[
                    _allow_policy(
                        include=[{"email": {"email": "attacker@example.com"}}]
                    )
                ]]
            ),
            "unapproved email",
        )

    def test_bypass_and_service_auth_policies_are_forbidden(self):
        for decision in ("bypass", "service_auth"):
            with self.subTest(decision=decision):
                self.assertAuditDenied(
                    FakeCloudflareApi(
                        pages=[[
                            _allow_policy(),
                            {
                                "id": "unsafe-policy",
                                "decision": decision,
                                "include": [{"everyone": {}}],
                            },
                        ]]
                    ),
                    "bypass or non-user",
                )

    def test_policy_level_session_and_mfa_cannot_weaken_application(self):
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[_allow_policy(session_duration="2h")]]
            ),
            "session duration",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[
                    _allow_policy(
                        mfa_config={
                            "allowed_authenticators": ["security_key", "totp"],
                            "mfa_disabled": False,
                            "session_duration": "0m",
                        }
                    )
                ]]
            ),
            "non-phishing-resistant",
        )
        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[
                    _allow_policy(
                        mfa_config={
                            "allowed_authenticators": ["security_key"],
                            "mfa_disabled": True,
                            "session_duration": "0m",
                        }
                    )
                ]]
            ),
            "MFA is disabled",
        )

    def test_at_least_one_allow_policy_is_required(self):
        self.assertAuditDenied(
            FakeCloudflareApi(pages=[[_block_policy()]]),
            "no exact-email allow policy",
        )

    def test_all_policy_pages_are_audited(self):
        api = FakeCloudflareApi(
            pages=[[_allow_policy()], [_block_policy()]]
        )
        result = _audit(api)
        self.assertEqual(result.audited_policy_count, 2)
        self.assertEqual(
            len([call for call in api.calls if "/policies?" in call[0]]),
            2,
        )

        self.assertAuditDenied(
            FakeCloudflareApi(
                pages=[[_allow_policy()], [_block_policy()]]
            ),
            "all policies were inspected",
            config=_config(max_policy_pages=1),
        )

    def test_cloudflare_api_failure_fails_closed(self):
        def failed(url, api_token, timeout_seconds):
            del url, api_token, timeout_seconds
            return {"success": False, "result": None}

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


if __name__ == "__main__":
    unittest.main()
