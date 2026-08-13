import re

from typing import Any, Dict, List


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
