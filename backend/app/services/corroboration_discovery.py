import re

from typing import Any, Dict, List

from app.services.news_search import (
    normalize_brave_news_candidates,
    search_brave_news,
)

from app.services.publication_time import (
    resolve_publication_time,
)


CORROBORATION_SEARCH_PLAN_VERSION = (
    "corroboration-search-plan-v1"
)

_CORE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "for",
    "from",
    "has",
    "have",
    "had",
    "he",
    "her",
    "his",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "they",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}

# Negation words are intentionally NOT stopwords.
# "not", "no", "never", etc. can materially change
# the meaning of a sports claim.


def _normalize_query_text(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _fit_search_query(
    value: str,
    *,
    max_characters: int = 400,
    max_words: int = 50,
) -> str:
    normalized = _normalize_query_text(
        value
    )

    if not normalized:
        return ""

    words = normalized.split()

    if len(words) > max_words:
        words = words[:max_words]

    fitted = " ".join(words)

    if len(fitted) <= max_characters:
        return fitted

    clipped_words = []

    for word in words:
        candidate = " ".join(
            clipped_words + [word]
        )

        if len(candidate) > max_characters:
            break

        clipped_words.append(word)

    return " ".join(
        clipped_words
    ).strip()


def _core_claim_query(
    canonical_text: str,
) -> str:
    normalized = _normalize_query_text(
        canonical_text
    )

    tokens = re.findall(
        r"[^\W_]+(?:['?.-][^\W_]+)*",
        normalized,
        flags=re.UNICODE,
    )

    retained = []

    for token in tokens:
        lowered = token.lower()

        if lowered in _CORE_STOPWORDS:
            continue

        retained.append(token)

    return _fit_search_query(
        " ".join(retained)
    )


def build_claim_corroboration_search_plan(
    claim: Dict[str, Any],
    *,
    source_url: str = "",
    freshness: str = "pw",
) -> Dict[str, Any]:
    if not isinstance(claim, dict):
        raise ValueError(
            "Corroboration search claim must "
            "be a dictionary."
        )

    claim_id = str(
        claim.get("id") or ""
    ).strip()

    canonical_key = str(
        claim.get("canonical_key") or ""
    ).strip()

    subject_key = str(
        claim.get("subject_key") or ""
    ).strip()

    claim_type = str(
        claim.get("claim_type") or ""
    ).strip().lower()

    canonical_text = (
        _normalize_query_text(
            claim.get(
                "canonical_text"
            )
            or ""
        )
    )

    normalized_source_url = str(
        source_url or ""
    ).strip()

    normalized_freshness = str(
        freshness or "pw"
    ).strip().lower()

    base = {
        "version": (
            CORROBORATION_SEARCH_PLAN_VERSION
        ),
        "claim_id": claim_id,
        "canonical_key": canonical_key,
        "subject_key": subject_key,
        "claim_type": claim_type,
        "canonical_text": canonical_text,
        "source_url": (
            normalized_source_url
        ),
        "freshness": (
            normalized_freshness
        ),
    }

    if not canonical_text:
        return {
            **base,
            "status": "not_searchable",
            "reason": (
                "canonical_text_missing"
            ),
            "queries": [],
        }

    full_query = _fit_search_query(
        canonical_text
    )

    core_query = _core_claim_query(
        canonical_text
    )

    raw_queries = [
        (
            "claim_text",
            full_query,
        ),
        (
            "claim_core",
            core_query,
        ),
    ]

    queries: List[
        Dict[str, Any]
    ] = []

    seen = set()

    for purpose, query in raw_queries:
        normalized_query = (
            _normalize_query_text(
                query
            )
        )

        if not normalized_query:
            continue

        dedupe_key = (
            normalized_query.lower()
        )

        if dedupe_key in seen:
            continue

        seen.add(
            dedupe_key
        )

        queries.append(
            {
                "sequence": (
                    len(queries) + 1
                ),
                "purpose": purpose,
                "query": (
                    normalized_query
                ),
                "freshness": (
                    normalized_freshness
                ),
            }
        )

    if not queries:
        return {
            **base,
            "status": "not_searchable",
            "reason": (
                "no_valid_search_query"
            ),
            "queries": [],
        }

    return {
        **base,
        "status": "searchable",
        "reason": "",
        "queries": queries,
        "policy": {
            (
                "canonical_key_is_not_sent_"
                "to_provider"
            ): True,
            (
                "subject_key_is_not_sent_"
                "to_provider"
            ): True,
            (
                "search_discovery_does_not_"
                "establish_support"
            ): True,
            (
                "search_discovery_does_not_"
                "establish_independence"
            ): True,
            (
                "search_discovery_does_not_"
                "establish_corroboration"
            ): True,
        },
    }


CORROBORATION_CANDIDATE_COLLECTION_VERSION = (
    "corroboration-candidate-collection-v1"
)


def _collection_policy() -> Dict[str, bool]:
    return {
        (
            "discovery_does_not_establish_"
            "support"
        ): True,
        (
            "discovery_does_not_establish_"
            "independence"
        ): True,
        (
            "discovery_does_not_establish_"
            "corroboration"
        ): True,
        (
            "candidate_content_must_be_"
            "evaluated_before_semantic_use"
        ): True,
    }


def collect_corroboration_candidates(
    *,
    plan: Dict[str, Any],
    api_key: str,
    normalize_url,
    domain_resolver,
    fetch_article,
    extract_article,
    publication_time_resolver=resolve_publication_time,
    searcher=search_brave_news,
    candidate_normalizer=(
        normalize_brave_news_candidates
    ),
    max_candidates: int = 8,
    results_per_query: int = 20,
) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError(
            "Corroboration search plan must "
            "be a dictionary."
        )

    base = {
        "version": (
            CORROBORATION_CANDIDATE_COLLECTION_VERSION
        ),
        "claim_id": str(
            plan.get("claim_id") or ""
        ).strip(),
        "source_url": str(
            plan.get("source_url") or ""
        ).strip(),
        "policy": _collection_policy(),
    }

    if (
        str(
            plan.get("status") or ""
        ).strip()
        != "searchable"
    ):
        return {
            **base,
            "status": "not_searchable",
            "reason": str(
                plan.get("reason") or ""
            ).strip(),
            "search_attempts": [],
            "candidates": [],
            "resolved_candidates": [],
            "counts": {
                "search_attempts": 0,
                "search_failures": 0,
                "discovered": 0,
                "resolution_attempts": 0,
                "resolved": 0,
                "failed": 0,
                "excluded": 0,
                "not_attempted": 0,
            },
        }

    normalized_key = str(
        api_key or ""
    ).strip()

    if not normalized_key:
        raise ValueError(
            "News search API key is required."
        )

    if (
        isinstance(max_candidates, bool)
        or not isinstance(
            max_candidates,
            int,
        )
        or max_candidates < 1
        or max_candidates > 20
    ):
        raise ValueError(
            "Corroboration candidate limit "
            "must be between 1 and 20."
        )

    if (
        isinstance(results_per_query, bool)
        or not isinstance(
            results_per_query,
            int,
        )
        or results_per_query < 1
        or results_per_query > 50
    ):
        raise ValueError(
            "Search results per query must "
            "be between 1 and 50."
        )

    source_url = base["source_url"]

    normalized_source_url = (
        normalize_url(source_url)
        if source_url
        else ""
    )

    raw_queries = plan.get(
        "queries",
        [],
    )

    if not isinstance(
        raw_queries,
        list,
    ):
        raw_queries = []

    search_attempts = []
    discovered_by_url = {}
    discovered_order = []

    for query_row in raw_queries:
        if not isinstance(
            query_row,
            dict,
        ):
            continue

        query = str(
            query_row.get("query") or ""
        ).strip()

        if not query:
            continue

        purpose = str(
            query_row.get(
                "purpose"
            ) or ""
        ).strip()

        sequence = query_row.get(
            "sequence"
        )

        freshness = str(
            query_row.get(
                "freshness"
            )
            or plan.get("freshness")
            or "pw"
        ).strip().lower()

        discovery_reference = {
            "sequence": sequence,
            "purpose": purpose,
            "query": query,
        }

        try:
            payload = searcher(
                query=query,
                api_key=normalized_key,
                count=results_per_query,
                offset=0,
                freshness=freshness,
            )
        except Exception as error:
            search_attempts.append(
                {
                    **discovery_reference,
                    "status": "search_failed",
                    "error_type": (
                        type(error).__name__
                    ),
                    "error": str(
                        error
                    )[:240],
                    "candidate_count": 0,
                }
            )
            continue

        try:
            normalized_candidates = (
                candidate_normalizer(
                    payload,
                    source_url=source_url,
                    normalize_url=normalize_url,
                    domain_resolver=(
                        domain_resolver
                    ),
                )
            )
        except Exception as error:
            search_attempts.append(
                {
                    **discovery_reference,
                    "status": (
                        "normalization_failed"
                    ),
                    "error_type": (
                        type(error).__name__
                    ),
                    "error": str(
                        error
                    )[:240],
                    "candidate_count": 0,
                }
            )
            continue

        search_attempts.append(
            {
                **discovery_reference,
                "status": "completed",
                "error_type": "",
                "error": "",
                "candidate_count": len(
                    normalized_candidates
                ),
            }
        )

        for candidate in (
            normalized_candidates
        ):
            if not isinstance(
                candidate,
                dict,
            ):
                continue

            normalized_url = str(
                candidate.get(
                    "normalized_url"
                )
                or ""
            ).strip()

            if not normalized_url:
                continue

            existing = (
                discovered_by_url.get(
                    normalized_url
                )
            )

            if existing is not None:
                references = existing[
                    "discovery_queries"
                ]

                if (
                    discovery_reference
                    not in references
                ):
                    references.append(
                        discovery_reference
                    )

                continue

            stored = {
                **candidate,
                "discovery_queries": [
                    discovery_reference
                ],
            }

            discovered_by_url[
                normalized_url
            ] = stored

            discovered_order.append(
                normalized_url
            )

    discovered_candidates = [
        discovered_by_url[
            normalized_url
        ]
        for normalized_url
        in discovered_order
    ]

    evaluated_candidates = []
    resolved_candidates = []
    resolved_final_urls = set()

    resolution_attempts = 0
    failed = 0
    excluded = 0
    not_attempted = 0

    for index, candidate in enumerate(
        discovered_candidates
    ):
        evaluated = dict(
            candidate
        )

        if index >= max_candidates:
            evaluated[
                "resolution_status"
            ] = "not_attempted_limit"

            evaluated_candidates.append(
                evaluated
            )

            not_attempted += 1
            continue

        resolution_attempts += 1

        candidate_url = str(
            candidate.get(
                "normalized_url"
            )
            or candidate.get("url")
            or ""
        ).strip()

        try:
            fetched = fetch_article(
                candidate_url
            )
        except Exception as error:
            evaluated.update(
                {
                    "resolution_status": (
                        "fetch_failed"
                    ),
                    "resolution_error_type": (
                        type(error).__name__
                    ),
                    "resolution_error": str(
                        error
                    )[:240],
                }
            )

            evaluated_candidates.append(
                evaluated
            )

            failed += 1
            continue

        if not isinstance(
            fetched,
            dict,
        ):
            evaluated.update(
                {
                    "resolution_status": (
                        "fetch_failed"
                    ),
                    "resolution_error_type": (
                        "InvalidFetchResult"
                    ),
                    "resolution_error": (
                        "Article fetcher returned "
                        "an invalid result."
                    ),
                }
            )

            evaluated_candidates.append(
                evaluated
            )

            failed += 1
            continue

        final_url = normalize_url(
            fetched.get(
                "final_url"
            )
            or candidate_url
        )

        evaluated[
            "final_url"
        ] = final_url

        evaluated[
            "redirect_count"
        ] = fetched.get(
            "redirect_count",
            0,
        )

        evaluated[
            "content_type"
        ] = str(
            fetched.get(
                "content_type"
            )
            or ""
        ).strip()

        evaluated[
            "byte_count"
        ] = fetched.get(
            "byte_count",
            0,
        )

        if (
            normalized_source_url
            and final_url
            == normalized_source_url
        ):
            evaluated[
                "resolution_status"
            ] = (
                "excluded_current_after_redirect"
            )

            evaluated_candidates.append(
                evaluated
            )

            excluded += 1
            continue

        if (
            final_url
            and final_url
            in resolved_final_urls
        ):
            evaluated[
                "resolution_status"
            ] = "duplicate_final_url"

            evaluated_candidates.append(
                evaluated
            )

            excluded += 1
            continue

        article_html = str(
            fetched.get(
                "html"
            )
            or ""
        )

        try:
            extracted = extract_article(
                article_html
            )
        except Exception as error:
            evaluated.update(
                {
                    "resolution_status": (
                        "extraction_failed"
                    ),
                    "resolution_error_type": (
                        type(error).__name__
                    ),
                    "resolution_error": str(
                        error
                    )[:240],
                }
            )

            evaluated_candidates.append(
                evaluated
            )

            failed += 1
            continue

        if not isinstance(
            extracted,
            dict,
        ):
            evaluated.update(
                {
                    "resolution_status": (
                        "extraction_failed"
                    ),
                    "resolution_error_type": (
                        "InvalidExtractionResult"
                    ),
                    "resolution_error": (
                        "Article extractor returned "
                        "an invalid result."
                    ),
                }
            )

            evaluated_candidates.append(
                evaluated
            )

            failed += 1
            continue

        try:
            publication_time = (
                publication_time_resolver(
                    article_html,
                    provider_page_age=(
                        candidate.get(
                            "page_age"
                        )
                        or ""
                    ),
                )
            )
        except Exception:
            publication_time = {
                "version": "",
                "status": "extraction_failed",
                "published_at": "",
                "raw_value": "",
                "timezone_known": False,
                "precision": "",
                "source_type": "",
                "source_key": "",
            }

        if not isinstance(
            publication_time,
            dict,
        ):
            publication_time = {
                "version": "",
                "status": "extraction_failed",
                "published_at": "",
                "raw_value": "",
                "timezone_known": False,
                "precision": "",
                "source_type": "",
                "source_key": "",
            }

        final_source_domain = (
            domain_resolver(
                final_url
            )
            if final_url
            else ""
        )

        source_domain = (
            domain_resolver(
                normalized_source_url
            )
            if normalized_source_url
            else ""
        )

        evaluated.update(
            {
                "resolution_status": (
                    "resolved"
                ),
                "resolution_error_type": "",
                "resolution_error": "",
                "final_source_domain": (
                    final_source_domain
                ),
                "final_same_source_domain": (
                    bool(
                        source_domain
                        and final_source_domain
                        == source_domain
                    )
                ),
                "extracted_title": str(
                    extracted.get(
                        "title"
                    )
                    or ""
                ).strip(),
                "text": str(
                    extracted.get(
                        "text"
                    )
                    or ""
                ).strip(),
                "extraction_method": str(
                    extracted.get(
                        "extraction_method"
                    )
                    or ""
                ).strip(),
                "paragraph_count": (
                    extracted.get(
                        "paragraph_count",
                        0,
                    )
                ),
                "character_count": (
                    extracted.get(
                        "character_count",
                        0,
                    )
                ),
                "published_at": str(
                    publication_time.get(
                        "published_at"
                    )
                    or ""
                ).strip(),
                "publication_time_version": str(
                    publication_time.get(
                        "version"
                    )
                    or ""
                ).strip(),
                "publication_time_status": str(
                    publication_time.get(
                        "status"
                    )
                    or ""
                ).strip(),
                "publication_time_raw": str(
                    publication_time.get(
                        "raw_value"
                    )
                    or ""
                ).strip(),
                "publication_time_source_type": str(
                    publication_time.get(
                        "source_type"
                    )
                    or ""
                ).strip(),
                "publication_time_source_key": str(
                    publication_time.get(
                        "source_key"
                    )
                    or ""
                ).strip(),
                "publication_time_timezone_known": bool(
                    publication_time.get(
                        "timezone_known",
                        False,
                    )
                ),
                "publication_time_precision": str(
                    publication_time.get(
                        "precision"
                    )
                    or ""
                ).strip(),
            }
        )

        if final_url:
            resolved_final_urls.add(
                final_url
            )

        evaluated_candidates.append(
            evaluated
        )

        resolved_candidates.append(
            evaluated
        )

    completed_attempts = [
        attempt
        for attempt in search_attempts
        if attempt["status"]
        == "completed"
    ]

    search_failures = (
        len(search_attempts)
        - len(completed_attempts)
    )

    if resolved_candidates:
        collection_status = (
            "resolved_candidates_available"
        )

    elif not discovered_candidates:
        if (
            search_attempts
            and not completed_attempts
        ):
            collection_status = (
                "search_failed"
            )
        else:
            collection_status = (
                "no_candidates_found"
            )

    else:
        collection_status = (
            "no_resolved_candidates"
        )

    return {
        **base,
        "status": collection_status,
        "reason": "",
        "search_attempts": (
            search_attempts
        ),
        "candidates": (
            evaluated_candidates
        ),
        "resolved_candidates": (
            resolved_candidates
        ),
        "counts": {
            "search_attempts": len(
                search_attempts
            ),
            "search_failures": (
                search_failures
            ),
            "discovered": len(
                discovered_candidates
            ),
            "resolution_attempts": (
                resolution_attempts
            ),
            "resolved": len(
                resolved_candidates
            ),
            "failed": failed,
            "excluded": excluded,
            "not_attempted": (
                not_attempted
            ),
        },
    }
