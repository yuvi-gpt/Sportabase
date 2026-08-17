from __future__ import annotations

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
from app.routes import inbox_discovery_admin
from app.services import browser_capture_inbox
from app.services import inbox_candidate_discovery as discovery


OBSERVED = "2026-08-17T09:30:00Z"
RECEIVED = "2026-08-17T09:31:00Z"


def x_capture(
    *,
    handle="reporter",
    status_id="100",
    observed_at=OBSERVED,
    body="Arsenal agree transfer terms with Player Alpha",
    title="",
):
    payload = {
        "platform": "x",
        "surface": "post",
        "container_kind": "post",
        "canonical_url": (
            "https://x.com/"
            + handle
            + "/status/"
            + status_id
        ),
        "body": body,
    }

    if title:
        payload["title"] = title

    return {
        "version": "browser-capture-v1",
        "source_url": payload[
            "canonical_url"
        ],
        "observed_at": observed_at,
        "extraction_method": "browser_dom",
        "payload": payload,
        "actor": {
            "handle": handle,
            "display_name": handle.title(),
            "profile_url": (
                "https://x.com/" + handle
            ),
        },
    }


def request(path=(
    "/admin/intelligence/"
    "multimodal-inbox-discovery"
)):
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": b"",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    })


def safe_result(
    anchor_id="bci_anchor",
):
    return {
        "version": (
            discovery
            .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        ),
        "status": "no_candidates",
        "anchor_capture_record_id": anchor_id,
        "anchor": {},
        "pair_candidates": [],
        "load_failures": [],
        "counts": {
            "independence_established": 0,
            "corroboration_established": 0,
            "live_merit_effects": 0,
        },
        "policy": {
            "read_only_discovery": True,
            "affects_live_merit": False,
        },
    }


def endpoint_for(router, path):
    for route in router.routes:
        if getattr(route, "path", "") == path:
            return route.endpoint

    raise AssertionError(
        "Endpoint not found: " + path
    )


class InboxCandidateDiscoveryTests(
    unittest.TestCase
):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.tmp.name)
            / "discovery.db"
        )

        conn = connect_database(
            self.db_path
        )
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

        self.factory = lambda: connect_database(
            self.db_path
        )

    def tearDown(self):
        self.tmp.cleanup()

    def store(self, capture):
        return (
            browser_capture_inbox
            .store_browser_capture(
                raw_capture=capture,
                connection_factory=self.factory,
                now_provider=lambda: RECEIVED,
            )
        )

    def entity(
        self,
        *,
        key="football|club|arsenal",
        name="Arsenal",
        entity_type="club",
        sport_key="football",
    ):
        return entities.upsert_canonical_entity(
            entity_key=key,
            entity_type=entity_type,
            canonical_name=name,
            sport_key=sport_key,
            seen_at=RECEIVED,
            connection_factory=self.factory,
        )

    def alias(
        self,
        entity,
        text,
        alias_type="common_name",
    ):
        return entities.record_entity_alias(
            entity_id=entity[
                "entity"
            ]["id"],
            alias_text=text,
            alias_type=alias_type,
            seen_at=RECEIVED,
            connection_factory=self.factory,
        )

    def discover(
        self,
        anchor_id,
        *,
        scan_limit=100,
        max_candidates=12,
        semantic_assessments=0,
        client=None,
        generator=None,
        assessor=(
            discovery
            .corroboration_semantics
            .assess_candidate_semantics_with_gemini
        ),
        loader=(
            browser_capture_inbox
            .load_browser_capture_record
        ),
    ):
        return discovery.discover_multimodal_inbox_candidates(
            anchor_capture_record_id=anchor_id,
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            semantic_assessments=semantic_assessments,
            connection_factory=self.factory,
            gemini_client=client,
            gemini_client_key="client-1",
            gemini_generator=generator,
            semantic_assessor=assessor,
            capture_loader=loader,
        )

    def anchor_and_candidate(
        self,
        *,
        anchor_body=(
            "Arsenal agree transfer terms with Player Alpha"
        ),
        candidate_body=(
            "Player Alpha agrees transfer terms with Arsenal"
        ),
        candidate_observed=OBSERVED,
    ):
        anchor = self.store(
            x_capture(
                handle="anchor",
                status_id="100",
                body=anchor_body,
            )
        )
        candidate = self.store(
            x_capture(
                handle="candidate",
                status_id="200",
                body=candidate_body,
                observed_at=candidate_observed,
            )
        )
        return anchor, candidate

    def snapshot_tables(self):
        conn = self.factory()
        try:
            result = {}
            for table in (
                "browser_capture_inbox",
                "canonical_entities",
                "entity_aliases",
                "intelligence_sources",
                "media_items",
                "intelligence_claims",
                "source_observations",
                "evidence_records",
            ):
                result[table] = [
                    tuple(row)
                    for row in conn.execute(
                        "SELECT * FROM "
                        + table
                        + " ORDER BY 1"
                    ).fetchall()
                ]
            return result
        finally:
            conn.close()

    def test_version_and_candidate_status(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            result["version"],
            "multimodal-inbox-candidate-discovery-v1",
        )
        self.assertEqual(
            result["status"],
            "candidates_available",
        )

    def test_empty_anchor_id_is_rejected(self):
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryInputError
        ):
            self.discover("")

    def test_scan_limit_lower_bound(self):
        anchor = self.store(x_capture())
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryInputError
        ):
            self.discover(
                anchor["capture_record_id"],
                scan_limit=0,
            )

    def test_scan_limit_upper_bound(self):
        anchor = self.store(x_capture())
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryInputError
        ):
            self.discover(
                anchor["capture_record_id"],
                scan_limit=501,
            )

    def test_boolean_scan_limit_is_rejected(self):
        anchor = self.store(x_capture())
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryInputError
        ):
            self.discover(
                anchor["capture_record_id"],
                scan_limit=True,
            )

    def test_candidate_limit_bounds(self):
        anchor = self.store(x_capture())
        for value in (0, 51):
            with self.subTest(value=value):
                with self.assertRaises(
                    discovery.InboxCandidateDiscoveryInputError
                ):
                    self.discover(
                        anchor["capture_record_id"],
                        max_candidates=value,
                    )

    def test_semantic_limit_bounds(self):
        anchor = self.store(x_capture())
        for value in (-1, 21):
            with self.subTest(value=value):
                with self.assertRaises(
                    discovery.InboxCandidateDiscoveryInputError
                ):
                    self.discover(
                        anchor["capture_record_id"],
                        semantic_assessments=value,
                    )

    def test_missing_anchor_fails_closed(self):
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryNotFoundError
        ):
            self.discover("bci_missing")

    def test_database_factory_failure_is_wrapped(self):
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryLookupError
        ):
            discovery.discover_multimodal_inbox_candidates(
                anchor_capture_record_id="bci_anchor",
                connection_factory=(
                    lambda: (_ for _ in ()).throw(
                        sqlite3.OperationalError("down")
                    )
                ),
                semantic_assessments=0,
            )

    def test_discovery_is_read_only(self):
        entity = self.entity()
        self.alias(entity, "Arsenal FC")
        anchor, _ = self.anchor_and_candidate()
        before = self.snapshot_tables()
        self.discover(
            anchor["capture_record_id"]
        )
        after = self.snapshot_tables()
        self.assertEqual(before, after)

    def test_anchor_is_not_returned_as_candidate(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        ids = {
            row["capture_record_id"]
            for row in result[
                "pair_candidates"
            ]
        }
        self.assertNotIn(
            anchor["capture_record_id"],
            ids,
        )

    def test_same_canonical_url_recapture_is_excluded(self):
        first = self.store(
            x_capture(
                handle="same",
                status_id="100",
                observed_at=OBSERVED,
                body="Arsenal Player Alpha transfer update",
            )
        )
        self.store(
            x_capture(
                handle="same",
                status_id="100",
                observed_at="2026-08-17T09:31:00Z",
                body="Arsenal Player Alpha transfer update changed",
            )
        )
        result = self.discover(
            first["capture_record_id"]
        )
        self.assertEqual(
            result["pair_candidates"],
            [],
        )
        self.assertEqual(
            result["counts"]["same_url_excluded"],
            1,
        )

    def test_unrelated_capture_without_signal_is_excluded(self):
        anchor = self.store(
            x_capture(
                handle="a",
                status_id="1",
                body="Arsenal Player Alpha transfer agreement",
            )
        )
        self.store(
            x_capture(
                handle="b",
                status_id="2",
                body="Formula racing tyre strategy qualifying",
            )
        )
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            result["pair_candidates"],
            [],
        )
        self.assertEqual(
            result["counts"]["no_signal_excluded"],
            1,
        )

    def test_stronger_lexical_candidate_ranks_first(self):
        anchor = self.store(
            x_capture(
                handle="anchor",
                status_id="1",
                body=(
                    "Arsenal Player Alpha agrees transfer terms medical"
                ),
            )
        )
        strong = self.store(
            x_capture(
                handle="strong",
                status_id="2",
                body=(
                    "Player Alpha agrees Arsenal transfer terms medical"
                ),
            )
        )
        self.store(
            x_capture(
                handle="weak",
                status_id="3",
                body="Arsenal transfer discussion update",
            )
        )
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            result["pair_candidates"][0][
                "capture_record_id"
            ],
            strong["capture_record_id"],
        )

    def test_candidate_limit_is_enforced_after_ranking(self):
        anchor = self.store(
            x_capture(
                handle="anchor",
                status_id="1",
            )
        )
        for index in range(5):
            self.store(
                x_capture(
                    handle=f"candidate{index}",
                    status_id=str(index + 10),
                    body=(
                        "Arsenal transfer terms Player Alpha "
                        + str(index)
                    ),
                )
            )
        result = self.discover(
            anchor["capture_record_id"],
            max_candidates=2,
        )
        self.assertEqual(
            len(result["pair_candidates"]),
            2,
        )

    def test_canonical_name_is_exact_entity_candidate(self):
        arsenal = self.entity()
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        ids = {
            row["id"]
            for row in result["anchor"][
                "entity_candidates"
            ]
        }
        self.assertIn(
            arsenal["entity"]["id"],
            ids,
        )

    def test_alias_normalization_matches_punctuation(self):
        arsenal = self.entity(
            name="Arsenal Football Club"
        )
        self.alias(
            arsenal,
            "Arsenal-FC",
        )
        anchor = self.store(
            x_capture(
                body="Arsenal FC agree Player Alpha transfer",
            )
        )
        result = self.discover(
            anchor["capture_record_id"]
        )
        entities_found = result[
            "anchor"
        ]["entity_candidates"]
        self.assertEqual(
            entities_found[0]["id"],
            arsenal["entity"]["id"],
        )

    def test_ambiguous_alias_surfaces_both_candidates(self):
        first = self.entity(
            key="football|club|united-one",
            name="United One",
        )
        second = self.entity(
            key="football|club|united-two",
            name="United Two",
        )
        self.alias(first, "United")
        self.alias(second, "United")
        anchor = self.store(
            x_capture(
                body="United transfer Player Alpha update",
            )
        )
        result = self.discover(
            anchor["capture_record_id"]
        )
        ids = {
            row["id"]
            for row in result["anchor"][
                "entity_candidates"
            ]
        }
        self.assertEqual(
            ids,
            {
                first["entity"]["id"],
                second["entity"]["id"],
            },
        )

    def test_entity_match_policy_never_verifies_subject(self):
        self.entity()
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        policy = result[
            "anchor"
        ]["entity_candidates"][0]["policy"]
        self.assertTrue(
            policy[
                "alias_match_does_not_verify_subject"
            ]
        )
        self.assertTrue(
            policy[
                "alias_match_does_not_establish_authority"
            ]
        )

    def test_shared_entity_signal_is_reported(self):
        arsenal = self.entity()
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        row = result["pair_candidates"][0]
        self.assertIn(
            arsenal["entity"]["id"],
            row["signals"]["shared_entity_ids"],
        )
        self.assertIn(
            "shared_exact_entity_candidates",
            row["candidate_reasons"],
        )

    def test_lexical_discovery_works_without_entity_catalog(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            len(result["pair_candidates"]),
            1,
        )
        self.assertEqual(
            result["anchor"]["entity_candidates"],
            [],
        )

    def test_shared_text_tokens_are_bounded_and_reported(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        signals = result[
            "pair_candidates"
        ][0]["signals"]
        self.assertGreaterEqual(
            signals["shared_token_count"],
            2,
        )
        self.assertLessEqual(
            len(signals["shared_tokens"]),
            24,
        )

    def test_closer_time_ranks_higher_when_text_is_equal(self):
        anchor = self.store(
            x_capture(
                handle="anchor",
                status_id="1",
                observed_at="2026-08-17T12:00:00Z",
                body="Arsenal Player Alpha transfer terms",
            )
        )
        close = self.store(
            x_capture(
                handle="close",
                status_id="2",
                observed_at="2026-08-17T12:05:00Z",
                body="Arsenal Player Alpha transfer terms",
            )
        )
        self.store(
            x_capture(
                handle="far",
                status_id="3",
                observed_at="2026-08-10T12:00:00Z",
                body="Arsenal Player Alpha transfer terms",
            )
        )
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            result["pair_candidates"][0][
                "capture_record_id"
            ],
            close["capture_record_id"],
        )

    def test_deterministic_score_is_bounded(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        score = result[
            "pair_candidates"
        ][0]["candidate_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_semantic_zero_makes_no_assessor_call(self):
        anchor, _ = self.anchor_and_candidate()
        assessor = mock.Mock()
        self.discover(
            anchor["capture_record_id"],
            semantic_assessments=0,
            assessor=assessor,
        )
        assessor.assert_not_called()

    def test_missing_provider_marks_semantics_unavailable(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=None,
            generator=mock.Mock(),
        )
        semantic = result[
            "pair_candidates"
        ][0]["semantic"]
        self.assertEqual(
            semantic["status"],
            "unavailable",
        )
        self.assertEqual(
            result["counts"][
                "semantic_unavailable"
            ],
            1,
        )

    def test_missing_generator_marks_semantics_unavailable(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=object(),
            generator=None,
        )
        self.assertEqual(
            result["pair_candidates"][0][
                "semantic"
            ]["status"],
            "unavailable",
        )

    def test_semantics_are_limited_to_top_n(self):
        anchor = self.store(
            x_capture(
                handle="anchor",
                status_id="1",
            )
        )
        for index in range(3):
            self.store(
                x_capture(
                    handle=f"c{index}",
                    status_id=str(index + 2),
                    body=(
                        "Arsenal agree transfer terms Player Alpha"
                    ),
                )
            )
        assessor = mock.Mock(
            return_value={
                "status": "assessed",
                "assessment": {
                    "claim_relevance": "same_claim",
                    "independence_established": False,
                },
            }
        )
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=2,
            client=object(),
            generator=mock.Mock(),
            assessor=assessor,
        )
        self.assertEqual(
            assessor.call_count,
            2,
        )
        self.assertEqual(
            result["counts"]["semantic_attempts"],
            2,
        )

    def test_same_claim_semantics_remain_candidate_only(self):
        anchor, _ = self.anchor_and_candidate()
        assessor = mock.Mock(
            return_value={
                "status": "assessed",
                "assessment": {
                    "claim_relevance": "same_claim",
                    "claim_stance": "supports",
                    "independence_established": False,
                },
            }
        )
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=object(),
            generator=mock.Mock(),
            assessor=assessor,
        )
        self.assertEqual(
            result["counts"][
                "semantic_same_claim_candidates"
            ],
            1,
        )
        self.assertTrue(
            result["policy"][
                "semantic_same_claim_is_candidate_only"
            ]
        )
        self.assertEqual(
            result["counts"][
                "corroboration_established"
            ],
            0,
        )

    def test_related_claim_semantics_are_counted_separately(self):
        anchor, _ = self.anchor_and_candidate()
        assessor = mock.Mock(
            return_value={
                "status": "assessed",
                "assessment": {
                    "claim_relevance": "related_claim",
                    "independence_established": False,
                },
            }
        )
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=object(),
            generator=mock.Mock(),
            assessor=assessor,
        )
        self.assertEqual(
            result["counts"][
                "semantic_related_claim_candidates"
            ],
            1,
        )

    def test_semantic_assessor_exception_is_best_effort(self):
        anchor, _ = self.anchor_and_candidate()
        assessor = mock.Mock(
            side_effect=RuntimeError("provider")
        )
        result = self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=object(),
            generator=mock.Mock(),
            assessor=assessor,
        )
        self.assertEqual(
            result["counts"]["semantic_failures"],
            1,
        )
        self.assertEqual(
            result["pair_candidates"][0][
                "semantic"
            ]["status"],
            "assessment_failed",
        )

    def test_semantic_independence_smuggling_fails_closed(self):
        anchor, _ = self.anchor_and_candidate()
        assessor = mock.Mock(
            return_value={
                "status": "assessed",
                "assessment": {
                    "claim_relevance": "same_claim",
                    "independence_established": True,
                },
            }
        )
        with self.assertRaises(
            discovery.InboxCandidateDiscoveryIntegrityError
        ):
            self.discover(
                anchor["capture_record_id"],
                semantic_assessments=1,
                client=object(),
                generator=mock.Mock(),
                assessor=assessor,
            )

    def test_semantic_prompt_uses_anchor_as_provisional_claim(self):
        anchor, candidate = self.anchor_and_candidate()
        assessor = mock.Mock(
            return_value={
                "status": "assessed",
                "assessment": {
                    "claim_relevance": "same_claim",
                    "independence_established": False,
                },
            }
        )
        self.discover(
            anchor["capture_record_id"],
            semantic_assessments=1,
            client=object(),
            generator=mock.Mock(),
            assessor=assessor,
        )
        kwargs = assessor.call_args.kwargs
        self.assertEqual(
            kwargs["claim"]["id"],
            "inbox-anchor:"
            + anchor["capture_record_id"],
        )
        self.assertIn(
            "Arsenal",
            kwargs["claim"]["canonical_text"],
        )
        self.assertEqual(
            kwargs["candidate"]["final_url"],
            candidate["canonical_url"],
        )

    def test_private_descriptors_are_not_returned(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertNotIn(
            "_descriptor",
            result["pair_candidates"][0],
        )

    def test_candidate_policy_has_no_merit_or_verification_effect(self):
        anchor, _ = self.anchor_and_candidate()
        result = self.discover(
            anchor["capture_record_id"]
        )
        policy = result[
            "pair_candidates"
        ][0]["policy"]
        self.assertTrue(policy["candidate_only"])
        self.assertTrue(
            policy["independence_not_established"]
        )
        self.assertTrue(
            policy["corroboration_not_established"]
        )
        self.assertFalse(
            policy["affects_live_merit"]
        )

    def test_global_policy_forbids_all_promotions(self):
        anchor, _ = self.anchor_and_candidate()
        policy = self.discover(
            anchor["capture_record_id"]
        )["policy"]
        for field in (
            "creates_entity",
            "creates_alias",
            "creates_source",
            "creates_media_item",
            "creates_story",
            "creates_claim",
            "creates_observation",
            "creates_evidence",
            "creates_verified_binding",
            "establishes_truth",
            "establishes_authority",
            "establishes_independence",
            "affects_live_merit",
        ):
            with self.subTest(field=field):
                self.assertFalse(policy[field])

    def test_counts_never_claim_independence_or_corroboration(self):
        anchor, _ = self.anchor_and_candidate()
        counts = self.discover(
            anchor["capture_record_id"]
        )["counts"]
        self.assertEqual(
            counts["independence_established"],
            0,
        )
        self.assertEqual(
            counts["corroboration_established"],
            0,
        )
        self.assertEqual(
            counts["live_merit_effects"],
            0,
        )

    def test_candidate_integrity_failure_is_best_effort(self):
        anchor, candidate = self.anchor_and_candidate()
        real_loader = (
            browser_capture_inbox
            .load_browser_capture_record
        )

        def loader(
            *,
            capture_record_id,
            connection_factory,
        ):
            if (
                capture_record_id
                == candidate["capture_record_id"]
            ):
                raise (
                    browser_capture_inbox
                    .BrowserCaptureInboxIntegrityError(
                        "tampered"
                    )
                )
            return real_loader(
                capture_record_id=capture_record_id,
                connection_factory=connection_factory,
            )

        result = self.discover(
            anchor["capture_record_id"],
            loader=loader,
        )
        self.assertEqual(
            result["pair_candidates"],
            [],
        )
        self.assertEqual(
            result["counts"][
                "candidate_load_failures"
            ],
            1,
        )

    def test_anchor_integrity_failure_aborts(self):
        anchor = self.store(x_capture())

        def loader(**kwargs):
            raise (
                browser_capture_inbox
                .BrowserCaptureInboxIntegrityError(
                    "tampered anchor"
                )
            )

        with self.assertRaises(
            discovery.InboxCandidateDiscoveryIntegrityError
        ):
            self.discover(
                anchor["capture_record_id"],
                loader=loader,
            )

    def test_no_candidate_status_when_only_anchor_exists(self):
        anchor = self.store(x_capture())
        result = self.discover(
            anchor["capture_record_id"]
        )
        self.assertEqual(
            result["status"],
            "no_candidates",
        )
        self.assertEqual(
            result["pair_candidates"],
            [],
        )


class InboxCandidateDiscoveryRouteTests(
    unittest.TestCase
):
    PATH = (
        "/admin/intelligence/"
        "multimodal-inbox-discovery"
    )

    def router(
        self,
        *,
        enabled=True,
        require_admin=mock.Mock(),
        connection_factory=mock.Mock(),
        client_factory=None,
        client_key_resolver=None,
        generator=None,
    ):
        return inbox_discovery_admin.build_router(
            enabled=enabled,
            require_admin=require_admin,
            connection_factory=connection_factory,
            gemini_client_factory=client_factory,
            request_client_key_resolver=(
                client_key_resolver
            ),
            gemini_generator=generator,
        )

    def req(self, **overrides):
        payload = {
            "anchor_capture_record_id": "bci_anchor",
            "scan_limit": 100,
            "max_candidates": 12,
            "semantic_assessments": 4,
        }
        payload.update(overrides)
        return (
            inbox_discovery_admin
            .MultimodalInboxDiscoveryRequest(
                **payload
            )
        )

    def test_request_forbids_unknown_fields(self):
        with self.assertRaises(
            ValidationError
        ):
            (
                inbox_discovery_admin
                .MultimodalInboxDiscoveryRequest(
                    anchor_capture_record_id=(
                        "bci_anchor"
                    ),
                    subject={"entity_key": "bad"},
                )
            )

    def test_request_contains_no_subject_or_binding_ids(self):
        fields = (
            inbox_discovery_admin
            .MultimodalInboxDiscoveryRequest
            .__fields__
        )
        self.assertNotIn("subject", fields)
        self.assertNotIn("source_id", fields)
        self.assertNotIn("media_item_id", fields)
        self.assertNotIn("claim_id", fields)

    def test_route_is_registered(self):
        router = self.router()
        endpoint_for(router, self.PATH)

    def test_feature_off_returns_404_before_admin(self):
        admin = mock.Mock()
        router = self.router(
            enabled=False,
            require_admin=admin,
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with self.assertRaises(
            HTTPException
        ) as captured:
            endpoint(
                self.req(),
                request(),
            )
        self.assertEqual(
            captured.exception.status_code,
            404,
        )
        admin.assert_not_called()

    def test_enabled_route_requires_admin(self):
        admin = mock.Mock(
            side_effect=HTTPException(
                status_code=401,
                detail="no",
            )
        )
        router = self.router(
            require_admin=admin,
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with self.assertRaises(
            HTTPException
        ) as captured:
            endpoint(
                self.req(),
                request(),
            )
        self.assertEqual(
            captured.exception.status_code,
            401,
        )

    def test_semantic_zero_does_not_create_gemini_client(self):
        client_factory = mock.Mock()
        router = self.router(
            client_factory=client_factory,
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            return_value=safe_result(),
        ):
            endpoint(
                self.req(
                    semantic_assessments=0
                ),
                request(),
            )
        client_factory.assert_not_called()

    def test_semantic_positive_uses_gemini_client_best_effort(self):
        client = object()
        client_factory = mock.Mock(
            return_value=client
        )
        router = self.router(
            client_factory=client_factory,
            generator=mock.Mock(),
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            return_value=safe_result(),
        ) as service:
            endpoint(
                self.req(),
                request(),
            )
        self.assertIs(
            service.call_args.kwargs[
                "gemini_client"
            ],
            client,
        )

    def test_gemini_factory_failure_does_not_block_discovery(self):
        client_factory = mock.Mock(
            side_effect=RuntimeError("down")
        )
        router = self.router(
            client_factory=client_factory,
            generator=mock.Mock(),
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            return_value=safe_result(),
        ) as service:
            endpoint(
                self.req(),
                request(),
            )
        self.assertIsNone(
            service.call_args.kwargs[
                "gemini_client"
            ]
        )

    def test_client_key_is_forwarded(self):
        router = self.router(
            client_factory=lambda: object(),
            client_key_resolver=(
                lambda _request: "client-25"
            ),
            generator=mock.Mock(),
        )
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            return_value=safe_result(),
        ) as service:
            endpoint(
                self.req(),
                request(),
            )
        self.assertEqual(
            service.call_args.kwargs[
                "gemini_client_key"
            ],
            "client-25",
        )

    def test_input_error_maps_422(self):
        router = self.router()
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            side_effect=(
                discovery
                .InboxCandidateDiscoveryInputError(
                    "bad"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.req(),
                    request(),
                )
        self.assertEqual(
            captured.exception.status_code,
            422,
        )

    def test_not_found_maps_404(self):
        router = self.router()
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            side_effect=(
                discovery
                .InboxCandidateDiscoveryNotFoundError(
                    "missing"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.req(),
                    request(),
                )
        self.assertEqual(
            captured.exception.status_code,
            404,
        )

    def test_lookup_error_maps_503(self):
        router = self.router()
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            side_effect=(
                discovery
                .InboxCandidateDiscoveryLookupError(
                    "down"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.req(),
                    request(),
                )
        self.assertEqual(
            captured.exception.status_code,
            503,
        )

    def test_integrity_error_maps_generic_500(self):
        router = self.router()
        endpoint = endpoint_for(
            router,
            self.PATH,
        )
        with mock.patch.object(
            discovery,
            "discover_multimodal_inbox_candidates",
            side_effect=(
                discovery
                .InboxCandidateDiscoveryIntegrityError(
                    "secret details"
                )
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as captured:
                endpoint(
                    self.req(),
                    request(),
                )
        self.assertEqual(
            captured.exception.status_code,
            500,
        )
        self.assertNotIn(
            "secret details",
            str(captured.exception.detail),
        )

    def test_response_model_preserves_candidate_policy(self):
        response = (
            inbox_discovery_admin
            .MultimodalInboxDiscoveryResponse(
                **safe_result()
            )
        )
        self.assertFalse(
            response.policy[
                "affects_live_merit"
            ]
        )

    def test_existing_multimodal_router_exposes_discovery_route(self):
        paths = {
            getattr(route, "path", "")
            for route in main.app.routes
        }
        self.assertIn(
            self.PATH,
            paths,
        )

    def test_openapi_exposes_discovery_schema(self):
        main.app.openapi_schema = None
        schema = main.app.openapi()
        self.assertIn(
            self.PATH,
            schema["paths"],
        )
        self.assertIn(
            "MultimodalInboxDiscoveryRequest",
            schema["components"]["schemas"],
        )


if __name__ == "__main__":
    unittest.main()
