import hashlib
import importlib
import sys
import unittest

import httpx
import requests

from fastapi import HTTPException

from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.application import config
from app.services import (
    gemini_runtime,
)


class FakeClientInfo:
    host = "203.0.113.10"


class FakeRequest:
    def __init__(
        self,
        headers=None,
        client=None,
    ):
        self.headers = (
            headers
            if headers is not None
            else {}
        )

        self.client = (
            client
            if client is not None
            else FakeClientInfo()
        )


class DummyResponse:
    usage_metadata = {
        "prompt_token_count": 10,
        "candidates_token_count": 5,
        "thoughts_token_count": 3,
    }


class RateLimitError(
    Exception
):
    status_code = 429


class ProviderStatusError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"provider status {code}")


class GeminiRuntimeModuleTests(
    unittest.TestCase
):
    def test_gemini_client_configures_single_sdk_attempt_and_timeout(
        self,
    ):
        sentinel = object()

        with (
            patch.dict(
                main.os.environ,
                {"GEMINI_API_KEY": "test-key"},
            ),
            patch.object(
                main,
                "_GEMINI_CLIENT",
                None,
            ),
            patch.object(
                main,
                "_GEMINI_LAST_INIT",
                0.0,
            ),
            patch.object(
                main.genai,
                "Client",
                return_value=sentinel,
            ) as client_factory,
        ):
            result = main.gemini_client()

        self.assertIs(result, sentinel)
        client_factory.assert_called_once()

        kwargs = client_factory.call_args.kwargs
        http_options = kwargs["http_options"]

        self.assertEqual(kwargs["api_key"], "test-key")
        self.assertEqual(http_options.timeout, 60000)
        self.assertIsInstance(http_options.timeout, int)
        self.assertEqual(
            http_options.retry_options.attempts,
            1,
        )

    def test_gemini_client_reuses_cached_transport_client(
        self,
    ):
        sentinel = object()

        with (
            patch.dict(
                main.os.environ,
                {"GEMINI_API_KEY": "test-key"},
            ),
            patch.object(
                main,
                "_GEMINI_CLIENT",
                None,
            ),
            patch.object(
                main,
                "_GEMINI_LAST_INIT",
                0.0,
            ),
            patch.object(
                main.time,
                "time",
                return_value=100.0,
            ),
            patch.object(
                main.genai,
                "Client",
                return_value=sentinel,
            ) as client_factory,
        ):
            first = main.gemini_client()
            second = main.gemini_client()

        self.assertIs(first, sentinel)
        self.assertIs(second, sentinel)
        client_factory.assert_called_once()

    def test_gemini_request_timeout_is_clamped_in_milliseconds(
        self,
    ):
        variable = (
            "SPORTABASE_GEMINI_REQUEST_TIMEOUT_MS"
        )

        try:
            with patch.dict(
                config.os.environ,
                {variable: "1000"},
            ):
                importlib.reload(config)
                self.assertEqual(
                    config.GEMINI_REQUEST_TIMEOUT_MS,
                    5000,
                )

            with patch.dict(
                config.os.environ,
                {variable: "180000"},
            ):
                importlib.reload(config)
                self.assertEqual(
                    config.GEMINI_REQUEST_TIMEOUT_MS,
                    120000,
                )

        finally:
            importlib.reload(config)

    def test_client_key_preserves_installation_identity(
        self,
    ):
        request = FakeRequest(
            headers={
                "x-sportabase-client-id":
                    "installation-123"
            }
        )

        result = (
            main.request_client_key(
                request
            )
        )

        expected = hashlib.sha256(
            (
                "installation:"
                "installation-123"
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:32]

        self.assertEqual(
            result,
            expected,
        )

    def test_usage_metadata_fallback_total_preserved(
        self,
    ):
        result = (
            gemini_runtime
            .usage_metadata_counts(
                DummyResponse()
            )
        )

        self.assertEqual(
            result[
                "prompt_tokens"
            ],
            10,
        )

        self.assertEqual(
            result[
                "output_tokens"
            ],
            5,
        )

        self.assertEqual(
            result[
                "thought_tokens"
            ],
            3,
        )

        self.assertEqual(
            result[
                "total_tokens"
            ],
            18,
        )

    def test_rate_limit_classification_preserved(
        self,
    ):
        result = (
            gemini_runtime
            .classify_gemini_failure(
                RateLimitError(
                    "quota exceeded"
                )
            )
        )

        self.assertEqual(
            result[
                "failure_status_code"
            ],
            429,
        )

        self.assertEqual(
            result[
                "failure_type"
            ],
            "rate_limit",
        )

    def test_actual_transport_exception_classification(
        self,
    ):
        request = httpx.Request(
            "POST",
            "https://example.invalid",
        )

        cases = (
            (
                httpx.TimeoutException(
                    "timed out",
                    request=request,
                ),
                "timeout",
            ),
            (
                httpx.ConnectError(
                    "connection failed",
                    request=request,
                ),
                "network",
            ),
            (
                requests.Timeout(
                    "request timed out"
                ),
                "timeout",
            ),
            (
                requests.ConnectionError(
                    "connection failed"
                ),
                "network",
            ),
        )

        for error, expected in cases:
            with self.subTest(
                error=type(error).__name__,
            ):
                result = (
                    gemini_runtime
                    .classify_gemini_failure(
                        error
                    )
                )
                self.assertEqual(
                    result["failure_type"],
                    expected,
                )

    def test_provider_status_classification_contract(
        self,
    ):
        expected = {
            400: "invalid_request",
            401: "authentication",
            403: "authentication",
            429: "rate_limit",
            500: "provider_error",
            502: "provider_error",
            503: "provider_capacity",
            504: "provider_error",
        }

        for code, failure_type in expected.items():
            with self.subTest(code=code):
                result = (
                    gemini_runtime
                    .classify_gemini_failure(
                        ProviderStatusError(code)
                    )
                )
                self.assertEqual(
                    result["failure_status_code"],
                    code,
                )
                self.assertEqual(
                    result["failure_type"],
                    failure_type,
                )

    def test_retryable_gemini_failure_contract(
        self,
    ):
        request = httpx.Request(
            "POST",
            "https://example.invalid",
        )

        retryable = (
            ProviderStatusError(500),
            ProviderStatusError(502),
            ProviderStatusError(503),
            ProviderStatusError(504),
            httpx.TimeoutException(
                "timed out",
                request=request,
            ),
            httpx.ConnectError(
                "connection failed",
                request=request,
            ),
        )

        not_retryable = (
            ProviderStatusError(400),
            ProviderStatusError(401),
            ProviderStatusError(403),
            ProviderStatusError(429),
            RuntimeError("unexpected"),
            HTTPException(
                status_code=429,
                detail="local capacity",
            ),
            httpx.ReadError(
                "ambiguous read failure",
                request=request,
            ),
            httpx.WriteError(
                "ambiguous write failure",
                request=request,
            ),
        )

        for error in retryable:
            with self.subTest(
                retryable=type(error).__name__,
            ):
                self.assertTrue(
                    gemini_runtime
                    .is_retryable_gemini_failure(
                        error
                    )
                )

        for error in not_retryable:
            with self.subTest(
                not_retryable=(
                    type(error).__name__
                ),
            ):
                self.assertFalse(
                    gemini_runtime
                    .is_retryable_gemini_failure(
                        error
                    )
                )

    def test_request_fingerprint_is_deterministic(
        self,
    ):
        first = (
            gemini_runtime
            .gemini_request_fingerprint(
                mode="article",
                model="model-x",
                contents={
                    "b": 2,
                    "a": 1,
                },
            )
        )

        second = (
            gemini_runtime
            .gemini_request_fingerprint(
                mode="article",
                model="model-x",
                contents={
                    "a": 1,
                    "b": 2,
                },
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(first),
            64,
        )

    def test_expiry_wrapper_injects_runtime_timeout(
        self,
    ):
        original_timeout = (
            main
            .GEMINI_RESERVATION_TIMEOUT_SECONDS
        )

        sentinel = 7

        try:
            (
                main
                .GEMINI_RESERVATION_TIMEOUT_SECONDS
            ) = 321

            with patch.object(
                main,
                "_expire_stale_gemini_reservations_runtime_impl",
                return_value=sentinel,
            ) as impl:
                result = (
                    main
                    .expire_stale_gemini_reservations(
                        object(),
                        usage_day="2026-08-14",
                    )
                )

        finally:
            (
                main
                .GEMINI_RESERVATION_TIMEOUT_SECONDS
            ) = original_timeout

        self.assertEqual(
            result,
            sentinel,
        )

        self.assertEqual(
            impl.call_args.kwargs[
                "reservation_timeout_seconds"
            ],
            321,
        )

    def test_reservation_wrapper_injects_caps_and_dependencies(
        self,
    ):
        original_global = (
            main
            .GLOBAL_DAILY_GEMINI_CALL_CAP
        )

        original_client = (
            main
            .CLIENT_DAILY_GEMINI_CALL_CAP
        )

        try:
            (
                main
                .GLOBAL_DAILY_GEMINI_CALL_CAP
            ) = 111

            (
                main
                .CLIENT_DAILY_GEMINI_CALL_CAP
            ) = 22

            with patch.object(
                main,
                "_reserve_gemini_call_runtime_impl",
                return_value=99,
            ) as impl:
                result = (
                    main.reserve_gemini_call(
                        "client",
                        "article",
                        "model-x",
                    )
                )

        finally:
            (
                main
                .GLOBAL_DAILY_GEMINI_CALL_CAP
            ) = original_global

            (
                main
                .CLIENT_DAILY_GEMINI_CALL_CAP
            ) = original_client

        self.assertEqual(
            result,
            99,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertEqual(
            kwargs[
                "global_daily_call_cap"
            ],
            111,
        )

        self.assertEqual(
            kwargs[
                "client_daily_call_cap"
            ],
            22,
        )

        self.assertIs(
            kwargs[
                "usage_day_resolver"
            ],
            main.utc_usage_day,
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "expire_reservations"
            ],
            (
                main
                .expire_stale_gemini_reservations
            ),
        )

    def test_finish_wrapper_injects_usage_counter_and_database(
        self,
    ):
        sentinel = {
            "total_tokens": 10
        }

        with patch.object(
            main,
            "_finish_gemini_call_runtime_impl",
            return_value=sentinel,
        ) as impl:
            result = (
                main.finish_gemini_call(
                    10,
                    "success",
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs[
                "usage_counter"
            ],
            main.usage_metadata_counts,
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

    def test_generate_wrapper_injects_shared_state_and_helpers(
        self,
    ):
        sentinel = object()

        with patch.object(
            main,
            "_generate_gemini_content_runtime_impl",
            return_value=sentinel,
        ) as impl:
            result = (
                main.generate_gemini_content(
                    client=object(),
                    client_key="client",
                    mode="article",
                    model="model-x",
                    contents="prompt",
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs[
                "inflight_lock"
            ],
            main._INFLIGHT_GEMINI_LOCK,
        )

        self.assertIs(
            kwargs[
                "inflight_calls"
            ],
            main._INFLIGHT_GEMINI_CALLS,
        )

        self.assertIs(
            kwargs[
                "fingerprint_resolver"
            ],
            main.gemini_request_fingerprint,
        )

        self.assertIs(
            kwargs[
                "reserve_call"
            ],
            main.reserve_gemini_call,
        )

        self.assertIs(
            kwargs[
                "finish_call"
            ],
            main.finish_gemini_call,
        )

        self.assertIs(
            kwargs[
                "classify_failure"
            ],
            main.classify_gemini_failure,
        )

        self.assertIs(
            kwargs[
                "record_join"
            ],
            main.record_inflight_gemini_join,
        )

    def test_cache_hit_wrapper_injects_database_and_usage_day(
        self,
    ):
        with patch.object(
            main,
            "_record_analysis_cache_hit_runtime_impl",
        ) as impl:
            main.record_analysis_cache_hit(
                "client",
                "article",
            )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "usage_day_resolver"
            ],
            main.utc_usage_day,
        )


if __name__ == "__main__":
    unittest.main()
