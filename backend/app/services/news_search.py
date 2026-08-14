import re

from datetime import date
from typing import Any, Callable, Dict, List, Optional

import requests


BRAVE_NEWS_SEARCH_VERSION = "brave-news-search-v1"

BRAVE_NEWS_SEARCH_URL = (
    "https://api.search.brave.com/res/v1/news/search"
)

BRAVE_NEWS_FRESHNESS_VALUES = {
    "",
    "pd",
    "pw",
    "pm",
    "py",
}


def normalize_brave_news_query(
    query: str,
) -> str:
    normalized = re.sub(
        r"\s+",
        " ",
        str(query or ""),
    ).strip()

    if not normalized:
        raise ValueError(
            "News search query is required."
        )

    if len(normalized) > 400:
        raise ValueError(
            "News search query cannot exceed "
            "400 characters."
        )

    if len(normalized.split()) > 50:
        raise ValueError(
            "News search query cannot exceed "
            "50 words."
        )

    return normalized


def normalize_brave_news_freshness(
    freshness: str,
) -> str:
    normalized = str(
        freshness or ""
    ).strip().lower()

    if normalized in BRAVE_NEWS_FRESHNESS_VALUES:
        return normalized

    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})to"
        r"(\d{4}-\d{2}-\d{2})",
        normalized,
    )

    if match is None:
        raise ValueError(
            "Unsupported Brave news freshness value."
        )

    try:
        start = date.fromisoformat(
            match.group(1)
        )
        end = date.fromisoformat(
            match.group(2)
        )
    except ValueError as error:
        raise ValueError(
            "Invalid Brave news freshness date."
        ) from error

    if start > end:
        raise ValueError(
            "Brave news freshness start date "
            "cannot be after the end date."
        )

    return normalized


def search_brave_news(
    *,
    query: str,
    api_key: str,
    count: int = 20,
    offset: int = 0,
    freshness: str = "pw",
    country: str = "ALL",
    search_lang: str = "en",
    timeout_seconds: float = 10.0,
    request_get: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    normalized_query = (
        normalize_brave_news_query(query)
    )

    normalized_key = str(
        api_key or ""
    ).strip()

    if not normalized_key:
        raise ValueError(
            "Brave Search API key is required."
        )

    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        or count > 50
    ):
        raise ValueError(
            "Brave news result count must be "
            "between 1 and 50."
        )

    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or offset > 9
    ):
        raise ValueError(
            "Brave news offset must be "
            "between 0 and 9."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "News search timeout must be "
            "greater than zero."
        )

    normalized_freshness = (
        normalize_brave_news_freshness(
            freshness
        )
    )

    normalized_country = (
        str(country or "ALL")
        .strip()
        .upper()
    )

    normalized_language = (
        str(search_lang or "en")
        .strip()
        .lower()
    )

    params = {
        "q": normalized_query,
        "count": count,
        "offset": offset,
        "country": normalized_country,
        "search_lang": normalized_language,
        "safesearch": "strict",
    }

    if normalized_freshness:
        params["freshness"] = (
            normalized_freshness
        )

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": (
            normalized_key
        ),
    }

    getter = (
        request_get
        if request_get is not None
        else requests.get
    )

    try:
        response = getter(
            BRAVE_NEWS_SEARCH_URL,
            params=params,
            headers=headers,
            timeout=(
                3.05,
                timeout_seconds,
            ),
        )
    except requests.Timeout as error:
        raise RuntimeError(
            "Brave news search timed out."
        ) from error
    except requests.RequestException as error:
        raise RuntimeError(
            "Brave news search request failed."
        ) from error

    status_code = int(
        getattr(
            response,
            "status_code",
            0,
        )
        or 0
    )

    if status_code != 200:
        raise RuntimeError(
            "Brave news search returned "
            f"HTTP {status_code}."
        )

    try:
        payload = response.json()
    except Exception as error:
        raise RuntimeError(
            "Brave news search returned "
            "invalid JSON."
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Brave news search returned "
            "an invalid response."
        )

    results = payload.get(
        "results",
        [],
    )

    if not isinstance(results, list):
        results = []

    provider_query = payload.get(
        "query",
        {},
    )

    if not isinstance(
        provider_query,
        dict,
    ):
        provider_query = {}

    return {
        "version": (
            BRAVE_NEWS_SEARCH_VERSION
        ),
        "provider": "brave_news",
        "query": normalized_query,
        "provider_query": provider_query,
        "results": results,
    }


def normalize_brave_news_candidates(
    payload: Dict[str, Any],
    *,
    source_url: str = "",
    normalize_url: Callable[[str], str],
    domain_resolver: Callable[[str], str],
) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(
            "News search payload must be "
            "a dictionary."
        )

    raw_results = payload.get(
        "results",
        [],
    )

    if not isinstance(raw_results, list):
        return []

    normalized_source_url = (
        normalize_url(source_url)
        if source_url
        else ""
    )

    source_domain = (
        domain_resolver(
            normalized_source_url
        )
        if normalized_source_url
        else ""
    )

    seen_urls = set()
    candidates = []

    for index, row in enumerate(
        raw_results
    ):
        if not isinstance(row, dict):
            continue

        raw_url = str(
            row.get("url") or ""
        ).strip()

        if not raw_url:
            continue

        normalized_url = (
            normalize_url(raw_url)
        )

        if not normalized_url:
            continue

        if (
            normalized_source_url
            and normalized_url
            == normalized_source_url
        ):
            continue

        if normalized_url in seen_urls:
            continue

        candidate_domain = (
            domain_resolver(
                normalized_url
            )
        )

        if not candidate_domain:
            continue

        seen_urls.add(
            normalized_url
        )

        extra_snippets = (
            row.get(
                "extra_snippets",
                [],
            )
        )

        if not isinstance(
            extra_snippets,
            list,
        ):
            extra_snippets = []

        clean_extra_snippets = [
            str(value).strip()
            for value in extra_snippets
            if str(value).strip()
        ]

        candidates.append(
            {
                "provider": "brave_news",
                "provider_rank": (
                    index + 1
                ),
                "title": str(
                    row.get(
                        "title"
                    ) or ""
                ).strip(),
                "url": raw_url,
                "normalized_url": (
                    normalized_url
                ),
                "source_domain": (
                    candidate_domain
                ),
                "same_source_domain": bool(
                    source_domain
                    and candidate_domain
                    == source_domain
                ),
                "description": str(
                    row.get(
                        "description"
                    ) or ""
                ).strip(),
                "extra_snippets": (
                    clean_extra_snippets
                ),
                "age": str(
                    row.get(
                        "age"
                    ) or ""
                ).strip(),
                "page_age": str(
                    row.get(
                        "page_age"
                    ) or ""
                ).strip(),
            }
        )

    return candidates
