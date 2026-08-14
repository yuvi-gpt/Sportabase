from __future__ import annotations

import os
import re
import json
import socket
import ipaddress
import time
import threading
import hashlib
import hmac
import sqlite3
from pathlib import Path
from concurrent.futures import Future
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional
import html as ihtml
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from google import genai
from lingua import LanguageDetectorBuilder
from app.db.schema import SCHEMA
from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.intelligence.sources import (
    source_domain_for_url as _source_domain_for_url_impl,
    source_key_for_url as _source_key_for_url_impl,
    source_id_for_url as _source_id_for_url_impl,
    upsert_intelligence_source as _upsert_intelligence_source_impl,
)
from app.intelligence.stories import (
    story_id_for_canonical_key as _story_id_for_canonical_key_impl,
    upsert_intelligence_story as _upsert_intelligence_story_impl,
)
from app.intelligence.claims import (
    claim_id_for_canonical_key as _claim_id_for_canonical_key_impl,
    upsert_intelligence_claim as _upsert_intelligence_claim_impl,
    claim_link_id_for_record as _claim_link_id_for_record_impl,
    record_claim_link as _record_claim_link_impl,
)
from app.intelligence.reporters import (
    reporter_id_for_identity_key as _reporter_id_for_identity_key_impl,
    upsert_intelligence_reporter as _upsert_intelligence_reporter_impl,
)
from app.intelligence.observations import (
    record_source_observation as _record_source_observation_impl,
    record_reporter_observation as _record_reporter_observation_impl,
)
from app.intelligence.evidence import (
    evidence_key_for_record as _evidence_key_for_record_impl,
    record_evidence as _record_evidence_impl,
    record_evidence_link as _record_evidence_link_impl,
)
from app.intelligence.dependencies import (
    _observation_dependency_identity as _observation_dependency_identity_impl,
    observation_dependency_id_for_record as _observation_dependency_id_for_record_impl,
    record_observation_dependency as _record_observation_dependency_impl,
)
from app.intelligence.independence_assertions import (
    OBSERVATION_INDEPENDENCE_ASSERTION_VERSION,
    OBSERVATION_INDEPENDENCE_VERIFICATION_VOCABULARY,
    observation_independence_assertion_id_for_record as _observation_independence_assertion_id_for_record_impl,
    record_observation_independence_assertion as _record_observation_independence_assertion_impl,
)
from app.intelligence.context import (
    EVIDENCE_CONTEXT_VERSION,
    MEDIA_EVIDENCE_CONTEXT_POLICY_VERSION,
    _evidence_context_confidence,
    _deduplicate_evidence_context_entries,
    _evidence_context_row,
    build_evidence_context,
    evidence_context_hash,
    load_evidence_context_for_source as _load_evidence_context_for_source_impl,
    load_evidence_context_for_reporter as _load_evidence_context_for_reporter_impl,
    load_evidence_context_for_media_item as _load_evidence_context_for_media_item_impl,
    load_expanded_evidence_context_for_media_item as _load_expanded_evidence_context_for_media_item_impl,
    evidence_context_hash_for_media_item as _evidence_context_hash_for_media_item_impl,
    expanded_evidence_context_hash_for_media_item as _expanded_evidence_context_hash_for_media_item_impl,
    load_evidence_context_for_story as _load_evidence_context_for_story_impl,
    load_evidence_context_for_subject as _load_evidence_context_for_subject_impl,
)
from app.intelligence.features import (
    EVIDENCE_SIGNAL_POLICY_VERSION,
    EVIDENCE_FEATURE_VERSION,
    EVIDENCE_ACTOR_FEATURE_VERSION,
    OBSERVATION_DEPENDENCY_POLICY_VERSION,
    OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY,
    EVIDENCE_SIGNAL_VOCABULARY,
    CLAIM_DEPENDENCY_FEATURE_VERSION,
    inspect_observation_dependency_vocabulary,
    inspect_evidence_signal_vocabulary,
    build_evidence_signal_features,
    build_evidence_actor_features,
    build_claim_dependency_features,
)
from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
    build_evidence_analysis_bundle,
    evidence_analysis_bundle_hash,
    load_evidence_analysis_bundle_for_media_item as _load_evidence_analysis_bundle_for_media_item_impl,
    load_evidence_analysis_state_for_media_item as _load_evidence_analysis_state_for_media_item_impl,
)
from app.analysis.independence import (
    CLAIM_INDEPENDENCE_POLICY_VERSION,
    CLAIM_INDEPENDENCE_STATUS_VOCABULARY,
    build_claim_independence_assessment,
)
from app.analysis.stance import (
    CLAIM_STANCE_POLICY_VERSION,
    CLAIM_LINK_STANCE_RELATIONSHIP_VOCABULARY,
    CLAIM_STANCE_STATUS_VOCABULARY,
    build_claim_stance_analysis,
)
from app.analysis.support import (
    CLAIM_SUPPORT_PROVENANCE_VERSION,
    CLAIM_SUPPORT_PROVENANCE_STATUS_VOCABULARY,
    build_claim_support_provenance,
)
from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
    CLAIM_CORROBORATION_STATUS_VOCABULARY,
    build_claim_corroboration_assessment,
)
from app.services.article_intelligence_shadow import (
    ARTICLE_INTELLIGENCE_SHADOW_VERSION,
    run_article_intelligence_shadow,
)
from app.models.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    ContentResolveRequest,
    ContentResolveResponse,
    IngestResponse,
    Story,
    VideoAnalyzeRequest,
    VideoAnalyzeResponse,
)
from app.services.content_resolution import (
    TRACKING_QUERY_PARAMETERS,
    YOUTUBE_HOSTS,
    _normalize_extracted_text,
    _validate_public_ip_address,
    detect_content_source,
    extract_article_content,
    fetch_safe_article_html,
    is_tracking_query_parameter,
    normalized_analysis_url,
    validate_safe_remote_url,
    youtube_video_id_from_url,
)
from app.services.analysis_history import (
    find_analysis_snapshot as _find_analysis_snapshot_history_impl,
    media_item_id_for_url as _media_item_id_for_url_history_impl,
    persist_analysis_snapshot as _persist_analysis_snapshot_history_impl,
    record_user_history as _record_user_history_history_impl,
    upsert_media_item as _upsert_media_item_history_impl,
)
from app.services.analysis_cache import (
    analysis_content_hash as _analysis_content_hash_cache_impl,
    cache_ttl_for_analysis as _cache_ttl_for_analysis_cache_impl,
    get_cached_analysis as _get_cached_analysis_cache_impl,
    make_analysis_cache_key as _make_analysis_cache_key_cache_impl,
    set_cached_analysis as _set_cached_analysis_cache_impl,
)
from app.services.gemini_runtime import (
    classify_gemini_failure as _classify_gemini_failure_runtime_impl,
    expire_stale_gemini_reservations as _expire_stale_gemini_reservations_runtime_impl,
    finish_gemini_call as _finish_gemini_call_runtime_impl,
    gemini_request_fingerprint as _gemini_request_fingerprint_runtime_impl,
    generate_gemini_content as _generate_gemini_content_runtime_impl,
    record_analysis_cache_hit as _record_analysis_cache_hit_runtime_impl,
    record_inflight_gemini_join as _record_inflight_gemini_join_runtime_impl,
    request_client_key as _request_client_key_runtime_impl,
    reserve_gemini_call as _reserve_gemini_call_runtime_impl,
    usage_metadata_counts as _usage_metadata_counts_runtime_impl,
)
from app.services.usage_reporting import (
    admin_usage_summary as _admin_usage_summary_reporting_impl,
    usage_derived_metrics as _usage_derived_metrics_reporting_impl,
    usage_mode_metrics as _usage_mode_metrics_reporting_impl,
    usage_savings_metrics as _usage_savings_metrics_reporting_impl,
    usage_scope_savings_summary as _usage_scope_savings_summary_reporting_impl,
)
from app.services.article_rules import (
    _TAG_RE,
    clean_html,
    _clamp,
    _domain_from_url,
    signal_hits,
    ARTICLE_TYPE_LABELS,
    AI_ARTICLE_TYPE_VALUES,
    normalize_ai_article_classification,
    _has_scoreline,
    _add_score,
    detect_article_type,
    HEDGE_WORDS,
    OFFICIAL_WORDS,
    NEGATED_OFFICIAL_PATTERNS,
    EVIDENCE_WORDS,
    UNNAMED_SOURCE_PATTERNS,
    SEVERE_RUMOR_PATTERNS,
    IMPACT_WORDS,
    OPINION_WORDS,
    CLICKBAIT_WORDS,
    _source_reputation,
    badge,
    merit_score,
)
from app.services.video_support import (
    prepare_video_transcript,
    split_video_transcript,
    get_language_detector,
    lingua_language_name,
    detect_content_language,
    _video_context_tokens,
    _video_context_sentences,
    build_video_transcript_context,
    normalize_video_transcript_metadata,
    VIDEO_MODEL_UI_LABEL_KEYS,
    clean_video_model_text,
    sanitize_video_model_payload,
    classify_video_provider_error,
    VIDEO_CONTENT_TYPES,
    VIDEO_VERDICTS,
    VIDEO_ALLOWED_VERDICTS_BY_TYPE,
    VIDEO_VERDICT_REQUIREMENTS,
    VIDEO_VERDICT_LABELS,
    bounded_video_score,
    validate_video_analysis_consistency,
    video_analysis_cache_decision,
)
from app.services.video_analysis import (
    ai_video_claim_readout_impl as _ai_video_claim_readout_impl,
)
from app.services.article_analysis import (
    ai_detect_article_type_impl as _ai_detect_article_type_impl,
    extractive_fallback,
    gemini_article_single_pass_impl as _gemini_article_single_pass_impl,
    gemini_candidate_collection_semantics_impl as _gemini_candidate_collection_semantics_impl,
    gemini_candidate_semantics_impl as _gemini_candidate_semantics_impl,
    gemini_tldr_impl as _gemini_tldr_impl,
    normalize_article_bullets,
    run_article_ai_strategy_impl as _run_article_ai_strategy_impl,
)
# from app.routes.insights import router as insights_router


# -----------------------------
# env + paths
# -----------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DOTENV_PATH = BACKEND_DIR / ".env"
load_dotenv(DOTENV_PATH)

DB_PATH = DATA_DIR / "sportabase.db"
SOURCES_PATH = DATA_DIR / "sources.json"

# Keep extension scans fast. Most sports articles can be summarized/scored well
# without sending the full extracted page body to Gemini.
MAX_ANALYZE_CHARS = int(
    os.getenv(
        "SPORTABASE_MAX_ANALYZE_CHARS",
        "6000",
    )
)

ANALYSIS_VERSION = os.getenv(
    "SPORTABASE_ANALYSIS_VERSION",
    "article-video-v14-score-single-pass",
).strip()
SCORING_VERSION = os.getenv(
    "SPORTABASE_SCORING_VERSION",
    "merit-v1-legacy",
).strip()

ANALYSIS_CACHE_TTL_SECONDS = int(
    os.getenv(
        "SPORTABASE_CACHE_TTL_SECONDS",
        "21600",
    )
)

LIVE_CACHE_TTL_SECONDS = int(
    os.getenv(
        "SPORTABASE_LIVE_CACHE_TTL_SECONDS",
        "180",
    )
)

GLOBAL_DAILY_GEMINI_CALL_CAP = int(
    os.getenv(
        "SPORTABASE_GLOBAL_DAILY_GEMINI_CALL_CAP",
        "300",
    )
)

CLIENT_DAILY_GEMINI_CALL_CAP = int(
    os.getenv(
        "SPORTABASE_CLIENT_DAILY_GEMINI_CALL_CAP",
        "30",
    )
)

GEMINI_RESERVATION_TIMEOUT_SECONDS = max(
    60,
    int(
        os.getenv(
            "SPORTABASE_GEMINI_RESERVATION_TIMEOUT_SECONDS",
            "900",
        )
    ),
)

ADMIN_API_KEY = os.getenv(
    "SPORTABASE_ADMIN_API_KEY",
    "",
).strip()

INTELLIGENCE_SHADOW_ENABLED = (
    os.getenv(
        "SPORTABASE_INTELLIGENCE_SHADOW_ENABLED",
        "0",
    )
    .strip()
    .lower()
    in {
        "1",
        "true",
        "yes",
        "on",
    }
)

BRAVE_NEWS_API_KEY = os.getenv(
    "SPORTABASE_BRAVE_NEWS_API_KEY",
    "",
).strip()


GEMINI_INPUT_COST_PER_MILLION_USD = float(
    os.getenv(
        "SPORTABASE_GEMINI_INPUT_COST_PER_MILLION_USD",
        "1.50",
    )
)

GEMINI_OUTPUT_COST_PER_MILLION_USD = float(
    os.getenv(
        "SPORTABASE_GEMINI_OUTPUT_COST_PER_MILLION_USD",
        "9.00",
    )
)

_INFLIGHT_GEMINI_LOCK = threading.Lock()

_INFLIGHT_GEMINI_CALLS: Dict[
    str,
    Future,
] = {}


# -----------------------------
# app
# -----------------------------
app = FastAPI(title="Sportabase API (RSS-first)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(insights_router, prefix="/insights", tags=["insights"])


@app.get("/health")
def health():
    return {"ok": True, "version": "0.3.0"}


# -----------------------------
# db
# -----------------------------


def db_conn() -> sqlite3.Connection:
    return connect_database(
        DB_PATH
    )


def init_db():
    initialize_database(
        db_conn,
        SCHEMA,
    )


init_db()


# -----------------------------
# analysis cache + usage limits
# -----------------------------
def require_admin(request: Request) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="The Sportabase admin API is not configured.",
        )

    provided_key = str(
        request.headers.get(
            "x-sportabase-admin-key",
            "",
        )
    ).strip()

    if not provided_key or not hmac.compare_digest(
        provided_key,
        ADMIN_API_KEY,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Sportabase admin key.",
        )


def utc_usage_day() -> str:
    return datetime.now(
        timezone.utc
    ).date().isoformat()



def analysis_content_hash(
    content: str,
) -> str:
    return (
        _analysis_content_hash_cache_impl(
            content,
            clean_html=clean_html,
        )
    )



def source_domain_for_url(
    url: str,
) -> str:
    return _source_domain_for_url_impl(
        url,
        normalize_url=normalized_analysis_url,
    )


def source_key_for_url(
    url: str,
    source_type: str = "publisher",
) -> str:
    return _source_key_for_url_impl(
        url,
        source_type,
        domain_resolver=source_domain_for_url,
    )


def source_id_for_url(
    url: str,
    source_type: str = "publisher",
) -> str:
    return _source_id_for_url_impl(
        url,
        source_type,
        key_resolver=source_key_for_url,
    )


def upsert_intelligence_source(
    *,
    url: str,
    display_name: str = "",
    source_type: str = "publisher",
    publication_founded_at: Optional[
        str
    ] = None,
    domain_registered_at: Optional[
        str
    ] = None,
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _upsert_intelligence_source_impl(
        url=url,
        display_name=display_name,
        source_type=source_type,
        publication_founded_at=(
            publication_founded_at
        ),
        domain_registered_at=(
            domain_registered_at
        ),
        metadata=metadata,
        seen_at=seen_at,
        domain_resolver=source_domain_for_url,
        connection_factory=db_conn,
    )


def story_id_for_canonical_key(
    canonical_key: str,
) -> str:
    return _story_id_for_canonical_key_impl(
        canonical_key
    )


def upsert_intelligence_story(
    *,
    canonical_key: str,
    canonical_title: str = "",
    status: str = "developing",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _upsert_intelligence_story_impl(
        canonical_key=canonical_key,
        canonical_title=canonical_title,
        status=status,
        metadata=metadata,
        seen_at=seen_at,
        id_resolver=story_id_for_canonical_key,
        connection_factory=db_conn,
    )


def claim_id_for_canonical_key(
    canonical_key: str,
) -> str:
    return _claim_id_for_canonical_key_impl(
        canonical_key
    )


def upsert_intelligence_claim(
    *,
    canonical_key: str,
    subject_key: str,
    canonical_text: str = "",
    claim_type: str = "assertion",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _upsert_intelligence_claim_impl(
        canonical_key=canonical_key,
        subject_key=subject_key,
        canonical_text=canonical_text,
        claim_type=claim_type,
        metadata=metadata,
        seen_at=seen_at,
        id_resolver=claim_id_for_canonical_key,
        connection_factory=db_conn,
    )


def claim_link_id_for_record(
    *,
    claim_id: str,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    source_observation_id: Optional[str] = None,
    reporter_observation_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> str:
    return _claim_link_id_for_record_impl(
        claim_id=claim_id,
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
    )


def record_claim_link(
    *,
    claim_id: str,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    source_observation_id: Optional[str] = None,
    reporter_observation_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    recorded_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _record_claim_link_impl(
        claim_id=claim_id,
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        source_observation_id=source_observation_id,
        reporter_observation_id=reporter_observation_id,
        evidence_id=evidence_id,
        metadata=metadata,
        recorded_at=recorded_at,
        connection_factory=db_conn,
    )


def link_media_item_to_story(
    *,
    story_id: str,
    media_item_id: str,
    relationship_type: str = "reports",
    confidence: float = 0.0,
    linked_at: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_story_id = str(
        story_id or ""
    ).strip()

    normalized_media_item_id = str(
        media_item_id or ""
    ).strip()

    normalized_relationship_type = str(
        relationship_type or ""
    ).strip().lower()

    if not normalized_story_id:
        raise ValueError(
            "Story media link story ID is required."
        )

    if not normalized_media_item_id:
        raise ValueError(
            "Story media link media item ID is required."
        )

    if not normalized_relationship_type:
        raise ValueError(
            "Story media link relationship type "
            "is required."
        )

    try:
        normalized_confidence = float(
            confidence
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Story media link confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= normalized_confidence
        <= 1.0
    ):
        raise ValueError(
            "Story media link confidence "
            "must be between 0 and 1."
        )

    normalized_linked_at = (
        str(
            linked_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    conn = db_conn()

    try:
        conn.execute(
            """
            INSERT INTO story_media_links (
              story_id,
              media_item_id,
              relationship_type,
              confidence,
              linked_at
            )
            VALUES (
              ?, ?, ?, ?, ?
            )
            ON CONFLICT(
              story_id,
              media_item_id
            )
            DO UPDATE SET
              relationship_type =
                excluded.relationship_type,
              confidence =
                excluded.confidence
            """,
            (
                normalized_story_id,
                normalized_media_item_id,
                normalized_relationship_type,
                normalized_confidence,
                normalized_linked_at,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM story_media_links
            WHERE story_id = ?
              AND media_item_id = ?
            """,
            (
                normalized_story_id,
                normalized_media_item_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Story media link persistence failed."
        )

    return dict(row)


def reporter_id_for_identity_key(
    identity_key: str,
) -> str:
    return _reporter_id_for_identity_key_impl(
        identity_key
    )


def upsert_intelligence_reporter(
    *,
    identity_key: str,
    display_name: str = "",
    metadata: Optional[
        Dict[str, Any]
    ] = None,
    seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _upsert_intelligence_reporter_impl(
        identity_key=identity_key,
        display_name=display_name,
        metadata=metadata,
        seen_at=seen_at,
        id_resolver=reporter_id_for_identity_key,
        connection_factory=db_conn,
    )


def record_source_observation(
    *,
    source_id: str,
    subject_key: str,
    observation_type: str,
    observed_at: str,
    status: str = "unresolved",
    claim_summary: str = "",
    provenance_url: str = "",
    confidence: Optional[float] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _record_source_observation_impl(
        source_id=source_id,
        subject_key=subject_key,
        observation_type=observation_type,
        observed_at=observed_at,
        status=status,
        claim_summary=claim_summary,
        provenance_url=provenance_url,
        confidence=confidence,
        media_item_id=media_item_id,
        story_id=story_id,
        recorded_at=recorded_at,
        metadata=metadata,
        normalize_url=normalized_analysis_url,
        connection_factory=db_conn,
    )


def record_reporter_observation(
    *,
    reporter_id: str,
    subject_key: str,
    observation_type: str,
    observed_at: str,
    status: str = "unresolved",
    claim_summary: str = "",
    provenance_url: str = "",
    confidence: Optional[float] = None,
    source_id: Optional[str] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _record_reporter_observation_impl(
        reporter_id=reporter_id,
        subject_key=subject_key,
        observation_type=observation_type,
        observed_at=observed_at,
        status=status,
        claim_summary=claim_summary,
        provenance_url=provenance_url,
        confidence=confidence,
        source_id=source_id,
        media_item_id=media_item_id,
        story_id=story_id,
        recorded_at=recorded_at,
        metadata=metadata,
        normalize_url=normalized_analysis_url,
        connection_factory=db_conn,
    )
def evidence_key_for_record(
    *,
    evidence_type: str,
    subject_key: str,
    observed_at: str,
    canonical_url: str = "",
    reference_key: str = "",
    verification_status: str = "unverified",
) -> str:
    return _evidence_key_for_record_impl(
        evidence_type=evidence_type,
        subject_key=subject_key,
        observed_at=observed_at,
        canonical_url=canonical_url,
        reference_key=reference_key,
        verification_status=verification_status,
        normalize_url=normalized_analysis_url,
    )


def record_evidence(
    *,
    evidence_type: str,
    subject_key: str,
    observed_at: str,
    claim_summary: str = "",
    canonical_url: str = "",
    reference_key: str = "",
    verification_status: str = "unverified",
    published_at: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _record_evidence_impl(
        evidence_type=evidence_type,
        subject_key=subject_key,
        observed_at=observed_at,
        claim_summary=claim_summary,
        canonical_url=canonical_url,
        reference_key=reference_key,
        verification_status=verification_status,
        published_at=published_at,
        recorded_at=recorded_at,
        metadata=metadata,
        normalize_url=normalized_analysis_url,
        connection_factory=db_conn,
    )


def record_evidence_link(
    *,
    evidence_id: str,
    relationship_type: str = "supports",
    confidence: Optional[float] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    source_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    linked_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _record_evidence_link_impl(
        evidence_id=evidence_id,
        relationship_type=relationship_type,
        confidence=confidence,
        media_item_id=media_item_id,
        story_id=story_id,
        source_id=source_id,
        reporter_id=reporter_id,
        linked_at=linked_at,
        metadata=metadata,
        connection_factory=db_conn,
    )
def _observation_dependency_identity(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    return _observation_dependency_identity_impl(
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        downstream_source_observation_id=(
            downstream_source_observation_id
        ),
        downstream_reporter_observation_id=(
            downstream_reporter_observation_id
        ),
        upstream_source_observation_id=(
            upstream_source_observation_id
        ),
        upstream_reporter_observation_id=(
            upstream_reporter_observation_id
        ),
        upstream_source_id=upstream_source_id,
        upstream_reporter_id=upstream_reporter_id,
    )


def observation_dependency_id_for_record(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
) -> str:
    return _observation_dependency_id_for_record_impl(
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        downstream_source_observation_id=(
            downstream_source_observation_id
        ),
        downstream_reporter_observation_id=(
            downstream_reporter_observation_id
        ),
        upstream_source_observation_id=(
            upstream_source_observation_id
        ),
        upstream_reporter_observation_id=(
            upstream_reporter_observation_id
        ),
        upstream_source_id=upstream_source_id,
        upstream_reporter_id=upstream_reporter_id,
    )


def record_observation_dependency(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _record_observation_dependency_impl(
        relationship_type=relationship_type,
        observed_at=observed_at,
        confidence=confidence,
        downstream_source_observation_id=(
            downstream_source_observation_id
        ),
        downstream_reporter_observation_id=(
            downstream_reporter_observation_id
        ),
        upstream_source_observation_id=(
            upstream_source_observation_id
        ),
        upstream_reporter_observation_id=(
            upstream_reporter_observation_id
        ),
        upstream_source_id=upstream_source_id,
        upstream_reporter_id=upstream_reporter_id,
        recorded_at=recorded_at,
        metadata=metadata,
        connection_factory=db_conn,
    )
def observation_independence_assertion_id_for_record(
    *,
    observed_at: str,
    provenance_evidence_id: str,
    verification_status: str = "unverified",
    confidence: Optional[float] = None,
    left_source_observation_id:
        Optional[str] = None,
    left_reporter_observation_id:
        Optional[str] = None,
    right_source_observation_id:
        Optional[str] = None,
    right_reporter_observation_id:
        Optional[str] = None,
) -> str:
    return (
        _observation_independence_assertion_id_for_record_impl(
            observed_at=observed_at,
            provenance_evidence_id=(
                provenance_evidence_id
            ),
            verification_status=(
                verification_status
            ),
            confidence=confidence,
            left_source_observation_id=(
                left_source_observation_id
            ),
            left_reporter_observation_id=(
                left_reporter_observation_id
            ),
            right_source_observation_id=(
                right_source_observation_id
            ),
            right_reporter_observation_id=(
                right_reporter_observation_id
            ),
        )
    )


def record_observation_independence_assertion(
    *,
    observed_at: str,
    provenance_evidence_id: str,
    verification_status: str = "unverified",
    confidence: Optional[float] = None,
    left_source_observation_id:
        Optional[str] = None,
    left_reporter_observation_id:
        Optional[str] = None,
    right_source_observation_id:
        Optional[str] = None,
    right_reporter_observation_id:
        Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return (
        _record_observation_independence_assertion_impl(
            observed_at=observed_at,
            provenance_evidence_id=(
                provenance_evidence_id
            ),
            verification_status=(
                verification_status
            ),
            confidence=confidence,
            left_source_observation_id=(
                left_source_observation_id
            ),
            left_reporter_observation_id=(
                left_reporter_observation_id
            ),
            right_source_observation_id=(
                right_source_observation_id
            ),
            right_reporter_observation_id=(
                right_reporter_observation_id
            ),
            recorded_at=recorded_at,
            metadata=metadata,
            connection_factory=db_conn,
        )
    )


def load_evidence_context_for_source(
    *,
    source_id: str,
) -> Dict[str, Any]:
    return _load_evidence_context_for_source_impl(
        source_id=source_id,
        connection_factory=db_conn,
    )


def load_evidence_context_for_reporter(
    *,
    reporter_id: str,
) -> Dict[str, Any]:
    return _load_evidence_context_for_reporter_impl(
        reporter_id=reporter_id,
        connection_factory=db_conn,
    )


def load_evidence_context_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _load_evidence_context_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )


def load_expanded_evidence_context_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _load_expanded_evidence_context_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )


def evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
) -> str:
    return _evidence_context_hash_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )


def expanded_evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
) -> str:
    return _expanded_evidence_context_hash_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )


def load_evidence_context_for_story(
    *,
    story_id: str,
) -> Dict[str, Any]:
    return _load_evidence_context_for_story_impl(
        story_id=story_id,
        connection_factory=db_conn,
    )


def load_evidence_context_for_subject(
    *,
    subject_key: str,
) -> Dict[str, Any]:
    return _load_evidence_context_for_subject_impl(
        subject_key=subject_key,
        connection_factory=db_conn,
    )














def load_evidence_analysis_bundle_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _load_evidence_analysis_bundle_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )


def load_evidence_analysis_state_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _load_evidence_analysis_state_for_media_item_impl(
        media_item_id=media_item_id,
        connection_factory=db_conn,
    )














































def media_item_id_for_url(
    url: str,
) -> str:
    return (
        _media_item_id_for_url_history_impl(
            url,
            normalize_url=(
                normalized_analysis_url
            ),
        )
    )


def upsert_media_item(
    *,
    url: str,
    mode: str,
    title: str,
    content_hash: str,
    published_at: Optional[str] = None,
    source_id: Optional[str] = None,
    reporter_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    seen_at: Optional[str] = None,
) -> Dict[str, Any]:
    return (
        _upsert_media_item_history_impl(
            url=url,
            mode=mode,
            title=title,
            content_hash=content_hash,
            published_at=published_at,
            source_id=source_id,
            reporter_id=reporter_id,
            metadata=metadata,
            seen_at=seen_at,
            normalize_url=(
                normalized_analysis_url
            ),
            id_resolver=(
                media_item_id_for_url
            ),
            connection_factory=db_conn,
        )
    )


def find_analysis_snapshot(
    *,
    media_item_id: str,
    mode: str,
    content_hash: str,
    context_hash: str = "",
    analysis_version: Optional[str] = None,
    scoring_version: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return (
        _find_analysis_snapshot_history_impl(
            media_item_id=media_item_id,
            mode=mode,
            content_hash=content_hash,
            context_hash=context_hash,
            analysis_version=(
                analysis_version
            ),
            scoring_version=(
                scoring_version
            ),
            default_analysis_version=(
                ANALYSIS_VERSION
            ),
            default_scoring_version=(
                SCORING_VERSION
            ),
            connection_factory=db_conn,
        )
    )


def persist_analysis_snapshot(
    *,
    media_item_id: str,
    mode: str,
    content_hash: str,
    response: Dict[str, Any],
    context_hash: str = "",
    analyzed_at: Optional[str] = None,
    analysis_version: Optional[str] = None,
    scoring_version: Optional[str] = None,
    story_id: Optional[str] = None,
    merit_score: Optional[int] = None,
    evidence_score: Optional[int] = None,
    logic_score: Optional[int] = None,
    badge: str = "",
    verdict: str = "",
    article_type: str = "",
    score_components: Optional[
        Dict[str, Any]
    ] = None,
    score_calculation: Optional[
        Dict[str, Any]
    ] = None,
    reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return (
        _persist_analysis_snapshot_history_impl(
            media_item_id=media_item_id,
            mode=mode,
            content_hash=content_hash,
            response=response,
            context_hash=context_hash,
            analyzed_at=analyzed_at,
            analysis_version=(
                analysis_version
            ),
            scoring_version=(
                scoring_version
            ),
            story_id=story_id,
            merit_score=merit_score,
            evidence_score=evidence_score,
            logic_score=logic_score,
            badge=badge,
            verdict=verdict,
            article_type=article_type,
            score_components=(
                score_components
            ),
            score_calculation=(
                score_calculation
            ),
            reasons=reasons,
            default_analysis_version=(
                ANALYSIS_VERSION
            ),
            default_scoring_version=(
                SCORING_VERSION
            ),
            connection_factory=db_conn,
        )
    )


def record_user_history(
    *,
    client_key: str,
    media_item_id: str,
    snapshot_id: Optional[int] = None,
    analyzed_at: Optional[str] = None,
) -> Dict[str, Any]:
    return (
        _record_user_history_history_impl(
            client_key=client_key,
            media_item_id=media_item_id,
            snapshot_id=snapshot_id,
            analyzed_at=analyzed_at,
            connection_factory=db_conn,
        )
    )



def make_analysis_cache_key(
    mode: str,
    url: str,
    content: str,
    variant: str = "",
    context_hash: str = "",
) -> str:
    return (
        _make_analysis_cache_key_cache_impl(
            mode,
            url,
            content,
            variant,
            context_hash,
            analysis_version=(
                ANALYSIS_VERSION
            ),
            scoring_version=(
                SCORING_VERSION
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            content_hash_resolver=(
                analysis_content_hash
            ),
        )
    )


def cache_ttl_for_analysis(
    mode: str,
    article_type: str = "",
) -> int:
    return (
        _cache_ttl_for_analysis_cache_impl(
            mode,
            article_type,
            analysis_cache_ttl_seconds=(
                ANALYSIS_CACHE_TTL_SECONDS
            ),
            live_cache_ttl_seconds=(
                LIVE_CACHE_TTL_SECONDS
            ),
        )
    )


def get_cached_analysis(
    cache_key: str,
) -> Optional[Dict[str, Any]]:
    return (
        _get_cached_analysis_cache_impl(
            cache_key,
            connection_factory=db_conn,
        )
    )


def set_cached_analysis(
    cache_key: str,
    mode: str,
    request_url: str,
    content: str,
    response_payload: Any,
    article_type: str = "",
) -> None:
    return (
        _set_cached_analysis_cache_impl(
            cache_key,
            mode,
            request_url,
            content,
            response_payload,
            article_type,
            connection_factory=db_conn,
            ttl_resolver=(
                cache_ttl_for_analysis
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            content_hash_resolver=(
                analysis_content_hash
            ),
            analysis_version=(
                ANALYSIS_VERSION
            ),
        )
    )



def request_client_key(
    request: Request,
) -> str:
    return (
        _request_client_key_runtime_impl(
            request
        )
    )


def expire_stale_gemini_reservations(
    conn: sqlite3.Connection,
    *,
    usage_day: Optional[str] = None,
    now: Optional[datetime] = None,
) -> int:
    return (
        _expire_stale_gemini_reservations_runtime_impl(
            conn,
            usage_day=usage_day,
            now=now,
            reservation_timeout_seconds=(
                GEMINI_RESERVATION_TIMEOUT_SECONDS
            ),
        )
    )


def reserve_gemini_call(
    client_key: str,
    mode: str,
    model: str,
) -> int:
    return (
        _reserve_gemini_call_runtime_impl(
            client_key,
            mode,
            model,
            usage_day_resolver=(
                utc_usage_day
            ),
            connection_factory=db_conn,
            expire_reservations=(
                expire_stale_gemini_reservations
            ),
            global_daily_call_cap=(
                GLOBAL_DAILY_GEMINI_CALL_CAP
            ),
            client_daily_call_cap=(
                CLIENT_DAILY_GEMINI_CALL_CAP
            ),
        )
    )


def usage_metadata_counts(
    response: Any,
) -> Dict[str, int]:
    return (
        _usage_metadata_counts_runtime_impl(
            response
        )
    )


def classify_gemini_failure(
    error: Exception,
) -> Dict[str, Any]:
    return (
        _classify_gemini_failure_runtime_impl(
            error
        )
    )


def finish_gemini_call(
    usage_id: int,
    status: str,
    response: Any = None,
    latency_ms: int = 0,
    failure_status_code: Optional[int] = None,
    failure_type: str = "",
    failure_detail: str = "",
) -> Dict[str, int]:
    return (
        _finish_gemini_call_runtime_impl(
            usage_id,
            status,
            response,
            latency_ms,
            failure_status_code,
            failure_type,
            failure_detail,
            usage_counter=(
                usage_metadata_counts
            ),
            connection_factory=db_conn,
        )
    )


def record_inflight_gemini_join(
    *,
    client_key: str,
    mode: str,
    model: str,
    succeeded: bool,
) -> None:
    return (
        _record_inflight_gemini_join_runtime_impl(
            client_key=client_key,
            mode=mode,
            model=model,
            succeeded=succeeded,
            connection_factory=db_conn,
            usage_day_resolver=(
                utc_usage_day
            ),
        )
    )


def gemini_request_fingerprint(
    *,
    mode: str,
    model: str,
    contents: Any,
) -> str:
    return (
        _gemini_request_fingerprint_runtime_impl(
            mode=mode,
            model=model,
            contents=contents,
        )
    )


def generate_gemini_content(
    *,
    client: Any,
    client_key: str,
    mode: str,
    model: str,
    contents: Any,
) -> Any:
    return (
        _generate_gemini_content_runtime_impl(
            client=client,
            client_key=client_key,
            mode=mode,
            model=model,
            contents=contents,
            inflight_lock=(
                _INFLIGHT_GEMINI_LOCK
            ),
            inflight_calls=(
                _INFLIGHT_GEMINI_CALLS
            ),
            fingerprint_resolver=(
                gemini_request_fingerprint
            ),
            reserve_call=(
                reserve_gemini_call
            ),
            finish_call=(
                finish_gemini_call
            ),
            classify_failure=(
                classify_gemini_failure
            ),
            record_join=(
                record_inflight_gemini_join
            ),
        )
    )


def record_analysis_cache_hit(
    client_key: str,
    mode: str,
) -> None:
    return (
        _record_analysis_cache_hit_runtime_impl(
            client_key,
            mode,
            connection_factory=db_conn,
            usage_day_resolver=(
                utc_usage_day
            ),
        )
    )



def usage_derived_metrics(
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return (
        _usage_derived_metrics_reporting_impl(
            summary,
            input_cost_per_million_usd=(
                GEMINI_INPUT_COST_PER_MILLION_USD
            ),
            output_cost_per_million_usd=(
                GEMINI_OUTPUT_COST_PER_MILLION_USD
            ),
            global_daily_call_cap=(
                GLOBAL_DAILY_GEMINI_CALL_CAP
            ),
        )
    )


def usage_savings_metrics(
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return (
        _usage_savings_metrics_reporting_impl(
            summary,
            input_cost_per_million_usd=(
                GEMINI_INPUT_COST_PER_MILLION_USD
            ),
            output_cost_per_million_usd=(
                GEMINI_OUTPUT_COST_PER_MILLION_USD
            ),
        )
    )


def usage_scope_savings_summary(
    mode_metrics: List[Dict[str, Any]],
    *,
    actual_estimated_cost: float,
    estimation_basis: str,
) -> Dict[str, Any]:
    return (
        _usage_scope_savings_summary_reporting_impl(
            mode_metrics,
            actual_estimated_cost=(
                actual_estimated_cost
            ),
            estimation_basis=(
                estimation_basis
            ),
        )
    )


def usage_mode_metrics(
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return (
        _usage_mode_metrics_reporting_impl(
            summary,
            derived_metrics_resolver=(
                usage_derived_metrics
            ),
            savings_metrics_resolver=(
                usage_savings_metrics
            ),
        )
    )


@app.get("/admin/usage/summary")
def admin_usage_summary(
    request: Request,
    days: int = Query(7, ge=1, le=30),
):
    require_admin(request)

    return (
        _admin_usage_summary_reporting_impl(
            days=int(days),
            connection_factory=db_conn,
            usage_day_resolver=(
                utc_usage_day
            ),
            expire_reservations=(
                expire_stale_gemini_reservations
            ),
            derived_metrics_resolver=(
                usage_derived_metrics
            ),
            mode_metrics_resolver=(
                usage_mode_metrics
            ),
            scope_savings_resolver=(
                usage_scope_savings_summary
            ),
            reservation_timeout_seconds=(
                GEMINI_RESERVATION_TIMEOUT_SECONDS
            ),
            global_daily_call_cap=(
                GLOBAL_DAILY_GEMINI_CALL_CAP
            ),
            client_daily_call_cap=(
                CLIENT_DAILY_GEMINI_CALL_CAP
            ),
            input_cost_per_million_usd=(
                GEMINI_INPUT_COST_PER_MILLION_USD
            ),
            output_cost_per_million_usd=(
                GEMINI_OUTPUT_COST_PER_MILLION_USD
            ),
        )
    )




# -----------------------------
# helpers
# -----------------------------
def stable_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()


def parse_published(entry: Any) -> Optional[str]:
    for k in ("published", "updated"):
        val = getattr(entry, k, None)
        if not val:
            continue

        try:
            dt = dtparser.parse(
                val,
                tzinfos={
                    "EST": -18000,
                    "EDT": -14400,
                    "CST": -21600,
                    "CDT": -18000,
                    "MST": -25200,
                    "MDT": -21600,
                    "PST": -28800,
                    "PDT": -25200,
                },
            )

            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()
        except Exception:
            pass

    return None


def load_sources() -> List[Dict[str, str]]:
    if not SOURCES_PATH.exists():
        SOURCES_PATH.write_text("[]", encoding="utf-8")
        return []

    raw = SOURCES_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []














# -----------------------------
# gemini tldr
# -----------------------------
_GEMINI_CLIENT = None
_GEMINI_LAST_INIT = 0.0


def gemini_client():
    global _GEMINI_CLIENT, _GEMINI_LAST_INIT

    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None

    if _GEMINI_CLIENT is None or (time.time() - _GEMINI_LAST_INIT) > 60:
        _GEMINI_CLIENT = genai.Client(api_key=key)
        _GEMINI_LAST_INIT = time.time()

    return _GEMINI_CLIENT


def gemini_candidate_semantics(
    *,
    claim: Dict[str, Any],
    candidate: Dict[str, Any],
    client_key: str = "anonymous",
) -> Dict[str, Any]:
    return (
        _gemini_candidate_semantics_impl(
            claim=claim,
            candidate=candidate,
            client_key=client_key,
            client_factory=gemini_client,
            generator=generate_gemini_content,
        )
    )


def gemini_candidate_collection_semantics(
    *,
    claim: Dict[str, Any],
    collection: Dict[str, Any],
    client_key: str = "anonymous",
    max_assessments: int = 8,
) -> Dict[str, Any]:
    return (
        _gemini_candidate_collection_semantics_impl(
            claim=claim,
            collection=collection,
            client_key=client_key,
            max_assessments=max_assessments,
            client_factory=gemini_client,
            generator=generate_gemini_content,
        )
    )


def gemini_tldr(
    title: str,
    text: str,
    max_bullets: int = 3,
    language_info: Optional[Dict[str, Any]] = None,
    article_type_label: str = "Article analysis",
    reasons: Optional[List[str]] = None,
    client_key: str = "anonymous",
) -> Dict[str, Any]:
    return (
        _gemini_tldr_impl(
            title=title,
            text=text,
            max_bullets=max_bullets,
            language_info=language_info,
            article_type_label=(
                article_type_label
            ),
            reasons=reasons,
            client_key=client_key,
            client_factory=gemini_client,
            generator=generate_gemini_content,
            fallback_resolver=(
                extractive_fallback
            ),
            max_analyze_chars=(
                MAX_ANALYZE_CHARS
            ),
        )
    )


def gemini_article_single_pass(
    title: str,
    text: str,
    url: str = "",
    max_bullets: int = 3,
    language_info: Optional[
        Dict[str, Any]
    ] = None,
    client_key: str = "anonymous",
) -> Dict[str, Any]:
    return (
        _gemini_article_single_pass_impl(
            title=title,
            text=text,
            url=url,
            max_bullets=max_bullets,
            language_info=language_info,
            client_key=client_key,
            client_factory=gemini_client,
            generator=generate_gemini_content,
            fallback_resolver=(
                extractive_fallback
            ),
            bullet_normalizer=(
                normalize_article_bullets
            ),
            classification_normalizer=(
                normalize_ai_article_classification
            ),
            max_analyze_chars=(
                MAX_ANALYZE_CHARS
            ),
        )
    )


def ai_detect_article_type(
    title: str,
    text: str,
    url: str = "",
    language_info: Optional[Dict[str, Any]] = None,
    client_key: str = "anonymous",
) -> Dict[str, Any]:
    return (
        _ai_detect_article_type_impl(
            title=title,
            text=text,
            url=url,
            language_info=language_info,
            client_key=client_key,
            client_factory=gemini_client,
            generator=generate_gemini_content,
            classification_normalizer=(
                normalize_ai_article_classification
            ),
        )
    )


def run_article_ai_strategy(
    *,
    title: str,
    text: str,
    url: str,
    max_bullets: int,
    language_info: Dict[str, Any],
    is_non_english_or_mixed: bool,
    rule_is_weak_generic: bool,
    client_key: str,
) -> Dict[str, Any]:
    return (
        _run_article_ai_strategy_impl(
            title=title,
            text=text,
            url=url,
            max_bullets=max_bullets,
            language_info=language_info,
            is_non_english_or_mixed=(
                is_non_english_or_mixed
            ),
            rule_is_weak_generic=(
                rule_is_weak_generic
            ),
            client_key=client_key,
            single_pass_runner=(
                gemini_article_single_pass
            ),
            classifier_runner=(
                ai_detect_article_type
            ),
        )
    )


















# -----------------------------
# AI article type classifier beta
# -----------------------------



# -----------------------------
# endpoints
# -----------------------------
@app.post("/ingest", response_model=IngestResponse)
def ingest():
    sources = load_sources()
    fetched_items = 0
    inserted = 0
    skipped = 0

    now = datetime.now(timezone.utc).isoformat()

    conn = db_conn()
    try:
        for src in sources:
            name = src.get("name", "unknown")
            sport = src.get("sport", "unknown")
            url = src.get("url", "")

            if not url:
                continue

            try:
                r = requests.get(
                    url,
                    timeout=12,
                    headers={"User-Agent": "Sportabase/0.3 (+rss-first)"},
                )
                r.raise_for_status()
                feed = feedparser.parse(r.text)
            except Exception as e:
                print(f"feed fetch failed: {name} | {type(e).__name__}: {str(e)[:140]}")
                continue

            entries = getattr(feed, "entries", [])[:40]

            for e in entries:
                link = getattr(e, "link", None)
                title = getattr(e, "title", None)

                if not link or not title:
                    continue

                fetched_items += 1
                sid = stable_id(str(link))

                exists = conn.execute(
                    "SELECT 1 FROM stories WHERE id = ?",
                    (sid,),
                ).fetchone()

                if exists:
                    skipped += 1
                    continue

                summary_html = getattr(e, "summary", "") or ""
                summary = clean_html(summary_html)
                published = parse_published(e)

                tldr = gemini_tldr(str(title), str(summary), max_bullets=3)
                type_info = detect_article_type(str(title), str(summary), str(link))
                score = merit_score(str(title), str(summary), str(link))

                conn.execute(
                    """
                    INSERT INTO stories (
                      id, source, sport, title, link, published, summary,
                      tldr_json, merit_score, badge, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        name,
                        sport,
                        str(title).strip(),
                        str(link).strip(),
                        published,
                        str(summary).strip(),
                        json.dumps(tldr, ensure_ascii=False),
                        int(score["total"]),
                        str(score["badge"]),
                        now,
                    ),
                )

                inserted += 1

        conn.commit()

    finally:
        conn.close()

    return IngestResponse(
        sources=len(sources),
        fetched_items=fetched_items,
        inserted=inserted,
        skipped=skipped,
    )


@app.get("/stories", response_model=List[Story])
def stories(
    sport: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
):
    conn = db_conn()
    try:
        where = []
        params: List[Any] = []

        if sport:
            where.append("sport = ?")
            params.append(sport)

        if source:
            where.append("source = ?")
            params.append(source)

        sql = "SELECT * FROM stories"

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()

        out: List[Story] = []
        for r in rows:
            out.append(
                Story(
                    id=r["id"],
                    source=r["source"],
                    sport=r["sport"],
                    title=r["title"],
                    link=r["link"],
                    published=r["published"],
                    summary=r["summary"] or "",
                    tldr=json.loads(r["tldr_json"] or "[]"),
                    merit_score=int(r["merit_score"] or 0),
                    badge=r["badge"] or badge(int(r["merit_score"] or 0)),
                    created_at=r["created_at"],
                )
            )

        return out

    finally:
        conn.close()
























def ai_video_claim_readout(
    title: str,
    transcript: str,
    url: str = "",
    transcript_metadata: Optional[
        Dict[str, Any]
    ] = None,
    client_key: str = "anonymous",
) -> Dict[str, Any]:
    return _ai_video_claim_readout_impl(
        title=title,
        transcript=transcript,
        url=url,
        transcript_metadata=(
            transcript_metadata
        ),
        client_key=client_key,
        client_factory=gemini_client,
        generator=generate_gemini_content,
    )













def resolve_youtube_content(
    normalized_url: str,
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=501,
        detail=(
            "YouTube content resolution "
            "is not implemented yet."
        ),
    )


def resolve_article_content(
    normalized_url: str,
) -> Dict[str, Any]:
    try:
        fetched = fetch_safe_article_html(
            normalized_url
        )
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error

    if not isinstance(fetched, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                "The article fetcher returned "
                "an invalid response."
            ),
        )

    article_html = str(
        fetched.get("html")
        or ""
    )

    if not article_html.strip():
        raise HTTPException(
            status_code=502,
            detail=(
                "The article fetcher returned "
                "an empty HTML page."
            ),
        )

    try:
        extracted = extract_article_content(
            article_html
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    if not isinstance(extracted, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                "The article extractor returned "
                "an invalid response."
            ),
        )

    title = str(
        extracted.get("title")
        or ""
    ).strip()

    content = str(
        extracted.get("text")
        or ""
    ).strip()

    if not content:
        raise HTTPException(
            status_code=422,
            detail=(
                "The page does not contain enough "
                "meaningful article text."
            ),
        )

    return {
        "title": title,
        "content": content,
        "metadata": {
            "final_url": str(
                fetched.get("final_url")
                or normalized_url
            ).strip(),
            "redirect_count": int(
                fetched.get("redirect_count")
                or 0
            ),
            "content_type": str(
                fetched.get("content_type")
                or ""
            ).strip(),
            "byte_count": int(
                fetched.get("byte_count")
                or 0
            ),
            "extraction_method": str(
                extracted.get(
                    "extraction_method"
                )
                or ""
            ).strip(),
            "paragraph_count": int(
                extracted.get(
                    "paragraph_count"
                )
                or 0
            ),
            "character_count": len(content),
        },
    }



@app.post(
    "/resolve-content",
    response_model=ContentResolveResponse,
)
def resolve_content(
    req: ContentResolveRequest,
):
    try:
        detected = detect_content_source(
            req.url
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    normalized_url = detected[
        "normalized_url"
    ]

    if detected["source"] == "youtube":
        resolved = resolve_youtube_content(
            normalized_url
        )
    else:
        resolved = resolve_article_content(
            normalized_url
        )

    if not isinstance(resolved, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                "The content resolver returned "
                "an invalid response."
            ),
        )

    title = str(
        resolved.get("title") or ""
    ).strip()

    content = str(
        resolved.get("content") or ""
    ).strip()

    metadata = resolved.get(
        "metadata",
        {},
    )

    if not isinstance(metadata, dict):
        metadata = {}

    if not content:
        raise HTTPException(
            status_code=502,
            detail=(
                "The content resolver returned "
                "no usable content."
            ),
        )

    return ContentResolveResponse(
        url=req.url,
        normalized_url=normalized_url,
        source=detected["source"],
        mode=detected["mode"],
        title=title,
        content=content,
        content_characters=len(content),
        metadata=metadata,
    )


@app.post("/analyze/video", response_model=VideoAnalyzeResponse)
def analyze_video(
    req: VideoAnalyzeRequest,
    request: Request,
):
    client_key = request_client_key(request)

    transcript_metadata = (
        normalize_video_transcript_metadata(
            req.transcript_metadata
        )
    )

    cache_content = (
        f"{req.title}\n"
        f"{req.transcript}\n"
        f"{json.dumps(
            transcript_metadata,
            sort_keys=True,
            ensure_ascii=False,
        )}"
    )

    cache_key = make_analysis_cache_key(
        mode="video",
        url=req.url,
        content=cache_content,
    )

    cached = get_cached_analysis(cache_key)

    if cached is not None:
        record_analysis_cache_hit(
            client_key,
            "video",
        )

        return VideoAnalyzeResponse(
            **cached
        )

    result = ai_video_claim_readout(
        req.title,
        req.transcript,
        req.url,
        transcript_metadata=(
            transcript_metadata
        ),
        client_key=client_key,
    )

    result = (
        validate_video_analysis_consistency(
            result
        )
    )

    cache_decision = (
        video_analysis_cache_decision(
            result
        )
    )

    cache_write_allowed = bool(
        cache_decision.get(
            "allowed",
            False,
        )
    )

    cache_write_reason = str(
        cache_decision.get(
            "reason",
            "unknown",
        )
    )

    response = VideoAnalyzeResponse(
        content_type=result.get(
            "content_type",
            "unknown",
        ),
        claim=result.get("claim", ""),
        evidence_used=result.get(
            "evidence_used",
            [],
        ),
        logic_check=result.get(
            "logic_check",
            "",
        ),
        hype_check=result.get(
            "hype_check",
            "",
        ),
        evidence_score=int(
            result.get(
                "evidence_score",
                0,
            )
        ),
        logic_score=int(
            result.get(
                "logic_score",
                0,
            )
        ),
        verdict=result.get(
            "verdict",
            "unclear",
        ),
        language=result.get(
            "language",
            result.get(
                "debug",
                {},
            ).get(
                "language",
                {},
            ),
        ),
        localized_content_type=result.get(
            "localized_content_type",
            "",
        ),
        localized_verdict=result.get(
            "localized_verdict",
            "",
        ),
        ui_labels=result.get(
            "ui_labels",
            {},
        ),
        debug={
            **result.get("debug", {}),
            "cache": {
                "hit": False,
                "analysis_version": (
                    ANALYSIS_VERSION
                ),
                "write_allowed": (
                    cache_write_allowed
                ),
                "write_reason": (
                    cache_write_reason
                ),
            },
        },
    )

    if cache_write_allowed:
        set_cached_analysis(
            cache_key=cache_key,
            mode="video",
            request_url=req.url,
            content=cache_content,
            response_payload=response,
            article_type=response.content_type,
        )
    else:
        print(
            "video analysis cache skipped:",
            cache_write_reason,
        )

    return response


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(
    req: AnalyzeRequest,
    request: Request,
):
    started = time.perf_counter()
    last_mark = started
    timings_ms: Dict[str, float] = {}

    def mark(name: str) -> None:
        nonlocal last_mark

        now = time.perf_counter()
        timings_ms[name] = round(
            (now - last_mark) * 1000,
            2,
        )
        last_mark = now

    client_key = request_client_key(request)

    cleaned_text = clean_html(req.text)
    original_chars = len(cleaned_text)

    cache_content = (
        f"{req.title}\n"
        f"{cleaned_text}"
    )

    content_hash = analysis_content_hash(
        cache_content
    )

    article_evidence_bundle: Optional[
        Dict[str, Any]
    ] = None

    article_evidence_context_hash = ""

    try:
        evidence_media_item_id = (
            media_item_id_for_url(
                req.url
            )
        )

        article_evidence_state = (
            load_evidence_analysis_state_for_media_item(
                media_item_id=(
                    evidence_media_item_id
                ),
            )
        )

        article_evidence_bundle = (
            article_evidence_state[
                "bundle"
            ]
        )

        article_evidence_context_hash = str(
            article_evidence_state[
                "context_hash"
            ]
        ).strip()

        if not article_evidence_context_hash:
            raise ValueError(
                "Evidence analysis context hash "
                "is empty."
            )

    except Exception as error:
        article_evidence_bundle = None
        article_evidence_context_hash = ""

        print(
            "article evidence analysis "
            "context skipped:",
            str(error),
        )

    cache_key = make_analysis_cache_key(
        mode="article",
        url=req.url,
        content=cache_content,
        variant=(
            f"max_bullets:{req.max_bullets}"
            "|intelligence_shadow:"
            f"{int(INTELLIGENCE_SHADOW_ENABLED)}"
        ),
        context_hash=(
            article_evidence_context_hash
        ),
    )

    cached = get_cached_analysis(cache_key)

    if cached is not None:
        record_analysis_cache_hit(
            client_key,
            "article",
        )

        try:
            media_item = upsert_media_item(
                url=req.url,
                mode="article",
                title=req.title,
                content_hash=content_hash,
            )

            snapshot = find_analysis_snapshot(
                media_item_id=media_item["id"],
                mode="article",
                content_hash=content_hash,
                context_hash=(
                    article_evidence_context_hash
                ),
            )

            record_user_history(
                client_key=client_key,
                media_item_id=media_item["id"],
                snapshot_id=(
                    int(snapshot["id"])
                    if snapshot is not None
                    else None
                ),
            )
        except Exception as error:
            print(
                "article history persistence skipped:",
                str(error),
            )

        return AnalyzeResponse(
            **cached
        )

    language_info = detect_content_language(
        cleaned_text
    )
    mark("language_detection_ms")

    cleaned_text = cleaned_text[
        :MAX_ANALYZE_CHARS
    ]
    mark("clean_and_cap_ms")

    type_info = detect_article_type(
        req.title,
        cleaned_text,
        req.url,
    )
    mark("article_type_ms")

    detected_language = str(
        language_info.get(
            "detected_language",
            "unknown",
        )
    ).strip().lower()

    is_non_english_or_mixed = (
        bool(
            language_info.get(
                "mixed_language",
                False,
            )
        )
        or detected_language
        not in {
            "english",
            "unknown",
        }
    )

    rule_type = str(
        type_info.get(
            "primary_type",
            "generic_news",
        )
    )

    rule_confidence = float(
        type_info.get(
            "confidence",
            0.0,
        )
        or 0.0
    )

    rule_is_weak_generic = (
        rule_type == "generic_news"
        and rule_confidence <= 0.35
    )

    should_use_ai_classifier = (
        is_non_english_or_mixed
        or rule_is_weak_generic
    )

    ai_strategy = (
        run_article_ai_strategy(
            title=req.title,
            text=cleaned_text,
            url=req.url,
            max_bullets=req.max_bullets,
            language_info=language_info,
            is_non_english_or_mixed=(
                is_non_english_or_mixed
            ),
            rule_is_weak_generic=(
                rule_is_weak_generic
            ),
            client_key=client_key,
        )
    )

    ai_type_info = ai_strategy[
        "ai_type_info"
    ]

    single_pass_result = ai_strategy[
        "single_pass_result"
    ]

    mark("ai_article_type_ms")

    final_type_info = type_info

    ai_type = ai_type_info.get(
        "article_type"
    )

    ai_confidence = float(
        ai_type_info.get(
            "confidence",
            0.0,
        )
        or 0.0
    )

    if (
        ai_type
        and ai_confidence >= 0.80
        and should_use_ai_classifier
    ):
        final_type_info = {
            "primary_type": ai_type,
            "label": ai_type_info.get(
                "article_type_label",
                ARTICLE_TYPE_LABELS.get(
                    ai_type,
                    "Generic Sports News",
                ),
            ),
            "subtype": ai_type_info.get(
                "article_subtype",
                "general",
            ),
            "confidence": ai_confidence,
            "signals": [
                (
                    "High-confidence "
                    "multilingual or fallback "
                    "AI classification."
                )
            ],
        }

    score = merit_score(
        req.title,
        cleaned_text,
        req.url,
        final_type_info,
    )
    mark("merit_score_ms")

    if isinstance(
        single_pass_result,
        dict,
    ):
        single_pass_bullets = (
            normalize_article_bullets(
                single_pass_result.get(
                    "bullets",
                    [],
                ),
                req.max_bullets,
            )
        )

        raw_single_pass_labels = (
            single_pass_result.get(
                "ui_labels",
                {},
            )
        )

        single_pass_labels = (
            raw_single_pass_labels
            if isinstance(
                raw_single_pass_labels,
                dict,
            )
            else {}
        )

        tldr_result = {
            "bullets": (
                single_pass_bullets
                or extractive_fallback(
                    cleaned_text,
                    max_bullets=(
                        req.max_bullets
                    ),
                )
            ),
            "localized_article_type": str(
                final_type_info.get(
                    "label",
                    "Generic Sports News",
                )
            ),
            "localized_reasons": score.get(
                "reasons",
                [],
            ),
            "ui_labels": (
                single_pass_labels
            ),
        }

    else:
        tldr_result = gemini_tldr(
            req.title,
            cleaned_text,
            max_bullets=req.max_bullets,
            language_info=language_info,
            article_type_label=str(
                final_type_info.get(
                    "label",
                    "Generic Sports News",
                )
            ),
            reasons=score.get(
                "reasons",
                [],
            ),
            client_key=client_key,
        )

    mark("tldr_ms")

    tldr = tldr_result.get(
        "bullets",
        [],
    )

    localized_article_type = str(
        tldr_result.get(
            "localized_article_type",
            final_type_info.get(
                "label",
                "Generic Sports News",
            ),
        )
    )

    localized_reasons = tldr_result.get(
        "localized_reasons",
        score.get(
            "reasons",
            [],
        ),
    )

    ui_labels = tldr_result.get(
        "ui_labels",
        {},
    )

    total_ms = round(
        (
            time.perf_counter()
            - started
        )
        * 1000,
        2,
    )

    response = AnalyzeResponse(
        url=req.url,
        title=req.title,
        tldr=tldr,
        merit_score=int(
            score["total"]
        ),
        badge=str(
            score["badge"]
        ),

        article_type=str(
            final_type_info.get(
                "primary_type",
                "generic_news",
            )
        ),
        article_type_label=str(
            final_type_info.get(
                "label",
                "Generic Sports News",
            )
        ),
        article_subtype=str(
            final_type_info.get(
                "subtype",
                "general",
            )
        ),
        type_confidence=float(
            final_type_info.get(
                "confidence",
                0.0,
            )
        ),
        type_signals=final_type_info.get(
            "signals",
            [],
        ),

        reasons=score.get(
            "reasons",
            [],
        ),

        score_components=score.get(
            "components",
            {},
        ),

        score_calculation=score.get(
            "calculation",
            {},
        ),

        language=language_info,
        localized_article_type=(
            localized_article_type
        ),
        localized_reasons=(
            localized_reasons
        ),
        ui_labels=ui_labels,

        debug={
            "timings": timings_ms,
            "total_ms": total_ms,
            "original_chars": original_chars,
            "chars_sent": len(
                cleaned_text
            ),
            "language": language_info,
            "cache": {
                "hit": False,
                "analysis_version": (
                    ANALYSIS_VERSION
                ),
            },
            "ai_classifier_requested": (
                should_use_ai_classifier
            ),
            "article_single_pass_used": (
                bool(
                    ai_strategy.get(
                        "used_single_pass",
                        False,
                    )
                )
            ),
            "rule_article_type": {
                "article_type": (
                    type_info.get(
                        "primary_type"
                    )
                ),
                "article_type_label": (
                    type_info.get(
                        "label"
                    )
                ),
                "article_subtype": (
                    type_info.get(
                        "subtype"
                    )
                ),
                "confidence": (
                    type_info.get(
                        "confidence"
                    )
                ),
                "signals": (
                    type_info.get(
                        "signals",
                        [],
                    )
                ),
            },
            "ai_article_type_shadow": (
                ai_type_info
            ),
        },
    )

    try:
        media_item = upsert_media_item(
            url=req.url,
            mode="article",
            title=req.title,
            content_hash=content_hash,
        )

        try:
            shadow_client = (
                gemini_client()
                if INTELLIGENCE_SHADOW_ENABLED
                else None
            )

            intelligence_shadow = (
                run_article_intelligence_shadow(
                    enabled=(
                        INTELLIGENCE_SHADOW_ENABLED
                    ),
                    media_item_id=(
                        media_item["id"]
                    ),
                    observed_at=(
                        media_item[
                            "first_seen_at"
                        ]
                    ),
                    title=req.title,
                    article_text=(
                        cleaned_text
                    ),
                    url=req.url,
                    article_type=(
                        response.article_type
                    ),
                    type_confidence=(
                        response.type_confidence
                    ),
                    legacy_score={
                        "total": (
                            response.merit_score
                        ),
                        "components": dict(
                            response.score_components
                        ),
                    },
                    news_api_key=(
                        BRAVE_NEWS_API_KEY
                    ),
                    normalize_url=(
                        normalized_analysis_url
                    ),
                    fetch_article=(
                        fetch_safe_article_html
                    ),
                    extract_article=(
                        extract_article_content
                    ),
                    gemini_client=(
                        shadow_client
                    ),
                    gemini_client_key=(
                        client_key
                    ),
                    gemini_generator=(
                        generate_gemini_content
                    ),
                    connection_factory=(
                        db_conn
                    ),
                )
            )

        except Exception as error:
            intelligence_shadow = {
                "version": (
                    ARTICLE_INTELLIGENCE_SHADOW_VERSION
                ),
                "status": "failed",
                "mode": "shadow",
                "error_type": (
                    type(error).__name__
                ),
                "error": str(
                    error
                )[:240],
                "live_merit_effect_enabled": (
                    False
                ),
                "truth_established": False,
            }

        response.debug[
            "intelligence_shadow"
        ] = intelligence_shadow

        snapshot_result = (
            persist_analysis_snapshot(
                media_item_id=media_item["id"],
                mode="article",
                content_hash=content_hash,
                context_hash=(
                    article_evidence_context_hash
                ),
                response=response.model_dump(),
                merit_score=response.merit_score,
                badge=response.badge,
                article_type=response.article_type,
                score_components=(
                    response.score_components
                ),
                score_calculation=(
                    response.score_calculation
                ),
                reasons=response.reasons,
            )
        )

        snapshot = snapshot_result[
            "snapshot"
        ]

        record_user_history(
            client_key=client_key,
            media_item_id=media_item["id"],
            snapshot_id=int(
                snapshot["id"]
            ),
        )

    except Exception as error:
        print(
            "article history persistence skipped:",
            str(error),
        )

    set_cached_analysis(
        cache_key=cache_key,
        mode="article",
        request_url=req.url,
        content=cache_content,
        response_payload=response,
        article_type=response.article_type,
    )

    return response
