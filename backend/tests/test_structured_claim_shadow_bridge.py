from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from app.intelligence import canonical_claims
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import partial_claim_semantics
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_bridge as production_bridge
from app.services import structured_claim_shadow_bridge as shadow


OBSERVED = "2026-08-18T09:00:00Z"
SUBJECT = "football|player|jude-bellingham"
REAL_MADRID = "football|club|real-madrid"
DORTMUND = "football|club|borussia-dortmund"
ALLOWED = [SUBJECT, REAL_MADRID, DORTMUND]


def provenance(
    *,
    url="https://example.com/bellingham",
    observed_at=OBSERVED,
    method="browser_dom",
    content_hash="source-hash",
):
    return artifact_models.ArtifactProvenance(
        source_url=url,
        observed_at=observed_at,
        extraction_method=method,
        source_content_hash=content_hash,
    )


def make_item(
    *,
    item_id="web:bellingham",
    text=(
        "Jude Bellingham later scored in a league match, "
        "a different claim from his transfer."
    ),
):
    return content.UnifiedContentItem(
        item_id=item_id,
        platform="web",
        platform_surface="article",
        container_kind="article",
        canonical_url="https://example.com/bellingham",
        observed_at=OBSERVED,
        published_at="2026-08-18T08:55:00Z",
        text_components=[
            content.TextComponent(
                component_id="body",
                role="body",
                text=text,
                provenance=content.ProvenanceRecord(
                    source_url="https://example.com/bellingham",
                    observed_at=OBSERVED,
                    extraction_method="browser_dom",
                    content_hash="body-source-hash",
                ),
            )
        ],
    )


def make_manifest(
    *,
    item_id="web:bellingham",
    candidates=None,
):
    if candidates is None:
        candidates = [
            {
                "candidate_id": "claim-candidate:a",
                "text": (
                    "Jude Bellingham later scored in a league match, "
                    "a different claim from his transfer."
                ),
                "confidence": 0.81,
                "source_artifact_ids": ["text:a"],
                "modality_sources": ["body"],
                "uncertainty": "",
            }
        ]

    source_artifact = artifact_models.ExtractionArtifact(
        artifact_id="text:a",
        artifact_kind="text_component",
        modality="text",
        source_item_ids=[item_id],
        source_component_ids=["body"],
        content_hash="artifact-source-hash",
        payload={
            "role": "body",
            "text": (
                "Jude Bellingham later scored in a league match, "
                "a different claim from his transfer."
            ),
        },
        provenance=provenance(),
    )

    candidate_artifact = artifact_models.ExtractionArtifact(
        artifact_id="claims:a",
        artifact_kind="claim_candidates",
        modality="multimodal",
        source_item_ids=[item_id],
        source_component_ids=["body"],
        content_hash="candidate-container-hash",
        payload={
            "candidates": list(candidates),
        },
        provenance=provenance(
            method="multimodal_fusion",
        ),
    )

    return artifact_models.ItemArtifactManifest(
        item_id=item_id,
        artifacts=[
            source_artifact,
            candidate_artifact,
        ],
        work_units=[],
    )


def bindings(
    *,
    subject_key=SUBJECT,
):
    return bridge_models.BridgeBindings(
        subject_key=subject_key,
    )


def partial_output(
    *,
    version=canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION,
):
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": "partial",
        "candidate": {
            "version": version,
            "subject_key": SUBJECT,
            "event_type": "match_event",
            "state": "goal",
            "negated": False,
            "roles": {},
            "facets": {},
        },
        "reason": (
            "The scoring event is clear but the exact match is absent."
        ),
    }


def full_output(
    *,
    version="model-owned-wrong-version",
):
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": "extracted",
        "candidate": {
            "version": version,
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {
                "destination": REAL_MADRID,
            },
            "facets": {
                "effective_period": "2023",
            },
        },
        "reason": "",
    }


def insufficient_output():
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": "insufficient",
        "candidate": None,
        "reason": "No supported structured event is available.",
    }


def build(
    *,
    shadow_enabled=False,
    outputs=None,
    allowed=ALLOWED,
    item=None,
    manifest=None,
    bridge_bindings=None,
):
    return (
        shadow
        .build_item_intelligence_bridge_with_structured_shadow(
            item=item or make_item(),
            manifest=manifest or make_manifest(),
            bindings=(
                bridge_bindings
                if bridge_bindings is not None
                else bindings()
            ),
            shadow_enabled=shadow_enabled,
            structured_outputs_by_candidate_id=outputs,
            allowed_entity_keys=allowed,
        )
    )


def dump_model(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="json"
        )
    return value.dict()


class StructuredClaimShadowBridgeTests(unittest.TestCase):
    def test_01_version(self):
        self.assertEqual(
            shadow.STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
            "structured-claim-shadow-bridge-v1",
        )

    def test_02_descriptor_is_zero_cost(self):
        descriptor = shadow.structured_claim_shadow_descriptor()
        self.assertFalse(
            descriptor["provider_call_performed"]
        )
        self.assertEqual(
            descriptor["provider_calls_expected"],
            0,
        )
        self.assertEqual(
            descriptor["provider_tokens_expected"],
            0,
        )
        self.assertEqual(
            descriptor["database_writes_expected"],
            0,
        )

    def test_03_policy_default_is_disabled(self):
        self.assertFalse(
            shadow.STRUCTURED_CLAIM_SHADOW_POLICY[
                "shadow_default_enabled"
            ]
        )
        self.assertTrue(
            shadow.STRUCTURED_CLAIM_SHADOW_POLICY[
                "shadow_is_opt_in"
            ]
        )

    def test_04_disabled_status(self):
        result = build()
        report = result["structured_shadow"]
        self.assertFalse(report["enabled"])
        self.assertEqual(
            report["status"],
            shadow.SHADOW_STATUS_DISABLED,
        )

    def test_05_disabled_has_no_candidate_rows(self):
        result = build()
        self.assertEqual(
            result["structured_shadow"]["candidate_rows"],
            [],
        )

    def test_06_disabled_does_not_call_protocol_parser(self):
        with mock.patch.object(
            shadow.ownership,
            "parse_protocol_owned_claim_semantic_output",
            side_effect=AssertionError("must not run"),
        ) as parser:
            build(
                shadow_enabled=False,
                outputs={
                    "claim-candidate:a": partial_output(),
                },
            )
        parser.assert_not_called()

    def test_07_disabled_ignores_malformed_shadow_outputs(self):
        result = build(
            shadow_enabled=False,
            outputs="not-a-mapping",
        )
        self.assertEqual(
            result["structured_shadow"]["report_errors"],
            [],
        )

    def test_08_disabled_production_plan_matches_direct_bridge(self):
        item = make_item()
        manifest = make_manifest()
        bridge_bindings = bindings()
        direct = production_bridge.build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bridge_bindings,
        )
        wrapped = build(
            item=item,
            manifest=manifest,
            bridge_bindings=bridge_bindings,
        )["production_plan"]
        self.assertEqual(
            dump_model(wrapped),
            dump_model(direct),
        )

    def test_09_active_without_output_is_not_provided(self):
        result = build(
            shadow_enabled=True,
            outputs={},
        )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_NOT_PROVIDED,
        )

    def test_10_active_report_uses_production_subject(self):
        result = build(
            shadow_enabled=True,
            outputs={},
        )
        self.assertEqual(
            result["structured_shadow"]["subject_key"],
            SUBJECT,
        )

    def test_11_active_report_never_stores_raw_outputs(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )
        report = result["structured_shadow"]
        self.assertFalse(
            report["raw_model_outputs_stored"]
        )
        self.assertFalse(
            report["candidate_rows"][0][
                "raw_model_output_stored"
            ]
        )

    def test_12_active_report_never_allows_persistence(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )
        report = result["structured_shadow"]
        self.assertFalse(
            report["persistence_allowed"]
        )
        self.assertFalse(
            report["candidate_rows"][0][
                "persistence_allowed"
            ]
        )

    def test_13_unbound_output_is_reported(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "not-a-production-candidate": partial_output(),
            },
        )
        self.assertEqual(
            result["structured_shadow"][
                "unbound_output_candidate_ids"
            ],
            ["not-a-production-candidate"],
        )

    def test_14_unbound_output_does_not_create_shadow_row(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "not-a-production-candidate": partial_output(),
            },
        )
        rows = result["structured_shadow"]["candidate_rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["candidate_id"],
            "claim-candidate:a",
        )
        self.assertEqual(
            rows[0]["shadow_status"],
            shadow.SHADOW_STATUS_NOT_PROVIDED,
        )

    def test_15_nonmapping_outputs_are_report_error_only(self):
        result = build(
            shadow_enabled=True,
            outputs="bad-container",
        )
        self.assertIn(
            "structured_outputs_by_candidate_id_not_mapping",
            result["structured_shadow"]["report_errors"],
        )
        self.assertIsNotNone(
            result["production_plan"]
        )

    def test_16_empty_shadow_candidate_id_is_reported(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "   ": partial_output(),
            },
        )
        self.assertIn(
            "empty_shadow_candidate_id",
            result["structured_shadow"]["report_errors"],
        )

    def test_17_whitespace_candidate_id_matches_existing_candidate(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "  claim-candidate:a  ": partial_output(),
            },
        )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_EVALUATED,
        )

    def test_18_partial_is_evaluated(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_EVALUATED,
        )
        self.assertEqual(
            row["router_status"],
            "partial",
        )

    def test_19_partial_routes_to_partial_semantics(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["route"],
            "partial_semantics",
        )

    def test_20_partial_event_and_state_use_locked_normalization(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["candidate"]["event_type"],
            "match_event",
        )
        self.assertEqual(
            row["candidate"]["state"],
            "scored",
        )

    def test_21_partial_validator_owns_contract_version(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["candidate"]["version"],
            partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        )

    def test_22_partial_model_version_is_removed_by_product35g(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        protocol = row["protocol_ownership"]
        self.assertTrue(
            protocol[
                "candidate_contract_version_supplied_by_model"
            ]
        )
        self.assertTrue(
            protocol[
                "candidate_contract_version_removed_before_validation"
            ]
        )

    def test_23_partial_has_no_fingerprints(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(row["core_key"], "")
        self.assertEqual(row["core_fingerprint"], "")
        self.assertEqual(row["specific_fingerprint"], "")

    def test_24_partial_identity_is_incomplete_with_event_key_missing(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertFalse(
            row["identity_complete"]
        )
        self.assertEqual(
            row["missing_identity_fields"],
            ["facets.event_key"],
        )

    def test_25_partial_cannot_replace_or_persist_production_identity(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertFalse(
            row["persistence_allowed"]
        )
        self.assertFalse(
            row["replaces_production_identity"]
        )

    def test_26_shadow_row_correlates_existing_production_claim_id(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
        )
        plan = result["production_plan"]
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["production_claim_id"],
            plan.candidates[0].claim.deterministic_id,
        )

    def test_27_partial_shadow_leaves_production_claim_proposal_unchanged(self):
        item = make_item()
        manifest = make_manifest()
        bridge_bindings = bindings()
        direct = production_bridge.build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bridge_bindings,
        )
        wrapped = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
            item=item,
            manifest=manifest,
            bridge_bindings=bridge_bindings,
        )["production_plan"]
        self.assertEqual(
            dump_model(wrapped.candidates[0].claim),
            dump_model(direct.candidates[0].claim),
        )

    def test_28_full_is_evaluated(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_EVALUATED,
        )
        self.assertEqual(
            row["router_status"],
            "extracted",
        )

    def test_29_full_routes_to_full_identity(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["route"],
            "full_identity",
        )
        self.assertTrue(
            row["identity_complete"]
        )

    def test_30_full_exposes_deterministic_fingerprints_for_inspection(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertTrue(row["core_key"])
        self.assertTrue(row["core_fingerprint"])
        self.assertTrue(row["specific_fingerprint"])

    def test_31_full_validator_owns_canonical_contract_version(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["candidate"]["version"],
            canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION,
        )

    def test_32_full_shadow_still_cannot_replace_production_identity(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertFalse(
            row["persistence_allowed"]
        )
        self.assertFalse(
            row["replaces_production_identity"]
        )
        self.assertFalse(
            row["live_merit_effect"]
        )

    def test_33_full_shadow_leaves_production_claim_proposal_unchanged(self):
        item = make_item()
        manifest = make_manifest()
        bridge_bindings = bindings()
        direct = production_bridge.build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bridge_bindings,
        )
        wrapped = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": full_output(),
            },
            item=item,
            manifest=manifest,
            bridge_bindings=bridge_bindings,
        )["production_plan"]
        self.assertEqual(
            dump_model(wrapped.candidates[0].claim),
            dump_model(direct.candidates[0].claim),
        )

    def test_34_insufficient_is_valid_shadow_evaluation_with_no_route(self):
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": insufficient_output(),
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_EVALUATED,
        )
        self.assertEqual(
            row["router_status"],
            "insufficient",
        )
        self.assertEqual(row["route"], "none")
        self.assertIsNone(row["candidate"])

    def test_35_wrong_outer_version_is_shadow_error_only(self):
        payload = partial_output()
        payload["version"] = "wrong-outer-version"
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": payload,
            },
        )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )
        self.assertIsNotNone(
            result["production_plan"]
        )

    def test_36_forbidden_truth_field_is_shadow_error_only(self):
        payload = partial_output()
        payload["candidate"]["truth"] = True
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": payload,
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )

    def test_37_unknown_semantic_field_is_shadow_error_only(self):
        payload = partial_output()
        payload["candidate"]["made_up_field"] = "x"
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": payload,
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )

    def test_38_complete_candidate_labeled_partial_is_shadow_error(self):
        payload = full_output()
        payload["status"] = "partial"
        row = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": payload,
            },
        )["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )

    def test_39_unresolved_subject_is_shadow_error_but_production_returns(self):
        result = build(
            shadow_enabled=True,
            outputs={
                "claim-candidate:a": partial_output(),
            },
            bridge_bindings=bridge_models.BridgeBindings(
                subject_resolution={
                    "status": "ambiguous",
                }
            ),
        )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )
        self.assertEqual(
            result["production_plan"].subject_key,
            "",
        )
        self.assertEqual(
            result["production_plan"].candidates[0].claim.readiness,
            "blocked",
        )

    def test_40_unexpected_shadow_parser_exception_is_isolated(self):
        item = make_item()
        manifest = make_manifest()
        bridge_bindings = bindings()
        direct = production_bridge.build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bridge_bindings,
        )
        with mock.patch.object(
            shadow.ownership,
            "parse_protocol_owned_claim_semantic_output",
            side_effect=RuntimeError("shadow-only-failure"),
        ):
            result = build(
                shadow_enabled=True,
                outputs={
                    "claim-candidate:a": partial_output(),
                },
                item=item,
                manifest=manifest,
                bridge_bindings=bridge_bindings,
            )
        row = result["structured_shadow"]["candidate_rows"][0]
        self.assertEqual(
            row["shadow_status"],
            shadow.SHADOW_STATUS_ERROR,
        )
        self.assertEqual(
            row["error_type"],
            "RuntimeError",
        )
        self.assertEqual(
            dump_model(result["production_plan"]),
            dump_model(direct),
        )


if __name__ == "__main__":
    unittest.main()
