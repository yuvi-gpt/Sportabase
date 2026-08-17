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


class IngestResponse(BaseModel):
    sources: int
    fetched_items: int
    inserted: int
    skipped: int


class Story(BaseModel):
    id: str
    source: str
    sport: str
    title: str
    link: str
    published: Optional[str] = None
    summary: str = ""
    tldr: List[str] = Field(default_factory=list)
    merit_score: int = 0
    badge: str = "Unverified Rumor"
    created_at: str


class AnalyzeRequest(BaseModel):
    title: str = Field(..., min_length=3)
    url: str = Field(..., min_length=8)
    text: str = Field(..., min_length=50)
    max_bullets: int = Field(3, ge=1, le=6)


class AnalyzeResponse(BaseModel):
    url: str
    title: str
    tldr: List[str]
    merit_score: int
    badge: str

    article_type: str = "generic_news"
    article_type_label: str = "Generic Sports News"
    article_subtype: str = "general"
    type_confidence: float = 0.0
    type_signals: List[str] = Field(default_factory=list)

    reasons: List[str] = Field(default_factory=list)

    score_components: Dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    score_calculation: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    language: Dict[str, Any] = Field(default_factory=dict)
    localized_article_type: str = ""
    localized_reasons: List[str] = Field(default_factory=list)
    ui_labels: Dict[str, str] = Field(default_factory=dict)

    intelligence: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    debug: Dict[str, Any] = Field(default_factory=dict)

class VideoAnalyzeRequest(BaseModel):
    title: str = ""
    transcript: str
    url: str = ""

    transcript_metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


class VideoAnalyzeResponse(BaseModel):
    content_type: str = "unknown"
    claim: str
    evidence_used: List[str]
    logic_check: str
    hype_check: str
    evidence_score: int
    logic_score: int
    verdict: str

    language: Dict[str, Any] = Field(
        default_factory=dict
    )

    localized_content_type: str = ""
    localized_verdict: str = ""

    ui_labels: Dict[str, str] = Field(
        default_factory=dict
    )

    debug: Dict[str, Any] = Field(
        default_factory=dict
    )



class ContentResolveRequest(BaseModel):
    url: str = Field(
        ...,
        min_length=8,
        max_length=2048,
    )


class ContentResolveResponse(BaseModel):
    url: str
    normalized_url: str

    source: Literal[
        "article",
        "youtube",
    ]

    mode: Literal[
        "article",
        "video",
    ]

    title: str = ""
    content: str = Field(..., min_length=1)
    content_characters: int = Field(..., ge=1)

    metadata: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )



class BrowserCaptureRequest(
    BaseModel
):
    capture: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    short_video_threshold_seconds: float = (
        Field(
            180.0,
            gt=0.0,
            le=86400.0,
        )
    )


class BrowserCaptureResponse(
    BaseModel
):
    version: str

    item: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    processing_plan: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    artifact_manifest: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    capture_record_id: str = ""
    capture_persisted: bool = False

    capture_inbox_status: Literal[
        "disabled",
        "stored",
        "replayed",
        "oversize",
        "unavailable",
    ] = "disabled"

    capture_inbox_version: str = ""


class _StrictMultimodalShadowApiModel(
    BaseModel
):
    class Config:
        extra = "forbid"


class MultimodalShadowSideRequest(
    _StrictMultimodalShadowApiModel
):
    capture: Dict[
        str,
        Any,
    ] = Field(...)

    source_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    media_item_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    story_id: str = Field(
        "",
        max_length=256,
    )


class MultimodalShadowRequest(
    _StrictMultimodalShadowApiModel
):
    subject_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
    )

    left: MultimodalShadowSideRequest
    right: MultimodalShadowSideRequest

    target_claim_id: str = Field(
        "",
        max_length=512,
    )

    legacy_score: Dict[
        str,
        Any,
    ] = Field(...)


class MultimodalShadowResponse(
    BaseModel
):
    version: str

    status: Literal[
        "completed_shadow"
    ]

    result: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    policy: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )
