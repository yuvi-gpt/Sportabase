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
MAX_ANALYZE_CHARS = int(os.getenv("SPORTABASE_MAX_ANALYZE_CHARS", "6000"))

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

    article_type: str = "generic_news"
    article_type_label: str = "Generic Sports News"
    article_subtype: str = "general"
    type_confidence: float = 0.0
    type_signals: List[str] = Field(default_factory=list)

    reasons: List[str] = Field(default_factory=list)
    debug: Dict[str, Any] = Field(default_factory=dict)

class VideoAnalyzeRequest(BaseModel):
    title: str = ""
    transcript: str
    url: str = ""


class VideoAnalyzeResponse(BaseModel):
    content_type: str = "unknown"
    claim: str
    evidence_used: List[str]
    logic_check: str
    hype_check: str
    evidence_score: int
    logic_score: int
    verdict: str
    debug: Dict[str, Any] = {}


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

def prepare_video_transcript(transcript: str) -> Dict[str, Any]:
    raw_transcript = clean_html(transcript)

    cleaned_transcript = re.sub(
        r"\[(music|applause|laughter)\]",
        " ",
        raw_transcript,
        flags=re.IGNORECASE,
    )
    cleaned_transcript = re.sub(
        r"\s+",
        " ",
        cleaned_transcript,
    ).strip()

    return {
        "raw_transcript": raw_transcript,
        "cleaned_transcript": cleaned_transcript,
        "transcript_confidence": None,
        "uncertain_corrections": [],
    }

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
# article type detection
# -----------------------------

ARTICLE_TYPE_LABELS = {
    "match_report": "Match Report / Result",
    "live_commentary": "Live Commentary",
    "official_announcement": "Official Announcement",
    "transfer_official": "Official Transfer",
    "transfer_report": "Transfer Report",
    "transfer_rumor": "Transfer Rumor",
    "transfer_roundup": "Transfer Roundup",
    "injury_confirmed": "Confirmed Injury Update",
    "injury_rumor": "Injury Rumor / Fitness Doubt",
    "lineup_confirmed": "Confirmed Lineup",
    "lineup_predicted": "Predicted Lineup",
    "squad_news": "Squad News",
    "manager_interview": "Manager Interview",
    "player_interview": "Player Interview",
    "agent_interview": "Agent Interview",
    "press_conference": "Press Conference",
    "discipline_legal": "Discipline / Legal",
    "managerial_news": "Managerial News",
    "contract_news": "Contract News",
    "fixture_schedule": "Fixture / Schedule / Draw",
    "tactical_analysis": "Tactical Analysis",
    "stats_data_report": "Stats / Data Report",
    "opinion_analysis": "Opinion / Column",
    "ownership_finance": "Ownership / Finance",
    "generic_news": "Generic Sports News",
}


def _has_scoreline(text: str) -> bool:
    patterns = [
        r"\b\d+\s*[-–]\s*\d+\b",          # 2-1, 1–0
        r"\b\d+\s+to\s+\d+\b",           # 2 to 1
        r"\bwon\s+\d+\s*[-–]\s*\d+\b",
        r"\blost\s+\d+\s*[-–]\s*\d+\b",
        r"\bdrew\s+\d+\s*[-–]\s*\d+\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _add_score(
    scores: Dict[str, float],
    signals: List[str],
    article_type: str,
    points: float,
    signal: str,
):
    scores[article_type] = scores.get(article_type, 0) + points
    if signal:
        signals.append(signal)


def detect_article_type(title: str, text: str, url: str = "") -> Dict[str, Any]:
    """
    Detects the sports article category and subtype.

    This does NOT score credibility.
    It only determines what kind of article this is:
    match report, transfer rumor, injury update, lineup news, interview, etc.
    """

    full_original = clean_html(f"{title}\n{text}".strip())
    full = full_original.lower()
    title_l = title.lower()
    domain = _domain_from_url(url)

    scores: Dict[str, float] = {k: 0.0 for k in ARTICLE_TYPE_LABELS}
    scores["generic_news"] = 1.0

    signals: List[str] = []

    # -----------------------------
    # common signal groups
    # -----------------------------
    scoreline_detected = _has_scoreline(full_original)

    match_result_terms = signal_hits([
        "beat", "defeated", "won", "lost", "drew", "draw",
        "full-time", "full time", "ft", "final score",
        "aggregate", "on aggregate", "sent", "sends",
        "advanced", "progressed", "reached the final",
        "knocked out", "eliminated", "came from behind",
        "late winner", "equaliser", "equalizer",
    ], full)

    competition_terms = signal_hits([
        "premier league", "champions league", "europa league",
        "conference league", "world cup", "euros", "fa cup",
        "carabao cup", "mls", "nba", "nfl", "mlb", "nhl",
        "ipl", "test match", "odi", "t20", "grand prix",
        "formula 1", "semifinal", "semi-final",
        "quarterfinal", "quarter-final", "final",
        "group stage", "league phase", "playoff", "playoffs",
    ], full)

    transfer_terms = signal_hits([
        "transfer", "signing", "signed", "bid", "offer",
        "contract", "release clause", "buyout clause", "loan",
        "permanent move", "medical", "personal terms", "fee",
        "move", "join", "joined", "agreement", "deal",
        "free agent", "free transfer",
    ], full)

    injury_terms = signal_hits([
        "injury", "injured", "hamstring", "ankle", "knee",
        "calf", "groin", "concussion", "fitness", "ruled out",
        "doubt", "scan", "medical assessment", "return to training",
        "setback", "unavailable", "misses", "miss out",
        "recovery", "rehab", "surgery", "operation",
    ], full)

    lineup_terms = signal_hits([
        "lineup", "line-up", "starting xi", "xi",
        "team news", "predicted lineup", "predicted xi",
        "confirmed lineup", "confirmed xi", "starts",
        "bench", "substitutes", "squad", "rotation",
        "rested", "available", "starting eleven",
    ], full)

    interview_terms = signal_hits([
        "interview", "said", "told", "speaking to",
        "speaking after", "speaking before", "quote", "quotes",
        "admitted", "insisted", "explained", "added",
        "revealed", "claimed", "responded",
    ], full)

    press_terms = signal_hits([
        "press conference", "news conference", "media briefing",
        "pre-match press conference", "post-match press conference",
        "manager said", "head coach said", "coach said",
        "speaking at his press conference",
    ], full)

    discipline_terms = signal_hits([
        "charged", "charge", "suspended", "suspension",
        "ban", "banned", "investigation", "investigating",
        "appeal", "sanction", "fine", "misconduct",
        "breach", "court", "legal", "lawsuit",
        "cleared", "disciplinary", "rules breach",
    ], full)

    managerial_terms = signal_hits([
        "sacked", "fired", "dismissed", "appointed",
        "resigned", "stepped down", "manager", "head coach",
        "new manager", "new head coach", "sporting director",
        "under pressure", "shortlist", "replacement",
    ], full)

    contract_terms = signal_hits([
        "contract", "new contract", "extension", "contract extension",
        "wage", "salary", "release clause", "buyout clause",
        "expires", "expiry", "renewal", "talks over a new deal",
        "long-term deal", "agreed terms",
    ], full)

    fixture_terms = signal_hits([
        "fixture", "fixtures", "schedule", "draw", "group",
        "venue", "kick-off", "kickoff", "date confirmed",
        "match date", "tournament draw", "world cup draw",
        "fixtures released", "rescheduled", "postponed",
        "delayed", "calendar",
    ], full)

    tactical_terms = signal_hits([
        "analysis", "tactical", "tactics", "breakdown",
        "explained", "deep dive", "shape", "formation",
        "pressing", "low block", "high line", "transition",
        "counterattack", "build-up", "build up", "positional",
    ], full)

    stats_terms = signal_hits([
        "stats", "statistics", "data", "numbers", "metrics",
        "xg", "expected goals", "possession", "shots",
        "shots on target", "chances created", "pass completion",
        "ranking", "record", "table", "model", "percent",
        "percentage", "per 90",
    ], full)

    opinion_terms = signal_hits(OPINION_WORDS, full)
    hedge_terms = signal_hits(HEDGE_WORDS, full)
    official_terms = signal_hits(OFFICIAL_WORDS, full)
    severe_rumor_terms = signal_hits(SEVERE_RUMOR_PATTERNS, full)
    negated_official_terms = signal_hits(NEGATED_OFFICIAL_PATTERNS, full)

    ownership_terms = signal_hits([
        "ownership", "owner", "takeover", "sale", "sold",
        "investment", "investor", "valuation", "revenue",
        "profit", "loss", "financial", "psr", "ffp",
        "accounts", "debt", "minority stake", "majority stake",
        "sponsorship", "broadcast deal",
    ], full)

    official_domain = domain and any(d in domain for d in [
        "fifa.com", "uefa.com", "premierleague.com",
        "mlssoccer.com", "arsenal.com", "mancity.com",
        "manutd.com", "chelseafc.com", "liverpoolfc.com",
        "tottenhamhotspur.com", "realmadrid.com",
        "fcbarcelona.com", "nba.com", "nfl.com",
        "mlb.com", "nhl.com", "formula1.com", "fia.com",
    ])

        # -----------------------------
    # headline-first intent layer
    # -----------------------------
    # Headlines are usually the clearest clue for article type.
    # This keeps obvious transfer, injury, lineup, match, and opinion pages
    # from falling back to Generic Sports News.

    headline_rules = [
        (
            "transfer_rumor",
            [
                "transfer rumor", "transfer rumours", "transfer rumors",
                "transfer news", "transfer latest", "transfer updates",
                "transfer live", "summer transfer", "winter transfer",
                "linked with", "linked to", "eyeing", "interested in",
                "monitoring", "targeting", "set sights on",
            ],
            18,
            "headline frames this as transfer coverage",
        ),

        (
            "transfer_roundup",
            [
                "transfer window",
                "summer transfer window",
                "winter transfer window",
                "transfer grades",
                "transfer window grades",
                "grading big signings",
                "big signings",
                "transfer roundup",
                "transfer round-up",
                "latest transfer news",
                "transfer news and rumors",
            ],
            22,
            "headline frames this as transfer roundup/window coverage",
        ),

        (
            "transfer_official",
            [
                "completed signing", "complete signing",
                "completed transfer", "complete transfer",
                "announced signing", "announce signing",
                "has signed", "have signed", "signs for", "joins from",                "sign",
                "signs",
                "signed",
                "signing",
                "big-money transfer",
            ],
            16,
            "headline suggests a completed transfer",
        ),
        (
            "injury_confirmed",
            [
                "injury update", "injury news", "ruled out",
                "will miss", "set to miss", "out injured",
                "return to training", "fitness update", "medical update",
            ],
            16,
            "headline frames this as an injury update",
        ),
        (
            "injury_rumor",
            [
                "injury doubt", "fitness doubt", "doubtful for",
                "could miss", "may miss", "race to be fit",
            ],
            14,
            "headline frames this as an injury or fitness doubt",
        ),
        (
            "lineup_confirmed",
            [
                "confirmed lineup", "confirmed line-up", "confirmed xi",
                "lineups confirmed", "starting lineup announced",
            ],
            18,
            "headline frames this as confirmed lineup news",
        ),
        (
            "lineup_predicted",
            [
                "predicted lineup", "predicted line-up", "predicted xi",
                "expected xi", "possible lineup", "possible line-up",
                "predicted team",
            ],
            16,
            "headline frames this as predicted lineup news",
        ),
        (
            "match_report",
            [
                "match report", "final score", "full-time", "full time",
                "highlights", "match recap", "game recap",
                "report and highlights",
            ],
            14,
            "headline frames this as match coverage",
        ),
        (
            "live_commentary",
            [
                "live updates", "live blog", "live commentary",
                "latest updates", "live score", "as it happened",
            ],
            18,
            "headline frames this as live coverage",
        ),
        (
            "fixture_schedule",
            [
                "fixtures", "schedule", "draw", "kick-off time",
                "kickoff time", "date confirmed", "match date",
                "rescheduled", "postponed",
            ],
            14,
            "headline frames this as fixture or schedule news",
        ),
        (
            "managerial_news",
            [
                "sacked", "fired", "dismissed", "appointed",
                "resigned", "stepped down", "new manager",
                "new head coach", "under pressure", "replacement",
            ],
            15,
            "headline frames this as manager or coach news",
        ),
        (
            "contract_news",
            [
                "contract extension", "new contract", "contract talks",
                "release clause", "buyout clause", "agrees deal",
                "new deal", "set to extend",
            ],
            14,
            "headline frames this as contract news",
        ),
        (
            "discipline_legal",
            [
                "suspended", "suspension", "ban", "banned", "charged",
                "investigation", "appeal", "sanction", "fine",
                "misconduct", "lawsuit", "disciplinary",
            ],
            15,
            "headline frames this as discipline or legal news",
        ),
        (
            "stats_data_report",
            [
                "stats", "statistics", "data", "numbers behind",
                "ranking", "ranked", "record", "xg",
                "expected goals", "analytics",
            ],
            13,
            "headline frames this as stats or data coverage",
        ),
        (
            "tactical_analysis",
            [
                "tactical analysis", "tactics", "tactical breakdown",
                "deep dive",
            ],
            13,
            "headline frames this as tactical coverage",
        ),
        (
            "opinion_analysis",
            [
                "opinion", "column", "verdict", "what we learned",
                "winners and losers", "talking points", "player ratings",
                "ratings", "takeaways",
            ],
            15,
            "headline frames this as opinion or column coverage",
        ),
        (
            "ownership_finance",
            [
                "takeover", "ownership", "owner", "investment",
                "valuation", "revenue", "profit", "loss",
                "financial", "accounts", "sponsorship",
            ],
            15,
            "headline frames this as ownership or finance news",
        ),
        (
            "official_announcement",
            [
                "official statement", "club statement", "press release",
                "club confirms", "league confirms", "announced by the club",
                "statement released",
            ],
            18,
            "headline frames this as an official announcement",
        ),
    ]

    for article_type_name, phrases, points, signal in headline_rules:
        if signal_hits(phrases, title_l):
            _add_score(scores, signals, article_type_name, points, signal)

    # -----------------------------
    # match report / live commentary
    # -----------------------------
    if scoreline_detected:
        _add_score(scores, signals, "match_report", 6, "scoreline detected")

    if match_result_terms:
        _add_score(scores, signals, "match_report", min(7, len(match_result_terms) * 1.6), "match-result language detected")

    if competition_terms:
        _add_score(scores, signals, "match_report", min(4, len(competition_terms)), "competition/stage language detected")

    if "live" in title_l or "latest updates" in title_l or "commentary" in title_l or "as it happened" in title_l:
        _add_score(scores, signals, "live_commentary", 8, "live commentary framing detected")

    if scoreline_detected and ("live" in title_l or "commentary" in title_l):
        _add_score(scores, signals, "live_commentary", 4, "live article includes scoreline/result context")

    # -----------------------------
    # official announcement
    # -----------------------------
    if official_terms:
        _add_score(scores, signals, "official_announcement", min(9, len(official_terms) * 2.2), "official/confirmed language detected")

    if official_domain:
        _add_score(scores, signals, "official_announcement", 6, "official/primary source domain detected")

    # -----------------------------
    # transfers
    # -----------------------------
    if transfer_terms:
        _add_score(scores, signals, "transfer_report", min(7, len(transfer_terms) * 1.2), "transfer/contract language detected")

    if transfer_terms and official_terms and not negated_official_terms:
        _add_score(scores, signals, "transfer_official", 10, "official transfer confirmation detected")

    if transfer_terms and hedge_terms:
        _add_score(scores, signals, "transfer_rumor", min(9, len(hedge_terms) * 1.25), "transfer rumor/hedging language detected")

    if severe_rumor_terms:
        _add_score(scores, signals, "transfer_rumor", min(8, len(severe_rumor_terms) * 2.2), "severe rumor language detected")

    if negated_official_terms and transfer_terms:
        _add_score(scores, signals, "transfer_rumor", 5, "lack-of-confirmation phrase detected")

    # -----------------------------
    # injury
    # -----------------------------
    if injury_terms:
        if official_terms or press_terms:
            _add_score(scores, signals, "injury_confirmed", min(10, len(injury_terms) * 1.6 + 3), "injury update tied to official/manager source")
        else:
            _add_score(scores, signals, "injury_rumor", min(8, len(injury_terms) * 1.4), "injury/availability language detected")

    if injury_terms and hedge_terms and not official_terms:
        _add_score(scores, signals, "injury_rumor", 5, "injury uncertainty language detected")

    # -----------------------------
    # lineup / squad
    # -----------------------------
    if "confirmed lineup" in full or "confirmed xi" in full or "starting lineup announced" in full:
        _add_score(scores, signals, "lineup_confirmed", 11, "confirmed lineup framing detected")

    if "predicted lineup" in full or "predicted xi" in full or "expected xi" in full:
        _add_score(scores, signals, "lineup_predicted", 10, "predicted lineup framing detected")

    if lineup_terms:
        _add_score(scores, signals, "squad_news", min(7, len(lineup_terms) * 1.2), "lineup/squad language detected")

    # -----------------------------
    # interviews / press conference
    # -----------------------------
    if press_terms:
        _add_score(scores, signals, "press_conference", min(10, len(press_terms) * 2.0), "press conference language detected")

    if interview_terms:
        _add_score(scores, signals, "manager_interview", min(5, len(interview_terms) * 0.8), "quote/interview language detected")

    if any(x in full for x in ["manager said", "head coach said", "coach said", "arteta said", "guardiola said", "slot said"]):
        _add_score(scores, signals, "manager_interview", 5, "manager/head coach quote detected")

    if any(x in full for x in ["player said", "captain said", "forward said", "midfielder said", "defender said", "goalkeeper said"]):
        _add_score(scores, signals, "player_interview", 6, "player quote detected")

    if any(x in full for x in ["agent said", "representative said", "his agent", "her agent"]):
        _add_score(scores, signals, "agent_interview", 6, "agent/representative quote detected")

    # -----------------------------
    # discipline / legal
    # -----------------------------
    if discipline_terms:
        _add_score(scores, signals, "discipline_legal", min(12, len(discipline_terms) * 1.9), "discipline/legal language detected")

    # -----------------------------
    # managerial news
    # -----------------------------
    if managerial_terms:
        _add_score(scores, signals, "managerial_news", min(10, len(managerial_terms) * 1.5), "managerial/coach news language detected")

    # -----------------------------
    # contract news
    # -----------------------------
    if contract_terms:
        _add_score(scores, signals, "contract_news", min(9, len(contract_terms) * 1.4), "contract/extension language detected")

    # -----------------------------
    # fixtures / schedule / draw
    # -----------------------------
    if fixture_terms:
        _add_score(scores, signals, "fixture_schedule", min(11, len(fixture_terms) * 1.7), "fixture/schedule/draw language detected")

    # -----------------------------
    # tactical / stats / opinion
    # -----------------------------
    if tactical_terms:
        _add_score(scores, signals, "tactical_analysis", min(10, len(tactical_terms) * 1.5), "tactical/analysis language detected")

    if stats_terms:
        _add_score(scores, signals, "stats_data_report", min(10, len(stats_terms) * 1.5), "stats/data language detected")

    if opinion_terms:
        _add_score(scores, signals, "opinion_analysis", min(12, len(opinion_terms) * 1.8), "opinion/analysis framing detected")

    if any(x in title_l for x in ["opinion", "column", "ratings", "ranked", "why", "what we learned"]):
        _add_score(scores, signals, "opinion_analysis", 5, "opinion-style title framing detected")

    # -----------------------------
    # ownership / finance
    # -----------------------------
    if ownership_terms:
        _add_score(scores, signals, "ownership_finance", min(11, len(ownership_terms) * 1.6), "ownership/finance language detected")

    # -----------------------------
    # tie-break nudges
    # -----------------------------
    # If match result is obvious, prevent generic interview words like "said" from stealing the type.
    if scoreline_detected and match_result_terms:
        scores["match_report"] += 3

    # If transfer terms + rumor terms exist, make rumor more likely than generic transfer report.
    if transfer_terms and hedge_terms and not official_terms:
        scores["transfer_rumor"] += 3

    # If official transfer is clear, suppress rumor interpretation.
    if scores["transfer_official"] >= 10:
        scores["transfer_rumor"] = max(0, scores["transfer_rumor"] - 6)

    # Confirmed lineup should outrank generic squad news.
    if scores["lineup_confirmed"] >= 8:
        scores["squad_news"] = max(0, scores["squad_news"] - 4)

    # Predicted lineup should outrank generic squad news.
    if scores["lineup_predicted"] >= 8:
        scores["squad_news"] = max(0, scores["squad_news"] - 3)

        # -----------------------------
    # classifier guardrails
    # -----------------------------
    # These stop broad words like "analysis", "reaction", or "confirmed"
    # from overpowering clearer article-type signals.

    hard_news_types = [
        "transfer_official",
        "transfer_report",
        "transfer_rumor",
        "injury_confirmed",
        "injury_rumor",
        "lineup_confirmed",
        "lineup_predicted",
        "squad_news",
        "match_report",
        "live_commentary",
        "fixture_schedule",
        "discipline_legal",
        "managerial_news",
        "contract_news",
        "ownership_finance",
    ]

    hard_news_top = max(scores.get(t, 0) for t in hard_news_types)

    transfer_roundup_title = any(x in title_l for x in [
        "transfer rumor",
        "transfer rumours",
        "transfer rumors",
        "transfer news",
        "transfer latest",
        "transfer updates",
        "transfer live",
        "summer transfer",
        "winter transfer",
    ])

    completed_transfer_title = any(x in title_l for x in [
        "complete signing",
        "completed signing",
        "complete transfer",
        "completed transfer",
        "announce signing",
        "announced signing",
        "signs for",
        "has signed",
        "have signed",
        "joins from",
    ])

    transfer_headline_title = any(x in title_l for x in [
        "transfer",
        "sign",
        "signs",
        "signed",
        "signing",
        "joins",
        "joined",
        "loan",
        "move",
    ])

    explicit_match_title = any(x in title_l for x in [
        "match report",
        "final score",
        "full-time",
        "full time",
        "highlights",
        "match recap",
        "game recap",
        "live updates",
        "live commentary",
    ])

    # If the headline is clearly about a transfer/signing, do not let old match-result
    # context inside the article body steal the category.
    if transfer_headline_title and not explicit_match_title:
        strongest_transfer_score = max(
            scores.get("transfer_official", 0),
            scores.get("transfer_report", 0),
            scores.get("transfer_rumor", 0),
        )

        if strongest_transfer_score >= 8:
            scores["match_report"] = min(
                scores.get("match_report", 0),
                max(0, strongest_transfer_score - 2),
            )
            scores["live_commentary"] = min(
                scores.get("live_commentary", 0),
                max(0, strongest_transfer_score - 3),
            )

    # Transfer roundup pages should not become Official Transfer unless the headline is clearly completed/official.
    if transfer_roundup_title and not completed_transfer_title and not official_domain:
        scores["transfer_official"] = min(
            scores.get("transfer_official", 0),
            max(0, scores.get("transfer_rumor", 0) - 3),
        )

    explicit_tactical_title = any(x in title_l for x in [
        "tactical analysis",
        "tactical breakdown",
        "tactics",
        "deep dive",
    ])

    explicit_opinion_title = any(x in title_l for x in [
        "opinion",
        "column",
        "verdict",
        "what we learned",
        "winners and losers",
        "talking points",
        "player ratings",
        "ratings",
        "takeaways",
    ])

    explicit_stats_title = any(x in title_l for x in [
        "stats",
        "statistics",
        "data",
        "numbers behind",
        "ranking",
        "ranked",
        "record",
        "xg",
        "expected goals",
        "analytics",
    ])

    # Analysis/opinion/stats should not steal obvious hard-news pages unless the headline clearly says so.
    if hard_news_top >= 12:
        if not explicit_tactical_title:
            scores["tactical_analysis"] = min(scores.get("tactical_analysis", 0), 8)

        if not explicit_opinion_title:
            scores["opinion_analysis"] = min(scores.get("opinion_analysis", 0), 8)

        if not explicit_stats_title:
            scores["stats_data_report"] = min(scores.get("stats_data_report", 0), 9)

    # Live pages should stay live pages instead of becoming normal match reports.
    if scores.get("live_commentary", 0) >= 14:
        scores["match_report"] = min(
            scores.get("match_report", 0),
            max(0, scores.get("live_commentary", 0) - 2),
        )

    # Confirmed lineup should beat predicted lineup when both are detected.
    if scores.get("lineup_confirmed", 0) >= 12:
        scores["lineup_predicted"] = max(0, scores.get("lineup_predicted", 0) - 6)

    # Generic Sports News should only win when nothing meaningful is detected.
    best_non_generic_score = max(
        score for article_type, score in scores.items()
        if article_type != "generic_news"
    )

    if best_non_generic_score >= 7:
        scores["generic_news"] = 0

    # -----------------------------
    # choose primary type
    # -----------------------------
    primary_type = max(scores, key=scores.get)
    top_score = scores[primary_type]

    if top_score <= 2:
        primary_type = "generic_news"
        top_score = scores["generic_news"]

    # -----------------------------
    # subtype
    # -----------------------------
    subtype = "general"

    if primary_type == "match_report":
        if "aggregate" in full or "on aggregate" in full:
            subtype = "aggregate_result"
        elif "final" in full or "semi-final" in full or "semifinal" in full:
            subtype = "knockout_result"
        elif "preview" in full or "prediction" in full:
            subtype = "match_preview"
        else:
            subtype = "final_score"

    elif primary_type == "live_commentary":
        subtype = "live_updates"

    elif primary_type == "official_announcement":
        subtype = "primary_source_statement"

    elif primary_type == "transfer_official":
        subtype = "confirmed_transfer"

    elif primary_type == "transfer_report":
        if "fee" in full or "personal terms" in full or "medical" in full:
            subtype = "advanced_transfer_report"
        else:
            subtype = "reported_interest"

    elif primary_type == "transfer_roundup":
        if "grade" in full or "grading" in full:
            subtype = "transfer_window_grades"
        elif "window" in full:
            subtype = "transfer_window_roundup"
        else:
            subtype = "transfer_roundup"

    elif primary_type == "transfer_rumor":
        subtype = "unconfirmed_transfer_claim"

    elif primary_type == "injury_confirmed":
        if any(x in full for x in ["ruled out", "will miss", "out injured"]):
            subtype = "confirmed_absence"
        elif "return to training" in full:
            subtype = "return_to_training"
        else:
            subtype = "medical_update"

    elif primary_type == "injury_rumor":
        subtype = "fitness_doubt"

    elif primary_type == "lineup_confirmed":
        subtype = "confirmed_lineup"

    elif primary_type == "lineup_predicted":
        subtype = "predicted_lineup"

    elif primary_type == "squad_news":
        subtype = "availability_update"

    elif primary_type == "manager_interview":
        subtype = "manager_quotes"

    elif primary_type == "player_interview":
        subtype = "player_quotes"

    elif primary_type == "agent_interview":
        subtype = "agent_quotes"

    elif primary_type == "press_conference":
        subtype = "manager_media_comments"

    elif primary_type == "discipline_legal":
        if "investigation" in full or "investigating" in full:
            subtype = "investigation"
        elif "suspended" in full or "ban" in full or "banned" in full:
            subtype = "suspension_ban"
        elif "court" in full or "legal" in full or "lawsuit" in full:
            subtype = "legal_case"
        else:
            subtype = "disciplinary_case"

    elif primary_type == "managerial_news":
        if "sacked" in full or "fired" in full or "dismissed" in full:
            subtype = "manager_sacking"
        elif "appointed" in full or "new manager" in full or "new head coach" in full:
            subtype = "manager_appointment"
        else:
            subtype = "manager_pressure"

    elif primary_type == "contract_news":
        if "extension" in full or "new contract" in full:
            subtype = "contract_extension"
        elif "release clause" in full or "buyout clause" in full:
            subtype = "release_clause"
        else:
            subtype = "contract_talks"

    elif primary_type == "fixture_schedule":
        if "draw" in full:
            subtype = "tournament_draw"
        elif "postponed" in full or "rescheduled" in full:
            subtype = "fixture_change"
        else:
            subtype = "schedule_update"

    elif primary_type == "tactical_analysis":
        subtype = "tactical_breakdown"

    elif primary_type == "stats_data_report":
        subtype = "data_report"

    elif primary_type == "opinion_analysis":
        if "ratings" in full or "player ratings" in full:
            subtype = "player_ratings"
        elif "ranked" in full or "ranking" in full:
            subtype = "ranking"
        else:
            subtype = "opinion_or_column"

    elif primary_type == "ownership_finance":
        if "takeover" in full or "ownership" in full:
            subtype = "ownership_update"
        elif "revenue" in full or "profit" in full or "loss" in full:
            subtype = "financial_report"
        else:
            subtype = "business_update"

    confidence = min(0.98, max(0.15, top_score / 14))

    cleaned_signals = []
    seen = set()
    for s in signals:
        if s not in seen:
            seen.add(s)
            cleaned_signals.append(s)

    return {
        "primary_type": primary_type,
        "label": ARTICLE_TYPE_LABELS.get(primary_type, "Generic Sports News"),
        "subtype": subtype,
        "confidence": round(confidence, 2),
        "signals": cleaned_signals[:12],
        "raw_type_scores": scores,
    }

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


def merit_score(
    title: str,
    text: str,
    url: str = "",
    type_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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

    if type_info is None:
        type_info = detect_article_type(title, text, url)

    detected_type = str(type_info.get("primary_type", "generic_news"))
    detected_subtype = str(type_info.get("subtype", "general"))
    type_signals = type_info.get("signals", [])

    type_signal_text = " ".join(type_signals).lower()

    has_official = len(official_hits) > 0
    has_evidence = len(evidence_hits) > 0
    is_opinion = len(opinion_hits) > 0

    is_match_result_type = detected_type in ["match_report", "live_commentary"]
    is_transfer_type = detected_type in ["transfer_report", "transfer_rumor", "transfer_official"]
    is_injury_type = detected_type in ["injury_confirmed", "injury_rumor"]
    is_lineup_type = detected_type in ["lineup_confirmed", "lineup_predicted", "squad_news"]
    is_interview_type = detected_type in ["manager_interview", "player_interview", "agent_interview", "press_conference"]
    is_official_type = detected_type in ["official_announcement", "transfer_official", "lineup_confirmed"]

    event_evidence = 0

    if is_match_result_type:
        if "scoreline detected" in type_signal_text:
            event_evidence += 8
        if "match-result language detected" in type_signal_text:
            event_evidence += 6
        if "competition/stage language detected" in type_signal_text:
            event_evidence += 4
        if detected_subtype in ["aggregate_result", "knockout_result", "final_score"]:
            event_evidence += 3

    if is_injury_type:
        if detected_type == "injury_confirmed":
            event_evidence += 8
        elif detected_type == "injury_rumor":
            event_evidence += 3

    if is_lineup_type:
        if detected_type == "lineup_confirmed":
            event_evidence += 10
        elif detected_type == "lineup_predicted":
            event_evidence += 3
        else:
            event_evidence += 5

    if is_interview_type:
        event_evidence += 6
    if is_official_type:
        event_evidence += 10

    event_evidence = min(18, event_evidence)

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

    # Traditional article evidence: quotes, attribution, statements.
    evidence_quality += min(8, len(evidence_hits) * 2)
    evidence_quality += min(4, quotes * 2)

    # Sports-specific event evidence.
    # A match scoreline/result is evidence even if the article does not say "according to".
    if event_evidence:
        evidence_quality += min(12, event_evidence)

    if unnamed_source_hits and not has_official and not is_match_result_type:
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

    # Match reports get corroboration from structured event facts:
    # scoreline, competition, final/aggregate language, named teams.
    if is_match_result_type:
        corroboration += min(6, event_evidence / 3)

    if is_official_type:
        corroboration += 4

    if unnamed_source_hits and not has_official and not is_match_result_type:
        corroboration -= 3

    corroboration = _clamp(corroboration, 0, 12)

    # -----------------------------
    # 7. Impact: /6
    # -----------------------------
    impact = _clamp(min(6, len(impact_hits) * 1.4), 0, 6)

    # Article-type fit rewards articles that strongly match a recognizable sports-news category.
    type_fit = 0

    if is_match_result_type:
        type_fit = min(12, 5 + event_evidence / 2)
    elif detected_type == "official_announcement":
        type_fit = 12
    elif detected_type == "transfer_official":
        type_fit = 12
    elif detected_type == "transfer_report":
        type_fit = 7
    elif detected_type == "transfer_rumor":
        type_fit = 3
    elif detected_type == "injury_confirmed":
        type_fit = 10
    elif detected_type == "injury_rumor":
        type_fit = 4
    elif detected_type == "lineup_confirmed":
        type_fit = 10
    elif detected_type == "lineup_predicted":
        type_fit = 4
    elif is_interview_type:
        type_fit = 8
    elif detected_type == "discipline_legal":
        type_fit = 9
    elif detected_type == "fixture_schedule":
        type_fit = 9
    elif detected_type == "stats_data_report":
        type_fit = 8
    elif detected_type == "tactical_analysis":
        type_fit = 6
    elif detected_type == "opinion_analysis":
        type_fit = 3
    else:
        type_fit = 2

    type_fit = _clamp(type_fit, 0, 12)

    raw_total = (
        source_score
        + evidence_quality
        + specificity
        + language_reliability
        + article_type
        + corroboration
        + impact
        + type_fit
    )

    # -----------------------------
    # Global penalties: small, not flattening caps
    # -----------------------------
    penalty = 0.0

    if word_count < 60:
        penalty += 8

    if not has_evidence and not has_official and not is_match_result_type:
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

    if not has_evidence and not has_official and not is_match_result_type:
        total = min(total, 52)

    # 90+ should be rare and earned.
    if total >= 90:
        if not has_official or len(evidence_hits) < 2 or nums < 1 or word_count < 120:
            total = 89

    total = _clamp(total, 0, 100)

    reasons: List[str] = [
        f"Article type: {type_info.get('label', detected_type)} / {detected_subtype}.",
        f"Source reputation: {source_score}/18 ({source_label}).",
        f"Evidence quality: {evidence_quality}/22.",
        f"Event/type fit: {type_fit}/12.",
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


def gemini_tldr(
    title: str,
    text: str,
    max_bullets: int = 3,
    language_info: Optional[Dict[str, Any]] = None,
) -> List[str]:
    text = clean_html(text)

    client = gemini_client()
    if client is None:
        return extractive_fallback(text, max_bullets=max_bullets)

    clipped = text[:MAX_ANALYZE_CHARS]

    prompt = (
        "Return ONLY valid JSON. No markdown. No commentary.\n"
        f"Task: summarize the sports/news article into exactly {max_bullets} TL;DR bullets.\n\n"
        f"Detected language information: {json.dumps(language_info or {})}\n"
        "Understand the article in its original language, including mixed or code-switched text.\n"
        "Return the TL;DR bullets in English for now.\n\n"
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
            model="gemini-3.5-flash",
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
# AI article type classifier beta
# -----------------------------
def ai_detect_article_type(
    title: str,
    text: str,
    url: str = "",
    language_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    AI classifier runs in shadow mode first.

    It does NOT control the live article type yet.
    It is used to compare AI classification vs rule classification.
    """

    client = gemini_client()

    if client is None:
        return {
            "enabled": False,
            "article_type": None,
            "article_subtype": None,
            "confidence": 0.0,
            "reason": "Gemini API key not available.",
        }

    clipped = clean_html(text)[:3500]

    allowed_types = [
        "match_report",
        "live_commentary",
        "official_announcement",
        "transfer_official",
        "transfer_report",
        "transfer_rumor",
        "transfer_roundup",
        "injury_confirmed",
        "injury_rumor",
        "lineup_confirmed",
        "lineup_predicted",
        "squad_news",
        "manager_interview",
        "player_interview",
        "agent_interview",
        "press_conference",
        "discipline_legal",
        "managerial_news",
        "contract_news",
        "fixture_schedule",
        "tactical_analysis",
        "stats_data_report",
        "opinion_analysis",
        "ownership_finance",
        "generic_news",
    ]

    prompt = (
        "Return ONLY valid JSON. No markdown. No commentary.\n\n"
        "Task: classify the type of this sports article.\n\n"
        f"Detected language information: {json.dumps(language_info or {})}\n"
        "Understand the article in its original language, including mixed or code-switched text.\n\n"
        "Important rules:\n"
        "- Classify the ARTICLE TYPE, not credibility.\n"
        "- Use the headline and URL as strong context.\n"
        "- Use the body text to support the classification, but do not let old match context override a clear transfer headline.\n"
        "- Do not call something an official transfer unless the story clearly says a signing/deal/transfer was completed or officially announced.\n"
        "- If it says linked, eyeing, interested, monitoring, rumors, or reports, use transfer_rumor.\n"
        "- If the article is grading, ranking, summarizing, or reviewing multiple transfers or a transfer window, use transfer_roundup.\n"
        "- If it is mainly explaining opinions, predictions, rankings, verdicts, or takeaways, use opinion_analysis.\n"
        "- If unsure, use generic_news with low confidence.\n\n"
        f"Allowed article_type values:\n{json.dumps(allowed_types)}\n\n"
        "Output JSON format:\n"
        "{\n"
        '  "article_type": "transfer_rumor",\n'
        '  "article_subtype": "unconfirmed_transfer_claim",\n'
        '  "confidence": 0.91,\n'
        '  "reason": "Short explanation of why this article type was chosen."\n'
        "}\n\n"
        f"Title: {title}\n"
        f"URL: {url}\n\n"
        f"Text:\n{clipped}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )

        raw = (resp.text or "").strip()

        start = raw.find("{")
        end = raw.rfind("}")

        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]

        data = json.loads(raw)

        article_type = str(data.get("article_type", "generic_news")).strip()
        article_subtype = str(data.get("article_subtype", "general")).strip()
        reason = str(data.get("reason", "")).strip()

        try:
            confidence = float(data.get("confidence", 0.0))
        except Exception:
            confidence = 0.0

        confidence = max(0.0, min(0.99, confidence))

        if article_type not in allowed_types:
            article_type = "generic_news"
            confidence = min(confidence, 0.35)
            reason = "AI returned an unsupported article type, so it was treated as generic."

        return {
            "enabled": True,
            "article_type": article_type,
            "article_type_label": ARTICLE_TYPE_LABELS.get(article_type, "Generic Sports News"),
            "article_subtype": article_subtype,
            "confidence": round(confidence, 2),
            "reason": reason,
        }

    except Exception as e:
        return {
            "enabled": True,
            "article_type": None,
            "article_subtype": None,
            "confidence": 0.0,
            "reason": f"AI classifier failed: {type(e).__name__}: {str(e)[:140]}",
        }

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

def detect_content_language(text: str) -> Dict[str, Any]:
    cleaned = clean_html(text).strip()

    if not cleaned:
        return {
            "detected_language": "unknown",
            "languages": [],
            "mixed_language": False,
            "language_confidence": 0.0,
        }

    client = gemini_client()

    if client is None:
        return {
            "detected_language": "unknown",
            "languages": [],
            "mixed_language": False,
            "language_confidence": 0.0,
        }

    sample = cleaned[:3000]

    if len(cleaned) > 6000:
        sample += "\n\n[END SAMPLE]\n" + cleaned[-3000:]

    prompt = (
        "Return ONLY valid JSON. No markdown. No commentary.\n\n"
        "Detect the language or languages used in this sports content.\n"
        "Recognize mixed-language and code-switched text such as Hinglish.\n"
        "Do not treat player names, club names, or short foreign phrases as a separate language.\n\n"
        "Output JSON format:\n"
        "{\n"
        '  "detected_language": "Hindi-English mixed",\n'
        '  "languages": ["Hindi", "English"],\n'
        '  "mixed_language": true,\n'
        '  "language_confidence": 0.95\n'
        "}\n\n"
        f"Content:\n{sample}\n"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = (response.text or "").strip()
        start = raw.find("{")
        end = raw.rfind("}")

        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]

        data = json.loads(raw)

        languages = data.get("languages", [])
        if not isinstance(languages, list):
            languages = [str(languages)]

        try:
            confidence = float(data.get("language_confidence", 0.0))
        except Exception:
            confidence = 0.0

        return {
            "detected_language": str(
                data.get("detected_language", "unknown")
            ),
            "languages": [str(language) for language in languages],
            "mixed_language": bool(data.get("mixed_language", False)),
            "language_confidence": round(
                max(0.0, min(1.0, confidence)),
                2,
            ),
        }

    except Exception as error:
        return {
            "detected_language": "unknown",
            "languages": [],
            "mixed_language": False,
            "language_confidence": 0.0,
            "error": f"{type(error).__name__}: {str(error)[:160]}",
        }

def ai_video_claim_readout(title: str, transcript: str, url: str = "") -> Dict[str, Any]:
    client = gemini_client()

    if client is None:
        return {
            "claim": "AI video analysis is unavailable.",
            "evidence_used": ["Gemini API key not available."],
            "logic_check": "Cannot check logic without AI access.",
            "hype_check": "Cannot check hype without AI access.",
            "evidence_score": 0,
            "logic_score": 0,
            "verdict": "ai_unavailable",
            "debug": {
                "mode": "video",
                "ai_enabled": False,
            },
        }

    language_info = {
        "detected_language": "unknown",
        "languages": [],
        "mixed_language": False,
        "language_confidence": 0.0,
    }
    
    transcript_data = prepare_video_transcript(transcript)
    cleaned_transcript = transcript_data["cleaned_transcript"]

    if len(cleaned_transcript) <= 12000:
        clipped_transcript = cleaned_transcript
    else:
        section_size = 4000
        middle_start = max(
            0,
            (len(cleaned_transcript) // 2) - (section_size // 2),
        )

        clipped_transcript = (
            "[START OF VIDEO]\n"
            + cleaned_transcript[:section_size]
            + "\n\n[MIDDLE OF VIDEO]\n"
            + cleaned_transcript[
                middle_start:middle_start + section_size
            ]
            + "\n\n[END OF VIDEO]\n"
            + cleaned_transcript[-section_size:]
        )

    prompt = (
        "Return ONLY valid JSON. No markdown. No commentary.\n\n"
        "Task: analyze a sports video transcript.\n\n"
        "The video may be reporting news, discussing a rumor, presenting technical "
        "analysis, giving an opinion, investigating a topic, or using engagement bait.\n"
        "Do not assume that every video is a rumor or breaking-news report.\n\n"
        "Detect the transcript's language or languages as part of this same analysis.\n"
        "Set mixed_language to true when the speaker meaningfully switches languages.\n"
        "Understand multilingual and code-switched speech in its original context.\n"
        "Return the claim analysis in English for now.\n\n"
        "Judge the video according to the type of content it actually contains.\n"
        "Separate dramatic presentation style from the quality of the underlying "
        "reasoning and evidence.\n"
        "A sensational title or introduction alone does not make a video engagement bait.\n"
        "You are not deciding absolute truth. You are evaluating the main claim, "
        "supporting evidence, reasoning quality, and level of overstatement.\n\n"
        "Output JSON format:\n"
        "{\n"
        '  "detected_language": "English",\n'
        '  "languages": ["English"],\n'
        '  "mixed_language": false,\n'
        '  "language_confidence": 0.95,\n'
        '  "content_type": "sports_analysis",\n'
        '  "claim": "Main claim or argument made by the video.",\n'
        '  "evidence_used": ["Evidence, examples, sources, or reasoning used."],\n'
        '  "logic_check": "Whether the reasoning supports the main claim.",\n'
        '  "hype_check": "Whether presentation is careful, dramatic, or misleading.",\n'
        '  "evidence_score": 0,\n'
        '  "logic_score": 0,\n'
        '  "verdict": "well_supported_analysis"\n'
        "}\n\n"
        "First choose one content_type:\n"
        "- confirmed_news\n"
        "- sports_report\n"
        "- rumor\n"
        "- sports_analysis\n"
        "- sports_opinion\n"
        "- engagement_bait\n"
        "- not_sports_content\n\n"

        "Scoring rules:\n"
        "- evidence_score measures the quality of support presented in the video, from 0 to 100.\n"
        "- Evidence may include official statements, named reporting, statistics, technical details, historical examples, or clearly explained observations.\n"
        "- Do not require official confirmation for analysis or opinion videos.\n"
        "- logic_score measures whether the reasoning connects the evidence to the main claim, from 0 to 100.\n"
        "- Score evidence and logic independently from title style, thumbnails, dramatic wording, or editing.\n"
        "- A video may be dramatic while still presenting reasonable analysis.\n"
        "- Use engagement_bait only when the video substantially misrepresents, fabricates, or fails to support its central claim.\n\n"

        "Choose one verdict:\n"
        "- confirmed\n"
        "- well_supported_report\n"
        "- well_supported_analysis\n"
        "- reasonable_opinion\n"
        "- plausible_rumor\n"
        "- weakly_supported\n"
        "- misleading\n"
        "- engagement_bait\n"
        "- not_sports_content\n\n"
        f"Video title: {title}\n"
        f"URL: {url}\n\n"
        f"Transcript:\n{clipped_transcript}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )

        raw = (resp.text or "").strip()
        start = raw.find("{")
        end = raw.rfind("}")

        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]

        data = json.loads(raw)

        languages = data.get("languages", [])
        if not isinstance(languages, list):
            languages = [str(languages)]

        try:
            language_confidence = float(
                data.get("language_confidence", 0.0)
            )
        except Exception:
            language_confidence = 0.0

        language_info = {
            "detected_language": str(
                data.get("detected_language", "unknown")
            ),
            "languages": [str(language) for language in languages],
            "mixed_language": bool(
                data.get("mixed_language", False)
            ),
            "language_confidence": round(
                max(0.0, min(1.0, language_confidence)),
                2,
            ),
        }

        evidence_score = int(float(data.get("evidence_score", 0)))
        logic_score = int(float(data.get("logic_score", 0)))

        evidence_score = max(0, min(100, evidence_score))
        logic_score = max(0, min(100, logic_score))

        evidence_used = data.get("evidence_used", [])
        if not isinstance(evidence_used, list):
            evidence_used = [str(evidence_used)]

        allowed_content_types = {
            "confirmed_news",
            "sports_report",
            "rumor",
            "sports_analysis",
            "sports_opinion",
            "engagement_bait",
            "not_sports_content",
        }

        content_type = str(
            data.get("content_type", "unknown")
        ).strip().lower()

        if content_type not in allowed_content_types:
            content_type = "unknown"

        allowed_verdicts = {
            "confirmed",
            "well_supported_report",
            "well_supported_analysis",
            "reasonable_opinion",
            "plausible_rumor",
            "weakly_supported",
            "misleading",
            "engagement_bait",
            "not_sports_content",
        }

        verdict = str(
            data.get("verdict", "weakly_supported")
        ).strip().lower()

        if verdict not in allowed_verdicts:
            verdict = "weakly_supported"

        if content_type == "unknown":
            verdict_to_content_type = {
                "confirmed": "confirmed_news",
                "well_supported_report": "sports_report",
                "well_supported_analysis": "sports_analysis",
                "reasonable_opinion": "sports_opinion",
                "plausible_rumor": "rumor",
                "engagement_bait": "engagement_bait",
                "not_sports_content": "not_sports_content",
            }

            content_type = verdict_to_content_type.get(
                verdict,
                "unknown",
            )

        return {
            "content_type": content_type,
            "claim": str(
                data.get("claim", "No clear claim found.")
            ),
            "evidence_used": [str(x) for x in evidence_used],
            "logic_check": str(data.get("logic_check", "")),
            "hype_check": str(data.get("hype_check", "")),
            "evidence_score": evidence_score,
            "logic_score": logic_score,
            "verdict": verdict,
            "debug": {
                "mode": "video",
                "ai_enabled": True,
                "transcript_raw_chars": len(
                    transcript_data["raw_transcript"]
                ),
                "transcript_cleaned_chars": len(
                    transcript_data["cleaned_transcript"]
                ),
                "transcript_confidence": transcript_data[
                    "transcript_confidence"
                ],
                "uncertain_corrections": transcript_data[
                    "uncertain_corrections"
                ],
                "language": language_info,
                "transcript_chars": len(transcript),
                "transcript_chars_sent": len(clipped_transcript),
            },
        }

    except Exception as e:
        return {
            "claim": "AI video analysis failed.",
            "evidence_used": [f"{type(e).__name__}: {str(e)[:160]}"],
            "logic_check": "Could not complete logic check.",
            "hype_check": "Could not complete hype check.",
            "evidence_score": 0,
            "logic_score": 0,
            "verdict": "analysis_failed",
            "debug": {
                "mode": "video",
                "ai_enabled": True,
                "transcript_raw_chars": len(
                    transcript_data["raw_transcript"]
                ),
                "transcript_cleaned_chars": len(
                    transcript_data["cleaned_transcript"]
                ),
                "transcript_confidence": transcript_data[
                    "transcript_confidence"
                ],
                "uncertain_corrections": transcript_data[
                    "uncertain_corrections"
                ],
                "error": str(e)[:200],
            },
        }

@app.post("/analyze/video", response_model=VideoAnalyzeResponse)
def analyze_video(req: VideoAnalyzeRequest):
    result = ai_video_claim_readout(req.title, req.transcript, req.url)

    return VideoAnalyzeResponse(
        claim=result.get("claim", ""),
        evidence_used=result.get("evidence_used", []),
        logic_check=result.get("logic_check", ""),
        hype_check=result.get("hype_check", ""),
        evidence_score=int(result.get("evidence_score", 0)),
        logic_score=int(result.get("logic_score", 0)),
        verdict=result.get("verdict", "unclear"),
        debug=result.get("debug", {}),
    )

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    started = time.perf_counter()
    last_mark = started
    timings_ms: Dict[str, float] = {}

    def mark(name: str) -> None:
        nonlocal last_mark

        now = time.perf_counter()
        timings_ms[name] = round((now - last_mark) * 1000, 2)
        last_mark = now

    cleaned_text = clean_html(req.text)
    original_chars = len(cleaned_text)
    language_info = detect_content_language(cleaned_text)
    mark("language_detection_ms")

    cleaned_text = cleaned_text[:MAX_ANALYZE_CHARS]
    mark("clean_and_cap_ms")

    type_info = detect_article_type(req.title, cleaned_text, req.url)
    mark("article_type_ms")

    ai_type_info = ai_detect_article_type(
        req.title,
        cleaned_text,
        req.url,
        language_info=language_info,
    )
    mark("ai_article_type_ms")

    final_type_info = type_info

    detected_language = str(
        language_info.get("detected_language", "unknown")
    ).strip().lower()

    is_non_english_or_mixed = (
        bool(language_info.get("mixed_language", False))
        or detected_language not in {"english", "unknown"}
    )

    ai_type = ai_type_info.get("article_type")
    ai_confidence = float(ai_type_info.get("confidence", 0.0) or 0.0)

    rule_type = str(type_info.get("primary_type", "generic_news"))
    rule_confidence = float(type_info.get("confidence", 0.0) or 0.0)

    rule_is_weak_generic = (
        rule_type == "generic_news"
        and rule_confidence <= 0.35
    )

    if (
        ai_type
        and ai_confidence >= 0.80
        and (
            is_non_english_or_mixed
            or rule_is_weak_generic
        )
    ):
        final_type_info = {
            "primary_type": ai_type,
            "label": ai_type_info.get(
                "article_type_label",
                ARTICLE_TYPE_LABELS.get(ai_type, "Generic Sports News"),
            ),
            "subtype": ai_type_info.get("article_subtype", "general"),
            "confidence": ai_confidence,
            "signals": [
                "High-confidence multilingual AI classification."
            ],
        }

    tldr = gemini_tldr(
        req.title,
        cleaned_text,
        max_bullets=req.max_bullets,
        language_info=language_info,
    )
    mark("tldr_ms")

    score = merit_score(req.title, cleaned_text, req.url, type_info)
    mark("merit_score_ms")

    total_ms = round((time.perf_counter() - started) * 1000, 2)

    return AnalyzeResponse(
        url=req.url,
        title=req.title,
        tldr=tldr,
        merit_score=int(score["total"]),
        badge=str(score["badge"]),

        article_type=str(final_type_info.get("primary_type", "generic_news")),
        article_type_label=str(final_type_info.get("label", "Generic Sports News")),
        article_subtype=str(final_type_info.get("subtype", "general")),
        type_confidence=float(final_type_info.get("confidence", 0.0)),
        type_signals=final_type_info.get("signals", []),

        reasons=score.get("reasons", []),
        debug={
            "timings": timings_ms,
            "total_ms": total_ms,
            "original_chars": original_chars,
            "chars_sent": len(cleaned_text),
            "language": language_info,

            "rule_article_type": {
                "article_type": type_info.get("primary_type"),
                "article_type_label": type_info.get("label"),
                "article_subtype": type_info.get("subtype"),
                "confidence": type_info.get("confidence"),
                "signals": type_info.get("signals", []),
            },
            "ai_article_type_shadow": ai_type_info,
        },
    )