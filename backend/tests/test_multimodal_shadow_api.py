from __future__ import annotations

import copy
import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.models import api as api_models
from app.services import multimodal_intelligence_runtime
from app.services import multimodal_shadow_api


SUBJECT = "club|arsenal"
LEFT_SOURCE = "source-left"
RIGHT_SOURCE = "source-right"
LEFT_MEDIA = "media-left"
RIGHT_MEDIA = "media-right"
LEFT_STORY = "story-left"
RIGHT_STORY = "story-right"
NOW = "2026-08-17T03:30:00Z"


SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE canonical_entities (
  id TEXT PRIMARY KEY,
  entity_key TEXT NOT NULL UNIQUE,
  entity_type TEXT NOT NULL,
  canonical_name TEXT NOT NULL
);

CREATE TABLE intelligence_sources (
  id TEXT PRIMARY KEY
);

CREATE TABLE media_items (
  id TEXT PRIMARY KEY,
  source_id TEXT,
  canonical_url TEXT NOT NULL
);

CREATE TABLE intelligence_stories (
  id TEXT PRIMARY KEY
);

CREATE TABLE story_media_links (
  story_id TEXT NOT NULL,
  media_item_id TEXT NOT NULL,
  PRIMARY KEY(story_id, media_item_id)
);
"""


def safe_runtime_result(
    *,
    subject_key=SUBJECT,
    left_media_item_id=LEFT_MEDIA,
    right_media_item_id=RIGHT_MEDIA,
):
    return {
        "version": (
            multimodal_intelligence_runtime
            .MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": "claim-1",
        "subject_key": subject_key,
        "left_media_item_id": (
            left_media_item_id
        ),
        "right_media_item_id": (
            right_media_item_id
        ),
        "live_score": {
            "total": 70.0,
        },
        "shadow": {
            "proposed_adjustment": 6.0,
            "proposed_shadow_total": 76.0,
            "boost_eligible": True,
        },
        "policy": {
            "exact_common_claim_required": True,
            "heuristic_cross_item_claim_matching": False,
            "verified_bindings_rechecked_downstream": True,
            "adjudication_intake_is_candidate_scoped": True,
            "multimodal_evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_independence": True,
            "independence_uses_existing_verifier_only": True,
            "merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


def request_payload(
    *,
    left_story="",
    right_story="",
):
    return {
        "subject_key": SUBJECT,
        "left": {
            "capture": {
                "source_url": (
                    "https://left.example/post"
                ),
            },
            "source_id": LEFT_SOURCE,
            "media_item_id": LEFT_MEDIA,
            "story_id": left_story,
        },
        "right": {
            "capture": {
                "source_url": (
                    "https://right.example/post"
                ),
            },
            "source_id": RIGHT_SOURCE,
            "media_item_id": RIGHT_MEDIA,
            "story_id": right_story,
        },
        "target_claim_id": "",
        "legacy_score": {
            "total": 70.0,
            "components": {
                "legacy": 70.0,
            },
        },
    }


def http_request(
    *,
    admin_key="",
):
    headers = []

    if admin_key:
        headers.append(
            (
                b"x-sportabase-admin-key",
                admin_key.encode(
                    "utf-8"
                ),
            )
        )

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": (
                "/admin/intelligence/"
                "multimodal-shadow"
            ),
            "raw_path": b"",
            "query_string": b"",
            "headers": headers,
            "client": (
                "127.0.0.1",
                12345,
            ),
            "server": (
                "testserver",
                80,
            ),
        }
    )


class MultimodalShadowApiServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.tmp = (
            tempfile
            .TemporaryDirectory()
        )

        self.db = (
            Path(
                self.tmp.name
            )
            / "shadow-api.db"
        )

        conn = sqlite3.connect(
            self.db
        )

        conn.executescript(
            SCHEMA
        )

        conn.execute(
            """
            INSERT INTO canonical_entities
            VALUES (?, ?, ?, ?)
            """,
            (
                "entity-arsenal",
                SUBJECT,
                "club",
                "Arsenal",
            ),
        )

        conn.executemany(
            """
            INSERT INTO intelligence_sources
            VALUES (?)
            """,
            [
                (
                    LEFT_SOURCE,
                ),
                (
                    RIGHT_SOURCE,
                ),
            ],
        )

        conn.executemany(
            """
            INSERT INTO media_items
            VALUES (?, ?, ?)
            """,
            [
                (
                    LEFT_MEDIA,
                    LEFT_SOURCE,
                    "https://left.example/post",
                ),
                (
                    RIGHT_MEDIA,
                    RIGHT_SOURCE,
                    "https://right.example/post",
                ),
            ],
        )

        conn.executemany(
            """
            INSERT INTO intelligence_stories
            VALUES (?)
            """,
            [
                (
                    LEFT_STORY,
                ),
                (
                    RIGHT_STORY,
                ),
            ],
        )

        conn.executemany(
            """
            INSERT INTO story_media_links
            VALUES (?, ?)
            """,
            [
                (
                    LEFT_STORY,
                    LEFT_MEDIA,
                ),
                (
                    RIGHT_STORY,
                    RIGHT_MEDIA,
                ),
            ],
        )

        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self):
        conn = sqlite3.connect(
            self.db
        )

        conn.row_factory = sqlite3.Row

        return conn

    def execute(
        self,
        sql,
        args=(),
    ):
        conn = self.factory()
        conn.execute(
            sql,
            args,
        )
        conn.commit()
        conn.close()

    def count(
        self,
        table,
    ):
        conn = self.factory()

        value = conn.execute(
            "SELECT COUNT(*) FROM "
            + table
        ).fetchone()[0]

        conn.close()

        return value

    def run_service(
        self,
        *,
        payload=None,
        runtime_result=None,
        runtime_side_effect=None,
    ):
        captured = {}

        def fake_runtime(
            **kwargs,
        ):
            captured.update(
                kwargs
            )

            if (
                runtime_side_effect
                is not None
            ):
                raise runtime_side_effect

            return copy.deepcopy(
                runtime_result
                or safe_runtime_result()
            )

        runtime = (
            mock.create_autospec(
                multimodal_intelligence_runtime
                .run_multimodal_intelligence_runtime,
                side_effect=fake_runtime,
            )
        )

        interpreter = object()
        interpreter_factory = mock.Mock(
            return_value=interpreter
        )

        result = (
            multimodal_shadow_api
            .execute_multimodal_shadow_api(
                request_payload=(
                    payload
                    or request_payload()
                ),
                connection_factory=(
                    self.factory
                ),
                gemini_client=object(),
                gemini_client_key=(
                    "client-test"
                ),
                gemini_generator=(
                    lambda **_kwargs:
                    object()
                ),
                runtime_runner=runtime,
                interpreter_factory=(
                    interpreter_factory
                ),
                now_provider=(
                    lambda: NOW
                ),
            )
        )

        return (
            result,
            captured,
            runtime,
            interpreter_factory,
            interpreter,
        )

    def test_ready_request_runs_locked_runtime(
        self,
    ):
        result, captured, runtime, _, _ = (
            self.run_service()
        )

        self.assertEqual(
            result["status"],
            "completed_shadow",
        )

        self.assertEqual(
            result["version"],
            multimodal_shadow_api
            .MULTIMODAL_SHADOW_API_VERSION,
        )

        runtime.assert_called_once()

        self.assertEqual(
            captured["as_of"],
            NOW,
        )

        self.assertEqual(
            captured["recorded_at"],
            NOW,
        )

    def test_runtime_call_matches_real_signature(
        self,
    ):
        _, _, runtime, _, _ = (
            self.run_service()
        )

        runtime.assert_called_once()

    def test_bindings_are_verified_server_side(
        self,
    ):
        _, captured, _, _, _ = (
            self.run_service()
        )

        left = captured[
            "left_bindings"
        ]
        right = captured[
            "right_bindings"
        ]

        self.assertTrue(
            left.source_record_verified
        )

        self.assertTrue(
            left.media_item_record_verified
        )

        self.assertTrue(
            right.source_record_verified
        )

        self.assertTrue(
            right.media_item_record_verified
        )

        self.assertEqual(
            left.subject_key,
            SUBJECT,
        )

        self.assertEqual(
            right.subject_key,
            SUBJECT,
        )

    def test_story_binding_is_verified_only_with_persisted_link(
        self,
    ):
        payload = request_payload(
            left_story=LEFT_STORY,
            right_story=RIGHT_STORY,
        )

        _, captured, _, _, _ = (
            self.run_service(
                payload=payload
            )
        )

        self.assertTrue(
            captured[
                "left_bindings"
            ].story_record_verified
        )

        self.assertTrue(
            captured[
                "right_bindings"
            ].story_record_verified
        )

    def test_story_omission_does_not_invent_verification(
        self,
    ):
        _, captured, _, _, _ = (
            self.run_service()
        )

        self.assertFalse(
            captured[
                "left_bindings"
            ].story_record_verified
        )

        self.assertEqual(
            captured[
                "left_bindings"
            ].story_id,
            "",
        )

    def test_missing_subject_fails_closed(
        self,
    ):
        self.execute(
            """
            DELETE FROM canonical_entities
            """
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service()

    def test_missing_source_fails_closed(
        self,
    ):
        self.execute(
            """
            DELETE FROM intelligence_sources
            WHERE id = ?
            """,
            (
                LEFT_SOURCE,
            ),
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service()

    def test_missing_media_fails_closed(
        self,
    ):
        self.execute(
            """
            DELETE FROM media_items
            WHERE id = ?
            """,
            (
                LEFT_MEDIA,
            ),
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service()

    def test_media_source_mismatch_fails_closed(
        self,
    ):
        self.execute(
            """
            UPDATE media_items
            SET source_id = ?
            WHERE id = ?
            """,
            (
                RIGHT_SOURCE,
                LEFT_MEDIA,
            ),
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service()

    def test_missing_story_fails_closed(
        self,
    ):
        payload = request_payload(
            left_story="missing-story"
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service(
                payload=payload
            )

    def test_missing_story_media_link_fails_closed(
        self,
    ):
        self.execute(
            """
            DELETE FROM story_media_links
            WHERE story_id = ?
              AND media_item_id = ?
            """,
            (
                LEFT_STORY,
                LEFT_MEDIA,
            ),
        )

        payload = request_payload(
            left_story=LEFT_STORY
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiBindingError
        ):
            self.run_service(
                payload=payload
            )

    def test_same_media_item_is_rejected_before_runtime(
        self,
    ):
        payload = request_payload()

        payload[
            "right"
        ][
            "media_item_id"
        ] = LEFT_MEDIA

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiInputError
        ):
            self.run_service(
                payload=payload
            )

    def test_empty_capture_is_rejected(
        self,
    ):
        payload = request_payload()
        payload["left"]["capture"] = {}

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiInputError
        ):
            self.run_service(
                payload=payload
            )

    def test_legacy_score_requires_total(
        self,
    ):
        payload = request_payload()
        payload["legacy_score"] = {}

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiInputError
        ):
            self.run_service(
                payload=payload
            )

    def test_legacy_score_rejects_boolean_total(
        self,
    ):
        payload = request_payload()

        payload[
            "legacy_score"
        ][
            "total"
        ] = True

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiInputError
        ):
            self.run_service(
                payload=payload
            )

    def test_legacy_score_rejects_out_of_range_total(
        self,
    ):
        payload = request_payload()

        payload[
            "legacy_score"
        ][
            "total"
        ] = 101

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiInputError
        ):
            self.run_service(
                payload=payload
            )

    def test_provider_must_be_configured(
        self,
    ):
        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiProviderUnavailable
        ):
            (
                multimodal_shadow_api
                .execute_multimodal_shadow_api(
                    request_payload=(
                        request_payload()
                    ),
                    connection_factory=(
                        self.factory
                    ),
                    gemini_client=None,
                    gemini_client_key=(
                        "client-test"
                    ),
                    gemini_generator=(
                        lambda **_kwargs:
                        object()
                    ),
                    now_provider=(
                        lambda: NOW
                    ),
                )
            )

    def test_server_constructs_semantic_interpreter(
        self,
    ):
        (
            _,
            captured,
            _,
            interpreter_factory,
            interpreter,
        ) = self.run_service()

        interpreter_factory.assert_called_once()

        self.assertIs(
            captured[
                "semantic_interpreter"
            ],
            interpreter,
        )

    def test_client_key_is_normalized(
        self,
    ):
        captured = {}

        def fake_runtime(
            **kwargs,
        ):
            captured.update(
                kwargs
            )
            return safe_runtime_result()

        (
            multimodal_shadow_api
            .execute_multimodal_shadow_api(
                request_payload=(
                    request_payload()
                ),
                connection_factory=(
                    self.factory
                ),
                gemini_client=object(),
                gemini_client_key="",
                gemini_generator=(
                    lambda **_kwargs:
                    object()
                ),
                runtime_runner=(
                    mock.create_autospec(
                        multimodal_intelligence_runtime
                        .run_multimodal_intelligence_runtime,
                        side_effect=fake_runtime,
                    )
                ),
                interpreter_factory=(
                    lambda **_kwargs:
                    object()
                ),
                now_provider=(
                    lambda: NOW
                ),
            )
        )

        self.assertEqual(
            captured[
                "gemini_client_key"
            ],
            "anonymous",
        )

    def test_runtime_error_is_wrapped(
        self,
    ):
        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiExecutionError
        ):
            self.run_service(
                runtime_side_effect=(
                    multimodal_intelligence_runtime
                    .MultimodalPipelineInputError(
                        "blocked"
                    )
                )
            )

    def test_wrong_runtime_version_fails_closed(
        self,
    ):
        value = safe_runtime_result()
        value["version"] = "future-version"

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_runtime_subject_drift_fails_closed(
        self,
    ):
        value = safe_runtime_result(
            subject_key=(
                "club|chelsea"
            )
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_runtime_media_drift_fails_closed(
        self,
    ):
        value = safe_runtime_result(
            left_media_item_id=(
                "media-elsewhere"
            )
        )

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_runtime_may_not_enable_live_merit(
        self,
    ):
        value = safe_runtime_result()

        value[
            "policy"
        ][
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_runtime_may_not_claim_truth(
        self,
    ):
        value = safe_runtime_result()

        value[
            "policy"
        ][
            "establishes_truth"
        ] = True

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_runtime_must_remain_shadow_only(
        self,
    ):
        value = safe_runtime_result()

        value[
            "policy"
        ][
            "merit_shadow_only"
        ] = False

        with self.assertRaises(
            multimodal_shadow_api
            .MultimodalShadowApiIntegrityError
        ):
            self.run_service(
                runtime_result=value
            )

    def test_service_does_not_write_binding_tables(
        self,
    ):
        before = {
            table: self.count(
                table
            )
            for table in (
                "canonical_entities",
                "intelligence_sources",
                "media_items",
                "intelligence_stories",
                "story_media_links",
            )
        }

        self.run_service()

        after = {
            table: self.count(
                table
            )
            for table in before
        }

        self.assertEqual(
            before,
            after,
        )

    def test_response_policy_is_shadow_only(
        self,
    ):
        result, _, _, _, _ = (
            self.run_service()
        )

        policy = result["policy"]

        self.assertTrue(
            policy[
                "bindings_verified_server_side"
            ]
        )

        self.assertTrue(
            policy[
                "caller_cannot_set_verification_flags"
            ]
        )

        self.assertFalse(
            policy[
                "live_enablement_authorized"
            ]
        )

        self.assertFalse(
            policy[
                "score_effect_applied"
            ]
        )

        self.assertFalse(
            policy[
                "establishes_truth"
            ]
        )

        self.assertFalse(
            policy[
                "affects_live_merit"
            ]
        )


class MultimodalShadowApiModelTests(
    unittest.TestCase
):
    def side(self):
        return (
            api_models
            .MultimodalShadowSideRequest(
                capture={
                    "source_url":
                        "https://left.example/post",
                },
                source_id=LEFT_SOURCE,
                media_item_id=LEFT_MEDIA,
            )
        )

    def test_new_models_are_reexported_by_main(
        self,
    ):
        for name in (
            "MultimodalShadowSideRequest",
            "MultimodalShadowRequest",
            "MultimodalShadowResponse",
        ):
            with self.subTest(
                name=name
            ):
                self.assertIs(
                    getattr(
                        main,
                        name,
                    ),
                    getattr(
                        api_models,
                        name,
                    ),
                )

    def test_side_model_rejects_caller_verification_flags(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            (
                api_models
                .MultimodalShadowSideRequest(
                    capture={
                        "source_url":
                            "https://left.example/post",
                    },
                    source_id=LEFT_SOURCE,
                    media_item_id=LEFT_MEDIA,
                    source_record_verified=True,
                )
            )

    def test_request_model_rejects_unknown_top_level_fields(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            (
                api_models
                .MultimodalShadowRequest(
                    subject_key=SUBJECT,
                    left=self.side(),
                    right=(
                        api_models
                        .MultimodalShadowSideRequest(
                            capture={
                                "source_url":
                                    "https://right.example/post",
                            },
                            source_id=RIGHT_SOURCE,
                            media_item_id=RIGHT_MEDIA,
                        )
                    ),
                    legacy_score={
                        "total": 70.0,
                    },
                    live_enablement_authorized=True,
                )
            )

    def test_openapi_exposes_admin_shadow_route(
        self,
    ):
        schema = main.app.openapi()

        self.assertIn(
            (
                "/admin/intelligence/"
                "multimodal-shadow"
            ),
            schema.get(
                "paths",
                {},
            ),
        )

        schemas = (
            schema
            .get(
                "components",
                {},
            )
            .get(
                "schemas",
                {},
            )
        )

        self.assertIn(
            "MultimodalShadowRequest",
            schemas,
        )

        self.assertIn(
            "MultimodalShadowResponse",
            schemas,
        )


class MultimodalShadowEndpointTests(
    unittest.TestCase
):
    def request_model(self):
        return (
            api_models
            .MultimodalShadowRequest(
                subject_key=SUBJECT,
                left=(
                    api_models
                    .MultimodalShadowSideRequest(
                        capture={
                            "source_url":
                                "https://left.example/post",
                        },
                        source_id=LEFT_SOURCE,
                        media_item_id=LEFT_MEDIA,
                    )
                ),
                right=(
                    api_models
                    .MultimodalShadowSideRequest(
                        capture={
                            "source_url":
                                "https://right.example/post",
                        },
                        source_id=RIGHT_SOURCE,
                        media_item_id=RIGHT_MEDIA,
                    )
                ),
                legacy_score={
                    "total": 70.0,
                },
            )
        )

    def call(
        self,
        *,
        admin_key="secret",
    ):
        return (
            main
            .admin_multimodal_shadow(
                self.request_model(),
                http_request(
                    admin_key=admin_key
                ),
            )
        )

    def test_feature_flag_defaults_off(
        self,
    ):
        with mock.patch.object(
            main,
            "MULTIMODAL_SHADOW_API_ENABLED",
            False,
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call(
                    admin_key=""
                )

        self.assertEqual(
            captured.exception.status_code,
            404,
        )

    def test_enabled_endpoint_requires_configured_admin_key(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "",
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call(
                    admin_key=""
                )

        self.assertEqual(
            captured.exception.status_code,
            503,
        )

    def test_enabled_endpoint_rejects_wrong_admin_key(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call(
                    admin_key="wrong"
                )

        self.assertEqual(
            captured.exception.status_code,
            401,
        )

    def test_enabled_endpoint_requires_gemini(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=None,
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            503,
        )

    def test_endpoint_calls_shadow_adapter_only(
        self,
    ):
        payload = {
            "version": (
                multimodal_shadow_api
                .MULTIMODAL_SHADOW_API_VERSION
            ),
            "status": "completed_shadow",
            "result": (
                safe_runtime_result()
            ),
            "policy": {
                "live_enablement_authorized": False,
                "score_effect_applied": False,
                "affects_live_merit": False,
            },
        }

        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main,
                "request_client_key",
                return_value="client-1",
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                return_value=payload,
            ) as adapter,
        ):
            result = self.call()

        adapter.assert_called_once()

        kwargs = (
            adapter
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs[
                "gemini_client_key"
            ],
            "client-1",
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

        self.assertEqual(
            result.status,
            "completed_shadow",
        )

    def test_input_error_maps_to_422(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                side_effect=(
                    multimodal_shadow_api
                    .MultimodalShadowApiInputError(
                        "bad input"
                    )
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            422,
        )

    def test_binding_error_maps_to_409(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                side_effect=(
                    multimodal_shadow_api
                    .MultimodalShadowApiBindingError(
                        "bad binding"
                    )
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            409,
        )

    def test_provider_error_maps_to_503(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                side_effect=(
                    multimodal_shadow_api
                    .MultimodalShadowApiProviderUnavailable(
                        "provider unavailable"
                    )
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            503,
        )

    def test_execution_error_maps_to_409(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                side_effect=(
                    multimodal_shadow_api
                    .MultimodalShadowApiExecutionError(
                        "cannot complete"
                    )
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            409,
        )

    def test_integrity_error_maps_to_500_without_internal_detail(
        self,
    ):
        with (
            mock.patch.object(
                main,
                "MULTIMODAL_SHADOW_API_ENABLED",
                True,
            ),
            mock.patch.object(
                main,
                "ADMIN_API_KEY",
                "secret",
            ),
            mock.patch.object(
                main,
                "gemini_client",
                return_value=object(),
            ),
            mock.patch.object(
                main.multimodal_shadow_api,
                "execute_multimodal_shadow_api",
                side_effect=(
                    multimodal_shadow_api
                    .MultimodalShadowApiIntegrityError(
                        "secret internal detail"
                    )
                ),
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                self.call()

        self.assertEqual(
            captured.exception.status_code,
            500,
        )

        self.assertNotIn(
            "secret internal detail",
            str(
                captured.exception.detail
            ),
        )


if __name__ == "__main__":
    unittest.main()
