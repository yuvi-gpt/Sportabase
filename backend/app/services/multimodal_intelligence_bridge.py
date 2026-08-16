from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from app.intelligence import claims as claim_intelligence
from app.intelligence import evidence as evidence_intelligence
from app.intelligence import sources as source_intelligence
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models


MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION = (
    "multimodal-intelligence-bridge-runtime-v1"
)

_ALLOWED_EVIDENTIARY_ARTIFACT_KINDS = {
    "text_component",
    "ocr_text",
    "transcript",
    "visual_observations",
}

_EXPLICIT_DEPENDENCY_RELATIONSHIPS = {
    "quote_of",
    "repost_of",
    "crosspost_of",
    "derives_from",
}

_DEPENDENCY_RELATIONSHIP_MAP = {
    "quote_of": "attributed_to",
    "repost_of": "derived_from",
    "crosspost_of": "derived_from",
    "derives_from": "derived_from",
}


def _clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _surface_normalize_claim_text(
    value: Any,
) -> str:
    return _clean(
        unicodedata.normalize(
            "NFKC",
            str(value or ""),
        )
    )


def _interpretation_confidence(
    value: Any,
) -> float | None:
    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    if result < 0.0 or result > 1.0:
        return None

    return result


def _identity_url(
    value: Any,
) -> str:
    return _clean(value)


def _subject_binding(
    bindings: bridge_models.BridgeBindings,
) -> tuple[str, str]:
    explicit = _clean(
        bindings.subject_key
    )

    if explicit:
        return (
            explicit,
            "explicit_binding",
        )

    resolution = dict(
        bindings.subject_resolution
        or {}
    )

    if (
        _clean(
            resolution.get("status")
        ).lower()
        != "exact_unique"
    ):
        return (
            "",
            _clean(
                resolution.get("status")
            ).lower()
            or "unresolved",
        )

    entity = resolution.get("entity")

    if not isinstance(
        entity,
        Mapping,
    ):
        return (
            "",
            "invalid_exact_unique_resolution",
        )

    entity_key = _clean(
        entity.get("entity_key")
    )

    if not entity_key:
        return (
            "",
            "invalid_exact_unique_resolution",
        )

    return (
        entity_key,
        "exact_unique",
    )


def _canonical_claim_key(
    *,
    subject_key: str,
    canonical_text: str,
) -> str:
    normalized_subject = _clean(
        subject_key
    ).casefold()

    normalized_text = (
        _surface_normalize_claim_text(
            canonical_text
        )
        .casefold()
    )

    if not normalized_subject:
        raise ValueError(
            "Canonical claim key requires a subject."
        )

    if not normalized_text:
        raise ValueError(
            "Canonical claim key requires claim text."
        )

    text_digest = hashlib.sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()

    return (
        "multimodal|"
        + normalized_subject
        + "|"
        + text_digest
    )


def _artifact_provenance(
    artifact: artifact_models.ExtractionArtifact,
) -> bridge_models.BridgeArtifactProvenance:
    return bridge_models.BridgeArtifactProvenance(
        artifact_id=artifact.artifact_id,
        artifact_kind=artifact.artifact_kind,
        modality=artifact.modality,
        content_hash=artifact.content_hash,
        source_item_ids=list(
            artifact.source_item_ids
        ),
        source_component_ids=list(
            artifact.source_component_ids
        ),
        source_url=_clean(
            artifact.provenance.source_url
        ),
        observed_at=_clean(
            artifact.provenance.observed_at
        ),
        extraction_method=_clean(
            artifact.provenance.extraction_method
        ),
        source_content_hash=_clean(
            artifact.provenance.source_content_hash
        ),
    )


def _candidate_observed_at(
    item: content.UnifiedContentItem,
    source_artifacts: Sequence[
        artifact_models.ExtractionArtifact
    ],
) -> str:
    item_observed = _clean(
        item.observed_at
    )

    if item_observed:
        return item_observed

    for artifact in source_artifacts:
        observed_at = _clean(
            artifact.provenance.observed_at
        )

        if observed_at:
            return observed_at

    return ""


def _candidate_canonical_url(
    item: content.UnifiedContentItem,
    source_artifacts: Sequence[
        artifact_models.ExtractionArtifact
    ],
) -> str:
    item_url = _clean(
        item.canonical_url
    )

    if item_url:
        return item_url

    for artifact in source_artifacts:
        source_url = _clean(
            artifact.provenance.source_url
        )

        if source_url:
            return source_url

    return ""


def _source_candidate(
    item: content.UnifiedContentItem,
) -> Dict[str, Any]:
    # A platform host is not the publisher identity
    # for social posts. Do not turn x.com, instagram.com,
    # etc. into the author/source.
    if (
        _clean(item.platform).casefold()
        != "web"
    ):
        return {
            "status": "not_derived",
            "reason": "social_or_nonweb_source_requires_explicit_binding",
        }

    canonical_url = _clean(
        item.canonical_url
    )

    if not canonical_url:
        return {
            "status": "not_derived",
            "reason": "canonical_url_missing",
        }

    domain_resolver = (
        lambda url: (
            source_intelligence
            .source_domain_for_url(
                url,
                normalize_url=_identity_url,
            )
        )
    )

    domain = domain_resolver(
        canonical_url
    )

    if not domain:
        return {
            "status": "not_derived",
            "reason": "source_domain_unavailable",
        }

    key_resolver = (
        lambda url, source_type: (
            source_intelligence
            .source_key_for_url(
                url,
                source_type,
                domain_resolver=domain_resolver,
            )
        )
    )

    source_key = (
        source_intelligence
        .source_key_for_url(
            canonical_url,
            "publisher",
            domain_resolver=domain_resolver,
        )
    )

    source_id = (
        source_intelligence
        .source_id_for_url(
            canonical_url,
            "publisher",
            key_resolver=key_resolver,
        )
    )

    return {
        "status": "derived_unverified",
        "source_type": "publisher",
        "canonical_domain": domain,
        "source_key": source_key,
        "source_id": source_id,
        "canonical_url": canonical_url,
        "record_exists": False,
        "persistence_ready": False,
    }


def _proposal(
    *,
    operation: str,
    kwargs: Mapping[str, Any],
    deterministic_id: str = "",
    blocked_reasons: Iterable[str] = (),
    not_applicable: bool = False,
) -> bridge_models.PersistenceProposal:
    reasons = []

    for reason in blocked_reasons:
        cleaned = _clean(reason)

        if (
            cleaned
            and cleaned not in reasons
        ):
            reasons.append(cleaned)

    if not_applicable:
        readiness = "not_applicable"
    elif reasons:
        readiness = "blocked"
    else:
        readiness = "ready"

    return bridge_models.PersistenceProposal(
        operation=operation,
        readiness=readiness,
        deterministic_id=_clean(
            deterministic_id
        ),
        blocked_reasons=reasons,
        kwargs=dict(kwargs),
    )


def _candidate_source_artifacts(
    *,
    item_id: str,
    candidate: Mapping[str, Any],
    artifact_by_id: Mapping[
        str,
        artifact_models.ExtractionArtifact,
    ],
) -> tuple[
    List[artifact_models.ExtractionArtifact],
    List[str],
]:
    raw_ids = candidate.get(
        "source_artifact_ids",
        [],
    )

    if not isinstance(
        raw_ids,
        list,
    ):
        return (
            [],
            [
                "source_artifact_ids_not_a_list"
            ],
        )

    source_ids = []

    for value in raw_ids:
        artifact_id = _clean(value)

        if (
            artifact_id
            and artifact_id not in source_ids
        ):
            source_ids.append(
                artifact_id
            )

    errors: List[str] = []
    artifacts: List[
        artifact_models.ExtractionArtifact
    ] = []

    if not source_ids:
        errors.append(
            "candidate_has_no_source_artifacts"
        )

    for artifact_id in source_ids:
        artifact = artifact_by_id.get(
            artifact_id
        )

        if artifact is None:
            errors.append(
                "unknown_source_artifact:"
                + artifact_id
            )
            continue

        if (
            artifact.artifact_kind
            not in _ALLOWED_EVIDENTIARY_ARTIFACT_KINDS
        ):
            errors.append(
                "unsupported_source_artifact_kind:"
                + artifact.artifact_kind
                + ":"
                + artifact_id
            )
            continue

        if (
            item_id
            not in set(
                artifact.source_item_ids
            )
        ):
            errors.append(
                "foreign_source_artifact:"
                + artifact_id
            )
            continue

        artifacts.append(
            artifact
        )

    return (
        artifacts,
        errors,
    )


def _evidence_id_for_key(
    evidence_key: str,
) -> str:
    return hashlib.sha256(
        (
            "evidence|"
            + evidence_key
        ).encode("utf-8")
    ).hexdigest()


def _build_candidate_record(
    *,
    item: content.UnifiedContentItem,
    candidate_container: (
        artifact_models.ExtractionArtifact
    ),
    raw_candidate: Mapping[str, Any],
    artifact_by_id: Mapping[
        str,
        artifact_models.ExtractionArtifact,
    ],
    bindings: bridge_models.BridgeBindings,
    subject_key: str,
) -> bridge_models.CandidateBridgeRecord:
    candidate_id = _clean(
        raw_candidate.get("candidate_id")
    )

    canonical_text = (
        _surface_normalize_claim_text(
            raw_candidate.get("text")
        )
    )

    interpretation_confidence = (
        _interpretation_confidence(
            raw_candidate.get(
                "confidence"
            )
        )
    )

    source_artifacts, source_errors = (
        _candidate_source_artifacts(
            item_id=item.item_id,
            candidate=raw_candidate,
            artifact_by_id=artifact_by_id,
        )
    )

    common_blockers = list(
        source_errors
    )

    if not candidate_id:
        common_blockers.append(
            "candidate_id_missing"
        )

    if not canonical_text:
        common_blockers.append(
            "candidate_text_missing"
        )

    if not subject_key:
        common_blockers.append(
            "subject_unresolved"
        )

    observed_at = (
        _candidate_observed_at(
            item,
            source_artifacts,
        )
    )

    if not observed_at:
        common_blockers.append(
            "observed_at_missing"
        )

    canonical_url = (
        _candidate_canonical_url(
            item,
            source_artifacts,
        )
    )

    provenance_rows = [
        _artifact_provenance(
            artifact
        )
        for artifact in source_artifacts
    ]

    provenance_payload = [
        (
            row.model_dump(
                mode="json"
            )
            if hasattr(
                row,
                "model_dump",
            )
            else row.dict()
        )
        for row in provenance_rows
    ]

    common_metadata = {
        "bridge_runtime_version": (
            MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION
        ),
        "candidate_id": candidate_id,
        "candidate_container_artifact_id": (
            candidate_container.artifact_id
        ),
        "candidate_container_content_hash": (
            candidate_container.content_hash
        ),
        "interpretation_confidence": (
            interpretation_confidence
        ),
        "candidate_uncertainty": (
            _clean(
                raw_candidate.get(
                    "uncertainty"
                )
            )
        ),
        "modality_sources": [
            _clean(value)
            for value
            in (
                raw_candidate.get(
                    "modality_sources",
                    [],
                )
                if isinstance(
                    raw_candidate.get(
                        "modality_sources",
                        [],
                    ),
                    list,
                )
                else []
            )
            if _clean(value)
        ],
        "source_artifact_provenance": (
            provenance_payload
        ),
        "training_eligible": False,
        "establishes_truth": False,
        "establishes_independence": False,
        "affects_live_merit": False,
    }

    claim_kwargs: Dict[
        str,
        Any,
    ] = {}

    claim_id = ""
    claim_blockers = list(
        common_blockers
    )

    if (
        subject_key
        and canonical_text
    ):
        canonical_key = (
            _canonical_claim_key(
                subject_key=subject_key,
                canonical_text=canonical_text,
            )
        )

        claim_id = (
            claim_intelligence
            .claim_id_for_canonical_key(
                canonical_key
            )
        )

        claim_kwargs = {
            "canonical_key": canonical_key,
            "subject_key": subject_key,
            "canonical_text": (
                canonical_text
            ),
            "claim_type": (
                "multimodal_candidate"
            ),
            "metadata": (
                common_metadata
            ),
            "seen_at": observed_at,
        }

    claim_proposal = _proposal(
        operation="upsert_intelligence_claim",
        kwargs=claim_kwargs,
        deterministic_id=claim_id,
        blocked_reasons=claim_blockers,
    )

    evidence_kwargs: Dict[
        str,
        Any,
    ] = {}

    evidence_id = ""
    evidence_blockers = list(
        common_blockers
    )

    if (
        subject_key
        and canonical_text
        and observed_at
        and candidate_id
    ):
        reference_key = (
            "multimodal-candidate|"
            + candidate_id
        )

        evidence_kwargs = {
            "evidence_type": (
                "multimodal_claim_candidate"
            ),
            "subject_key": (
                subject_key
            ),
            "observed_at": (
                observed_at
            ),
            "claim_summary": (
                canonical_text
            ),
            "canonical_url": (
                canonical_url
            ),
            "reference_key": (
                reference_key
            ),
            "verification_status": (
                "unverified"
            ),
            "published_at": (
                _clean(
                    item.published_at
                )
                or None
            ),
            "metadata": (
                common_metadata
            ),
        }

        evidence_key = (
            evidence_intelligence
            .evidence_key_for_record(
                evidence_type=(
                    evidence_kwargs[
                        "evidence_type"
                    ]
                ),
                subject_key=subject_key,
                observed_at=observed_at,
                canonical_url=(
                    canonical_url
                ),
                reference_key=(
                    reference_key
                ),
                verification_status=(
                    "unverified"
                ),
                normalize_url=_identity_url,
            )
        )

        evidence_id = (
            _evidence_id_for_key(
                evidence_key
            )
        )

    evidence_proposal = _proposal(
        operation="record_evidence",
        kwargs=evidence_kwargs,
        deterministic_id=evidence_id,
        blocked_reasons=evidence_blockers,
    )

    claim_link_kwargs: Dict[
        str,
        Any,
    ] = {}

    claim_link_id = ""
    claim_link_blockers = []

    if (
        claim_proposal.readiness
        != "ready"
    ):
        claim_link_blockers.append(
            "claim_proposal_not_ready"
        )

    if (
        evidence_proposal.readiness
        != "ready"
    ):
        claim_link_blockers.append(
            "evidence_proposal_not_ready"
        )

    if (
        not claim_link_blockers
        and claim_id
        and evidence_id
        and observed_at
    ):
        claim_link_kwargs = {
            "claim_id": claim_id,
            "relationship_type": (
                "aligned_to"
            ),
            "observed_at": observed_at,
            "confidence": None,
            "evidence_id": evidence_id,
            "metadata": {
                "bridge_runtime_version": (
                    MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION
                ),
                "candidate_id": (
                    candidate_id
                ),
                "semantic_candidate_only": (
                    True
                ),
                "establishes_support": (
                    False
                ),
                "establishes_truth": (
                    False
                ),
                "affects_live_merit": (
                    False
                ),
            },
        }

        claim_link_id = (
            claim_intelligence
            .claim_link_id_for_record(
                claim_id=claim_id,
                relationship_type=(
                    "aligned_to"
                ),
                observed_at=observed_at,
                confidence=None,
                evidence_id=evidence_id,
            )
        )

    claim_link_proposal = _proposal(
        operation="record_claim_link",
        kwargs=claim_link_kwargs,
        deterministic_id=claim_link_id,
        blocked_reasons=(
            claim_link_blockers
        ),
    )

    observation_kwargs: Dict[
        str,
        Any,
    ] = {}

    observation_blockers = list(
        common_blockers
    )

    source_id = _clean(
        bindings.source_id
    )

    if (
        not source_id
        or not bindings.source_record_verified
    ):
        observation_blockers.append(
            "source_record_not_verified"
        )

    if (
        source_id
        and bindings.source_record_verified
        and subject_key
        and canonical_text
        and observed_at
    ):
        observation_kwargs = {
            "source_id": source_id,
            "subject_key": subject_key,
            "observation_type": (
                "report"
            ),
            "observed_at": (
                observed_at
            ),
            "status": (
                "unresolved"
            ),
            "claim_summary": (
                canonical_text
            ),
            "provenance_url": (
                canonical_url
            ),
            # Model interpretation confidence is not
            # source-observation confidence.
            "confidence": None,
            "metadata": {
                **common_metadata,
                "media_item_binding_ignored": (
                    bool(
                        _clean(
                            bindings.media_item_id
                        )
                    )
                    and not (
                        bindings
                        .media_item_record_verified
                    )
                ),
                "story_binding_ignored": (
                    bool(
                        _clean(
                            bindings.story_id
                        )
                    )
                    and not (
                        bindings
                        .story_record_verified
                    )
                ),
            },
        }

        if (
            bindings.media_item_record_verified
            and _clean(
                bindings.media_item_id
            )
        ):
            observation_kwargs[
                "media_item_id"
            ] = _clean(
                bindings.media_item_id
            )

        if (
            bindings.story_record_verified
            and _clean(
                bindings.story_id
            )
        ):
            observation_kwargs[
                "story_id"
            ] = _clean(
                bindings.story_id
            )

    source_observation_proposal = (
        _proposal(
            operation=(
                "record_source_observation"
            ),
            kwargs=observation_kwargs,
            blocked_reasons=(
                observation_blockers
            ),
        )
    )

    return (
        bridge_models
        .CandidateBridgeRecord(
            candidate_id=(
                candidate_id
            ),
            canonical_text=(
                canonical_text
            ),
            interpretation_confidence=(
                interpretation_confidence
            ),
            source_artifacts=(
                provenance_rows
            ),
            source_validation_errors=(
                source_errors
            ),
            claim=claim_proposal,
            evidence=evidence_proposal,
            claim_link=(
                claim_link_proposal
            ),
            source_observation=(
                source_observation_proposal
            ),
            policy={
                "training_eligible": (
                    False
                ),
                "establishes_truth": (
                    False
                ),
                "establishes_independence": (
                    False
                ),
                "affects_live_merit": (
                    False
                ),
            },
        )
    )


def _dependency_constraints(
    *,
    item: content.UnifiedContentItem,
    relationships: Sequence[
        content.ContentRelationship
    ],
    bindings: bridge_models.BridgeBindings,
) -> List[
    bridge_models.DependencyConstraint
]:
    output = []

    for relationship in relationships:
        if (
            relationship.source_item_id
            != item.item_id
        ):
            continue

        if (
            relationship.relationship_type
            not in (
                _EXPLICIT_DEPENDENCY_RELATIONSHIPS
            )
        ):
            continue

        persistence_relationship = (
            _DEPENDENCY_RELATIONSHIP_MAP[
                relationship.relationship_type
            ]
        )

        blockers = []

        downstream_id = _clean(
            bindings
            .downstream_source_observation_id
        )

        if not downstream_id:
            blockers.append(
                "downstream_source_observation_not_bound"
            )

        upstream_binding = (
            bindings
            .upstream_targets_by_item_id
            .get(
                relationship.target_item_id,
                {},
            )
        )

        if not isinstance(
            upstream_binding,
            Mapping,
        ):
            upstream_binding = {}

        upstream_verified = bool(
            upstream_binding.get(
                "record_verified",
                False,
            )
        )

        upstream_fields = {
            key: _clean(
                upstream_binding.get(key)
            )
            for key in (
                "upstream_source_observation_id",
                "upstream_reporter_observation_id",
                "upstream_source_id",
                "upstream_reporter_id",
            )
        }

        active_upstream = [
            (
                key,
                value,
            )
            for (
                key,
                value,
            )
            in upstream_fields.items()
            if value
        ]

        if (
            not upstream_verified
            or len(active_upstream) != 1
        ):
            blockers.append(
                "upstream_dependency_target_not_verified"
            )

        observed_at = (
            _clean(
                relationship
                .provenance
                .observed_at
            )
            or _clean(
                item.observed_at
            )
        )

        if not observed_at:
            blockers.append(
                "dependency_observed_at_missing"
            )

        kwargs: Dict[
            str,
            Any,
        ] = {}

        deterministic_id = ""

        if not blockers:
            upstream_key, upstream_id = (
                active_upstream[0]
            )

            kwargs = {
                "relationship_type": (
                    persistence_relationship
                ),
                "observed_at": (
                    observed_at
                ),
                "confidence": None,
                "downstream_source_observation_id": (
                    downstream_id
                ),
                upstream_key: (
                    upstream_id
                ),
                "metadata": {
                    "bridge_runtime_version": (
                        MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION
                    ),
                    "content_relationship_id": (
                        relationship
                        .relationship_id
                    ),
                    "content_relationship_type": (
                        relationship
                        .relationship_type
                    ),
                    "source_url": (
                        _clean(
                            relationship
                            .provenance
                            .source_url
                        )
                    ),
                    "extraction_method": (
                        _clean(
                            relationship
                            .provenance
                            .extraction_method
                        )
                    ),
                    "source_content_hash": (
                        _clean(
                            relationship
                            .provenance
                            .content_hash
                        )
                    ),
                    "establishes_independence": (
                        False
                    ),
                    "affects_live_merit": (
                        False
                    ),
                },
            }

            # Import locally so the runtime surface
            # stays read-only; this helper only hashes.
            from app.intelligence import (
                dependencies as dependency_intelligence,
            )

            deterministic_id = (
                dependency_intelligence
                .observation_dependency_id_for_record(
                    relationship_type=(
                        persistence_relationship
                    ),
                    observed_at=(
                        observed_at
                    ),
                    confidence=None,
                    downstream_source_observation_id=(
                        downstream_id
                    ),
                    **{
                        upstream_key: (
                            upstream_id
                        )
                    },
                )
            )

        proposal = _proposal(
            operation=(
                "record_observation_dependency"
            ),
            kwargs=kwargs,
            deterministic_id=(
                deterministic_id
            ),
            blocked_reasons=blockers,
        )

        output.append(
            bridge_models
            .DependencyConstraint(
                relationship_id=(
                    relationship
                    .relationship_id
                ),
                relationship_type=(
                    relationship
                    .relationship_type
                ),
                source_item_id=(
                    relationship
                    .source_item_id
                ),
                target_item_id=(
                    relationship
                    .target_item_id
                ),
                persistence_relationship_type=(
                    persistence_relationship
                ),
                independence_status=(
                    "blocked_by_explicit_dependency"
                ),
                persistence_proposal=(
                    proposal
                ),
                policy={
                    "explicit_dependency_blocks_independence": (
                        True
                    ),
                    "absence_of_dependency_does_not_establish_independence": (
                        True
                    ),
                    "establishes_truth": (
                        False
                    ),
                    "affects_live_merit": (
                        False
                    ),
                },
            )
        )

    return output


def build_item_intelligence_bridge(
    *,
    item: content.UnifiedContentItem,
    manifest: artifact_models.ItemArtifactManifest,
    bindings: (
        bridge_models.BridgeBindings
        | None
    ) = None,
    relationships: Sequence[
        content.ContentRelationship
    ] = (),
) -> (
    bridge_models
    .ItemIntelligenceBridgePlan
):
    content.validate_unified_content_item(
        item
    )

    artifact_models.validate_item_artifact_manifest(
        manifest
    )

    if manifest.item_id != item.item_id:
        raise ValueError(
            "Bridge item and artifact manifest IDs must match."
        )

    normalized_bindings = (
        bindings
        or bridge_models.BridgeBindings()
    )

    subject_key, subject_status = (
        _subject_binding(
            normalized_bindings
        )
    )

    artifact_by_id = {
        artifact.artifact_id: artifact
        for artifact in manifest.artifacts
    }

    candidate_records = []

    for candidate_container in (
        manifest.artifacts
    ):
        if (
            candidate_container.artifact_kind
            != "claim_candidates"
        ):
            continue

        raw_candidates = (
            candidate_container.payload.get(
                "candidates",
                [],
            )
        )

        if not isinstance(
            raw_candidates,
            list,
        ):
            continue

        for raw_candidate in raw_candidates:
            if not isinstance(
                raw_candidate,
                Mapping,
            ):
                continue

            candidate_records.append(
                _build_candidate_record(
                    item=item,
                    candidate_container=(
                        candidate_container
                    ),
                    raw_candidate=(
                        raw_candidate
                    ),
                    artifact_by_id=(
                        artifact_by_id
                    ),
                    bindings=(
                        normalized_bindings
                    ),
                    subject_key=(
                        subject_key
                    ),
                )
            )

    dependency_constraints = (
        _dependency_constraints(
            item=item,
            relationships=relationships,
            bindings=normalized_bindings,
        )
    )

    independence_status = (
        "blocked_by_explicit_dependency"
        if dependency_constraints
        else "unknown"
    )

    return (
        bridge_models
        .ItemIntelligenceBridgePlan(
            item_id=item.item_id,
            subject_key=subject_key,
            subject_resolution_status=(
                subject_status
            ),
            source_candidate=(
                _source_candidate(
                    item
                )
            ),
            candidates=(
                candidate_records
            ),
            dependency_constraints=(
                dependency_constraints
            ),
            independence_status=(
                independence_status
            ),
            policy={
                "bridge_runtime_version": (
                    MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION
                ),
                "dry_run_only": True,
                "training_eligible": False,
                "establishes_truth": False,
                "establishes_independence": False,
                "affects_live_merit": False,
                "model_confidence_is_not_source_confidence": (
                    True
                ),
                "source_row_must_be_verified_before_observation_persistence": (
                    True
                ),
                "media_item_row_must_be_verified_before_fk_use": (
                    True
                ),
                "ambiguity_fails_closed": (
                    True
                ),
            },
        )
    )
