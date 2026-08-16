from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from app.models import artifacts as artifact_models
from app.models import content
from app.services import (
    content_normalization,
    multimodal_extraction,
)


ARTIFACT_EXTRACTION_VERSION = "artifact-extraction-v1"

SHORT_VIDEO_FRAME_FRACTIONS = (
    0.00,
    0.20,
    0.40,
    0.60,
    0.80,
    0.98,
)

LONG_VIDEO_FRAME_FRACTIONS = (
    0.02,
    0.08,
    0.18,
    0.32,
    0.50,
    0.68,
    0.82,
    0.92,
    0.98,
)

_FORBIDDEN_ARTIFACT_FIELDS = {
    *content_normalization.FORBIDDEN_SEMANTIC_FIELDS,
    "authority",
    "source_role",
    "reliability",
    "reliability_score",
    "trust_score",
    "training_eligible",
    "independence",
    "independent",
    "is_independent",
}


def _normalized_key(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _reject_semantic_fields(
    value: Any,
    *,
    path: str = "artifact",
) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if (
                _normalized_key(raw_key)
                in _FORBIDDEN_ARTIFACT_FIELDS
            ):
                raise ValueError(
                    "Artifact extraction cannot establish "
                    "semantic intelligence field "
                    f"{path}.{raw_key}."
                )

            _reject_semantic_fields(
                child,
                path=f"{path}.{raw_key}",
            )

        return

    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_semantic_fields(
                child,
                path=f"{path}[{index}]",
            )


def _model_dump(
    value: Any,
) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    return value.dict()


def _model_copy(value: Any) -> Any:
    if hasattr(value, "model_copy"):
        return value.model_copy(deep=True)

    return value.copy(deep=True)


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _stable_id(
    prefix: str,
    *,
    operation: str,
    source_item_ids: Sequence[str],
    source_component_ids: Sequence[str],
    payload: Any,
) -> str:
    digest = _canonical_hash(
        {
            "operation": operation,
            "source_item_ids": list(source_item_ids),
            "source_component_ids": list(
                source_component_ids
            ),
            "payload": payload,
        }
    )[:24]

    return f"{prefix}:{digest}"


def _component_provenance(
    *,
    item: content.UnifiedContentItem,
    component: Any,
    extraction_method: str,
) -> artifact_models.ArtifactProvenance:
    source = component.provenance

    metadata = {
        "source_extraction_method": (
            source.extraction_method
        ),
        "source_provenance_metadata": deepcopy(
            source.metadata
        ),
    }

    _reject_semantic_fields(
        metadata,
        path="artifact.provenance.metadata",
    )

    return artifact_models.ArtifactProvenance(
        source_url=(
            source.source_url
            or item.canonical_url
        ),
        observed_at=(
            source.observed_at
            or item.observed_at
        ),
        extraction_method=extraction_method,
        source_content_hash=(
            source.content_hash
        ),
        metadata=metadata,
    )


def _item_provenance(
    item: content.UnifiedContentItem,
    *,
    extraction_method: str,
) -> artifact_models.ArtifactProvenance:
    return artifact_models.ArtifactProvenance(
        source_url=item.canonical_url,
        observed_at=item.observed_at,
        extraction_method=extraction_method,
        metadata={
            "platform": item.platform,
            "platform_surface": (
                item.platform_surface
            ),
        },
    )


def _artifact(
    *,
    artifact_kind: str,
    modality: str,
    source_item_ids: Sequence[str],
    source_component_ids: Sequence[str],
    payload: Mapping[str, Any],
    provenance: artifact_models.ArtifactProvenance,
    metadata: Optional[
        Mapping[str, Any]
    ] = None,
) -> artifact_models.ExtractionArtifact:
    clean_payload = deepcopy(
        dict(payload)
    )

    clean_metadata = deepcopy(
        dict(metadata or {})
    )

    _reject_semantic_fields(
        clean_payload,
        path="artifact.payload",
    )

    _reject_semantic_fields(
        clean_metadata,
        path="artifact.metadata",
    )

    hash_payload = {
        "artifact_kind": artifact_kind,
        "modality": modality,
        "source_item_ids": list(
            source_item_ids
        ),
        "source_component_ids": list(
            source_component_ids
        ),
        "payload": clean_payload,
    }

    return artifact_models.ExtractionArtifact(
        artifact_id=_stable_id(
            "artifact",
            operation=artifact_kind,
            source_item_ids=source_item_ids,
            source_component_ids=(
                source_component_ids
            ),
            payload=clean_payload,
        ),
        artifact_kind=artifact_kind,
        modality=modality,
        source_item_ids=list(
            source_item_ids
        ),
        source_component_ids=list(
            source_component_ids
        ),
        content_hash=_canonical_hash(
            hash_payload
        ),
        payload=clean_payload,
        provenance=provenance,
        metadata=clean_metadata,
    )


def _work(
    *,
    operation: str,
    source_item_ids: Sequence[str],
    source_component_ids: Sequence[str],
    strategy: str,
    parameters: Mapping[str, Any],
    provenance: artifact_models.ArtifactProvenance,
    depends_on_work_ids: Sequence[str] = (),
    metadata: Optional[
        Mapping[str, Any]
    ] = None,
) -> artifact_models.ArtifactWorkUnit:
    clean_parameters = deepcopy(
        dict(parameters)
    )

    clean_metadata = deepcopy(
        dict(metadata or {})
    )

    _reject_semantic_fields(
        clean_parameters,
        path="work.parameters",
    )

    _reject_semantic_fields(
        clean_metadata,
        path="work.metadata",
    )

    identity = {
        "strategy": strategy,
        "parameters": clean_parameters,
        "depends_on_work_ids": list(
            depends_on_work_ids
        ),
    }

    return artifact_models.ArtifactWorkUnit(
        work_id=_stable_id(
            "work",
            operation=operation,
            source_item_ids=source_item_ids,
            source_component_ids=(
                source_component_ids
            ),
            payload=identity,
        ),
        operation=operation,
        source_item_ids=list(
            source_item_ids
        ),
        source_component_ids=list(
            source_component_ids
        ),
        depends_on_work_ids=list(
            depends_on_work_ids
        ),
        status="pending",
        strategy=strategy,
        parameters=clean_parameters,
        provenance=provenance,
        metadata=clean_metadata,
    )


def _deduplicate_rounded(
    values: Iterable[float],
) -> Tuple[float, ...]:
    output: List[float] = []
    seen = set()

    for value in values:
        rounded = round(
            max(
                0.0,
                float(value),
            ),
            3,
        )

        if rounded in seen:
            continue

        seen.add(rounded)
        output.append(rounded)

    return tuple(output)


def frame_sampling_schedule(
    media: content.MediaComponent,
    *,
    short_video_threshold_seconds: float = (
        multimodal_extraction
        .DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> Dict[str, Any]:
    if media.media_kind != "video":
        raise ValueError(
            "Frame sampling requires "
            "a video component."
        )

    if short_video_threshold_seconds <= 0:
        raise ValueError(
            "Short-video threshold "
            "must be positive."
        )

    duration = media.duration_seconds

    if duration is None:
        return {
            "strategy": (
                "duration_probe_then_sample"
            ),
            "duration_seconds": None,
            "timestamps_seconds": [],
            "sample_limit": len(
                LONG_VIDEO_FRAME_FRACTIONS
            ),
            "requires_duration_probe": True,
        }

    if (
        duration
        <= short_video_threshold_seconds
    ):
        fractions = (
            SHORT_VIDEO_FRAME_FRACTIONS
        )

        strategy = (
            "uniform_short_video"
        )

    else:
        fractions = (
            LONG_VIDEO_FRAME_FRACTIONS
        )

        strategy = (
            "stratified_long_video"
        )

    timestamps = _deduplicate_rounded(
        duration * fraction
        for fraction in fractions
    )

    return {
        "strategy": strategy,
        "duration_seconds": float(duration),
        "timestamps_seconds": list(
            timestamps
        ),
        "sample_limit": len(fractions),
        "requires_duration_probe": False,
    }


def _text_artifact(
    item: content.UnifiedContentItem,
    component: content.TextComponent,
) -> artifact_models.ExtractionArtifact:
    return _artifact(
        artifact_kind="text_component",
        modality="text",
        source_item_ids=[
            item.item_id
        ],
        source_component_ids=[
            component.component_id
        ],
        payload={
            "role": component.role,
            "text": component.text,
            "language": component.language,
            "sequence_index": (
                component.sequence_index
            ),
            "start_seconds": (
                component.start_seconds
            ),
            "end_seconds": (
                component.end_seconds
            ),
        },
        provenance=_component_provenance(
            item=item,
            component=component,
            extraction_method=(
                "artifact_materialization:"
                "text_component"
            ),
        ),
        metadata={
            "role": component.role
        },
    )


def _media_reference_artifact(
    item: content.UnifiedContentItem,
    component: content.MediaComponent,
) -> artifact_models.ExtractionArtifact:
    return _artifact(
        artifact_kind="media_reference",
        modality=component.media_kind,
        source_item_ids=[
            item.item_id
        ],
        source_component_ids=[
            component.component_id
        ],
        payload={
            "media_kind": (
                component.media_kind
            ),
            "media_url": (
                component.media_url
            ),
            "sequence_index": (
                component.sequence_index
            ),
            "duration_seconds": (
                component.duration_seconds
            ),
            "width": component.width,
            "height": component.height,
            "has_audio": (
                component.has_audio
            ),
            "metadata": deepcopy(
                component.metadata
            ),
        },
        provenance=_component_provenance(
            item=item,
            component=component,
            extraction_method=(
                "artifact_materialization:"
                "media_reference"
            ),
        ),
    )


def _schedule_artifact(
    item: content.UnifiedContentItem,
    media: content.MediaComponent,
    schedule: Mapping[str, Any],
) -> artifact_models.ExtractionArtifact:
    return _artifact(
        artifact_kind=(
            "frame_sampling_schedule"
        ),
        modality="video",
        source_item_ids=[
            item.item_id
        ],
        source_component_ids=[
            media.component_id
        ],
        payload=schedule,
        provenance=_component_provenance(
            item=item,
            component=media,
            extraction_method=(
                "artifact_materialization:"
                "frame_schedule"
            ),
        ),
    )


def materialize_item_artifacts(
    item: content.UnifiedContentItem,
    *,
    plan: Optional[
        multimodal_extraction
        .ModalityProcessingPlan
    ] = None,
    short_video_threshold_seconds: float = (
        multimodal_extraction
        .DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> artifact_models.ItemArtifactManifest:
    if plan is None:
        plan = (
            multimodal_extraction
            .plan_content_item(
                item,
                short_video_threshold_seconds=(
                    short_video_threshold_seconds
                ),
            )
        )

    if plan.item_id != item.item_id:
        raise ValueError(
            "Artifact plan item ID does not "
            "match content item."
        )

    text_map = {
        component.component_id: component
        for component
        in item.text_components
    }

    media_map = {
        component.component_id: component
        for component
        in item.media_components
    }

    artifacts = [
        _text_artifact(
            item,
            component,
        )
        for component
        in item.text_components
    ]

    artifacts.extend(
        _media_reference_artifact(
            item,
            component,
        )
        for component
        in item.media_components
    )

    work_units: List[
        artifact_models.ArtifactWorkUnit
    ] = []

    work_by_component: Dict[
        str,
        Dict[str, str],
    ] = {}

    def register(
        component_id: str,
        operation: str,
        work: artifact_models.ArtifactWorkUnit,
    ) -> None:
        work_units.append(work)

        work_by_component.setdefault(
            component_id,
            {},
        )[operation] = work.work_id

    for component_id in (
        plan.image_visual_component_ids
    ):
        media = media_map[
            component_id
        ]

        register(
            component_id,
            "image_visual",
            _work(
                operation="image_visual",
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[
                    component_id
                ],
                strategy=(
                    "direct_image_visual"
                ),
                parameters={
                    "media_url": (
                        media.media_url
                    ),
                },
                provenance=(
                    _component_provenance(
                        item=item,
                        component=media,
                        extraction_method=(
                            "artifact_work:"
                            "image_visual"
                        ),
                    )
                ),
            ),
        )

    for component_id in (
        plan.video_frame_component_ids
    ):
        media = media_map[
            component_id
        ]

        schedule = frame_sampling_schedule(
            media,
            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )

        artifacts.append(
            _schedule_artifact(
                item,
                media,
                schedule,
            )
        )

        register(
            component_id,
            "video_frame_extract",
            _work(
                operation=(
                    "video_frame_extract"
                ),
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[
                    component_id
                ],
                strategy=(
                    schedule["strategy"]
                ),
                parameters={
                    **schedule,
                    "media_url": (
                        media.media_url
                    ),
                },
                provenance=(
                    _component_provenance(
                        item=item,
                        component=media,
                        extraction_method=(
                            "artifact_work:"
                            "video_frame_extract"
                        ),
                    )
                ),
            ),
        )

    for component_id in (
        plan.transcription_component_ids
    ):
        media = media_map[
            component_id
        ]

        register(
            component_id,
            "transcription",
            _work(
                operation="transcription",
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[
                    component_id
                ],
                strategy=(
                    "direct_media_transcription"
                ),
                parameters={
                    "media_kind": (
                        media.media_kind
                    ),
                    "media_url": (
                        media.media_url
                    ),
                    "duration_seconds": (
                        media.duration_seconds
                    ),
                },
                provenance=(
                    _component_provenance(
                        item=item,
                        component=media,
                        extraction_method=(
                            "artifact_work:"
                            "transcription"
                        ),
                    )
                ),
            ),
        )

    for component_id in (
        plan.ocr_component_ids
    ):
        media = media_map[
            component_id
        ]

        dependencies: List[str] = []

        strategy = (
            "direct_image_ocr"
        )

        if media.media_kind == "video":
            strategy = (
                "ocr_from_extracted_frames"
            )

            frame_work = (
                work_by_component
                .get(
                    component_id,
                    {},
                )
                .get(
                    "video_frame_extract"
                )
            )

            if frame_work:
                dependencies.append(
                    frame_work
                )

        register(
            component_id,
            "ocr",
            _work(
                operation="ocr",
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[
                    component_id
                ],
                strategy=strategy,
                parameters={
                    "media_kind": (
                        media.media_kind
                    ),
                    "media_url": (
                        media.media_url
                    ),
                },
                depends_on_work_ids=(
                    dependencies
                ),
                provenance=(
                    _component_provenance(
                        item=item,
                        component=media,
                        extraction_method=(
                            "artifact_work:ocr"
                        ),
                    )
                ),
            ),
        )

    for (
        caption_id,
        media_id,
    ) in plan.caption_media_alignment_pairs:
        if (
            caption_id not in text_map
            or media_id not in media_map
        ):
            raise ValueError(
                "Alignment plan references "
                "unknown components."
            )

        dependencies: List[str] = []

        for operation in (
            "image_visual",
            "video_frame_extract",
            "ocr",
            "transcription",
        ):
            dependency = (
                work_by_component
                .get(
                    media_id,
                    {},
                )
                .get(
                    operation
                )
            )

            if (
                dependency
                and dependency
                not in dependencies
            ):
                dependencies.append(
                    dependency
                )

        work_units.append(
            _work(
                operation=(
                    "caption_media_alignment"
                ),
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[
                    caption_id,
                    media_id,
                ],
                strategy=(
                    "multimodal_caption_"
                    "media_alignment"
                ),
                parameters={
                    "caption_component_id": (
                        caption_id
                    ),
                    "media_component_id": (
                        media_id
                    ),
                },
                depends_on_work_ids=(
                    dependencies
                ),
                provenance=(
                    _item_provenance(
                        item,
                        extraction_method=(
                            "artifact_work:"
                            "caption_media_alignment"
                        ),
                    )
                ),
            )
        )

    if (
        plan.conversation_traversal_required
    ):
        work_units.append(
            _work(
                operation=(
                    "conversation_traversal"
                ),
                source_item_ids=[
                    item.item_id
                ],
                source_component_ids=[],
                strategy=(
                    "platform_relationship_"
                    "discovery"
                ),
                parameters={
                    "platform": (
                        item.platform
                    ),
                    "platform_surface": (
                        item.platform_surface
                    ),
                    "container_kind": (
                        item.container_kind
                    ),
                    "canonical_url": (
                        item.canonical_url
                    ),
                },
                provenance=(
                    _item_provenance(
                        item,
                        extraction_method=(
                            "artifact_work:"
                            "conversation_traversal"
                        ),
                    )
                ),
            )
        )

    manifest = (
        artifact_models
        .ItemArtifactManifest(
            item_id=item.item_id,
            artifacts=artifacts,
            work_units=work_units,
            metadata={
                "artifact_extraction_version": (
                    ARTIFACT_EXTRACTION_VERSION
                ),
                "processing_plan_item_id": (
                    plan.item_id
                ),
            },
        )
    )

    (
        artifact_models
        .validate_item_artifact_manifest(
            manifest
        )
    )

    return manifest


def materialize_bundle_artifacts(
    bundle: content.UnifiedContentBundle,
    *,
    plan: Optional[
        multimodal_extraction
        .BundleProcessingPlan
    ] = None,
    short_video_threshold_seconds: float = (
        multimodal_extraction
        .DEFAULT_SHORT_VIDEO_THRESHOLD_SECONDS
    ),
) -> artifact_models.BundleArtifactManifest:
    if plan is None:
        plan = (
            multimodal_extraction
            .plan_content_bundle(
                bundle,
                short_video_threshold_seconds=(
                    short_video_threshold_seconds
                ),
            )
        )

    plan_by_item_id = {
        item_plan.item_id: item_plan
        for item_plan
        in plan.item_plans
    }

    if (
        set(plan_by_item_id)
        != {
            item.item_id
            for item in bundle.items
        }
    ):
        raise ValueError(
            "Bundle artifact plan does "
            "not match bundle items."
        )

    item_manifests = [
        materialize_item_artifacts(
            item,
            plan=(
                plan_by_item_id[
                    item.item_id
                ]
            ),
            short_video_threshold_seconds=(
                short_video_threshold_seconds
            ),
        )
        for item in bundle.items
    ]

    relationship_by_id = {
        relationship.relationship_id: (
            relationship
        )
        for relationship
        in bundle.relationships
    }

    work_units: List[
        artifact_models.ArtifactWorkUnit
    ] = []

    def relationship_work(
        relationship_id: str,
        operation: str,
        strategy: str,
    ) -> None:
        relationship = (
            relationship_by_id[
                relationship_id
            ]
        )

        metadata = deepcopy(
            relationship.metadata
        )

        _reject_semantic_fields(
            metadata,
            path=(
                "bundle.relationship.metadata"
            ),
        )

        work_units.append(
            _work(
                operation=operation,
                source_item_ids=[
                    relationship.source_item_id,
                    relationship.target_item_id,
                ],
                source_component_ids=[],
                strategy=strategy,
                parameters={
                    "relationship_id": (
                        relationship_id
                    ),
                    "relationship_type": (
                        relationship
                        .relationship_type
                    ),
                },
                provenance=(
                    artifact_models
                    .ArtifactProvenance(
                        source_url=(
                            relationship
                            .provenance
                            .source_url
                        ),
                        observed_at=(
                            relationship
                            .provenance
                            .observed_at
                        ),
                        extraction_method=(
                            f"artifact_work:"
                            f"{operation}"
                        ),
                        source_content_hash=(
                            relationship
                            .provenance
                            .content_hash
                        ),
                        metadata={
                            (
                                "source_"
                                "extraction_method"
                            ): (
                                relationship
                                .provenance
                                .extraction_method
                            ),
                            (
                                "relationship_metadata"
                            ): metadata,
                        },
                    )
                ),
            )
        )

    for relationship_id in (
        plan.dependency_relationship_ids
    ):
        relationship_work(
            relationship_id,
            "dependency_trace",
            "relationship_lineage_trace",
        )

    for relationship_id in (
        plan.conversation_relationship_ids
    ):
        relationship_work(
            relationship_id,
            "conversation_traversal",
            (
                "relationship_"
                "conversation_traversal"
            ),
        )

    manifest = (
        artifact_models
        .BundleArtifactManifest(
            bundle_id=bundle.bundle_id,
            item_manifests=(
                item_manifests
            ),
            work_units=work_units,
            metadata={
                "artifact_extraction_version": (
                    ARTIFACT_EXTRACTION_VERSION
                ),
                (
                    "dependency_tracing_required"
                ): (
                    plan
                    .dependency_tracing_required
                ),
                (
                    "conversation_traversal_"
                    "required"
                ): (
                    plan
                    .conversation_traversal_required
                ),
            },
        )
    )

    (
        artifact_models
        .validate_bundle_artifact_manifest(
            manifest
        )
    )

    return manifest


def _normalize_executor_output(
    raw_output: Any,
    *,
    work: artifact_models.ArtifactWorkUnit,
) -> artifact_models.ExtractionArtifact:
    if isinstance(
        raw_output,
        artifact_models.ExtractionArtifact,
    ):
        raw = _model_dump(
            raw_output
        )

    elif isinstance(raw_output, Mapping):
        raw = dict(raw_output)

    else:
        raise ValueError(
            "Artifact executor output must "
            "be an artifact object."
        )

    _reject_semantic_fields(
        raw,
        path="executor_output",
    )

    artifact_kind = str(
        raw.get("artifact_kind")
        or ""
    ).strip()

    modality = str(
        raw.get("modality")
        or ""
    ).strip()

    if not artifact_kind or not modality:
        raise ValueError(
            "Artifact executor output "
            "requires artifact_kind "
            "and modality."
        )

    payload = raw.get(
        "payload",
        {},
    )

    metadata = raw.get(
        "metadata",
        {},
    )

    if not isinstance(payload, Mapping):
        raise ValueError(
            "Artifact executor payload "
            "must be an object."
        )

    if not isinstance(metadata, Mapping):
        raise ValueError(
            "Artifact executor metadata "
            "must be an object."
        )

    source_item_ids = list(
        raw.get(
            "source_item_ids"
        )
        or work.source_item_ids
    )

    source_component_ids = list(
        raw.get(
            "source_component_ids"
        )
        or work.source_component_ids
    )

    if (
        set(source_item_ids)
        - set(work.source_item_ids)
    ):
        raise ValueError(
            "Artifact executor output "
            "cannot introduce foreign "
            "source items."
        )

    if (
        set(source_component_ids)
        - set(work.source_component_ids)
    ):
        raise ValueError(
            "Artifact executor output "
            "cannot introduce foreign "
            "source components."
        )

    return _artifact(
        artifact_kind=artifact_kind,
        modality=modality,
        source_item_ids=source_item_ids,
        source_component_ids=(
            source_component_ids
        ),
        payload=payload,
        provenance=_model_copy(
            work.provenance
        ),
        metadata=metadata,
    )


def execute_item_artifact_manifest(
    manifest: (
        artifact_models.ItemArtifactManifest
    ),
    *,
    executors: Mapping[
        str,
        Callable[..., Any],
    ],
) -> artifact_models.ItemArtifactManifest:
    result = _model_copy(
        manifest
    )

    (
        artifact_models
        .validate_item_artifact_manifest(
            result
        )
    )

    artifact_lookup = {
        artifact.artifact_id: artifact
        for artifact in result.artifacts
    }

    work_lookup = {
        work.work_id: work
        for work in result.work_units
    }

    maximum_passes = max(
        1,
        len(result.work_units) + 1,
    )

    for _ in range(maximum_passes):
        progress = False

        for work in result.work_units:
            if work.status != "pending":
                continue

            dependencies = [
                work_lookup[
                    dependency_id
                ]
                for dependency_id
                in work.depends_on_work_ids
            ]

            if any(
                dependency.status
                in {
                    "unavailable",
                    "skipped",
                }
                for dependency
                in dependencies
            ):
                work.status = "skipped"

                work.metadata = {
                    **work.metadata,
                    "skip_reason": (
                        "dependency_unavailable"
                    ),
                }

                progress = True
                continue

            if not all(
                dependency.status
                == "completed"
                for dependency
                in dependencies
            ):
                continue

            executor = executors.get(
                work.operation
            )

            if executor is None:
                continue

            dependency_outputs = {
                dependency.work_id: tuple(
                    _model_copy(
                        artifact_lookup[
                            artifact_id
                        ]
                    )
                    for artifact_id
                    in (
                        dependency
                        .output_artifact_ids
                    )
                )
                for dependency
                in dependencies
            }

            available_artifacts = tuple(
                _model_copy(artifact)
                for artifact
                in artifact_lookup.values()
            )

            try:
                raw_outputs = executor(
                    _model_copy(work),
                    available_artifacts,
                    dependency_outputs,
                )

                if isinstance(
                    raw_outputs,
                    (
                        Mapping,
                        artifact_models
                        .ExtractionArtifact,
                    ),
                ):
                    outputs = [
                        raw_outputs
                    ]

                else:
                    outputs = list(
                        raw_outputs
                        or []
                    )

                if not outputs:
                    work.status = (
                        "unavailable"
                    )

                    work.metadata = {
                        **work.metadata,
                        "failure_type": (
                            "no_output"
                        ),
                    }

                    progress = True
                    continue

                output_ids: List[str] = []

                for raw_output in outputs:
                    artifact = (
                        _normalize_executor_output(
                            raw_output,
                            work=work,
                        )
                    )

                    if (
                        artifact.artifact_id
                        not in artifact_lookup
                    ):
                        result.artifacts.append(
                            artifact
                        )

                        artifact_lookup[
                            artifact.artifact_id
                        ] = artifact

                    output_ids.append(
                        artifact.artifact_id
                    )

                work.output_artifact_ids = (
                    output_ids
                )

                work.status = "completed"

            except Exception as error:
                work.status = "unavailable"

                work.metadata = {
                    **work.metadata,
                    "failure_type": (
                        type(error).__name__
                    ),
                }

            progress = True

        if not progress:
            break

    (
        artifact_models
        .validate_item_artifact_manifest(
            result
        )
    )

    return result