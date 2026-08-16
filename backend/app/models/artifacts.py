from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


MULTIMODAL_ARTIFACT_MODEL_VERSION = "multimodal-artifact-model-v1"

ArtifactWorkStatus = Literal[
    "pending",
    "completed",
    "unavailable",
    "skipped",
]


class StrictArtifactModel(BaseModel):
    if ConfigDict is not None and hasattr(BaseModel, "model_validate"):
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
        )
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class ArtifactProvenance(StrictArtifactModel):
    source_url: str = ""
    observed_at: str = ""
    extraction_method: str = "artifact_runtime"
    source_content_hash: str = ""

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


class ExtractionArtifact(StrictArtifactModel):
    artifact_id: str = Field(
        ...,
        min_length=1,
    )

    artifact_kind: str = Field(
        ...,
        min_length=1,
    )

    modality: str = Field(
        ...,
        min_length=1,
    )

    source_item_ids: List[str] = Field(
        default_factory=list
    )

    source_component_ids: List[str] = Field(
        default_factory=list
    )

    content_hash: str = Field(
        ...,
        min_length=1,
    )

    payload: Dict[str, Any] = Field(
        default_factory=dict
    )

    provenance: ArtifactProvenance = Field(
        default_factory=ArtifactProvenance
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


class ArtifactWorkUnit(StrictArtifactModel):
    work_id: str = Field(
        ...,
        min_length=1,
    )

    operation: str = Field(
        ...,
        min_length=1,
    )

    source_item_ids: List[str] = Field(
        default_factory=list
    )

    source_component_ids: List[str] = Field(
        default_factory=list
    )

    depends_on_work_ids: List[str] = Field(
        default_factory=list
    )

    status: ArtifactWorkStatus = "pending"

    strategy: str = ""

    parameters: Dict[str, Any] = Field(
        default_factory=dict
    )

    output_artifact_ids: List[str] = Field(
        default_factory=list
    )

    provenance: ArtifactProvenance = Field(
        default_factory=ArtifactProvenance
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


class ItemArtifactManifest(StrictArtifactModel):
    version: Literal[
        "multimodal-artifact-model-v1"
    ] = MULTIMODAL_ARTIFACT_MODEL_VERSION

    item_id: str = Field(
        ...,
        min_length=1,
    )

    artifacts: List[ExtractionArtifact] = Field(
        default_factory=list
    )

    work_units: List[ArtifactWorkUnit] = Field(
        default_factory=list
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


class BundleArtifactManifest(StrictArtifactModel):
    version: Literal[
        "multimodal-artifact-model-v1"
    ] = MULTIMODAL_ARTIFACT_MODEL_VERSION

    bundle_id: str = Field(
        ...,
        min_length=1,
    )

    item_manifests: List[
        ItemArtifactManifest
    ] = Field(
        default_factory=list
    )

    work_units: List[
        ArtifactWorkUnit
    ] = Field(
        default_factory=list
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


def validate_item_artifact_manifest(
    manifest: ItemArtifactManifest,
) -> None:
    artifact_ids = [
        artifact.artifact_id
        for artifact in manifest.artifacts
    ]

    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError(
            "Artifact IDs must be unique "
            "within an item manifest."
        )

    work_ids = [
        work.work_id
        for work in manifest.work_units
    ]

    if len(work_ids) != len(set(work_ids)):
        raise ValueError(
            "Work IDs must be unique "
            "within an item manifest."
        )

    work_id_set = set(work_ids)
    artifact_id_set = set(artifact_ids)

    for work in manifest.work_units:
        if work.work_id in work.depends_on_work_ids:
            raise ValueError(
                "Artifact work cannot depend on itself."
            )

        if set(work.depends_on_work_ids) - work_id_set:
            raise ValueError(
                "Artifact work references "
                "unknown dependencies."
            )

        if set(work.output_artifact_ids) - artifact_id_set:
            raise ValueError(
                "Artifact work references "
                "unknown output artifacts."
            )

        if (
            work.status != "completed"
            and work.output_artifact_ids
        ):
            raise ValueError(
                "Only completed artifact work "
                "may expose outputs."
            )


def validate_bundle_artifact_manifest(
    manifest: BundleArtifactManifest,
) -> None:
    item_ids = [
        item.item_id
        for item in manifest.item_manifests
    ]

    if len(item_ids) != len(set(item_ids)):
        raise ValueError(
            "Bundle artifact item IDs "
            "must be unique."
        )

    for item_manifest in manifest.item_manifests:
        validate_item_artifact_manifest(
            item_manifest
        )

    work_ids = [
        work.work_id
        for work in manifest.work_units
    ]

    if len(work_ids) != len(set(work_ids)):
        raise ValueError(
            "Bundle artifact work IDs "
            "must be unique."
        )

    work_id_set = set(work_ids)

    for work in manifest.work_units:
        if work.work_id in work.depends_on_work_ids:
            raise ValueError(
                "Bundle artifact work "
                "cannot depend on itself."
            )

        if set(work.depends_on_work_ids) - work_id_set:
            raise ValueError(
                "Bundle artifact work "
                "references unknown dependencies."
            )