from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


MULTIMODAL_INTELLIGENCE_BRIDGE_MODEL_VERSION = (
    "multimodal-intelligence-bridge-model-v1"
)

BridgeReadiness = Literal[
    "ready",
    "blocked",
    "not_applicable",
]

BridgeIndependenceStatus = Literal[
    "unknown",
    "blocked_by_explicit_dependency",
]


class StrictBridgeModel(BaseModel):
    if (
        ConfigDict is not None
        and hasattr(BaseModel, "model_validate")
    ):
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
        )
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class BridgeBindings(StrictBridgeModel):
    subject_key: str = ""

    subject_resolution: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    source_id: str = ""
    source_record_verified: bool = False

    media_item_id: str = ""
    media_item_record_verified: bool = False

    story_id: str = ""
    story_record_verified: bool = False

    downstream_source_observation_id: str = ""

    upstream_targets_by_item_id: Dict[
        str,
        Dict[str, Any],
    ] = Field(
        default_factory=dict
    )


class BridgeArtifactProvenance(StrictBridgeModel):
    artifact_id: str
    artifact_kind: str
    modality: str
    content_hash: str

    source_item_ids: List[str] = Field(
        default_factory=list
    )

    source_component_ids: List[str] = Field(
        default_factory=list
    )

    source_url: str = ""
    observed_at: str = ""
    extraction_method: str = ""
    source_content_hash: str = ""


class PersistenceProposal(StrictBridgeModel):
    operation: str
    readiness: BridgeReadiness

    deterministic_id: str = ""

    blocked_reasons: List[str] = Field(
        default_factory=list
    )

    kwargs: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class DependencyConstraint(StrictBridgeModel):
    relationship_id: str
    relationship_type: str

    source_item_id: str
    target_item_id: str

    persistence_relationship_type: str = ""

    independence_status: (
        BridgeIndependenceStatus
    ) = "blocked_by_explicit_dependency"

    persistence_proposal: PersistenceProposal

    policy: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class CandidateBridgeRecord(StrictBridgeModel):
    candidate_id: str
    canonical_text: str = ""

    interpretation_confidence: float | None = None

    source_artifacts: List[
        BridgeArtifactProvenance
    ] = Field(
        default_factory=list
    )

    source_validation_errors: List[str] = Field(
        default_factory=list
    )

    claim: PersistenceProposal
    evidence: PersistenceProposal
    claim_link: PersistenceProposal
    source_observation: PersistenceProposal

    policy: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class ItemIntelligenceBridgePlan(StrictBridgeModel):
    version: Literal[
        "multimodal-intelligence-bridge-model-v1"
    ] = MULTIMODAL_INTELLIGENCE_BRIDGE_MODEL_VERSION

    item_id: str
    subject_key: str = ""
    subject_resolution_status: str = "unresolved"

    source_candidate: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    candidates: List[
        CandidateBridgeRecord
    ] = Field(
        default_factory=list
    )

    dependency_constraints: List[
        DependencyConstraint
    ] = Field(
        default_factory=list
    )

    independence_status: (
        BridgeIndependenceStatus
    ) = "unknown"

    policy: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )
