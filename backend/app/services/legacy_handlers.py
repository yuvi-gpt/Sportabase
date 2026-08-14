from __future__ import annotations

import hashlib
import json

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from dateutil import parser as dtparser
from fastapi import HTTPException

from app.models.api import (
    ContentResolveRequest,
)


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


def load_sources_impl(
    *,
    SOURCES_PATH,
) -> List[Dict[str, str]]:
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


def ingest_impl(
    *,
    IngestResponse,
    clean_html,
    db_conn,
    detect_article_type,
    feedparser,
    gemini_tldr,
    load_sources,
    merit_score,
    parse_published,
    requests,
    stable_id,
):
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


def stories_impl(
    sport: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 30,
    *,
    Story,
    badge,
    db_conn,
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


def resolve_article_content_impl(
    normalized_url: str,
    *,
    extract_article_content,
    fetch_safe_article_html,
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


def resolve_content_impl(
    req: ContentResolveRequest,
    *,
    ContentResolveResponse,
    detect_content_source,
    resolve_article_content,
    resolve_youtube_content,
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
