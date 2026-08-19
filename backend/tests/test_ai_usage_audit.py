from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest

from app.operations.ai_usage_audit import (
    AI_USAGE_AUDIT_VERSION,
    build_provider_day_ai_usage_audit,
)


SCHEMA = """
CREATE TABLE gemini_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  usage_day TEXT NOT NULL,
  provider_day TEXT NOT NULL,
  client_key TEXT NOT NULL,
  mode TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL,
  estimated_prompt_tokens INTEGER NOT NULL DEFAULT 0,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  thought_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  cache_hit INTEGER NOT NULL DEFAULT 0,
  inflight_join INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  failure_status_code INTEGER,
  failure_type TEXT NOT NULL DEFAULT '',
  failure_detail TEXT NOT NULL DEFAULT ''
);
"""


def _insert(
    conn: sqlite3.Connection,
    *,
    created_at: str,
    provider_day: str = "2026-08-19",
    client_key: str = "benchmark",
    mode: str = "article_single_pass",
    model: str = "gemini-3.5-flash",
    status: str = "success",
    estimated_prompt_tokens: int = 100,
    prompt_tokens: int = 90,
    output_tokens: int = 20,
    thought_tokens: int = 5,
    total_tokens: int = 115,
    cache_hit: int = 0,
    inflight_join: int = 0,
    latency_ms: int = 1000,
    failure_status_code: int | None = None,
    failure_type: str = "",
    failure_detail: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO gemini_usage (
          created_at,
          usage_day,
          provider_day,
          client_key,
          mode,
          model,
          status,
          estimated_prompt_tokens,
          prompt_tokens,
          output_tokens,
          thought_tokens,
          total_tokens,
          cache_hit,
          inflight_join,
          latency_ms,
          failure_status_code,
          failure_type,
          failure_detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_at,
            provider_day,
            provider_day,
            client_key,
            mode,
            model,
            status,
            estimated_prompt_tokens,
            prompt_tokens,
            output_tokens,
            thought_tokens,
            total_tokens,
            cache_hit,
            inflight_join,
            latency_ms,
            failure_status_code,
            failure_type,
            failure_detail,
        ),
    )


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "usage.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)

        _insert(
            conn,
            created_at="2026-08-19T10:00:00+00:00",
            model="gemini-3.5-flash",
            prompt_tokens=90,
            output_tokens=20,
            thought_tokens=5,
            total_tokens=115,
            latency_ms=1000,
        )
        _insert(
            conn,
            created_at="2026-08-19T10:01:00+00:00",
            model="gemini-3.7-flash",
            status="failed",
            prompt_tokens=0,
            output_tokens=0,
            thought_tokens=0,
            total_tokens=0,
            latency_ms=28000,
            failure_status_code=503,
            failure_type="provider_capacity",
            failure_detail="503 UNAVAILABLE",
        )
        _insert(
            conn,
            created_at="2026-08-19T10:02:00+00:00",
            client_key="campaign",
            mode="video_analysis",
            model="gemma-4-26b-a4b-it",
            estimated_prompt_tokens=200,
            prompt_tokens=180,
            output_tokens=40,
            thought_tokens=10,
            total_tokens=230,
            latency_ms=3000,
        )
        _insert(
            conn,
            created_at="2026-08-19T10:03:00+00:00",
            status="success",
            cache_hit=1,
            estimated_prompt_tokens=0,
            prompt_tokens=0,
            output_tokens=0,
            thought_tokens=0,
            total_tokens=0,
            latency_ms=0,
        )
        _insert(
            conn,
            created_at="2026-08-19T10:04:00+00:00",
            status="success",
            inflight_join=1,
            estimated_prompt_tokens=0,
            prompt_tokens=0,
            output_tokens=0,
            thought_tokens=0,
            total_tokens=0,
            latency_ms=0,
        )
        _insert(
            conn,
            created_at="2026-08-18T10:00:00+00:00",
            provider_day="2026-08-18",
            total_tokens=999,
        )

        conn.commit()
    finally:
        conn.close()

    return path


def test_provider_day_audit_separates_calls_tokens_and_avoidance(
    tmp_path: Path,
) -> None:
    payload = build_provider_day_ai_usage_audit(
        db_path=_database(tmp_path),
        provider_day="2026-08-19",
    )

    assert payload["version"] == AI_USAGE_AUDIT_VERSION
    assert payload["provider_day"] == "2026-08-19"

    summary = payload["summary"]

    assert summary["records"] == 5
    assert summary["provider_attempts"] == 3
    assert summary["completed_provider_calls"] == 3
    assert summary["successful_calls"] == 2
    assert summary["failed_calls"] == 1
    assert summary["cache_hits"] == 1
    assert summary["inflight_joins"] == 1
    assert summary["success_rate_percent"] == 66.67
    assert summary["failure_rate_percent"] == 33.33

    assert summary["prompt_tokens"] == 270
    assert summary["output_tokens"] == 60
    assert summary["thought_tokens"] == 15
    assert summary["billable_output_tokens"] == 75
    assert summary["total_tokens"] == 345

    assert summary["successful_prompt_tokens"] == 270
    assert summary["successful_output_tokens"] == 60
    assert summary["successful_thought_tokens"] == 15
    assert summary["successful_total_tokens"] == 345
    assert summary["average_total_tokens_per_success"] == 172.5

    assert summary["reported_token_calls"] == 2
    assert summary["token_accounting_coverage_percent"] == 66.67

    assert summary["latency"] == {
        "average_ms": 10666.67,
        "fastest_ms": 1000,
        "median_ms": 3000,
        "p95_ms": 28000,
        "slowest_ms": 28000,
    }


def test_provider_day_audit_includes_model_mode_client_and_failure_detail(
    tmp_path: Path,
) -> None:
    payload = build_provider_day_ai_usage_audit(
        db_path=_database(tmp_path),
        provider_day="2026-08-19",
    )

    models = {
        row["model"]: row
        for row in payload["by_model"]
    }

    assert models["gemini-3.5-flash"]["provider_attempts"] == 1
    assert models["gemini-3.7-flash"]["failed_calls"] == 1
    assert models["gemma-4-26b-a4b-it"]["total_tokens"] == 230

    modes = {
        row["mode"]: row
        for row in payload["by_mode"]
    }
    assert modes["article_single_pass"]["provider_attempts"] == 2
    assert modes["video_analysis"]["provider_attempts"] == 1

    clients = {
        row["client_key"]: row
        for row in payload["by_client"]
    }
    assert clients["benchmark"]["provider_attempts"] == 2
    assert clients["campaign"]["provider_attempts"] == 1

    assert payload["failures"] == [
        {
            "id": 2,
            "created_at": "2026-08-19T10:01:00+00:00",
            "client_key": "benchmark",
            "mode": "article_single_pass",
            "model": "gemini-3.7-flash",
            "status_code": 503,
            "failure_type": "provider_capacity",
            "failure_detail": "503 UNAVAILABLE",
            "latency_ms": 28000,
        }
    ]

    assert len(payload["provider_calls"]) == 3


def test_provider_day_audit_rejects_empty_provider_day(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="provider_day is required"):
        build_provider_day_ai_usage_audit(
            db_path=_database(tmp_path),
            provider_day="",
        )
