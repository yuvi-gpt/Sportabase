from __future__ import annotations

import os

from pathlib import Path

from dotenv import load_dotenv

from app.ai.quota import (
    capacity_policy_for_model,
    sportabase_daily_caps,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
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

_GEMINI_CAPACITY_POLICY = capacity_policy_for_model("")
(
    GLOBAL_DAILY_GEMINI_CALL_CAP,
    CLIENT_DAILY_GEMINI_CALL_CAP,
) = sportabase_daily_caps(
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

# Control Room security is disabled by default. All identity, application,
# allowlist, and audit credentials are deployment configuration only; none are
# committed to the repository.
CONTROL_ROOM_ENABLED = (
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_ENABLED",
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

CONTROL_ROOM_CLOUDFLARE_TEAM_DOMAIN = os.getenv(
    "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_TEAM_DOMAIN",
    "",
).strip()

CONTROL_ROOM_CLOUDFLARE_ACCOUNT_ID = os.getenv(
    "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_ACCOUNT_ID",
    "",
).strip()

CONTROL_ROOM_CLOUDFLARE_APPLICATION_ID = os.getenv(
    "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_APPLICATION_ID",
    "",
).strip()

CONTROL_ROOM_CLOUDFLARE_APPLICATION_AUDIENCE = os.getenv(
    "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_APPLICATION_AUDIENCE",
    "",
).strip()

CONTROL_ROOM_GOOGLE_IDP_ID = os.getenv(
    "SPORTABASE_CONTROL_ROOM_GOOGLE_IDP_ID",
    "",
).strip()

CONTROL_ROOM_ALLOWED_EMAILS = tuple(
    value.strip()
    for value in os.getenv(
        "SPORTABASE_CONTROL_ROOM_ALLOWED_EMAILS",
        "",
    ).split(",")
    if value.strip()
)

CONTROL_ROOM_CLOUDFLARE_POLICY_AUDIT_API_TOKEN = os.getenv(
    "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_POLICY_AUDIT_API_TOKEN",
    "",
).strip()

CONTROL_ROOM_ORIGIN_PROVENANCE_SECRET = os.getenv(
    "SPORTABASE_CONTROL_ROOM_ORIGIN_PROVENANCE_SECRET",
    "",
).strip()

CONTROL_ROOM_POLICY_CACHE_TTL_SECONDS = int(
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_POLICY_CACHE_TTL_SECONDS",
        "240",
    )
)

CONTROL_ROOM_CLOUDFLARE_REQUEST_TIMEOUT_SECONDS = int(
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_CLOUDFLARE_REQUEST_TIMEOUT_SECONDS",
        "10",
    )
)

CONTROL_ROOM_MAX_SESSION_DURATION_SECONDS = int(
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_MAX_SESSION_DURATION_SECONDS",
        "900",
    )
)

CONTROL_ROOM_MAX_POLICY_PAGES = int(
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_MAX_POLICY_PAGES",
        "10",
    )
)

CONTROL_ROOM_CLOCK_SKEW_SECONDS = int(
    os.getenv(
        "SPORTABASE_CONTROL_ROOM_CLOCK_SKEW_SECONDS",
        "60",
    )
)
