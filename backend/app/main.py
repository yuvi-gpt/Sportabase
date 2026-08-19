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
from app.services.live_merit_release import (
    apply_certified_live_merit,
    live_merit_release_cache_token,
)
from app.models.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    BrowserCaptureRequest,
    BrowserCaptureResponse,
    MultimodalShadowRequest,
    MultimodalShadowResponse,
    MultimodalShadowSideRequest,
    ContentResolveRequest,
    ContentResolveResponse,
    IngestResponse,
    Story,
    VideoAnalyzeRequest,
    VideoAnalyzeResponse,
)
from app.services import browser_ingestion
from app.services import browser_capture_inbox
from app.services import browser_capture_automation
from app.services import multimodal_shadow_api
from app.routes import (
    multimodal_admin,
    product_api,
    usage_admin,
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
from app.services.gemini_capacity import (
    capacity_policy_for_model as _capacity_policy_for_model_impl,
    sportabase_daily_caps as _sportabase_daily_caps_impl,
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
from app.services.analysis_handlers import (
    analyze_article_impl as _analyze_article_handler_impl,
    analyze_video_impl as _analyze_video_handler_impl,
)
from app.services.legacy_handlers import (
    ingest_impl as _ingest_handler_impl,
    load_sources_impl as _load_sources_handler_impl,
    parse_published,
    resolve_article_content_impl as _resolve_article_content_handler_impl,
    resolve_content_impl as _resolve_content_handler_impl,
    resolve_youtube_content,
    stable_id,
    stories_impl as _stories_handler_impl,
)
from app.services.intelligence_facade import (
    source_domain_for_url_impl as _facade_source_domain_for_url_impl,
    source_key_for_url_impl as _facade_source_key_for_url_impl,
    source_id_for_url_impl as _facade_source_id_for_url_impl,
    upsert_intelligence_source_impl as _facade_upsert_intelligence_source_impl,
    story_id_for_canonical_key_impl as _facade_story_id_for_canonical_key_impl,
    upsert_intelligence_story_impl as _facade_upsert_intelligence_story_impl,
    claim_id_for_canonical_key_impl as _facade_claim_id_for_canonical_key_impl,
    upsert_intelligence_claim_impl as _facade_upsert_intelligence_claim_impl,
    claim_link_id_for_record_impl as _facade_claim_link_id_for_record_impl,
    record_claim_link_impl as _facade_record_claim_link_impl,
    link_media_item_to_story_impl as _facade_link_media_item_to_story_impl,
    reporter_id_for_identity_key_impl as _facade_reporter_id_for_identity_key_impl,
    upsert_intelligence_reporter_impl as _facade_upsert_intelligence_reporter_impl,
    record_source_observation_impl as _facade_record_source_observation_impl,
    record_reporter_observation_impl as _facade_record_reporter_observation_impl,
    evidence_key_for_record_impl as _facade_evidence_key_for_record_impl,
    record_evidence_impl as _facade_record_evidence_impl,
    record_evidence_link_impl as _facade_record_evidence_link_impl,
    _observation_dependency_identity_impl as _facade_observation_dependency_identity_impl,
    observation_dependency_id_for_record_impl as _facade_observation_dependency_id_for_record_impl,
    record_observation_dependency_impl as _facade_record_observation_dependency_impl,
    observation_independence_assertion_id_for_record_impl as _facade_observation_independence_assertion_id_for_record_impl,
    record_observation_independence_assertion_impl as _facade_record_observation_independence_assertion_impl,
    load_evidence_context_for_source_impl as _facade_load_evidence_context_for_source_impl,
    load_evidence_context_for_reporter_impl as _facade_load_evidence_context_for_reporter_impl,
    load_evidence_context_for_media_item_impl as _facade_load_evidence_context_for_media_item_impl,
    load_expanded_evidence_context_for_media_item_impl as _facade_load_expanded_evidence_context_for_media_item_impl,
    evidence_context_hash_for_media_item_impl as _facade_evidence_context_hash_for_media_item_impl,
    expanded_evidence_context_hash_for_media_item_impl as _facade_expanded_evidence_context_hash_for_media_item_impl,
    load_evidence_context_for_story_impl as _facade_load_evidence_context_for_story_impl,
    load_evidence_context_for_subject_impl as _facade_load_evidence_context_for_subject_impl,
    load_evidence_analysis_bundle_for_media_item_impl as _facade_load_evidence_analysis_bundle_for_media_item_impl,
    load_evidence_analysis_state_for_media_item_impl as _facade_load_evidence_analysis_state_for_media_item_impl,
)


def _invoke_intelligence_facade(
    implementation,
    local_values,
):
    call_kwargs = dict(
        local_values
    )

    dependencies = getattr(
        implementation,
        "__sportabase_dependencies__",
        (),
    )

    for dependency in dependencies:
        if dependency not in globals():
            raise RuntimeError(
                "Missing intelligence facade "
                "runtime dependency: "
                + str(
                    dependency
                )
            )

        call_kwargs[
            dependency
        ] = globals()[
            dependency
        ]

    return implementation(
        **call_kwargs
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
    "merit-v2-certified-corroboration",
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

_GEMINI_CAPACITY_POLICY = (
    _capacity_policy_for_model_impl("")
)
(
    GLOBAL_DAILY_GEMINI_CALL_CAP,
    CLIENT_DAILY_GEMINI_CALL_CAP,
) = _sportabase_daily_caps_impl(
    _GEMINI_CAPACITY_POLICY
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

MULTIMODAL_SHADOW_API_ENABLED = (
    os.getenv(
        "SPORTABASE_MULTIMODAL_SHADOW_API_ENABLED",
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


LIVE_MERIT_ENABLED = (
    os.getenv(
        "SPORTABASE_LIVE_MERIT_ENABLED",
        "1",
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

MERIT_SCORE_RELEASE_CERTIFICATE_PATH = (
    DATA_DIR
    / "merit_score_release_certificate.json"
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


# Importing app.main must be side-effect free with respect
# to the persistent database. Uvicorn/FastAPI startup still
# initializes the production schema before requests are
# served, while tests may explicitly override DB_PATH and
# call init_db() against temporary databases.
app.add_event_handler(
    "startup",
    init_db,
)


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
    return _invoke_intelligence_facade(
        _facade_source_domain_for_url_impl,
        locals(),
    )


def source_key_for_url(
    url: str,
    source_type: str = "publisher",
) -> str:
    return _invoke_intelligence_facade(
        _facade_source_key_for_url_impl,
        locals(),
    )


def source_id_for_url(
    url: str,
    source_type: str = "publisher",
) -> str:
    return _invoke_intelligence_facade(
        _facade_source_id_for_url_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_upsert_intelligence_source_impl,
        locals(),
    )


def story_id_for_canonical_key(
    canonical_key: str,
) -> str:
    return _invoke_intelligence_facade(
        _facade_story_id_for_canonical_key_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_upsert_intelligence_story_impl,
        locals(),
    )


def claim_id_for_canonical_key(
    canonical_key: str,
) -> str:
    return _invoke_intelligence_facade(
        _facade_claim_id_for_canonical_key_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_upsert_intelligence_claim_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_claim_link_id_for_record_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_claim_link_impl,
        locals(),
    )


def link_media_item_to_story(
    *,
    story_id: str,
    media_item_id: str,
    relationship_type: str = "reports",
    confidence: float = 0.0,
    linked_at: Optional[str] = None,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_link_media_item_to_story_impl,
        locals(),
    )


def reporter_id_for_identity_key(
    identity_key: str,
) -> str:
    return _invoke_intelligence_facade(
        _facade_reporter_id_for_identity_key_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_upsert_intelligence_reporter_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_source_observation_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_reporter_observation_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_evidence_key_for_record_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_evidence_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_evidence_link_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_observation_dependency_identity_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_observation_dependency_id_for_record_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_observation_dependency_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_observation_independence_assertion_id_for_record_impl,
        locals(),
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
    return _invoke_intelligence_facade(
        _facade_record_observation_independence_assertion_impl,
        locals(),
    )


def load_evidence_context_for_source(
    *,
    source_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_context_for_source_impl,
        locals(),
    )


def load_evidence_context_for_reporter(
    *,
    reporter_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_context_for_reporter_impl,
        locals(),
    )


def load_evidence_context_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_context_for_media_item_impl,
        locals(),
    )


def load_expanded_evidence_context_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_expanded_evidence_context_for_media_item_impl,
        locals(),
    )


def evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
) -> str:
    return _invoke_intelligence_facade(
        _facade_evidence_context_hash_for_media_item_impl,
        locals(),
    )


def expanded_evidence_context_hash_for_media_item(
    *,
    media_item_id: str,
) -> str:
    return _invoke_intelligence_facade(
        _facade_expanded_evidence_context_hash_for_media_item_impl,
        locals(),
    )


def load_evidence_context_for_story(
    *,
    story_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_context_for_story_impl,
        locals(),
    )


def load_evidence_context_for_subject(
    *,
    subject_key: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_context_for_subject_impl,
        locals(),
    )


def load_evidence_analysis_bundle_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_analysis_bundle_for_media_item_impl,
        locals(),
    )


def load_evidence_analysis_state_for_media_item(
    *,
    media_item_id: str,
) -> Dict[str, Any]:
    return _invoke_intelligence_facade(
        _facade_load_evidence_analysis_state_for_media_item_impl,
        locals(),
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
    estimated_prompt_tokens: int = 0,
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
            estimated_prompt_tokens=(
                estimated_prompt_tokens
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




def load_sources() -> List[Dict[str, str]]:
    return _load_sources_handler_impl(
        SOURCES_PATH=SOURCES_PATH,
    )














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
# compatibility endpoint handlers
# -----------------------------
def ingest():
    return _ingest_handler_impl(
        IngestResponse=IngestResponse,
        clean_html=clean_html,
        db_conn=db_conn,
        detect_article_type=detect_article_type,
        feedparser=feedparser,
        gemini_tldr=gemini_tldr,
        load_sources=load_sources,
        merit_score=merit_score,
        parse_published=parse_published,
        requests=requests,
        stable_id=stable_id,
    )


def stories(
    sport: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
):
    return _stories_handler_impl(
        sport=sport,
        source=source,
        limit=limit,
        Story=Story,
        badge=badge,
        db_conn=db_conn,
    )
























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















def resolve_article_content(
    normalized_url: str,
) -> Dict[str, Any]:
    return _resolve_article_content_handler_impl(
        normalized_url,
        extract_article_content=extract_article_content,
        fetch_safe_article_html=fetch_safe_article_html,
    )



def resolve_content(
    req: ContentResolveRequest,
):
    return _resolve_content_handler_impl(
        req,
        ContentResolveResponse=ContentResolveResponse,
        detect_content_source=detect_content_source,
        resolve_article_content=resolve_article_content,
        resolve_youtube_content=resolve_youtube_content,
    )



def browser_capture_preview(
    req: BrowserCaptureRequest,
):
    return (
        browser_capture_inbox
        .execute_browser_capture_http(
            req=req,
            connection_factory=db_conn,
            response_model=BrowserCaptureResponse,
            automation_enqueue=(
                browser_capture_automation
                .enqueue_browser_capture_job
            ),
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
    )



def admin_multimodal_shadow(
    req: MultimodalShadowRequest,
    request: Request,
):
    return (
        multimodal_shadow_api
        .execute_multimodal_shadow_http(
            req=req,
            request=request,
            enabled=(
                MULTIMODAL_SHADOW_API_ENABLED
            ),
            require_admin=require_admin,
            gemini_client_factory=gemini_client,
            request_client_key_resolver=(
                request_client_key
            ),
            gemini_generator=(
                generate_gemini_content
            ),
            connection_factory=db_conn,
            response_model=(
                MultimodalShadowResponse
            ),
        )
    )



def analyze_video(
    req: VideoAnalyzeRequest,
    request: Request,
):
    return _analyze_video_handler_impl(
        req,
        request,
        ANALYSIS_VERSION=ANALYSIS_VERSION,
        VideoAnalyzeResponse=VideoAnalyzeResponse,
        ai_video_claim_readout=ai_video_claim_readout,
        app=app,
        get_cached_analysis=get_cached_analysis,
        json=json,
        make_analysis_cache_key=make_analysis_cache_key,
        normalize_video_transcript_metadata=normalize_video_transcript_metadata,
        record_analysis_cache_hit=record_analysis_cache_hit,
        request_client_key=request_client_key,
        set_cached_analysis=set_cached_analysis,
        validate_video_analysis_consistency=validate_video_analysis_consistency,
        video_analysis_cache_decision=video_analysis_cache_decision,
    )



def analyze(
    req: AnalyzeRequest,
    request: Request,
):
    return _analyze_article_handler_impl(
        req,
        request,
        ANALYSIS_VERSION=ANALYSIS_VERSION,
        ARTICLE_INTELLIGENCE_SHADOW_VERSION=ARTICLE_INTELLIGENCE_SHADOW_VERSION,
        ARTICLE_TYPE_LABELS=ARTICLE_TYPE_LABELS,
        AnalyzeResponse=AnalyzeResponse,
        BRAVE_NEWS_API_KEY=BRAVE_NEWS_API_KEY,
        INTELLIGENCE_SHADOW_ENABLED=INTELLIGENCE_SHADOW_ENABLED,
        LIVE_MERIT_ENABLED=LIVE_MERIT_ENABLED,
        MAX_ANALYZE_CHARS=MAX_ANALYZE_CHARS,
        MERIT_SCORE_RELEASE_CERTIFICATE_PATH=MERIT_SCORE_RELEASE_CERTIFICATE_PATH,
        analysis_content_hash=analysis_content_hash,
        apply_certified_live_merit=apply_certified_live_merit,
        app=app,
        badge=badge,
        clean_html=clean_html,
        db_conn=db_conn,
        detect_article_type=detect_article_type,
        detect_content_language=detect_content_language,
        extract_article_content=extract_article_content,
        extractive_fallback=extractive_fallback,
        fetch_safe_article_html=fetch_safe_article_html,
        find_analysis_snapshot=find_analysis_snapshot,
        gemini_client=gemini_client,
        gemini_tldr=gemini_tldr,
        generate_gemini_content=generate_gemini_content,
        get_cached_analysis=get_cached_analysis,
        load_evidence_analysis_state_for_media_item=load_evidence_analysis_state_for_media_item,
        live_merit_release_cache_token=live_merit_release_cache_token,
        make_analysis_cache_key=make_analysis_cache_key,
        media_item_id_for_url=media_item_id_for_url,
        merit_score=merit_score,
        normalize_article_bullets=normalize_article_bullets,
        normalized_analysis_url=normalized_analysis_url,
        persist_analysis_snapshot=persist_analysis_snapshot,
        record_analysis_cache_hit=record_analysis_cache_hit,
        record_user_history=record_user_history,
        request_client_key=request_client_key,
        run_article_ai_strategy=run_article_ai_strategy,
        run_article_intelligence_shadow=run_article_intelligence_shadow,
        set_cached_analysis=set_cached_analysis,
        time=time,
        upsert_media_item=upsert_media_item,
    )


app.include_router(
    product_api.build_router(
        health_handler=health,
        ingest_handler=ingest,
        stories_handler=stories,
        resolve_content_handler=resolve_content,
        browser_capture_handler=(
            browser_capture_preview
        ),
        analyze_video_handler=analyze_video,
        analyze_handler=analyze,
    )
)

app.include_router(
    usage_admin.build_router(
        usage_summary_handler=(
            admin_usage_summary
        ),
    )
)

app.include_router(
    multimodal_admin.build_router(
        MULTIMODAL_SHADOW_API_ENABLED,
        require_admin,
        db_conn,
        gemini_client,
        request_client_key,
        generate_gemini_content,
        ANALYSIS_VERSION,
        SCORING_VERSION,
    )
)

browser_capture_automation.register_browser_capture_automation_lifecycle(
    app=app,
    connection_factory=db_conn,
    analysis_version=ANALYSIS_VERSION,
    scoring_version=SCORING_VERSION,
    gemini_client_factory=gemini_client,
    gemini_generator=generate_gemini_content,
)
