from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from typing import Any

from app.intelligence.article_product_runtime import (
    build_article_product_intelligence,
)
from app.intelligence.projection import (
    build_claim_projection,
    build_story_projection,
)


BACKGROUND_INTELLIGENCE_REFRESH_VERSION = (
    "background-intelligence-refresh-v1"
)
BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION = (
    "background-intelligence-job-view-v1"
)

_MAX_CLAIMS = 50
_MAX_STORIES = 50


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    text = str(value or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return dict(parsed) if isinstance(parsed, dict) else {}


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _bounded_limit(value: Any, *, default: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(1, min(maximum, parsed))


def _unique_ids(values: Any, *, maximum: int) -> list[str]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return []

    output: list[str] = []
    seen = set()
    for raw in values:
        value = _clean(raw, 128)
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
        if len(output) >= maximum:
            break

    return output


def _result_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    raw = result.get("result")
    return dict(raw) if isinstance(raw, Mapping) else {}


def _collect_claim_ids(
    payload: Mapping[str, Any],
    *,
    maximum: int,
) -> list[str]:
    values: list[str] = []

    single = _clean(payload.get("claim_id"), 128)
    if single:
        values.append(single)

    raw_claim_ids = payload.get("claim_ids")
    if isinstance(raw_claim_ids, list):
        values.extend(raw_claim_ids)

    graph = payload.get("story_graph_materialization")
    if isinstance(graph, Mapping):
        graph_claim_ids = graph.get("claim_ids")
        if isinstance(graph_claim_ids, list):
            values.extend(graph_claim_ids)

    return _unique_ids(values, maximum=maximum)


def _collect_story_ids(
    payload: Mapping[str, Any],
    *,
    maximum: int,
) -> list[str]:
    values: list[str] = []

    raw_story_ids = payload.get("story_ids")
    if isinstance(raw_story_ids, list):
        values.extend(raw_story_ids)

    graph = payload.get("story_graph_materialization")
    if isinstance(graph, Mapping):
        graph_story_ids = graph.get("story_ids")
        if isinstance(graph_story_ids, list):
            values.extend(graph_story_ids)

    return _unique_ids(values, maximum=maximum)


def _structured_identity_flags(
    *,
    claim_ids: list[str],
    connection_factory,
) -> dict[str, bool]:
    if not claim_ids:
        return {}

    placeholders = ",".join("?" for _ in claim_ids)
    conn = connection_factory()
    try:
        rows = conn.execute(
            "SELECT id, metadata_json FROM intelligence_claims "
            "WHERE id IN (" + placeholders + ")",
            tuple(claim_ids),
        ).fetchall()
    finally:
        conn.close()

    output: dict[str, bool] = {}
    for raw in rows:
        row = dict(raw)
        claim_id = _clean(row.get("id"), 128)
        metadata = _json_object(row.get("metadata_json"))
        output[claim_id] = (
            _clean(metadata.get("identity_source"), 128)
            == "deterministic_structured_claim_core"
            and isinstance(metadata.get("structured_claim"), Mapping)
        )

    return output


def _projection_state_row(
    projection: Mapping[str, Any],
    *,
    item_id: str,
    structured_identity: bool = False,
) -> dict[str, Any]:
    freshness = projection.get("freshness")
    freshness_state = (
        _clean(freshness.get("state"), 64)
        if isinstance(freshness, Mapping)
        else ""
    )

    return {
        "id": item_id,
        "status": _clean(projection.get("status"), 64),
        "projection_state": _clean(
            projection.get("projection_state"),
            128,
        ),
        "freshness_state": freshness_state,
        "structured_identity": bool(structured_identity),
    }


def _project_claims(
    *,
    claim_ids: list[str],
    connection_factory,
    stale_after_days: int,
) -> tuple[list[dict[str, Any]], int]:
    structured = _structured_identity_flags(
        claim_ids=claim_ids,
        connection_factory=connection_factory,
    )
    rows: list[dict[str, Any]] = []
    failures = 0

    for claim_id in claim_ids:
        try:
            projection = build_claim_projection(
                claim_id=claim_id,
                connection_factory=connection_factory,
                stale_after_days=stale_after_days,
            )
        except Exception:
            failures += 1
            rows.append(
                {
                    "id": claim_id,
                    "status": "unavailable",
                    "projection_state": "",
                    "freshness_state": "",
                    "structured_identity": bool(structured.get(claim_id)),
                }
            )
            continue

        rows.append(
            _projection_state_row(
                projection,
                item_id=claim_id,
                structured_identity=bool(structured.get(claim_id)),
            )
        )

    return rows, failures


def _project_stories(
    *,
    story_ids: list[str],
    connection_factory,
    stale_after_days: int,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    failures = 0

    for story_id in story_ids:
        try:
            projection = build_story_projection(
                story_id=story_id,
                connection_factory=connection_factory,
                stale_after_days=stale_after_days,
            )
        except Exception:
            failures += 1
            rows.append(
                {
                    "id": story_id,
                    "status": "unavailable",
                    "projection_state": "",
                    "freshness_state": "",
                    "structured_identity": False,
                }
            )
            continue

        rows.append(
            _projection_state_row(
                projection,
                item_id=story_id,
            )
        )

    return rows, failures


def _article_baseline_url(
    *,
    payload: Mapping[str, Any],
    connection_factory,
) -> str:
    baseline = payload.get("baseline_resolution")
    if not isinstance(baseline, Mapping):
        return ""

    media_item_id = _clean(baseline.get("media_item_id"), 128)
    if not media_item_id:
        return ""

    conn = connection_factory()
    try:
        row = conn.execute(
            "SELECT canonical_url, mode FROM media_items WHERE id = ?",
            (media_item_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return ""

    record = dict(row)
    if _clean(record.get("mode"), 64).casefold() != "article":
        return ""

    return _clean(record.get("canonical_url"), 2048)


def _article_runtime_summary(
    *,
    execution_mode: str,
    payload: Mapping[str, Any],
    connection_factory,
    stale_after_days: int,
) -> dict[str, Any]:
    if execution_mode != "article_history_merit":
        return {
            "status": "not_applicable",
            "runtime_state": "",
            "counts": {},
        }

    try:
        url = _article_baseline_url(
            payload=payload,
            connection_factory=connection_factory,
        )
        if not url:
            return {
                "status": "baseline_media_unavailable",
                "runtime_state": "",
                "counts": {},
            }

        runtime = build_article_product_intelligence(
            url=url,
            connection_factory=connection_factory,
            stale_after_days=stale_after_days,
        )
    except Exception:
        return {
            "status": "unavailable",
            "runtime_state": "",
            "counts": {},
        }

    counts = runtime.get("counts")
    return {
        "status": _clean(runtime.get("status"), 64),
        "runtime_state": _clean(runtime.get("runtime_state"), 128),
        "counts": (
            {
                _clean(key, 64): _safe_int(value)
                for key, value in counts.items()
                if _clean(key, 64)
            }
            if isinstance(counts, Mapping)
            else {}
        ),
    }


def build_background_intelligence_refresh(
    *,
    result: Mapping[str, Any],
    connection_factory,
    stale_after_days: int = 30,
    max_claims: int = _MAX_CLAIMS,
    max_stories: int = _MAX_STORIES,
) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("Background intelligence refresh requires a job result.")
    if connection_factory is None:
        raise ValueError("Background intelligence refresh requires database access.")

    status = _clean(result.get("status"), 64).casefold()
    if status != "completed":
        return {
            "version": BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
            "status": "not_applicable",
            "execution_mode": _clean(result.get("execution_mode"), 96),
            "counts": {
                "claims": 0,
                "stories": 0,
                "structured_claims": 0,
                "projection_failures": 0,
            },
            "claim_states": [],
            "story_states": [],
            "article_runtime": {
                "status": "not_applicable",
                "runtime_state": "",
                "counts": {},
            },
            "policy": {
                "completed_jobs_only": True,
                "provider_call_performed": False,
                "historical_snapshots_mutated": False,
                "affects_live_merit": False,
            },
        }

    stale_days = _bounded_limit(
        stale_after_days,
        default=30,
        maximum=3650,
    )
    claim_limit = _bounded_limit(
        max_claims,
        default=_MAX_CLAIMS,
        maximum=_MAX_CLAIMS,
    )
    story_limit = _bounded_limit(
        max_stories,
        default=_MAX_STORIES,
        maximum=_MAX_STORIES,
    )

    execution_mode = _clean(result.get("execution_mode"), 96).casefold()
    payload = _result_payload(result)
    claim_ids = _collect_claim_ids(payload, maximum=claim_limit)
    story_ids = _collect_story_ids(payload, maximum=story_limit)

    claim_states, claim_failures = _project_claims(
        claim_ids=claim_ids,
        connection_factory=connection_factory,
        stale_after_days=stale_days,
    )
    story_states, story_failures = _project_stories(
        story_ids=story_ids,
        connection_factory=connection_factory,
        stale_after_days=stale_days,
    )

    claim_state_counts = Counter(
        _clean(item.get("projection_state"), 128) or "unknown"
        for item in claim_states
    )
    story_state_counts = Counter(
        _clean(item.get("projection_state"), 128) or "unknown"
        for item in story_states
    )
    structured_claims = sum(
        1 for item in claim_states if item.get("structured_identity") is True
    )
    stale_claims = sum(
        1 for item in claim_states if item.get("freshness_state") == "stale"
    )
    conflict_claims = sum(
        1
        for item in claim_states
        if item.get("projection_state")
        in {
            "adjudication_history_conflict",
            "claim_conflict_present",
        }
    )

    article_runtime = _article_runtime_summary(
        execution_mode=execution_mode,
        payload=payload,
        connection_factory=connection_factory,
        stale_after_days=stale_days,
    )

    projection_failures = claim_failures + story_failures
    if projection_failures:
        refresh_status = "partial"
    else:
        refresh_status = "ready"

    return {
        "version": BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
        "status": refresh_status,
        "execution_mode": execution_mode,
        "counts": {
            "claims": len(claim_states),
            "stories": len(story_states),
            "structured_claims": structured_claims,
            "stale_claims": stale_claims,
            "conflict_claims": conflict_claims,
            "projection_failures": projection_failures,
        },
        "claim_projection_states": dict(sorted(claim_state_counts.items())),
        "story_projection_states": dict(sorted(story_state_counts.items())),
        "claim_states": claim_states,
        "story_states": story_states,
        "article_runtime": article_runtime,
        "policy": {
            "completed_jobs_only": True,
            "bounded_claim_projection_refresh": True,
            "bounded_story_projection_refresh": True,
            "article_runtime_derived_from_persisted_baseline_media": True,
            "provider_call_performed": False,
            "provider_required": False,
            "historical_snapshots_mutated": False,
            "job_outcome_not_reclassified": True,
            "refresh_failure_is_advisory": True,
            "projection_state_is_context_not_truth": True,
            "affects_live_merit": False,
        },
    }


def _persisted_refresh(refresh: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": _clean(refresh.get("version"), 128),
        "status": _clean(refresh.get("status"), 64),
        "execution_mode": _clean(refresh.get("execution_mode"), 96),
        "counts": dict(refresh.get("counts") or {}),
        "claim_projection_states": dict(
            refresh.get("claim_projection_states") or {}
        ),
        "story_projection_states": dict(
            refresh.get("story_projection_states") or {}
        ),
        "article_runtime": dict(refresh.get("article_runtime") or {}),
        "policy": dict(refresh.get("policy") or {}),
    }


def persist_background_intelligence_refresh(
    *,
    result: Mapping[str, Any],
    refresh: Mapping[str, Any],
    connection_factory,
) -> dict[str, Any] | None:
    raw_job = result.get("job")
    if not isinstance(raw_job, Mapping):
        return None

    job_id = _clean(raw_job.get("id"), 128)
    if not job_id:
        return None

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status, result_json FROM browser_capture_automation_jobs "
            "WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            conn.rollback()
            return None

        current = dict(row)
        if _clean(current.get("status"), 64).casefold() != "completed":
            conn.rollback()
            return None

        payload = _json_object(current.get("result_json"))
        payload["intelligence_refresh"] = _persisted_refresh(refresh)

        conn.execute(
            "UPDATE browser_capture_automation_jobs "
            "SET result_json = ? WHERE id = ? AND status = 'completed'",
            (_canonical_json(payload), job_id),
        )
        updated = conn.execute(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return dict(updated) if updated is not None else None


def refresh_completed_job_intelligence(
    *,
    result: Mapping[str, Any] | None,
    connection_factory,
) -> dict[str, Any] | None:
    if not isinstance(result, Mapping):
        return None if result is None else dict(result)

    output = dict(result)
    if _clean(output.get("status"), 64).casefold() != "completed":
        return output

    try:
        refresh = build_background_intelligence_refresh(
            result=output,
            connection_factory=connection_factory,
        )
    except Exception as error:
        refresh = {
            "version": BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
            "status": "unavailable",
            "execution_mode": _clean(output.get("execution_mode"), 96),
            "counts": {
                "claims": 0,
                "stories": 0,
                "structured_claims": 0,
                "stale_claims": 0,
                "conflict_claims": 0,
                "projection_failures": 0,
            },
            "claim_projection_states": {},
            "story_projection_states": {},
            "claim_states": [],
            "story_states": [],
            "article_runtime": {
                "status": "unavailable",
                "runtime_state": "",
                "counts": {},
            },
            "error_type": type(error).__name__,
            "policy": {
                "provider_call_performed": False,
                "historical_snapshots_mutated": False,
                "job_outcome_not_reclassified": True,
                "refresh_failure_is_advisory": True,
                "affects_live_merit": False,
            },
        }

    output["intelligence_refresh"] = refresh

    try:
        updated_job = persist_background_intelligence_refresh(
            result=output,
            refresh=refresh,
            connection_factory=connection_factory,
        )
    except Exception:
        updated_job = None

    if updated_job is not None:
        output["job"] = updated_job

    raw_result = output.get("result")
    if isinstance(raw_result, Mapping):
        public_result = dict(raw_result)
        public_result["intelligence_refresh"] = _persisted_refresh(refresh)
        output["result"] = public_result

    return output


def load_background_intelligence_job(
    *,
    job_id: str,
    connection_factory,
) -> dict[str, Any]:
    normalized_job_id = _clean(job_id, 128)
    if not normalized_job_id:
        raise ValueError("Background intelligence job_id is required.")
    if connection_factory is None:
        raise ValueError("Background intelligence job view requires database access.")

    conn = connection_factory()
    try:
        row = conn.execute(
            """
            SELECT
              id, capture_record_id, status, attempts, max_attempts,
              analysis_version, scoring_version, created_at, updated_at,
              started_at, finished_at, last_outcome, error_type, result_json
            FROM browser_capture_automation_jobs
            WHERE id = ?
            """,
            (normalized_job_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "version": BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION,
            "status": "not_found",
            "job_id": normalized_job_id,
        }

    record = dict(row)
    payload = _json_object(record.get("result_json"))
    refresh = payload.get("intelligence_refresh")

    return {
        "version": BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION,
        "status": "ok",
        "job": {
            "id": _clean(record.get("id"), 128),
            "capture_record_id": _clean(record.get("capture_record_id"), 128),
            "status": _clean(record.get("status"), 64),
            "attempts": _safe_int(record.get("attempts")),
            "max_attempts": _safe_int(record.get("max_attempts")),
            "analysis_version": _clean(record.get("analysis_version"), 128),
            "scoring_version": _clean(record.get("scoring_version"), 128),
            "created_at": _clean(record.get("created_at"), 128),
            "updated_at": _clean(record.get("updated_at"), 128),
            "started_at": _clean(record.get("started_at"), 128),
            "finished_at": _clean(record.get("finished_at"), 128),
            "last_outcome": _clean(record.get("last_outcome"), 160),
            "error_type": _clean(record.get("error_type"), 128),
        },
        "intelligence_refresh": (
            dict(refresh)
            if isinstance(refresh, Mapping)
            else {
                "status": "not_recorded",
            }
        ),
        "policy": {
            "admin_read_model_only": True,
            "raw_result_json_not_returned": True,
            "error_detail_not_returned": True,
            "capture_payload_not_returned": True,
            "provider_call_performed": False,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "BACKGROUND_INTELLIGENCE_REFRESH_VERSION",
    "BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION",
    "build_background_intelligence_refresh",
    "persist_background_intelligence_refresh",
    "refresh_completed_job_intelligence",
    "load_background_intelligence_job",
]
