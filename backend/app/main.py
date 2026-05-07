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
from urllib.parse import urlparse

import requests
import feedparser
from dateutil import parser as dtparser

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from google import genai
from app.routes.insights import router as insights_router


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
app = FastAPI(title="Sportabase API (RSS-first)", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(insights_router, prefix="/insights", tags=["insights"])


@app.get("/health")
def health():
    return {"ok": True, "version": "0.3.0"}


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
    reasons: List[str] = Field(default_factory=list)


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
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=WAL;")
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


_TAG_RE = re.compile(r"<[^>]+>")


def clean_html(s: str) -> str:
    s = s or ""
    s = ihtml.unescape(s)
    s = _TAG_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clamp(value: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(value))))


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def signal_hits(patterns: List[str], body: str) -> List[str]:
    """
    Safe phrase matching.

    Example:
    - matches "interest"
    - does NOT match "interesting"
    - matches "no official offer"
    """
    hits: List[str] = []

    for phrase in patterns:
        p = phrase.lower().strip()
        if not p:
            continue

        pattern = r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])"

        if re.search(pattern, body):
            hits.append(phrase)

    return hits


# -----------------------------
# scoring v3: nuanced component score
# -----------------------------
HEDGE_WORDS = [
    # soft uncertainty
    "could", "may", "might", "would", "should", "appears", "suggests",
    "likely", "unlikely", "expected", "set to", "in line to", "poised to",
    "on course to", "tipped to", "projected to", "forecast to",

    # reporting uncertainty
    "reportedly", "understood", "believed", "claimed", "claims", "allegedly",
    "said to be", "thought to be", "rumoured", "rumored", "rumour", "rumor",
    "according to reports", "reports suggest", "reports claim", "it is claimed",
    "it is believed", "it is understood", "it has been suggested",

    # transfer gossip language
    "linked", "interest", "interested", "monitoring", "keeping tabs",
    "eyeing", "plotting", "weighing up", "considering", "exploring",
    "readying", "preparing", "lining up", "targeting", "chasing",
    "tracking", "scouting", "admiring", "long-term admirer",
    "shortlist", "shortlisted", "on the radar", "made enquiries",
    "enquired", "approach", "potential approach", "possible move",
    "potential move", "summer move", "winter move", "shock move",

    # negotiation uncertainty
    "talks", "informal talks", "initial talks", "early talks",
    "preliminary talks", "conversations", "discussions", "contact",
    "representatives", "agent", "intermediaries", "open to",
    "willing to listen", "could listen", "may listen", "no agreement",
    "yet to agree", "far apart", "not advanced", "not close",
    "nothing advanced", "deal depends", "dependent on",

    # vague sourcing
    "sources", "insiders", "club sources", "people close to",
    "those close to", "sources close to", "unnamed source",
    "unnamed sources", "well-placed source", "well-placed sources",
    "senior source", "dressing-room source",

    # low-commitment phrases
    "potential", "possible", "possibility", "candidate", "option",
    "alternative", "backup option", "contingency", "fallback option",
    "one to watch", "situation to watch", "developing situation",
    "watch this space",
]


OFFICIAL_WORDS = [
    # strict official confirmation only — do NOT include plain "official"
    "officially confirmed",
    "officially announced",
    "confirmed by the club",
    "announced by the club",
    "club confirmed",
    "club announced",
    "league confirmed",
    "league announced",
    "fifa confirmed",
    "fifa announced",
    "uefa confirmed",
    "uefa announced",
    "premier league confirmed",
    "premier league announced",

    # formal statements
    "club statement",
    "official statement",
    "press release",
    "statement released",
    "statement from the club",
    "statement from fifa",
    "statement from uefa",
    "statement from the premier league",

    # official bodies / primary source attribution
    "according to the club",
    "according to fifa",
    "according to uefa",
    "according to the premier league",
    "according to the fa",
    "according to the governing body",
    "governing body confirmed",

    # completed transaction language
    "has signed",
    "have signed",
    "completed the signing",
    "completed the transfer",
    "has completed his move",
    "has completed her move",
    "contract signed",
    "new contract signed",
    "deal completed",
    "transfer completed",
    "registration completed",
    "medical completed",
    "announced the signing",
    "confirmed the signing",

    # official disciplinary / legal language
    "charged by",
    "sanctioned by",
    "banned by",
    "suspended by",
    "cleared by",
    "appeal rejected",
    "appeal upheld",
]


NEGATED_OFFICIAL_PATTERNS = [
    "no official offer",
    "no official bid",
    "no official approach",
    "no formal offer",
    "no concrete offer",
    "no official contact",
    "no formal contact",
    "no bid submitted",
    "no offer submitted",
    "no approach made",

    "nothing has been confirmed",
    "not confirmed",
    "has not been confirmed",
    "have not been confirmed",
    "yet to be confirmed",
    "still unconfirmed",
    "remains unconfirmed",
    "unverified",

    "no agreement has been reached",
    "no agreement reached",
    "yet to reach agreement",
    "agreement has not been reached",
    "terms have not been agreed",
    "deal has not been agreed",
    "no deal agreed",
    "not agreed a deal",
]


EVIDENCE_WORDS = [
    # attribution
    "said", "told", "according to", "reported by", "cited", "quoted",
    "confirmed by", "announced by", "revealed by", "published by",
    "released by", "stated", "wrote", "added", "explained",

    # hard evidence / documentation
    "statement", "press release", "documents", "records", "filing",
    "court filing", "court documents", "legal documents", "published report",
    "official report", "medical report", "injury report", "match report",
    "disciplinary report", "financial report",

    # numbers / data
    "data", "figures", "statistics", "stats", "metrics", "records show",
    "figures show", "data shows", "according to data", "according to figures",
    "percent", "percentage", "million", "billion",

    # interview / direct quote context
    "interview", "news conference", "press conference", "post-match interview",
    "pre-match press conference", "media briefing", "broadcast interview",
    "speaking to", "speaking after", "speaking before",

    # named-source reporting
    "club source", "league source", "team source", "coach said",
    "manager said", "player said", "agent said", "director said",
    "president said", "chief executive said", "sporting director said",
]


UNNAMED_SOURCE_PATTERNS = [
    "unnamed sources",
    "unnamed source",
    "anonymous source",
    "anonymous sources",
    "sources claim",
    "sources suggest",
    "sources believe",
    "sources indicate",
    "sources close to",
    "insiders claim",
    "insiders suggest",
    "insiders believe",
    "people close to",
    "those close to",
    "it is believed",
    "it is understood",
    "it is thought",
    "well-placed sources",
    "a source told",
    "a source claimed",
]


SEVERE_RUMOR_PATTERNS = [
    "unnamed sources",
    "anonymous sources",
    "unverified",
    "unconfirmed",
    "rumour mill",
    "rumor mill",
    "shock move",
    "mystery",
    "secret talks",
    "secret meeting",
    "behind closed doors",
    "bombshell",

    "nothing has been confirmed",
    "no agreement has been reached",
    "no agreement reached",
    "no official offer",
    "no official bid",
    "no official approach",
    "no formal offer",
    "no concrete offer",
    "no bid submitted",
    "no offer submitted",
    "no deal agreed",
    "terms have not been agreed",

    "deal could depend",
    "move could depend",
    "depends on several conditions",
    "could hinge on",
    "may hinge on",
    "might hinge on",
    "uncertain conditions",
]


IMPACT_WORDS = [
    # transfers/contracts
    "signed", "signing", "transfer", "deal", "contract", "extension",
    "release clause", "buyout clause", "loan", "permanent move",
    "free transfer", "medical", "registration", "deadline day",

    # injuries/availability
    "injury", "injured", "hamstring", "ankle", "knee", "concussion",
    "out injured", "ruled out", "setback", "fitness", "return date",
    "unavailable", "doubt", "misses", "miss out",

    # discipline/legal
    "suspended", "suspension", "ban", "banned", "charged", "investigation",
    "appeal", "sanction", "fine", "breach", "rules breach", "misconduct",
    "disciplinary", "cleared", "punished",

    # managerial/team decisions
    "sacked", "fired", "dismissed", "appointed", "resigned", "stepped down",
    "new manager", "head coach", "sporting director", "captaincy",
    "dropped", "benched", "recalled",

    # competition outcomes
    "won", "lost", "defeated", "beat", "draw", "final", "semi-final",
    "quarter-final", "title", "trophy", "champions league", "world cup",
    "premier league", "euros", "qualified", "qualification", "eliminated",
    "relegated", "promoted", "playoffs", "record", "milestone",

    # finance / governance
    "financial", "revenue", "profit", "loss", "valuation", "takeover",
    "ownership", "investment", "sponsorship", "broadcast deal",
]


OPINION_WORDS = [
    # obvious opinion labels
    "opinion", "column", "comment", "commentary", "cartoon", "cartoonist",
    "editorial", "viewpoint", "perspective", "essay",

    # analysis/reaction formats
    "analysis", "verdict", "reaction", "talking points", "what we learned",
    "things we learned", "player ratings", "ratings", "ranked",
    "ranking", "best and worst", "winners and losers", "takeaways",
    "grades", "report card",

    # subjective framing
    "i think", "i believe", "my view", "in my view", "for me",
    "we think", "we believe", "our view", "it feels like",
    "it seems like", "arguably", "perhaps", "maybe",

    # opinion-style titles
    "why", "how", "what the future holds", "welcome to",
    "the problem with", "the case for", "the case against",
    "needs to", "must", "should",

    # vibes/editorial language
    "naive", "parlance", "ridiculous", "absurd", "brilliant",
    "terrible", "disaster", "masterstroke", "genius", "embarrassing",
]


CLICKBAIT_WORDS = [
    "shock", "shocking", "stunning", "secret", "mystery", "bombshell",
    "huge twist", "twist", "you won't believe", "sensational",
    "crazy", "insane", "wild", "massive", "huge", "dramatic",
    "explosive", "jaw-dropping", "unbelievable", "surprise",
    "major surprise", "unexpected", "leaked", "exposed",
    "revealed", "brutal", "savage", "chaos",
]


def _source_reputation(url: str) -> tuple[int, str]:
    """
    Source reputation is not truth.
    It is just a domain-quality prior before reading the text.
    """

    domain = _domain_from_url(url)

    if not domain:
        return 7, "unknown source"

    official_domains = [
        "fifa.com",
        "uefa.com",
        "premierleague.com",
        "mlssoccer.com",
        "arsenal.com",
        "mancity.com",
        "manutd.com",
        "chelseafc.com",
        "liverpoolfc.com",
        "tottenhamhotspur.com",
        "realmadrid.com",
        "fcbarcelona.com",
        "nba.com",
        "nfl.com",
        "mlb.com",
        "nhl.com",
        "formula1.com",
        "fia.com",
    ]

    top_news_domains = [
        "bbc.co.uk",
        "bbc.com",
        "theguardian.com",
        "espn.com",
        "skysports.com",
        "reuters.com",
        "apnews.com",
        "nytimes.com",
        "washingtonpost.com",
        "espncricinfo.com",
        "cricbuzz.com",
        "cbssports.com",
        "sports.yahoo.com",
        "si.com",
    ]

    solid_specialist_domains = [
        "theathletic.com",
        "football.london",
        "goal.com",
        "transfermarkt.com",
        "autosport.com",
        "motorsport.com",
        "racer.com",
        "nbcsports.com",
        "bleacherreport.com",
    ]

    rumor_or_aggregator_domains = [
        "teamtalk.com",
        "football365.com",
        "caughtoffside.com",
        "yardbarker.com",
        "fichajes.net",
        "todofichajes.com",
        "90min.com",
        "sportsmole.co.uk",
        "givemesport.com",
    ]

    low_quality_domains = [
        "footballtransfers.com",
        "tribalfootball.com",
        "thehardtackle.com",
        "footballinsider247.com",
    ]

    if any(d in domain for d in official_domains):
        return 18, "official/primary source"

    if any(d in domain for d in top_news_domains):
        return 15, "major news/sports outlet"

    if any(d in domain for d in solid_specialist_domains):
        return 11, "specialist sports outlet"

    if any(d in domain for d in rumor_or_aggregator_domains):
        return 5, "rumor/aggregator source"

    if any(d in domain for d in low_quality_domains):
        return 4, "low-confidence rumor source"

    return 8, "unrated source"


def badge(score: int) -> str:
    if score < 20:
        return "Unverified Rumor"
    if score < 35:
        return "Speculative"
    if score < 50:
        return "Low Evidence"
    if score < 65:
        return "Developing"
    if score < 80:
        return "Substantial Signal"
    if score < 90:
        return "Strong Evidence"
    return "High Credibility"


def merit_score(title: str, text: str, url: str = "") -> Dict[str, Any]:
    """
    Nuanced credibility-style score.

    This is NOT fact-checking.
    It scores article quality signals:
    - source reputation
    - evidence quality
    - specificity/detail
    - language reliability
    - article type
    - corroboration
    - impact

    Goal:
    - avoid repeated same-score outputs
    - make every point come from visible signals
    - keep 90+ genuinely rare
    """

    body_original = clean_html(f"{title}\n{text}".strip())
    body = body_original.lower()

    word_count = max(len(body_original.split()), 1)
    nums = len(re.findall(r"\b\d+([.,]\d+)?\b", body_original))
    quotes = body_original.count('"') + body_original.count("“") + body_original.count("”")
    proper_nouns = len(re.findall(r"\b[A-Z][a-z]{2,}\b", body_original))

    hedge_hits = signal_hits(HEDGE_WORDS, body)
    official_hits = signal_hits(OFFICIAL_WORDS, body)
    negated_official_hits = signal_hits(NEGATED_OFFICIAL_PATTERNS, body)

    if negated_official_hits:
        official_hits = []

    evidence_hits = signal_hits(EVIDENCE_WORDS, body)
    unnamed_source_hits = signal_hits(UNNAMED_SOURCE_PATTERNS, body)
    severe_rumor_hits = signal_hits(SEVERE_RUMOR_PATTERNS, body)
    impact_hits = signal_hits(IMPACT_WORDS, body)
    opinion_hits = signal_hits(OPINION_WORDS, body)
    clickbait_hits = signal_hits(CLICKBAIT_WORDS, body)

    has_official = len(official_hits) > 0
    has_evidence = len(evidence_hits) > 0
    is_opinion = len(opinion_hits) > 0

    # -----------------------------
    # 1. Source reputation: /18
    # -----------------------------
    source_score, source_label = _source_reputation(url)

    # -----------------------------
    # 2. Evidence quality: /22
    # -----------------------------
    evidence_quality = 0.0

    if has_official:
        evidence_quality += 10

    evidence_quality += min(8, len(evidence_hits) * 2)
    evidence_quality += min(4, quotes * 2)

    if unnamed_source_hits and not has_official:
        evidence_quality -= min(6, len(unnamed_source_hits) * 3)

    evidence_quality = _clamp(evidence_quality, 0, 22)

    # -----------------------------
    # 3. Specificity/detail: /16
    # -----------------------------
    if word_count >= 350:
        length_score = 6
    elif word_count >= 240:
        length_score = 5
    elif word_count >= 150:
        length_score = 4
    elif word_count >= 90:
        length_score = 3
    elif word_count >= 60:
        length_score = 1
    else:
        length_score = 0

    number_score = min(6, nums * 1.4)
    entity_score = min(4, proper_nouns / 5)

    specificity = _clamp(length_score + number_score + entity_score, 0, 16)

    # -----------------------------
    # 4. Language reliability: /18
    # -----------------------------
    language_reliability = 18.0

    language_reliability -= min(10, len(hedge_hits) * 1.7)
    language_reliability -= min(6, len(severe_rumor_hits) * 2.6)
    language_reliability -= min(5, len(negated_official_hits) * 3)
    language_reliability -= min(4, len(clickbait_hits) * 1.8)

    if has_official:
        language_reliability += 2

    language_reliability = _clamp(language_reliability, 0, 18)

    # -----------------------------
    # 5. Article type: /8
    # -----------------------------
    article_type = 8.0
    article_type -= min(8, len(opinion_hits) * 2.5)
    article_type = _clamp(article_type, 0, 8)

    # -----------------------------
    # 6. Corroboration: /12
    # -----------------------------
    corroboration = 0.0

    if has_official:
        corroboration += 4

    corroboration += min(4, len(evidence_hits) * 0.9)
    corroboration += min(2, quotes)
    corroboration += min(2, nums // 2)

    if unnamed_source_hits and not has_official:
        corroboration -= 3

    corroboration = _clamp(corroboration, 0, 12)

    # -----------------------------
    # 7. Impact: /6
    # -----------------------------
    impact = _clamp(min(6, len(impact_hits) * 1.4), 0, 6)

    raw_total = (
        source_score
        + evidence_quality
        + specificity
        + language_reliability
        + article_type
        + corroboration
        + impact
    )

    # -----------------------------
    # Global penalties: small, not flattening caps
    # -----------------------------
    penalty = 0.0

    if word_count < 60:
        penalty += 8

    if not has_evidence and not has_official:
        penalty += 6

    if severe_rumor_hits and not has_official:
        penalty += min(12, len(severe_rumor_hits) * 3.5)

    if len(hedge_hits) >= 5 and not has_official:
        penalty += 5

    if is_opinion:
        penalty += min(10, len(opinion_hits) * 2.5)

    if len(clickbait_hits) >= 2 and not has_official:
        penalty += 4

    total = _clamp(raw_total - penalty, 0, 100)

    # -----------------------------
    # Soft ceilings
    # These prevent nonsense, but avoid making everything identical.
    # -----------------------------
    if not has_official and source_score <= 5 and len(hedge_hits) >= 3:
        total = min(total, 48)

    if severe_rumor_hits and not has_official and len(hedge_hits) >= 3:
        total = min(total, 34)

    if is_opinion and not has_official:
        total = min(total, 64)

    if not has_evidence and not has_official:
        total = min(total, 52)

    # 90+ should be rare and earned.
    if total >= 90:
        if not has_official or len(evidence_hits) < 2 or nums < 1 or word_count < 120:
            total = 89

    total = _clamp(total, 0, 100)

    reasons: List[str] = [
        f"Source reputation: {source_score}/18 ({source_label}).",
        f"Evidence quality: {evidence_quality}/22.",
        f"Specificity/detail: {specificity}/16.",
        f"Language reliability: {language_reliability}/18.",
        f"Corroboration: {corroboration}/12.",
    ]

    if hedge_hits:
        reasons.append(f"Hedge signals: {len(hedge_hits)} detected ({', '.join(hedge_hits[:4])}).")

    if severe_rumor_hits:
        reasons.append(f"Severe rumor signals: {', '.join(severe_rumor_hits[:3])}.")

    if negated_official_hits:
        reasons.append("Negated official language detected, such as no official offer or nothing confirmed.")

    if opinion_hits:
        reasons.append("Opinion/analysis style detected, reducing hard-news credibility.")

    if clickbait_hits:
        reasons.append(f"Clickbait-style language detected ({', '.join(clickbait_hits[:3])}).")

    if total >= 90:
        reasons.append("Meets strict high-credibility threshold.")
    elif total >= 80:
        reasons.append("Strong evidence, but below high-credibility threshold.")
    elif total < 35:
        reasons.append("Low source/evidence reliability pushes this into speculative territory.")

    return {
        "total": total,
        "badge": badge(total),
        "reasons": reasons[:9],
    }


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


def extractive_fallback(text: str, max_bullets: int = 3) -> List[str]:
    text = clean_html(text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    sents = re.split(r"(?<=[.!?])\s+", text)

    junk_patterns = [
        "for other uses",
        "this article is about",
        "disambiguation",
        "may refer to",
        "continue reading",
        "read more",
        "sign up",
        "subscribe",
        "newsletter",
        "advertisement",
        "cookies",
        "all rights reserved",
    ]

    def sent_score(s: str) -> float:
        lower = s.lower()
        nums = len(re.findall(r"\b\d+([.,]\d+)?\b", s))
        quotes = s.count('"') + s.count("“") + s.count("”")
        evidence = len(signal_hits(EVIDENCE_WORDS, lower))
        impact = len(signal_hits(IMPACT_WORDS, lower))
        official = len(signal_hits(OFFICIAL_WORDS, lower))
        length_bonus = min(len(s), 220) / 220.0

        return (
            nums * 2.0
            + quotes * 1.5
            + evidence * 2.0
            + impact * 1.2
            + official * 2.5
            + length_bonus
        )

    candidates = []
    seen = set()

    for s in sents:
        s = clean_html(s)
        s = re.sub(r"\s+", " ", s).strip()

        if len(s) < 45:
            continue

        lower = s.lower()

        if any(j in lower for j in junk_patterns):
            continue

        if lower in seen:
            continue

        seen.add(lower)
        candidates.append(s)

    if not candidates:
        candidates = [s.strip() for s in sents if len(s.strip()) >= 35]

    ranked = sorted(candidates, key=sent_score, reverse=True)

    out: List[str] = []
    for s in ranked:
        if len(s) > 230:
            s = s[:227].rstrip() + "..."
        out.append(s)

        if len(out) >= max_bullets:
            break

    return out


def gemini_tldr(title: str, text: str, max_bullets: int = 3) -> List[str]:
    text = clean_html(text)

    client = gemini_client()
    if client is None:
        return extractive_fallback(text, max_bullets=max_bullets)

    clipped = text[:8000]

    prompt = (
        "Return ONLY valid JSON. No markdown. No commentary.\n"
        f"Task: summarize the sports/news article into exactly {max_bullets} TL;DR bullets.\n\n"
        "Rules:\n"
        "- Each bullet must be one sentence.\n"
        "- Each bullet must be under 26 words.\n"
        "- Prioritize concrete facts: who, what, when, why it matters.\n"
        "- Remove site boilerplate, ads, newsletter text, captions, and navigation text.\n"
        "- Do not invent facts not present in the text.\n"
        "- Do not mention that this is an article.\n"
        "- Do not repeat the title as a bullet.\n"
        "- If the text is mostly opinion, summarize the claim as opinion, not fact.\n\n"
        'Output format: {"bullets": ["...", "...", "..."]}\n\n'
        f"Title: {title}\n\n"
        f"Text:\n{clipped}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = (resp.text or "").strip()

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]

        data = json.loads(raw)

        bullets = data.get("bullets", [])
        cleaned: List[str] = []

        for b in bullets:
            if not isinstance(b, str):
                continue

            b = clean_html(b)
            b = re.sub(r"\s+", " ", b).strip()

            if not b:
                continue

            words = b.split()
            if len(words) > 28:
                b = " ".join(words[:28]).rstrip(" ,;:") + "..."

            low = b.lower()
            if low not in [x.lower() for x in cleaned]:
                cleaned.append(b)

            if len(cleaned) >= max_bullets:
                break

        if cleaned:
            return cleaned[:max_bullets]

        return extractive_fallback(text, max_bullets=max_bullets)

    except Exception as e:
        print("gemini_tldr fallback:", type(e).__name__, str(e)[:160])
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


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    cleaned_text = clean_html(req.text)

    tldr = gemini_tldr(req.title, cleaned_text, max_bullets=req.max_bullets)
    score = merit_score(req.title, cleaned_text, req.url)

    return AnalyzeResponse(
        url=req.url,
        title=req.title,
        tldr=tldr,
        merit_score=int(score["total"]),
        badge=str(score["badge"]),
        reasons=score.get("reasons", []),
    )