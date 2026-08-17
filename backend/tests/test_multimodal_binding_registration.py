from __future__ import annotations

import json
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
from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence import entities
from app.routes import multimodal_admin
from app.services import multimodal_binding_registration as registration


NOW = "2026-08-17T09:00:00Z"
OBSERVED = "2026-08-17T08:45:00Z"


def subject_payload(
    *,
    entity_key="football|club|arsenal",
    entity_type="club",
    canonical_name="Arsenal",
    sport_key="football",
):
    return {
        "entity_key": entity_key,
        "entity_type": entity_type,
        "canonical_name": canonical_name,
        "sport_key": sport_key,
    }


def x_capture(
    *,
    handle="reporter_one",
    status_id="111111",
    display_name="Reporter One",
    platform_actor_id="",
    profile_url="",
    canonical_entity_id="",
):
    actor = {
        "handle": handle,
        "display_name": display_name,
    }

    if platform_actor_id:
        actor["platform_actor_id"] = (
            platform_actor_id
        )

    if profile_url:
        actor["profile_url"] = profile_url

    if canonical_entity_id:
        actor["canonical_entity_id"] = (
            canonical_entity_id
        )

    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://x.com/"
            + handle
            + "/status/"
            + status_id
        ),
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "x",
            "surface": "post",
            "container_kind": "post",
            "canonical_url": (
                "https://x.com/"
                + handle
                + "/status/"
                + status_id
            ),
            "body": (
                "Arsenal transfer update "
                + status_id
            ),
        },
        "actor": actor,
    }


def youtube_capture(
    *,
    handle="@channel_one",
    video_id="abcDEF12345",
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://youtube.com/watch?v="
            + video_id
        ),
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "youtube",
            "surface": "video",
            "container_kind": "media",
            "canonical_url": (
                "https://youtube.com/watch?v="
                + video_id
            ),
            "title": "Transfer update",
            "description": "Club news",
        },
        "actor": {
            "handle": handle,
            "display_name": "Channel One",
            "profile_url": (
                "https://youtube.com/"
                + handle
            ),
        },
    }


def web_capture(
    *,
    domain="example.com",
    slug="story-one",
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://"
            + domain
            + "/"
            + slug
        ),
        "observed_at": OBSERVED,
        "extraction_method": (
            "browser_dom+article_extractor"
        ),
        "payload": {
            "platform": "web",
            "surface": "article",
            "container_kind": "article",
            "canonical_url": (
                "https://"
                + domain
                + "/"
                + slug
            ),
            "title": "Article title",
            "body": "Article body",
        },
        "actor": {},
    }


def http_request(
    *,
    admin_key="secret",
):
    headers = []

    if admin_key:
        headers.append(
            (
                b"x-sportabase-admin-key",
                admin_key.encode("utf-8"),
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
                "multimodal-bindings"
            ),
            "raw_path": b"",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


class MultimodalBindingRegistrationTests(
    unittest.TestCase
):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.tmp.name)
            / "bindings.db"
        )

        conn = connect_database(
            self.db_path
        )

        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def factory(self):
        return connect_database(
            self.db_path
        )

    def count(self, table):
        conn = self.factory()

        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM "
                    + table
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def one(self, sql, args=()):
        conn = self.factory()

        try:
            row = conn.execute(
                sql,
                args,
            ).fetchone()
            return (
                dict(row)
                if row is not None
                else None
            )
        finally:
            conn.close()

    def register(
        self,
        *,
        subject=None,
        left=None,
        right=None,
    ):
        return registration.register_multimodal_bindings(
            subject=(
                subject
                or subject_payload()
            ),
            left_capture=(
                left
                or x_capture(
                    handle="reporter_one",
                    status_id="111111",
                )
            ),
            right_capture=(
                right
                or x_capture(
                    handle="reporter_two",
                    status_id="222222",
                )
            ),
            connection_factory=self.factory,
            now_provider=lambda: NOW,
        )

    def test_version_and_status(self):
        result = self.register()

        self.assertEqual(
            result["version"],
            registration.MULTIMODAL_BINDING_REGISTRATION_VERSION,
        )
        self.assertEqual(
            result["status"],
            "registered",
        )

    def test_admin_subject_is_persisted_as_identity_only(self):
        result = self.register()

        self.assertEqual(
            result["subject_key"],
            "football|club|arsenal",
        )
        self.assertEqual(
            self.count("canonical_entities"),
            1,
        )
        self.assertTrue(
            result["policy"][
                "subject_record_is_identity_only"
            ]
        )

    def test_subject_id_uses_canonical_entity_contract(self):
        result = self.register()

        self.assertEqual(
            result["subject"]["entity_id"],
            entities.canonical_entity_id_for_key(
                "football|club|arsenal"
            ),
        )

    def test_subject_name_can_refresh_without_changing_identity(self):
        first = self.register()
        second = self.register(
            subject=subject_payload(
                canonical_name=(
                    "Arsenal Football Club"
                )
            )
        )

        self.assertEqual(
            first["subject"]["entity_id"],
            second["subject"]["entity_id"],
        )
        self.assertEqual(
            second["subject"]["canonical_name"],
            "Arsenal Football Club",
        )

    def test_subject_type_conflict_fails_and_rolls_back(self):
        self.register()

        with self.assertRaises(
            registration.MultimodalBindingIdentityError
        ):
            self.register(
                subject=subject_payload(
                    entity_type="team"
                ),
                left=x_capture(
                    handle="new_a",
                    status_id="333333",
                ),
                right=x_capture(
                    handle="new_b",
                    status_id="444444",
                ),
            )

        self.assertEqual(
            self.count("intelligence_sources"),
            2,
        )
        self.assertEqual(
            self.count("media_items"),
            2,
        )

    def test_subject_sport_conflict_fails_closed(self):
        self.register()

        with self.assertRaises(
            registration.MultimodalBindingIdentityError
        ):
            self.register(
                subject=subject_payload(
                    sport_key="basketball"
                )
            )

    def test_invalid_subject_type_is_rejected_before_database(self):
        with self.assertRaises(
            registration.MultimodalBindingInputError
        ):
            self.register(
                subject=subject_payload(
                    entity_type="banana"
                )
            )

        self.assertEqual(
            self.count("canonical_entities"),
            0,
        )

    def test_social_accounts_on_same_platform_remain_distinct_sources(self):
        result = self.register()

        self.assertNotEqual(
            result["left"]["source_id"],
            result["right"]["source_id"],
        )
        self.assertEqual(
            self.count("intelligence_sources"),
            2,
        )
        self.assertTrue(
            result["left"]["source_key"].startswith(
                "social_account|x|handle|"
            )
        )

    def test_two_posts_from_same_account_reuse_one_source(self):
        result = self.register(
            left=x_capture(
                handle="same_account",
                status_id="111111",
            ),
            right=x_capture(
                handle="same_account",
                status_id="222222",
            ),
        )

        self.assertEqual(
            result["left"]["source_id"],
            result["right"]["source_id"],
        )
        self.assertEqual(
            self.count("intelligence_sources"),
            1,
        )
        self.assertEqual(
            self.count("media_items"),
            2,
        )

    def test_platform_actor_id_has_identity_priority(self):
        result = self.register(
            left=x_capture(
                handle="renameable",
                status_id="111111",
                platform_actor_id="ACTOR-123",
                profile_url=(
                    "https://x.com/renameable"
                ),
            )
        )

        self.assertEqual(
            result["left"][
                "source_identity_basis"
            ],
            "platform_actor_id",
        )
        self.assertIn(
            "|platform_actor_id|actor-123",
            result["left"]["source_key"],
        )

    def test_handle_has_priority_over_profile_url(self):
        result = self.register(
            left=x_capture(
                handle="HandleChoice",
                status_id="111111",
                profile_url=(
                    "https://x.com/HandleChoice"
                ),
            )
        )

        self.assertEqual(
            result["left"][
                "source_identity_basis"
            ],
            "handle",
        )
        self.assertTrue(
            result["left"]["source_key"].endswith(
                "|handlechoice"
            )
        )

    def test_profile_url_is_valid_actor_fallback(self):
        capture = x_capture(
            handle="temporary",
            status_id="111111",
            profile_url="https://x.com/profile-only",
        )
        capture["actor"]["handle"] = ""

        result = self.register(
            left=capture
        )

        self.assertEqual(
            result["left"][
                "source_identity_basis"
            ],
            "profile_url",
        )

    def test_social_capture_without_stable_actor_fails_closed(self):
        capture = x_capture()
        capture["actor"] = {
            "display_name": "Only a display name"
        }

        with self.assertRaises(
            registration.MultimodalBindingIdentityError
        ):
            self.register(
                left=capture
            )

        self.assertEqual(
            self.count("intelligence_sources"),
            0,
        )

    def test_youtube_uses_channel_source_type(self):
        result = self.register(
            left=youtube_capture(
                handle="@alpha",
                video_id="abcDEF12345",
            ),
            right=youtube_capture(
                handle="@beta",
                video_id="xyzDEF12345",
            ),
        )

        self.assertEqual(
            result["left"]["source_type"],
            "channel",
        )
        self.assertTrue(
            result["left"]["source_key"].startswith(
                "channel|youtube|handle|alpha"
            )
        )

    def test_web_uses_existing_publisher_domain_identity(self):
        result = self.register(
            left=web_capture(
                domain="www.example.com",
                slug="story-one",
            ),
            right=web_capture(
                domain="example.org",
                slug="story-two",
            ),
        )

        self.assertEqual(
            result["left"]["source_key"],
            "publisher|example.com",
        )
        self.assertEqual(
            result["left"]["source_type"],
            "publisher",
        )

    def test_actor_canonical_entity_id_is_not_trusted(self):
        result = self.register(
            left=x_capture(
                canonical_entity_id="caller-asserted"
            )
        )

        source = self.one(
            """
            SELECT metadata_json
            FROM intelligence_sources
            WHERE id = ?
            """,
            (result["left"]["source_id"],),
        )

        metadata = json.loads(
            source["metadata_json"]
        )

        self.assertTrue(
            metadata[
                "actor_canonical_entity_id_ignored"
            ]
        )
        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            0,
        )

    def test_media_rows_bind_exact_source_ids(self):
        result = self.register()

        left = self.one(
            "SELECT * FROM media_items WHERE id = ?",
            (result["left"]["media_item_id"],),
        )

        self.assertEqual(
            left["source_id"],
            result["left"]["source_id"],
        )

    def test_media_metadata_preserves_unified_item_id(self):
        result = self.register()

        left = self.one(
            "SELECT metadata_json FROM media_items WHERE id = ?",
            (result["left"]["media_item_id"],),
        )

        metadata = json.loads(
            left["metadata_json"]
        )

        self.assertEqual(
            metadata["unified_item_id"],
            result["left"]["unified_item_id"],
        )

    def test_story_ids_are_empty_and_no_story_is_created(self):
        result = self.register()

        self.assertEqual(
            result["left"]["story_id"],
            "",
        )
        self.assertEqual(
            result["right"]["story_id"],
            "",
        )
        self.assertEqual(
            self.count("intelligence_stories"),
            0,
        )

    def test_same_media_item_is_rejected_before_writes(self):
        capture = x_capture(
            handle="same",
            status_id="111111",
        )

        with self.assertRaises(
            registration.MultimodalBindingInputError
        ):
            self.register(
                left=capture,
                right=capture,
            )

        self.assertEqual(
            self.count("canonical_entities"),
            0,
        )

    def test_invalid_browser_capture_is_input_error(self):
        capture = x_capture()
        capture["version"] = "wrong"

        with self.assertRaises(
            registration.MultimodalBindingInputError
        ):
            self.register(
                left=capture
            )

    def test_exact_replay_is_idempotent(self):
        first = self.register()
        second = self.register()

        self.assertEqual(
            first["left"]["source_id"],
            second["left"]["source_id"],
        )
        self.assertEqual(
            first["left"]["media_item_id"],
            second["left"]["media_item_id"],
        )
        self.assertEqual(
            self.count("canonical_entities"),
            1,
        )
        self.assertEqual(
            self.count("intelligence_sources"),
            2,
        )
        self.assertEqual(
            self.count("media_items"),
            2,
        )

    def test_existing_media_mode_is_not_overwritten(self):
        first = self.register()

        conn = self.factory()
        try:
            conn.execute(
                """
                UPDATE media_items
                SET mode = 'article'
                WHERE id = ?
                """,
                (first["left"]["media_item_id"],),
            )
            conn.commit()
        finally:
            conn.close()

        self.register()

        row = self.one(
            "SELECT mode FROM media_items WHERE id = ?",
            (first["left"]["media_item_id"],),
        )

        self.assertEqual(
            row["mode"],
            "article",
        )

    def test_existing_media_source_conflict_rolls_back_new_source(self):
        first = self.register()
        source_count = self.count(
            "intelligence_sources"
        )

        conflicting = x_capture(
            handle="intruder",
            status_id="111111",
        )
        conflicting["payload"][
            "canonical_url"
        ] = first["left"]["canonical_url"]
        conflicting["source_url"] = (
            first["left"]["canonical_url"]
        )

        with self.assertRaises(
            registration.MultimodalBindingIdentityError
        ):
            self.register(
                left=conflicting,
                right=x_capture(
                    handle="fresh",
                    status_id="999999",
                ),
            )

        self.assertEqual(
            self.count("intelligence_sources"),
            source_count,
        )

    def test_mid_transaction_failure_rolls_back_everything(self):
        original = registration._persist_media
        calls = {"count": 0}

        def fail_second(conn, media):
            calls["count"] += 1

            if calls["count"] == 2:
                raise sqlite3.IntegrityError(
                    "injected"
                )

            return original(
                conn,
                media,
            )

        with mock.patch.object(
            registration,
            "_persist_media",
            side_effect=fail_second,
        ):
            with self.assertRaises(
                registration.MultimodalBindingPersistenceError
            ):
                self.register()

        self.assertEqual(
            self.count("canonical_entities"),
            0,
        )
        self.assertEqual(
            self.count("intelligence_sources"),
            0,
        )
        self.assertEqual(
            self.count("media_items"),
            0,
        )

    def test_registration_creates_no_claim_observation_or_evidence(self):
        self.register()

        for table in (
            "intelligence_claims",
            "source_observations",
            "reporter_observations",
            "evidence_records",
            "verified_claim_entity_participants",
            "verified_source_entity_bindings",
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.count(table),
                    0,
                )

    def test_policy_never_claims_truth_authority_independence_or_merit(self):
        policy = self.register()["policy"]

        self.assertFalse(
            policy["establishes_truth"]
        )
        self.assertFalse(
            policy["establishes_authority"]
        )
        self.assertFalse(
            policy["establishes_independence"]
        )
        self.assertFalse(
            policy["training_eligible"]
        )
        self.assertFalse(
            policy["affects_live_merit"]
        )
        self.assertTrue(
            policy["live_release_not_called"]
        )

    def test_source_identity_metadata_records_basis(self):
        result = self.register()

        row = self.one(
            "SELECT metadata_json FROM intelligence_sources WHERE id = ?",
            (result["left"]["source_id"],),
        )

        metadata = json.loads(
            row["metadata_json"]
        )

        self.assertEqual(
            metadata["identity_basis"],
            "handle",
        )
        self.assertEqual(
            metadata["platform"],
            "x",
        )

    def test_service_source_has_no_live_release_dependency(self):
        source = Path(
            registration.__file__
        ).read_text(
            encoding="utf-8-sig"
        )

        for marker in (
            "apply_certified_live_merit",
            "evaluate_live_merit_release",
            "release_certificate",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(
                    marker,
                    source,
                )

    def test_service_never_writes_verified_binding_tables(self):
        source = Path(
            registration.__file__
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertNotIn(
            "INSERT INTO verified_source_entity_bindings",
            source,
        )
        self.assertNotIn(
            "INSERT INTO verified_claim_entity_participants",
            source,
        )


class MultimodalBindingRouteTests(
    unittest.TestCase
):
    def request_model(self):
        return multimodal_admin.MultimodalBindingRequest(
            subject=subject_payload(),
            left_capture=x_capture(
                handle="one",
                status_id="111111",
            ),
            right_capture=x_capture(
                handle="two",
                status_id="222222",
            ),
        )

    def endpoint(
        self,
        *,
        enabled=True,
        admin_guard=None,
        connection_factory=None,
    ):
        guard = (
            admin_guard
            or mock.Mock()
        )

        factory = (
            connection_factory
            or mock.Mock()
        )

        router = multimodal_admin.build_router(
            enabled,
            guard,
            factory,
        )

        route = next(
            route
            for route in router.routes
            if route.path == (
                "/admin/intelligence/"
                "multimodal-bindings"
            )
        )

        return (
            route.endpoint,
            guard,
            factory,
        )

    def safe_result(self):
        return {
            "version": (
                registration
                .MULTIMODAL_BINDING_REGISTRATION_VERSION
            ),
            "status": "registered",
            "subject": {
                "entity_id": "entity-1",
                "entity_key": "football|club|arsenal",
                "entity_type": "club",
                "canonical_name": "Arsenal",
                "sport_key": "football",
            },
            "subject_key": "football|club|arsenal",
            "left": {
                "source_id": "source-left",
                "media_item_id": "media-left",
            },
            "right": {
                "source_id": "source-right",
                "media_item_id": "media-right",
            },
            "policy": {
                "affects_live_merit": False,
            },
        }

    def test_request_models_forbid_verification_and_live_fields(self):
        payload = {
            "subject": subject_payload(),
            "left_capture": x_capture(),
            "right_capture": x_capture(
                handle="two",
                status_id="222222",
            ),
            "verified": True,
        }

        with self.assertRaises(
            ValidationError
        ):
            multimodal_admin.MultimodalBindingRequest(
                **payload
            )

    def test_disabled_route_returns_404_before_admin(self):
        endpoint, guard, _ = self.endpoint(
            enabled=False
        )

        with self.assertRaises(
            HTTPException
        ) as captured:
            endpoint(
                self.request_model(),
                http_request(),
            )

        self.assertEqual(
            captured.exception.status_code,
            404,
        )
        guard.assert_not_called()

    def test_enabled_route_calls_admin_guard(self):
        endpoint, guard, _ = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            return_value=self.safe_result(),
        ):
            endpoint(
                self.request_model(),
                http_request(),
            )

        guard.assert_called_once()

    def test_route_calls_registration_service_with_captures(self):
        endpoint, _, factory = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            return_value=self.safe_result(),
        ) as service:
            result = endpoint(
                self.request_model(),
                http_request(),
            )

        self.assertEqual(
            result.status,
            "registered",
        )
        kwargs = service.call_args.kwargs
        self.assertEqual(
            kwargs["subject"]["entity_key"],
            "football|club|arsenal",
        )
        self.assertEqual(
            kwargs["connection_factory"],
            factory,
        )

    def test_input_error_maps_to_422(self):
        endpoint, _, _ = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            side_effect=(
                registration.MultimodalBindingInputError(
                    "bad input"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )

        self.assertEqual(
            captured.exception.status_code,
            422,
        )

    def test_identity_error_maps_to_409(self):
        endpoint, _, _ = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            side_effect=(
                registration.MultimodalBindingIdentityError(
                    "identity conflict"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )

        self.assertEqual(
            captured.exception.status_code,
            409,
        )

    def test_persistence_error_maps_to_generic_500(self):
        endpoint, _, _ = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            side_effect=(
                registration.MultimodalBindingPersistenceError(
                    "secret db detail"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )

        self.assertEqual(
            captured.exception.status_code,
            500,
        )
        self.assertNotIn(
            "secret db detail",
            str(captured.exception.detail),
        )

    def test_integrity_error_maps_to_generic_500(self):
        endpoint, _, _ = self.endpoint()

        with mock.patch.object(
            registration,
            "register_multimodal_bindings",
            side_effect=(
                registration.MultimodalBindingIntegrityError(
                    "secret integrity detail"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )

        self.assertEqual(
            captured.exception.status_code,
            500,
        )
        self.assertNotIn(
            "secret integrity detail",
            str(captured.exception.detail),
        )

    def test_main_openapi_exposes_binding_route(self):
        paths = main.app.openapi()["paths"]

        self.assertIn(
            "/admin/intelligence/multimodal-bindings",
            paths,
        )

    def test_main_stays_within_decomposition_budget(self):
        main_path = (
            BACKEND_DIR
            / "app"
            / "main.py"
        )

        line_count = len(
            main_path.read_text(
                encoding="utf-8"
            ).splitlines()
        )

        self.assertLessEqual(
            line_count,
            2200,
        )


if __name__ == "__main__":
    unittest.main()
