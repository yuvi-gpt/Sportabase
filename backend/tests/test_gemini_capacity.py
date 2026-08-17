from __future__ import annotations

import os
import unittest

from contextlib import contextmanager
from datetime import datetime, timezone

from app.services import gemini_capacity


_ENV_KEYS = (
    "SPORTABASE_GEMINI_PROVIDER_RPM",
    "SPORTABASE_GEMINI_DISPATCH_RPM",
    "SPORTABASE_GEMINI_PROVIDER_TPM",
    "SPORTABASE_GEMINI_USABLE_TPM",
    "SPORTABASE_GEMINI_PROVIDER_RPD",
    "SPORTABASE_GEMINI_RPD_RESERVE",
    "SPORTABASE_GEMINI_MAX_ESTIMATED_INPUT_TOKENS",
    "SPORTABASE_GEMINI_MAX_PACING_WAIT_SECONDS",
    "SPORTABASE_GEMINI_GLOBAL_DAILY_CALL_CAP",
    "SPORTABASE_GEMINI_CLIENT_DAILY_CALL_CAP",
    "SPORTABASE_GLOBAL_DAILY_GEMINI_CALL_CAP",
    "SPORTABASE_CLIENT_DAILY_GEMINI_CALL_CAP",
    "SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_PROVIDER_RPM",
    "SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_PROVIDER_RPD",
    "SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_RPD_RESERVE",
)


@contextmanager
def clean_capacity_env(**values):
    previous = {
        key: os.environ.get(key)
        for key in _ENV_KEYS
    }
    try:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in values.items():
            os.environ[key] = str(value)
        yield
    finally:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value


class GeminiCapacityPolicyTests(unittest.TestCase):
    def test_defaults_match_observed_free_project_capacity(self):
        with clean_capacity_env():
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )

        self.assertEqual(policy.provider_rpm, 5)
        self.assertEqual(policy.dispatch_rpm, 4)
        self.assertEqual(policy.provider_tpm, 250_000)
        self.assertEqual(policy.usable_tpm, 200_000)
        self.assertEqual(policy.provider_rpd, 20)
        self.assertEqual(policy.rpd_reserve, 4)
        self.assertEqual(policy.usable_rpd, 16)
        self.assertEqual(
            policy.max_estimated_input_tokens,
            50_000,
        )
        self.assertEqual(
            policy.max_pacing_wait_seconds,
            75.0,
        )

    def test_default_sportabase_daily_caps_keep_headroom(self):
        with clean_capacity_env():
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )
            caps = gemini_capacity.sportabase_daily_caps(
                policy
            )

        self.assertEqual(caps, (16, 8))

    def test_legacy_large_caps_can_never_raise_safe_defaults(self):
        with clean_capacity_env(
            SPORTABASE_GLOBAL_DAILY_GEMINI_CALL_CAP=300,
            SPORTABASE_CLIENT_DAILY_GEMINI_CALL_CAP=30,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )
            caps = gemini_capacity.sportabase_daily_caps(
                policy
            )

        self.assertEqual(caps, (16, 8))

    def test_legacy_caps_may_only_reduce_capacity(self):
        with clean_capacity_env(
            SPORTABASE_GLOBAL_DAILY_GEMINI_CALL_CAP=10,
            SPORTABASE_CLIENT_DAILY_GEMINI_CALL_CAP=3,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )
            caps = gemini_capacity.sportabase_daily_caps(
                policy
            )

        self.assertEqual(caps, (10, 3))

    def test_new_client_cap_can_rise_within_safe_global_ceiling(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_CLIENT_DAILY_CALL_CAP=10,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )
            caps = gemini_capacity.sportabase_daily_caps(
                policy
            )

        self.assertEqual(caps, (16, 10))

    def test_new_global_cap_is_clamped_to_usable_provider_rpd(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_GLOBAL_DAILY_CALL_CAP=999,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )
            caps = gemini_capacity.sportabase_daily_caps(
                policy
            )

        self.assertEqual(caps[0], 16)

    def test_model_specific_provider_override_is_supported(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_PROVIDER_RPD=10,
            SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_RPD_RESERVE=2,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )

        self.assertEqual(policy.provider_rpd, 10)
        self.assertEqual(policy.rpd_reserve, 2)
        self.assertEqual(policy.usable_rpd, 8)

    def test_model_specific_rpm_override_is_supported(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_MODEL_GEMINI_2_5_FLASH_PROVIDER_RPM=7,
        ):
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )

        self.assertEqual(policy.provider_rpm, 7)
        self.assertEqual(policy.dispatch_rpm, 4)

    def test_dispatch_rpm_cannot_exceed_provider_rpm(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_PROVIDER_RPM=3,
            SPORTABASE_GEMINI_DISPATCH_RPM=4,
        ):
            with self.assertRaises(
                gemini_capacity.GeminiCapacityConfigurationError
            ):
                gemini_capacity.capacity_policy_for_model(
                    "gemini-test"
                )

    def test_usable_tpm_cannot_exceed_provider_tpm(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_PROVIDER_TPM=100,
            SPORTABASE_GEMINI_USABLE_TPM=101,
        ):
            with self.assertRaises(
                gemini_capacity.GeminiCapacityConfigurationError
            ):
                gemini_capacity.capacity_policy_for_model(
                    "gemini-test"
                )

    def test_rpd_reserve_must_leave_one_request(self):
        with clean_capacity_env(
            SPORTABASE_GEMINI_PROVIDER_RPD=20,
            SPORTABASE_GEMINI_RPD_RESERVE=20,
        ):
            with self.assertRaises(
                gemini_capacity.GeminiCapacityConfigurationError
            ):
                gemini_capacity.capacity_policy_for_model(
                    "gemini-test"
                )

    def test_provider_day_uses_pacific_calendar_not_utc_day(self):
        before_pacific_midnight = datetime(
            2026,
            8,
            17,
            6,
            59,
            tzinfo=timezone.utc,
        )
        after_pacific_midnight = datetime(
            2026,
            8,
            17,
            7,
            1,
            tzinfo=timezone.utc,
        )

        self.assertEqual(
            gemini_capacity.provider_usage_day(
                before_pacific_midnight
            ),
            "2026-08-16",
        )
        self.assertEqual(
            gemini_capacity.provider_usage_day(
                after_pacific_midnight
            ),
            "2026-08-17",
        )

    def test_naive_provider_day_input_is_treated_as_utc(self):
        current = datetime(
            2026,
            8,
            17,
            6,
            59,
        )

        self.assertEqual(
            gemini_capacity.provider_usage_day(
                current
            ),
            "2026-08-16",
        )

    def test_prompt_estimate_is_deterministic_and_nonzero(self):
        first = gemini_capacity.estimate_prompt_tokens(
            {"b": 2, "a": "hello"}
        )
        second = gemini_capacity.estimate_prompt_tokens(
            {"a": "hello", "b": 2}
        )

        self.assertEqual(first, second)
        self.assertGreater(first, 0)

    def test_prompt_estimate_is_conservative_by_utf8_bytes(self):
        text = "a" * 300
        estimate = gemini_capacity.estimate_prompt_tokens(
            text
        )

        self.assertEqual(estimate, 100)

    def test_default_dispatch_interval_is_fifteen_seconds(self):
        with clean_capacity_env():
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )

        self.assertEqual(
            policy.minimum_dispatch_interval_seconds,
            15.0,
        )

    def test_policy_descriptor_exposes_provider_not_truth_semantics(self):
        with clean_capacity_env():
            policy = gemini_capacity.capacity_policy_for_model(
                "gemini-2.5-flash"
            )

        descriptor = policy.as_dict()

        self.assertEqual(
            descriptor["version"],
            "gemini-capacity-policy-v2",
        )
        self.assertEqual(
            descriptor["provider_timezone"],
            "America/Los_Angeles",
        )
        self.assertEqual(
            descriptor["usable_rpd"],
            16,
        )


if __name__ == "__main__":
    unittest.main()
