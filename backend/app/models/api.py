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
