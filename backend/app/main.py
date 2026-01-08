from __future__ import annotations

import os
import re
import json
import time
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import html as ihtml

import requests
import feedparser
from dateutil import parser as dtparser

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from google import genai


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


# -----------------------------
# app
# -----------------------------
app = FastAPI(title="Sportabase API (RSS-first)", version="0.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # keep false with "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


# -----------------------------
# models
# -----------------------------
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
    tldr: List[str] = []
    merit_score: int = 0
    badge: str = "Speculative"
    created_at: str


class AnalyzeRequest(BaseModel):
    # used by the extension (user is already viewing the page)
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
    reasons: List[str] = []



# -----------------------------
# db
# -----------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  sport TEXT NOT NULL,
  title TEXT NOT NULL,
  link TEXT NOT NULL,
  published TEXT,
  summary TEXT,
  tldr_json TEXT,
  merit_score INTEGER,
  badge TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at);
CREATE INDEX IF NOT EXISTS idx_stories_sport ON stories(sport);
CREATE INDEX IF NOT EXISTS idx_stories_source ON stories(source);
"""

def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=30,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000;")   # wait for locks
    conn.execute("PRAGMA journal_mode=WAL;")     # better concurrency
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = db_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

init_db()


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
            dt = dtparser.parse(val)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return None

def load_sources() -> List[Dict[str, str]]:
    if not SOURCES_PATH.exists():
        # if missing, create a minimal default
        SOURCES_PATH.write_text("[]", encoding="utf-8")
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))

_TAG_RE = re.compile(r"<[^>]+>")

def clean_html(s: str) -> str:
    s = s or ""
    s = ihtml.unescape(s)
    s = _TAG_RE.sub(" ", s)          # remove tags
    s = re.sub(r"\s+", " ", s).strip()
    return s


# -----------------------------
# scoring
# -----------------------------
HEDGE_WORDS = [
    "linked", "interest", "monitoring", "could", "reportedly", "talks",
    "close to", "understood", "sources", "believed", "expected", "set to"
]
OFFICIAL_WORDS = ["official", "club statement", "press release", "confirmed", "announced"]

def badge(score: int) -> str:
    if score <= 20: return "Speculative"
    if score <= 40: return "Low Evidence"
    if score <= 60: return "Emerging"
    if score <= 80: return "High Credibility"
    return "Confirmed"

def merit_score(title: str, text: str) -> Dict[str, Any]:
    body = f"{title}\n{text}".strip().lower()

    nums = len(re.findall(r"\b\d+([.,]\d+)?\b", body))
    quotes = body.count('"') + body.count("“") + body.count("”")

    hedging_hits = [w for w in HEDGE_WORDS if w in body]
    official_hits = [w for w in OFFICIAL_WORDS if w in body]

    hedging = len(hedging_hits) > 0
    has_official = len(official_hits) > 0

    factual_density = min(35, nums * 3 + min(12, quotes))
    evidence_quality = 28 if has_official else (12 - (6 if hedging else 0))

    # these are placeholders until you add cross-source clustering
    originality = 15
    relevance = 10
    impact = 10

    total = factual_density + evidence_quality + originality + relevance + impact
    total = max(0, min(100, int(total)))

    reasons: List[str] = []

    # evidence / language signals
    if has_official:
        reasons.append("Uses official/confirmed language (e.g., confirmed/announced).")
    if hedging and not has_official:
        reasons.append("Contains hedging/rumor language (e.g., reportedly/could/sources).")

    # density signals
    if nums >= 3:
        reasons.append("Includes multiple specific numbers/details (higher factual density).")
    elif nums == 0:
        reasons.append("Few concrete details (mostly narrative / low specificity).")

    if quotes >= 2:
        reasons.append("Includes quoted statements (adds some evidence context).")

    # outcome signal
    if total >= 80:
        reasons.append("Overall signals point to high credibility.")
    elif total <= 40:
        reasons.append("Overall signals point to low evidence / speculative content.")

    # keep it short + stable
    reasons = reasons[:4]

    return {"total": total, "badge": badge(total), "reasons": reasons}


# -----------------------------
# gemini tldr (rss snippet OR extension text → bullets)
# -----------------------------
_GEMINI_CLIENT = None
_GEMINI_LAST_INIT = 0.0

def gemini_client():
    global _GEMINI_CLIENT, _GEMINI_LAST_INIT
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None

    # lazy init + tiny cooldown so reload doesn't spam
    if _GEMINI_CLIENT is None or (time.time() - _GEMINI_LAST_INIT) > 60:
        _GEMINI_CLIENT = genai.Client(api_key=key)
        _GEMINI_LAST_INIT = time.time()
    return _GEMINI_CLIENT

def extractive_fallback(text: str, max_bullets: int = 3) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, seen = [], set()
    for s in sents:
        s = s.strip()
        if len(s) < 30:
            continue
        low = s.lower()
        if any(x in low for x in ["for other uses", "this article is about", "disambiguation", "may refer to"]):
            continue
        if low in seen:
            continue
        seen.add(low)
        if len(s) > 240:
            s = s[:237].rstrip() + "..."
        out.append(s)
        if len(out) >= max_bullets:
            break
    return out

def gemini_tldr(title: str, text: str, max_bullets: int = 3) -> List[str]:
    client = gemini_client()
    if client is None:
        return extractive_fallback(text, max_bullets=max_bullets)

    clipped = (text or "")[:6000]
    prompt = (
        "return ONLY valid json. no markdown.\n"
        f"task: write a {max_bullets}-bullet tldr.\n"
        "rules:\n"
        "- bullets must be short, factual, and not repetitive\n"
        "- do not invent facts\n"
        'output format: {"bullets": ["...","...","..."]}\n\n'
        f"title: {title}\n"
        f"text: {clipped}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = (resp.text or "").strip()

        # loose json extraction
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end+1]

        data = json.loads(raw)

        bullets = data.get("bullets", [])
        bullets = [b.strip() for b in bullets if isinstance(b, str) and b.strip()]
        return bullets[:max_bullets] if bullets else extractive_fallback(text, max_bullets=max_bullets)
    except Exception:
        return extractive_fallback(text, max_bullets=max_bullets)


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
                    headers={"User-Agent": "Sportabase/0.2 (+rss-first)"},
                )
                r.raise_for_status()
                feed = feedparser.parse(r.text)
            except Exception:
                continue

            entries = getattr(feed, "entries", [])[:40]
            for e in entries:
                link = getattr(e, "link", None)
                title = getattr(e, "title", None)
                if not link or not title:
                    continue

                fetched_items += 1
                sid = stable_id(str(link))

                exists = conn.execute("SELECT 1 FROM stories WHERE id = ?", (sid,)).fetchone()
                if exists:
                    skipped += 1
                    continue

                summary_html = getattr(e, "summary", "") or ""
                summary = clean_html(summary_html)

                published = parse_published(e)

                # rss-first: summarize snippet, not full article
                tldr = gemini_tldr(str(title), str(summary), max_bullets=3)

                score = merit_score(str(title), str(summary))
                conn.execute(
                    """
                    INSERT INTO stories (id, source, sport, title, link, published, summary, tldr_json, merit_score, badge, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sid, name, sport, str(title).strip(), str(link).strip(),
                        published, str(summary).strip(),
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


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    Extension endpoint:
    - user is already viewing the page (logged in if needed)
    - extension extracts readable text and sends it here
    - we return tldr + merit score
    - we DO NOT store req.text anywhere
    """
    tldr = gemini_tldr(req.title, req.text, max_bullets=req.max_bullets)
    score = merit_score(req.title, req.text)

    return AnalyzeResponse(
        url=req.url,
        title=req.title,
        tldr=tldr,
        merit_score=int(score["total"]),
        badge=str(score["badge"]),
        reasons=score.get("reasons", []),
    )

