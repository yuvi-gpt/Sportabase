from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from fastapi import Request

from app.models.api import (
    AnalyzeRequest,
    VideoAnalyzeRequest,
)


def analyze_video_impl(
    req: VideoAnalyzeRequest,
    request: Request,
    *,
    ANALYSIS_VERSION,
    VideoAnalyzeResponse,
    ai_video_claim_readout,
    app,
    get_cached_analysis,
    json,
    make_analysis_cache_key,
    normalize_video_transcript_metadata,
    record_analysis_cache_hit,
    request_client_key,
    set_cached_analysis,
    validate_video_analysis_consistency,
    video_analysis_cache_decision,
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


def analyze_article_impl(
    req: AnalyzeRequest,
    request: Request,
    *,
    ANALYSIS_VERSION,
    ARTICLE_INTELLIGENCE_SHADOW_VERSION,
    ARTICLE_TYPE_LABELS,
    AnalyzeResponse,
    BRAVE_NEWS_API_KEY,
    INTELLIGENCE_SHADOW_ENABLED,
    MAX_ANALYZE_CHARS,
    analysis_content_hash,
    app,
    clean_html,
    db_conn,
    detect_article_type,
    detect_content_language,
    extract_article_content,
    extractive_fallback,
    fetch_safe_article_html,
    find_analysis_snapshot,
    gemini_client,
    gemini_tldr,
    generate_gemini_content,
    get_cached_analysis,
    load_evidence_analysis_state_for_media_item,
    make_analysis_cache_key,
    media_item_id_for_url,
    merit_score,
    normalize_article_bullets,
    normalized_analysis_url,
    persist_analysis_snapshot,
    record_analysis_cache_hit,
    record_user_history,
    request_client_key,
    run_article_ai_strategy,
    run_article_intelligence_shadow,
    set_cached_analysis,
    time,
    upsert_media_item,
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
