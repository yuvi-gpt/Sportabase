from __future__ import annotations

import math
from pathlib import Path
import unittest
from unittest import mock

from app.intelligence import claims as claim_intelligence
from app.intelligence import evidence as evidence_intelligence
from app.intelligence import sources as source_intelligence
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_bridge as bridge


OBSERVED = "2026-08-16T12:00:00Z"


def provenance(
    *,
    url="https://example.com/post",
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
    item_id="web:item",
    platform="web",
    canonical_url="https://example.com/post",
    observed_at=OBSERVED,
    published_at="2026-08-16T11:55:00Z",
):
    return content.UnifiedContentItem(
        item_id=item_id,
        platform=platform,
        platform_surface="post",
        container_kind="post",
        canonical_url=canonical_url,
        observed_at=observed_at,
        published_at=published_at,
        text_components=[
            content.TextComponent(
                component_id="caption",
                role="caption",
                text="Arsenal completed the signing.",
                provenance=content.ProvenanceRecord(
                    source_url=canonical_url,
                    observed_at=observed_at,
                    extraction_method="browser_dom",
                    content_hash="caption-source-hash",
                ),
            )
        ],
    )


def make_manifest(
    *,
    item_id="web:item",
    candidate=None,
    source_kind="text_component",
    source_item_ids=None,
    source_artifact_id="text:a",
):
    if candidate is None:
        candidate = {
            "candidate_id": "claim-candidate:a",
            "text": "Arsenal completed the signing.",
            "confidence": 0.82,
            "source_artifact_ids": [
                source_artifact_id
            ],
            "modality_sources": [
                "caption"
            ],
            "uncertainty": "",
        }

    source_artifact = (
        artifact_models.ExtractionArtifact(
            artifact_id=source_artifact_id,
            artifact_kind=source_kind,
            modality=(
                "text"
                if source_kind
                in {
                    "text_component",
                    "ocr_text",
                    "transcript",
                }
                else "image"
            ),
            source_item_ids=(
                list(source_item_ids)
                if source_item_ids is not None
                else [item_id]
            ),
            source_component_ids=[
                "caption"
            ],
            content_hash="artifact-source-hash",
            payload={
                "role": "caption",
                "text": "Arsenal completed the signing.",
            },
            provenance=provenance(),
        )
    )

    candidates_artifact = (
        artifact_models.ExtractionArtifact(
            artifact_id="claims:a",
            artifact_kind="claim_candidates",
            modality="multimodal",
            source_item_ids=[item_id],
            source_component_ids=[
                "caption"
            ],
            content_hash="candidate-container-hash",
            payload={
                "candidates": [
                    candidate
                ]
            },
            provenance=provenance(
                method="multimodal_fusion",
            ),
        )
    )

    return (
        artifact_models.ItemArtifactManifest(
            item_id=item_id,
            artifacts=[
                source_artifact,
                candidates_artifact,
            ],
            work_units=[],
        )
    )


def explicit_bindings(
    *,
    source=False,
    media=False,
    story=False,
):
    return bridge_models.BridgeBindings(
        subject_key="club|arsenal",
        source_id=(
            "source-verified"
            if source
            else ""
        ),
        source_record_verified=source,
        media_item_id=(
            "media-row-1"
            if media
            else ""
        ),
        media_item_record_verified=media,
        story_id=(
            "story-row-1"
            if story
            else ""
        ),
        story_record_verified=story,
    )


def plan(
    *,
    item=None,
    manifest=None,
    bindings=None,
    relationships=(),
):
    item = item or make_item()
    manifest = manifest or make_manifest()

    return (
        bridge.build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bindings,
            relationships=relationships,
        )
    )


class MultimodalIntelligenceBridgeTests(
    unittest.TestCase
):
    def test_surface_normalization_preserves_claim_wording(self):
        self.assertEqual(
            bridge._surface_normalize_claim_text(
                "  Arsenal\u00a0 completed   the signing. "
            ),
            "Arsenal completed the signing.",
        )

    def test_interpretation_confidence_accepts_probability(self):
        self.assertEqual(
            bridge._interpretation_confidence(
                0.75
            ),
            0.75,
        )

    def test_interpretation_confidence_rejects_boolean(self):
        self.assertIsNone(
            bridge._interpretation_confidence(
                True
            )
        )

    def test_interpretation_confidence_rejects_nan_and_infinity(self):
        for value in (
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(
                value=value
            ):
                self.assertIsNone(
                    bridge._interpretation_confidence(
                        value
                    )
                )

    def test_interpretation_confidence_rejects_out_of_range(self):
        self.assertIsNone(
            bridge._interpretation_confidence(
                1.01
            )
        )

        self.assertIsNone(
            bridge._interpretation_confidence(
                -0.01
            )
        )

    def test_explicit_subject_binding_wins(self):
        result = plan(
            bindings=(
                bridge_models
                .BridgeBindings(
                    subject_key="club|arsenal",
                    subject_resolution={
                        "status": "ambiguous",
                    },
                )
            )
        )

        self.assertEqual(
            result.subject_key,
            "club|arsenal",
        )

        self.assertEqual(
            result.subject_resolution_status,
            "explicit_binding",
        )

    def test_exact_unique_entity_resolution_can_bind_subject(self):
        result = plan(
            bindings=(
                bridge_models
                .BridgeBindings(
                    subject_resolution={
                        "status": "exact_unique",
                        "entity": {
                            "entity_key": (
                                "club|arsenal"
                            ),
                            "id": "entity-1",
                        },
                    }
                )
            )
        )

        self.assertEqual(
            result.subject_key,
            "club|arsenal",
        )

        self.assertEqual(
            result.subject_resolution_status,
            "exact_unique",
        )

    def test_ambiguous_entity_resolution_fails_closed(self):
        result = plan(
            bindings=(
                bridge_models
                .BridgeBindings(
                    subject_resolution={
                        "status": "ambiguous",
                        "candidates": [
                            {"entity_key": "a"},
                            {"entity_key": "b"},
                        ],
                    }
                )
            )
        )

        candidate = result.candidates[0]

        self.assertEqual(
            result.subject_key,
            "",
        )

        self.assertEqual(
            candidate.claim.readiness,
            "blocked",
        )

        self.assertIn(
            "subject_unresolved",
            candidate.claim.blocked_reasons,
        )

    def test_no_match_entity_resolution_fails_closed(self):
        result = plan(
            bindings=(
                bridge_models
                .BridgeBindings(
                    subject_resolution={
                        "status": "no_match",
                    }
                )
            )
        )

        self.assertEqual(
            result.candidates[0]
            .evidence.readiness,
            "blocked",
        )

    def test_canonical_claim_key_is_subject_scoped(self):
        first = bridge._canonical_claim_key(
            subject_key="club|arsenal",
            canonical_text="Agreement reached.",
        )

        second = bridge._canonical_claim_key(
            subject_key="club|chelsea",
            canonical_text="Agreement reached.",
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_ready_candidate_builds_claim_evidence_and_aligned_link(self):
        result = plan(
            bindings=explicit_bindings()
        )

        candidate = result.candidates[0]

        self.assertEqual(
            candidate.claim.readiness,
            "ready",
        )

        self.assertEqual(
            candidate.evidence.readiness,
            "ready",
        )

        self.assertEqual(
            candidate.claim_link.readiness,
            "ready",
        )

        self.assertEqual(
            candidate.claim_link.kwargs[
                "relationship_type"
            ],
            "aligned_to",
        )

        self.assertIsNone(
            candidate.claim_link.kwargs[
                "confidence"
            ]
        )

    def test_claim_id_uses_existing_intelligence_helper(self):
        result = plan(
            bindings=explicit_bindings()
        )

        claim = (
            result.candidates[0].claim
        )

        expected = (
            claim_intelligence
            .claim_id_for_canonical_key(
                claim.kwargs[
                    "canonical_key"
                ]
            )
        )

        self.assertEqual(
            claim.deterministic_id,
            expected,
        )

    def test_evidence_identity_matches_existing_contract(self):
        result = plan(
            bindings=explicit_bindings()
        )

        evidence = (
            result.candidates[0]
            .evidence
        )

        kwargs = evidence.kwargs

        evidence_key = (
            evidence_intelligence
            .evidence_key_for_record(
                evidence_type=kwargs[
                    "evidence_type"
                ],
                subject_key=kwargs[
                    "subject_key"
                ],
                observed_at=kwargs[
                    "observed_at"
                ],
                canonical_url=kwargs[
                    "canonical_url"
                ],
                reference_key=kwargs[
                    "reference_key"
                ],
                verification_status=kwargs[
                    "verification_status"
                ],
                normalize_url=(
                    lambda value: value
                ),
            )
        )

        expected = bridge._evidence_id_for_key(
            evidence_key
        )

        self.assertEqual(
            evidence.deterministic_id,
            expected,
        )

    def test_evidence_is_unverified_and_not_training_eligible(self):
        result = plan(
            bindings=explicit_bindings()
        )

        evidence = (
            result.candidates[0]
            .evidence
        )

        self.assertEqual(
            evidence.kwargs[
                "verification_status"
            ],
            "unverified",
        )

        self.assertFalse(
            evidence.kwargs[
                "metadata"
            ][
                "training_eligible"
            ]
        )

    def test_model_confidence_does_not_become_observation_confidence(self):
        result = plan(
            bindings=(
                explicit_bindings(
                    source=True
                )
            )
        )

        candidate = result.candidates[0]
        observation = (
            candidate.source_observation
        )

        self.assertEqual(
            candidate.interpretation_confidence,
            0.82,
        )

        self.assertIsNone(
            observation.kwargs[
                "confidence"
            ]
        )

        self.assertEqual(
            observation.kwargs[
                "metadata"
            ][
                "interpretation_confidence"
            ],
            0.82,
        )

    def test_web_source_candidate_is_derived_but_not_verified(self):
        result = plan(
            bindings=explicit_bindings()
        )

        source = (
            result.source_candidate
        )

        self.assertEqual(
            source["status"],
            "derived_unverified",
        )

        self.assertEqual(
            source[
                "canonical_domain"
            ],
            "example.com",
        )

        self.assertFalse(
            source[
                "persistence_ready"
            ]
        )

        self.assertEqual(
            result.candidates[0]
            .source_observation.readiness,
            "blocked",
        )

    def test_web_source_candidate_matches_existing_source_identity_helper(self):
        result = plan(
            bindings=explicit_bindings()
        )

        source = (
            result.source_candidate
        )

        domain_resolver = (
            lambda url: (
                source_intelligence
                .source_domain_for_url(
                    url,
                    normalize_url=(
                        lambda value: value
                    ),
                )
            )
        )

        key_resolver = (
            lambda url, source_type: (
                source_intelligence
                .source_key_for_url(
                    url,
                    source_type,
                    domain_resolver=(
                        domain_resolver
                    ),
                )
            )
        )

        expected = (
            source_intelligence
            .source_id_for_url(
                "https://example.com/post",
                "publisher",
                key_resolver=(
                    key_resolver
                ),
            )
        )

        self.assertEqual(
            source["source_id"],
            expected,
        )

    def test_verified_source_binding_makes_observation_ready(self):
        result = plan(
            bindings=(
                explicit_bindings(
                    source=True
                )
            )
        )

        observation = (
            result.candidates[0]
            .source_observation
        )

        self.assertEqual(
            observation.readiness,
            "ready",
        )

        self.assertEqual(
            observation.kwargs[
                "source_id"
            ],
            "source-verified",
        )

    def test_social_platform_does_not_guess_platform_host_as_source(self):
        item = make_item(
            item_id="x:item",
            platform="x",
            canonical_url=(
                "https://x.com/reporter/status/1"
            ),
        )

        manifest = make_manifest(
            item_id="x:item",
        )

        result = plan(
            item=item,
            manifest=manifest,
            bindings=(
                bridge_models
                .BridgeBindings(
                    subject_key=(
                        "club|arsenal"
                    )
                )
            ),
        )

        self.assertEqual(
            result.source_candidate[
                "status"
            ],
            "not_derived",
        )

        self.assertNotIn(
            "source_id",
            result.source_candidate,
        )

    def test_unverified_media_item_binding_is_never_used_as_fk(self):
        bindings = (
            explicit_bindings(
                source=True
            )
        )

        bindings.media_item_id = (
            "not-verified-media"
        )

        bindings.media_item_record_verified = (
            False
        )

        result = plan(
            bindings=bindings
        )

        observation = (
            result.candidates[0]
            .source_observation
        )

        self.assertEqual(
            observation.readiness,
            "ready",
        )

        self.assertNotIn(
            "media_item_id",
            observation.kwargs,
        )

        self.assertTrue(
            observation.kwargs[
                "metadata"
            ][
                "media_item_binding_ignored"
            ]
        )

    def test_unified_item_id_is_never_substituted_for_media_item_fk(self):
        result = plan(
            bindings=(
                explicit_bindings(
                    source=True
                )
            )
        )

        observation = (
            result.candidates[0]
            .source_observation
        )

        self.assertNotIn(
            "media_item_id",
            observation.kwargs,
        )

        self.assertNotIn(
            "web:item",
            observation.kwargs.values(),
        )

    def test_verified_media_item_binding_is_included(self):
        result = plan(
            bindings=(
                explicit_bindings(
                    source=True,
                    media=True,
                )
            )
        )

        self.assertEqual(
            result.candidates[0]
            .source_observation.kwargs[
                "media_item_id"
            ],
            "media-row-1",
        )

    def test_unverified_story_binding_is_omitted(self):
        bindings = (
            explicit_bindings(
                source=True
            )
        )

        bindings.story_id = (
            "story-unverified"
        )

        result = plan(
            bindings=bindings
        )

        observation = (
            result.candidates[0]
            .source_observation
        )

        self.assertNotIn(
            "story_id",
            observation.kwargs,
        )

        self.assertTrue(
            observation.kwargs[
                "metadata"
            ][
                "story_binding_ignored"
            ]
        )

    def test_verified_story_binding_is_included(self):
        result = plan(
            bindings=(
                explicit_bindings(
                    source=True,
                    story=True,
                )
            )
        )

        self.assertEqual(
            result.candidates[0]
            .source_observation.kwargs[
                "story_id"
            ],
            "story-row-1",
        )

    def test_unknown_source_artifact_blocks_candidate_persistence(self):
        candidate = {
            "candidate_id": "claim-candidate:a",
            "text": "Agreement reached.",
            "confidence": 0.7,
            "source_artifact_ids": [
                "missing:a"
            ],
        }

        result = plan(
            manifest=make_manifest(
                candidate=candidate
            ),
            bindings=explicit_bindings(),
        )

        record = result.candidates[0]

        self.assertEqual(
            record.claim.readiness,
            "blocked",
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "unknown_source_artifact:"
                )
                for reason
                in record.source_validation_errors
            )
        )

    def test_unsupported_artifact_kind_blocks_candidate_persistence(self):
        result = plan(
            manifest=make_manifest(
                source_kind=(
                    "frame_sampling_schedule"
                )
            ),
            bindings=explicit_bindings(),
        )

        record = result.candidates[0]

        self.assertEqual(
            record.evidence.readiness,
            "blocked",
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "unsupported_source_artifact_kind:"
                )
                for reason
                in record.source_validation_errors
            )
        )

    def test_foreign_artifact_blocks_candidate_persistence(self):
        result = plan(
            manifest=make_manifest(
                source_item_ids=[
                    "another:item"
                ],
            ),
            bindings=explicit_bindings(),
        )

        record = result.candidates[0]

        self.assertEqual(
            record.claim.readiness,
            "blocked",
        )

        self.assertTrue(
            any(
                reason.startswith(
                    "foreign_source_artifact:"
                )
                for reason
                in record.source_validation_errors
            )
        )

    def test_artifact_provenance_preserves_hash_url_time_and_method(self):
        result = plan(
            bindings=explicit_bindings()
        )

        provenance_row = (
            result.candidates[0]
            .source_artifacts[0]
        )

        self.assertEqual(
            provenance_row.content_hash,
            "artifact-source-hash",
        )

        self.assertEqual(
            provenance_row.source_content_hash,
            "source-hash",
        )

        self.assertEqual(
            provenance_row.source_url,
            "https://example.com/post",
        )

        self.assertEqual(
            provenance_row.observed_at,
            OBSERVED,
        )

        self.assertEqual(
            provenance_row.extraction_method,
            "browser_dom",
        )

    def test_invalid_candidate_confidence_becomes_none_not_persistence_confidence(self):
        candidate = {
            "candidate_id": "claim-candidate:a",
            "text": "Agreement reached.",
            "confidence": float("nan"),
            "source_artifact_ids": [
                "text:a"
            ],
        }

        result = plan(
            manifest=make_manifest(
                candidate=candidate
            ),
            bindings=(
                explicit_bindings(
                    source=True
                )
            ),
        )

        record = result.candidates[0]

        self.assertIsNone(
            record.interpretation_confidence
        )

        self.assertIsNone(
            record.source_observation
            .kwargs["confidence"]
        )

    def test_explicit_repost_blocks_independence(self):
        relationship = (
            content.ContentRelationship(
                relationship_id="rel:1",
                source_item_id="web:item",
                target_item_id="upstream:item",
                relationship_type="repost_of",
                provenance=(
                    content.ProvenanceRecord(
                        source_url=(
                            "https://example.com/post"
                        ),
                        observed_at=OBSERVED,
                        extraction_method=(
                            "browser_dom"
                        ),
                        content_hash=(
                            "relationship-hash"
                        ),
                    )
                ),
            )
        )

        result = plan(
            bindings=explicit_bindings(),
            relationships=[
                relationship
            ],
        )

        self.assertEqual(
            result.independence_status,
            "blocked_by_explicit_dependency",
        )

        self.assertEqual(
            len(
                result.dependency_constraints
            ),
            1,
        )

    def test_absence_of_dependency_keeps_independence_unknown(self):
        result = plan(
            bindings=explicit_bindings()
        )

        self.assertEqual(
            result.independence_status,
            "unknown",
        )

        self.assertEqual(
            result.dependency_constraints,
            [],
        )

    def test_dependency_is_blocked_without_persisted_observation_bindings(self):
        relationship = (
            content.ContentRelationship(
                relationship_id="rel:1",
                source_item_id="web:item",
                target_item_id="upstream:item",
                relationship_type="quote_of",
                provenance=(
                    content.ProvenanceRecord(
                        observed_at=OBSERVED
                    )
                ),
            )
        )

        result = plan(
            bindings=explicit_bindings(),
            relationships=[
                relationship
            ],
        )

        proposal = (
            result.dependency_constraints[0]
            .persistence_proposal
        )

        self.assertEqual(
            proposal.readiness,
            "blocked",
        )

        self.assertIn(
            "downstream_source_observation_not_bound",
            proposal.blocked_reasons,
        )

        self.assertIn(
            "upstream_dependency_target_not_verified",
            proposal.blocked_reasons,
        )

    def test_dependency_becomes_ready_with_verified_exact_targets(self):
        relationship = (
            content.ContentRelationship(
                relationship_id="rel:1",
                source_item_id="web:item",
                target_item_id="upstream:item",
                relationship_type="derives_from",
                provenance=(
                    content.ProvenanceRecord(
                        source_url=(
                            "https://example.com/post"
                        ),
                        observed_at=OBSERVED,
                        extraction_method="browser_dom",
                        content_hash="rel-hash",
                    )
                ),
            )
        )

        bindings = explicit_bindings()

        bindings.downstream_source_observation_id = (
            "downstream-observation"
        )

        bindings.upstream_targets_by_item_id = {
            "upstream:item": {
                "record_verified": True,
                "upstream_source_id": (
                    "upstream-source"
                ),
            }
        }

        result = plan(
            bindings=bindings,
            relationships=[
                relationship
            ],
        )

        proposal = (
            result.dependency_constraints[0]
            .persistence_proposal
        )

        self.assertEqual(
            proposal.readiness,
            "ready",
        )

        self.assertEqual(
            proposal.kwargs[
                "relationship_type"
            ],
            "derived_from",
        )

        self.assertEqual(
            proposal.kwargs[
                "upstream_source_id"
            ],
            "upstream-source",
        )

        self.assertTrue(
            proposal.deterministic_id
        )

    def test_quote_dependency_maps_to_attributed_to(self):
        relationship = (
            content.ContentRelationship(
                relationship_id="rel:q",
                source_item_id="web:item",
                target_item_id="upstream:item",
                relationship_type="quote_of",
                provenance=(
                    content.ProvenanceRecord(
                        observed_at=OBSERVED
                    )
                ),
            )
        )

        result = plan(
            bindings=explicit_bindings(),
            relationships=[
                relationship
            ],
        )

        self.assertEqual(
            result.dependency_constraints[0]
            .persistence_relationship_type,
            "attributed_to",
        )

    def test_non_dependency_relationship_does_not_change_independence(self):
        relationship = (
            content.ContentRelationship(
                relationship_id="rel:link",
                source_item_id="web:item",
                target_item_id="upstream:item",
                relationship_type="links_to",
            )
        )

        result = plan(
            bindings=explicit_bindings(),
            relationships=[
                relationship
            ],
        )

        self.assertEqual(
            result.independence_status,
            "unknown",
        )

        self.assertEqual(
            result.dependency_constraints,
            [],
        )

    def test_item_manifest_identity_mismatch_fails(self):
        with self.assertRaises(
            ValueError
        ):
            plan(
                item=make_item(
                    item_id="web:item-a"
                ),
                manifest=make_manifest(
                    item_id="web:item-b"
                ),
                bindings=explicit_bindings(),
            )

    def test_empty_candidate_text_fails_closed(self):
        candidate = {
            "candidate_id": "claim-candidate:a",
            "text": "   ",
            "confidence": 0.4,
            "source_artifact_ids": [
                "text:a"
            ],
        }

        result = plan(
            manifest=make_manifest(
                candidate=candidate
            ),
            bindings=explicit_bindings(),
        )

        record = result.candidates[0]

        self.assertEqual(
            record.claim.readiness,
            "blocked",
        )

        self.assertIn(
            "candidate_text_missing",
            record.claim.blocked_reasons,
        )

    def test_no_source_artifacts_fails_closed(self):
        candidate = {
            "candidate_id": "claim-candidate:a",
            "text": "Agreement reached.",
            "confidence": 0.4,
            "source_artifact_ids": [],
        }

        result = plan(
            manifest=make_manifest(
                candidate=candidate
            ),
            bindings=explicit_bindings(),
        )

        self.assertEqual(
            result.candidates[0]
            .evidence.readiness,
            "blocked",
        )

    def test_bridge_never_calls_persistence_functions(self):
        with (
            mock.patch.object(
                claim_intelligence,
                "upsert_intelligence_claim",
                side_effect=AssertionError(
                    "must not persist"
                ),
            ),
            mock.patch.object(
                evidence_intelligence,
                "record_evidence",
                side_effect=AssertionError(
                    "must not persist"
                ),
            ),
        ):
            result = plan(
                bindings=(
                    explicit_bindings(
                        source=True
                    )
                )
            )

        self.assertTrue(
            result.policy[
                "dry_run_only"
            ]
        )

    def test_policy_never_establishes_truth_independence_or_merit(self):
        result = plan(
            bindings=explicit_bindings()
        )

        self.assertFalse(
            result.policy[
                "establishes_truth"
            ]
        )

        self.assertFalse(
            result.policy[
                "establishes_independence"
            ]
        )

        self.assertFalse(
            result.policy[
                "affects_live_merit"
            ]
        )

        self.assertFalse(
            result.policy[
                "training_eligible"
            ]
        )


if __name__ == "__main__":
    unittest.main()
