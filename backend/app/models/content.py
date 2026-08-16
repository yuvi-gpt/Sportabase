from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover
    ConfigDict = None


UNIFIED_CONTENT_MODEL_VERSION = (
    "unified-content-model-v1"
)


ContentContainerKind = Literal[
    "article",
    "post",
    "story",
    "thread",
    "comment",
    "reply",
    "media",
    "unknown",
]

TextRole = Literal[
    "title",
    "body",
    "caption",
    "description",
    "transcript",
    "on_screen_text",
    "alt_text",
    "comment",
    "reply",
    "link_text",
    "other",
]

MediaKind = Literal[
    "image",
    "video",
    "audio",
]

AlignmentStatus = Literal[
    "aligned",
    "partially_aligned",
    "unrelated",
    "unknown",
]

ContentRelationshipType = Literal[
    "reply_to",
    "quote_of",
    "repost_of",
    "crosspost_of",
    "derives_from",
    "links_to",
    "part_of",
]


class StrictContentModel(BaseModel):
    if (
        ConfigDict is not None
        and hasattr(
            BaseModel,
            "model_validate",
        )
    ):
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
        )
    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            validate_assignment = True


class ActorReference(
    StrictContentModel
):
    platform_actor_id: str = ""
    handle: str = ""
    display_name: str = ""
    profile_url: str = ""
    canonical_entity_id: str = ""

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class ProvenanceRecord(
    StrictContentModel
):
    source_url: str = ""
    observed_at: str = ""
    extraction_method: str = "unknown"
    content_hash: str = ""

    extraction_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class TextComponent(
    StrictContentModel
):
    component_id: str = Field(
        ...,
        min_length=1,
    )

    role: TextRole

    text: str = Field(
        ...,
        min_length=1,
    )

    language: str = ""

    sequence_index: Optional[
        int
    ] = Field(
        default=None,
        ge=0,
    )

    start_seconds: Optional[
        float
    ] = Field(
        default=None,
        ge=0.0,
    )

    end_seconds: Optional[
        float
    ] = Field(
        default=None,
        ge=0.0,
    )

    provenance: ProvenanceRecord = Field(
        default_factory=ProvenanceRecord
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class MediaComponent(
    StrictContentModel
):
    component_id: str = Field(
        ...,
        min_length=1,
    )

    media_kind: MediaKind
    media_url: str = ""

    sequence_index: Optional[
        int
    ] = Field(
        default=None,
        ge=0,
    )

    duration_seconds: Optional[
        float
    ] = Field(
        default=None,
        ge=0.0,
    )

    width: Optional[
        int
    ] = Field(
        default=None,
        ge=1,
    )

    height: Optional[
        int
    ] = Field(
        default=None,
        ge=1,
    )

    has_audio: Optional[
        bool
    ] = None

    provenance: ProvenanceRecord = Field(
        default_factory=ProvenanceRecord
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class EngagementSnapshot(
    StrictContentModel
):
    observed_at: str = ""

    metrics: Dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class AlignmentAssessment(
    StrictContentModel
):
    left_component_id: str = Field(
        ...,
        min_length=1,
    )

    right_component_id: str = Field(
        ...,
        min_length=1,
    )

    status: AlignmentStatus = "unknown"

    confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
    )

    method: str = "unassessed"

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class ContentClaimCandidate(
    StrictContentModel
):
    candidate_id: str = Field(
        ...,
        min_length=1,
    )

    text: str = Field(
        ...,
        min_length=1,
    )

    origin_component_ids: List[
        str
    ] = Field(
        default_factory=list
    )

    extraction_method: str = "unknown"

    extraction_confidence: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class UnifiedContentItem(
    StrictContentModel
):
    version: Literal[
        "unified-content-model-v1"
    ] = UNIFIED_CONTENT_MODEL_VERSION

    item_id: str = Field(
        ...,
        min_length=1,
    )

    platform: str = Field(
        ...,
        min_length=1,
    )

    platform_surface: str = ""

    container_kind: (
        ContentContainerKind
    )

    canonical_url: str = ""
    platform_content_id: str = ""

    actor: ActorReference = Field(
        default_factory=ActorReference
    )

    published_at: str = ""
    observed_at: str = ""

    ephemeral: bool = False
    expires_at: str = ""

    text_components: List[
        TextComponent
    ] = Field(
        default_factory=list
    )

    media_components: List[
        MediaComponent
    ] = Field(
        default_factory=list
    )

    claim_candidates: List[
        ContentClaimCandidate
    ] = Field(
        default_factory=list
    )

    alignments: List[
        AlignmentAssessment
    ] = Field(
        default_factory=list
    )

    engagement_snapshots: List[
        EngagementSnapshot
    ] = Field(
        default_factory=list
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class ContentRelationship(
    StrictContentModel
):
    relationship_id: str = Field(
        ...,
        min_length=1,
    )

    source_item_id: str = Field(
        ...,
        min_length=1,
    )

    target_item_id: str = Field(
        ...,
        min_length=1,
    )

    relationship_type: (
        ContentRelationshipType
    )

    provenance: ProvenanceRecord = Field(
        default_factory=ProvenanceRecord
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class UnifiedContentBundle(
    StrictContentModel
):
    version: Literal[
        "unified-content-model-v1"
    ] = UNIFIED_CONTENT_MODEL_VERSION

    bundle_id: str = Field(
        ...,
        min_length=1,
    )

    root_item_ids: List[
        str
    ] = Field(
        default_factory=list
    )

    items: List[
        UnifiedContentItem
    ] = Field(
        default_factory=list
    )

    relationships: List[
        ContentRelationship
    ] = Field(
        default_factory=list
    )

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


def validate_unified_content_item(
    item: UnifiedContentItem,
) -> None:
    component_ids = [
        component.component_id
        for component
        in item.text_components
    ] + [
        component.component_id
        for component
        in item.media_components
    ]

    if not component_ids:
        raise ValueError(
            "Unified content item must "
            "contain at least one text "
            "or media component."
        )

    if (
        len(component_ids)
        != len(
            set(
                component_ids
            )
        )
    ):
        raise ValueError(
            "Unified content component IDs "
            "must be unique within an item."
        )

    component_id_set = set(
        component_ids
    )

    candidate_ids = [
        candidate.candidate_id
        for candidate
        in item.claim_candidates
    ]

    if (
        len(candidate_ids)
        != len(
            set(
                candidate_ids
            )
        )
    ):
        raise ValueError(
            "Claim candidate IDs must be "
            "unique within an item."
        )

    for candidate in (
        item.claim_candidates
    ):
        if not (
            candidate
            .origin_component_ids
        ):
            raise ValueError(
                "Every claim candidate must "
                "retain at least one origin "
                "component."
            )

        unknown_origins = (
            set(
                candidate
                .origin_component_ids
            )
            - component_id_set
        )

        if unknown_origins:
            raise ValueError(
                "Claim candidate references "
                "unknown origin components: "
                + ", ".join(
                    sorted(
                        unknown_origins
                    )
                )
            )

    for alignment in (
        item.alignments
    ):
        if (
            alignment.left_component_id
            == alignment.right_component_id
        ):
            raise ValueError(
                "Alignment cannot compare a "
                "component with itself."
            )

        alignment_ids = {
            alignment.left_component_id,
            alignment.right_component_id,
        }

        unknown_alignment_ids = (
            alignment_ids
            - component_id_set
        )

        if unknown_alignment_ids:
            raise ValueError(
                "Alignment references unknown "
                "components: "
                + ", ".join(
                    sorted(
                        unknown_alignment_ids
                    )
                )
            )

    for component in (
        item.text_components
    ):
        if (
            component.start_seconds
            is not None
            and component.end_seconds
            is not None
            and component.end_seconds
            < component.start_seconds
        ):
            raise ValueError(
                "Text component end_seconds "
                "cannot precede start_seconds."
            )

    if (
        item.expires_at
        and not item.ephemeral
    ):
        raise ValueError(
            "expires_at requires "
            "ephemeral=True."
        )

    if (
        item.ephemeral
        and not item.observed_at
    ):
        raise ValueError(
            "Ephemeral content must retain "
            "an observed_at timestamp."
        )


def validate_unified_content_bundle(
    bundle: UnifiedContentBundle,
) -> None:
    item_ids = [
        item.item_id
        for item
        in bundle.items
    ]

    if not item_ids:
        raise ValueError(
            "Unified content bundle must "
            "contain at least one item."
        )

    if (
        len(item_ids)
        != len(
            set(
                item_ids
            )
        )
    ):
        raise ValueError(
            "Unified content item IDs must "
            "be unique within a bundle."
        )

    item_id_set = set(
        item_ids
    )

    if not bundle.root_item_ids:
        raise ValueError(
            "Unified content bundle must "
            "identify at least one root item."
        )

    unknown_roots = (
        set(
            bundle.root_item_ids
        )
        - item_id_set
    )

    if unknown_roots:
        raise ValueError(
            "Bundle root references unknown "
            "items: "
            + ", ".join(
                sorted(
                    unknown_roots
                )
            )
        )

    relationship_ids = [
        relationship.relationship_id
        for relationship
        in bundle.relationships
    ]

    if (
        len(relationship_ids)
        != len(
            set(
                relationship_ids
            )
        )
    ):
        raise ValueError(
            "Content relationship IDs must "
            "be unique within a bundle."
        )

    for item in bundle.items:
        validate_unified_content_item(
            item
        )

    for relationship in (
        bundle.relationships
    ):
        if (
            relationship.source_item_id
            == relationship.target_item_id
        ):
            raise ValueError(
                "Content relationship cannot "
                "point an item to itself."
            )

        endpoints = {
            relationship.source_item_id,
            relationship.target_item_id,
        }

        unknown_endpoints = (
            endpoints
            - item_id_set
        )

        if unknown_endpoints:
            raise ValueError(
                "Content relationship "
                "references unknown items: "
                + ", ".join(
                    sorted(
                        unknown_endpoints
                    )
                )
            )
