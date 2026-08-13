import html as ihtml
import json
import re

from datetime import timezone
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from dateutil import parser as dtparser


PUBLICATION_TIME_VERSION = "publication-time-v1"


_EXPLICIT_META_KEYS = (
    "article:published_time",
    "og:published_time",
    "datepublished",
    "parsely-pub-date",
    "pubdate",
    "publishdate",
    "publish-date",
    "dc.date.issued",
    "dcterms.issued",
)

_GENERIC_META_KEYS = (
    "date",
    "dc.date",
    "dcterms.date",
)


def _clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        ihtml.unescape(
            str(value or "")
        ),
    ).strip()


def normalize_publication_timestamp(
    value: Any,
) -> Optional[Dict[str, Any]]:
    raw = _clean(value)

    if not raw:
        return None

    # Reject relative values such as "2 hours ago".
    # Resolving those against retrieval time would make
    # historical identity non-deterministic.
    if re.search(
        r"\b\d{4}\b",
        raw,
    ) is None:
        return None

    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        raw,
    ):
        try:
            parsed = dtparser.parse(raw)
        except Exception:
            return None

        return {
            "published_at": (
                parsed.date().isoformat()
            ),
            "raw_value": raw,
            "timezone_known": False,
            "precision": "date",
        }

    try:
        parsed = dtparser.parse(raw)
    except Exception:
        return None

    timezone_known = (
        parsed.utcoffset() is not None
    )

    if timezone_known:
        published_at = (
            parsed.astimezone(
                timezone.utc
            ).isoformat()
        )
    else:
        published_at = (
            parsed.isoformat()
        )

    return {
        "published_at": published_at,
        "raw_value": raw,
        "timezone_known": timezone_known,
        "precision": "datetime",
    }


def _result(
    *,
    status: str,
    normalized: Optional[
        Dict[str, Any]
    ] = None,
    source_type: str = "",
    source_key: str = "",
) -> Dict[str, Any]:
    normalized = (
        normalized
        if isinstance(
            normalized,
            dict,
        )
        else {}
    )

    return {
        "version": PUBLICATION_TIME_VERSION,
        "status": status,
        "published_at": str(
            normalized.get(
                "published_at"
            )
            or ""
        ).strip(),
        "raw_value": str(
            normalized.get(
                "raw_value"
            )
            or ""
        ).strip(),
        "timezone_known": bool(
            normalized.get(
                "timezone_known",
                False,
            )
        ),
        "precision": str(
            normalized.get(
                "precision"
            )
            or ""
        ).strip(),
        "source_type": str(
            source_type or ""
        ).strip(),
        "source_key": str(
            source_key or ""
        ).strip(),
    }


def _meta_rows(soup):
    rows = []

    for tag in soup.find_all("meta"):
        key = _clean(
            tag.get("property")
            or tag.get("name")
            or tag.get("itemprop")
            or ""
        ).lower()

        value = _clean(
            tag.get("content")
            or tag.get("value")
            or ""
        )

        if key and value:
            rows.append(
                (key, value)
            )

    return rows


def _json_ld_date_values(
    value: Any,
):
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                str(key).strip().lower()
                == "datepublished"
                and isinstance(
                    child,
                    (
                        str,
                        int,
                        float,
                    ),
                )
            ):
                cleaned = _clean(child)

                if cleaned:
                    yield cleaned

            yield from (
                _json_ld_date_values(
                    child
                )
            )

    elif isinstance(value, list):
        for child in value:
            yield from (
                _json_ld_date_values(
                    child
                )
            )


def extract_publication_time(
    html: str,
) -> Dict[str, Any]:
    raw_html = str(html or "")

    if not raw_html.strip():
        return _result(
            status="not_found"
        )

    soup = BeautifulSoup(
        raw_html,
        "lxml",
    )

    meta_rows = _meta_rows(soup)

    # Strongest explicit publication metadata first.
    for wanted_key in _EXPLICIT_META_KEYS:
        for key, value in meta_rows:
            if key != wanted_key:
                continue

            normalized = (
                normalize_publication_timestamp(
                    value
                )
            )

            if normalized is None:
                continue

            return _result(
                status="found",
                normalized=normalized,
                source_type="meta",
                source_key=key,
            )

    # Then structured NewsArticle/Article JSON-LD.
    for script in soup.find_all("script"):
        script_type = _clean(
            script.get("type") or ""
        ).lower()

        if (
            script_type
            != "application/ld+json"
        ):
            continue

        payload_text = str(
            script.string
            or script.get_text(
                " ",
                strip=True,
            )
            or ""
        ).strip()

        if not payload_text:
            continue

        try:
            payload = json.loads(
                payload_text
            )
        except Exception:
            continue

        for value in (
            _json_ld_date_values(
                payload
            )
        ):
            normalized = (
                normalize_publication_timestamp(
                    value
                )
            )

            if normalized is None:
                continue

            return _result(
                status="found",
                normalized=normalized,
                source_type="json_ld",
                source_key="datePublished",
            )

    # Generic date metadata is deliberately weaker.
    for wanted_key in _GENERIC_META_KEYS:
        for key, value in meta_rows:
            if key != wanted_key:
                continue

            normalized = (
                normalize_publication_timestamp(
                    value
                )
            )

            if normalized is None:
                continue

            return _result(
                status="found",
                normalized=normalized,
                source_type="meta",
                source_key=key,
            )

    return _result(
        status="not_found"
    )


def resolve_publication_time(
    html: str,
    *,
    provider_page_age: Any = "",
) -> Dict[str, Any]:
    html_result = extract_publication_time(
        html
    )

    if html_result["status"] == "found":
        return html_result

    provider_result = (
        normalize_publication_timestamp(
            provider_page_age
        )
    )

    if provider_result is not None:
        return _result(
            status="found",
            normalized=provider_result,
            source_type="provider",
            source_key="page_age",
        )

    return html_result
