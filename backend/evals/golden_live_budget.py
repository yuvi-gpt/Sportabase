from __future__ import annotations

import sqlite3
import threading
import time

from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from app.services import gemini_capacity
from app.services import gemini_runtime

from .golden_capture import clean


DEFAULT_MAX_PROVIDER_CALLS = 12
HARD_MAX_PROVIDER_CALLS = 12
DEFAULT_RESERVATION_TIMEOUT_SECONDS = 900


class MultimodalGoldenLiveError(RuntimeError):
    pass


class MultimodalGoldenLiveInputError(MultimodalGoldenLiveError):
    pass


class MultimodalGoldenLiveBudgetExceeded(MultimodalGoldenLiveError):
    pass


class MultimodalGoldenLiveProviderError(MultimodalGoldenLiveError):
    pass


def bounded_calls(value: Any) -> int:
    if isinstance(value, bool):
        raise MultimodalGoldenLiveInputError(
            "Provider call budget must be an integer."
        )
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalGoldenLiveInputError(
            "Provider call budget must be an integer."
        ) from error
    if result < 0 or result > HARD_MAX_PROVIDER_CALLS:
        raise MultimodalGoldenLiveInputError(
            "Provider call budget must be between 0 and "
            + str(HARD_MAX_PROVIDER_CALLS)
            + "."
        )
    return result


def analytics_usage_day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def sqlite_connection_factory(
    db_path: str | Path,
) -> Callable[[], sqlite3.Connection]:
    path = Path(db_path).resolve()

    def factory() -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn

    return factory


def _usage_value(usage: Any, field: str) -> int:
    if usage is None:
        return 0
    raw = (
        usage.get(field)
        if isinstance(usage, Mapping)
        else getattr(usage, field, 0)
    )
    if isinstance(raw, bool):
        return 0
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def response_usage_counts(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = _usage_value(
        usage,
        "prompt_token_count",
    )
    output_tokens = _usage_value(
        usage,
        "candidates_token_count",
    )
    thought_tokens = _usage_value(
        usage,
        "thoughts_token_count",
    )
    cached_tokens = _usage_value(
        usage,
        "cached_content_token_count",
    )
    total_tokens = _usage_value(
        usage,
        "total_token_count",
    )
    if total_tokens <= 0:
        total_tokens = (
            prompt_tokens
            + output_tokens
            + thought_tokens
        )
    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thought_tokens": thought_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
    }


def _usage_columns(
    conn: sqlite3.Connection,
) -> set[str]:
    return {
        str(row["name"])
        if hasattr(row, "keys")
        else str(row[1])
        for row in conn.execute(
            "PRAGMA table_info(gemini_usage)"
        ).fetchall()
    }


def _provider_day_from_created_at(
    value: Any,
) -> str:
    try:
        parsed = datetime.fromisoformat(
            str(value or "")
        )
    except (TypeError, ValueError):
        return ""

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return gemini_capacity.provider_usage_day(
        parsed
    )


def _ensure_capacity_usage_schema(
    usage_connection_factory,
) -> None:
    """
    Narrow #34B compatibility migration.

    Only gemini_usage capacity fields/indexes are touched.
    No story, claim, evidence, Merit, cache, or analysis
    production tables are migrated here.
    """

    conn = usage_connection_factory()

    try:
        conn.execute("BEGIN IMMEDIATE")

        columns = _usage_columns(conn)

        required = {
            "provider_day":
                "TEXT NOT NULL DEFAULT ''",

            "estimated_prompt_tokens":
                "INTEGER NOT NULL DEFAULT 0",

            "inflight_join":
                "INTEGER NOT NULL DEFAULT 0",

            "latency_ms":
                "INTEGER NOT NULL DEFAULT 0",

            "failure_status_code":
                "INTEGER",

            "failure_type":
                "TEXT NOT NULL DEFAULT ''",

            "failure_detail":
                "TEXT NOT NULL DEFAULT ''",
        }

        for name, definition in required.items():
            if name in columns:
                continue

            conn.execute(
                "ALTER TABLE gemini_usage "
                f"ADD COLUMN {name} "
                f"{definition}"
            )

        rows = conn.execute(
            """
            SELECT id, created_at
            FROM gemini_usage
            WHERE provider_day = ''
              AND cache_hit = 0
              AND inflight_join = 0
            """
        ).fetchall()

        for row in rows:
            usage_id = (
                int(row["id"])
                if hasattr(row, "keys")
                else int(row[0])
            )

            created_at = (
                row["created_at"]
                if hasattr(row, "keys")
                else row[1]
            )

            day = (
                _provider_day_from_created_at(
                    created_at
                )
            )

            if not day:
                continue

            conn.execute(
                """
                UPDATE gemini_usage
                SET provider_day = ?
                WHERE id = ?
                """,
                (
                    day,
                    usage_id,
                ),
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_gemini_usage_model_provider_day
            ON gemini_usage(
              model,
              provider_day
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_gemini_usage_model_created_at
            ON gemini_usage(
              model,
              created_at
            )
            """
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def capacity_snapshot(
    *,
    usage_connection_factory,
    model: str,
    client_keys: Sequence[str],
    required_calls: int,
    max_calls_per_client: int,
) -> Dict[str, Any]:

    model_name = (
        gemini_capacity.normalized_model_name(
            model
        )
    )

    policy = (
        gemini_capacity.capacity_policy_for_model(
            model_name
        )
    )

    global_cap, client_cap = (
        gemini_capacity.sportabase_daily_caps(
            policy
        )
    )

    provider_day = (
        gemini_capacity.provider_usage_day()
    )

    statuses = {
        "reserved",
        "success",
        "failed",
        "expired",
    }

    normalized_clients = [
        clean(value)
        for value in client_keys
    ]

    client_used = {
        key: 0
        for key in normalized_clients
    }

    global_used = 0
    model_used = 0

    conn = usage_connection_factory()

    try:
        columns = _usage_columns(conn)

        rows = conn.execute(
            "SELECT * FROM gemini_usage"
        ).fetchall()

        for row in rows:
            if int(
                row["cache_hit"]
                or 0
            ):
                continue

            if (
                "inflight_join"
                in columns
                and int(
                    row["inflight_join"]
                    or 0
                )
            ):
                continue

            if str(
                row["status"]
                or ""
            ) not in statuses:
                continue

            row_day = ""

            if (
                "provider_day"
                in columns
            ):
                row_day = str(
                    row["provider_day"]
                    or ""
                ).strip()

            if not row_day:
                row_day = (
                    _provider_day_from_created_at(
                        row["created_at"]
                    )
                )

            if row_day != provider_day:
                continue

            global_used += 1

            row_model = (
                gemini_capacity
                .normalized_model_name(
                    row["model"]
                )
            )

            if row_model == model_name:
                model_used += 1

            row_client = str(
                row["client_key"]
                or ""
            ).strip()

            if row_client in client_used:
                client_used[
                    row_client
                ] += 1

    finally:
        conn.close()

    global_remaining = max(
        0,
        int(global_cap)
        - global_used,
    )

    model_remaining = max(
        0,
        int(policy.usable_rpd)
        - model_used,
    )

    client_remaining = {
        key: max(
            0,
            int(client_cap) - used,
        )
        for key, used
        in client_used.items()
    }

    failures = []

    if (
        global_remaining
        < int(required_calls)
    ):
        failures.append(
            "insufficient_global_provider_day_capacity"
        )

    if (
        model_remaining
        < int(required_calls)
    ):
        failures.append(
            "insufficient_model_provider_day_capacity"
        )

    for (
        key,
        remaining,
    ) in client_remaining.items():

        if (
            remaining
            < int(
                max_calls_per_client
            )
        ):
            failures.append(
                "insufficient_eval_client_capacity:"
                + key
            )

    return {
        "policy_version":
            policy.version,

        "model":
            model_name,

        "provider_day":
            provider_day,

        "provider_timezone":
            gemini_capacity
            .PROVIDER_TIMEZONE_NAME,

        "provider_rpm":
            policy.provider_rpm,

        "dispatch_rpm":
            policy.dispatch_rpm,

        "minimum_dispatch_interval_seconds":
            policy
            .minimum_dispatch_interval_seconds,

        "provider_tpm":
            policy.provider_tpm,

        "usable_tpm":
            policy.usable_tpm,

        "max_estimated_input_tokens":
            policy.max_estimated_input_tokens,

        "provider_rpd":
            policy.provider_rpd,

        "rpd_reserve":
            policy.rpd_reserve,

        "usable_rpd":
            policy.usable_rpd,

        "global_daily_call_cap":
            global_cap,

        "client_daily_call_cap":
            client_cap,

        "global_used":
            global_used,

        "global_remaining":
            global_remaining,

        "model_used":
            model_used,

        "model_remaining":
            model_remaining,

        "client_used":
            client_used,

        "client_remaining":
            client_remaining,

        "required_calls":
            int(required_calls),

        "max_calls_per_client":
            int(max_calls_per_client),

        "ready":
            not failures,

        "failures":
            failures,

        "tpm_guarded_per_call":
            True,

        "cross_model_quota_pooling":
            False,

        "legacy_usage_schema_read_compatible":
            True,
    }


class _ProviderStartModels:
    def __init__(
        self,
        *,
        real_models,
        on_start: Callable[[], None],
    ):
        self._real_models = real_models
        self._on_start = on_start

    def generate_content(
        self,
        *,
        model,
        contents,
    ):
        self._on_start()
        return self._real_models.generate_content(
            model=model,
            contents=contents,
        )


class _ProviderStartClient:
    def __init__(
        self,
        *,
        real_client,
        on_start: Callable[[], None],
    ):
        self.models = _ProviderStartModels(
            real_models=real_client.models,
            on_start=on_start,
        )


class BudgetedGeminiGenerator:
    """Bounded #34B generator routed through the #34A capacity runtime."""

    def __init__(
        self,
        *,
        usage_connection_factory,
        max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
        event_sink: Optional[
            Callable[[Mapping[str, Any]], None]
        ] = None,
        reservation_timeout_seconds: int = (
            DEFAULT_RESERVATION_TIMEOUT_SECONDS
        ),
        sleep_func: Callable[[float], None] = time.sleep,
        runtime_generator=(
            gemini_runtime.generate_gemini_content
        ),
    ):
        if usage_connection_factory is None:
            raise MultimodalGoldenLiveInputError(
                "Usage connection factory is required."
            )
        self.usage_connection_factory = (
            usage_connection_factory
        )
        self.max_calls = bounded_calls(max_calls)

        if self.max_calls > 0:
            _ensure_capacity_usage_schema(
                self.usage_connection_factory
            )
        self.calls: list[Dict[str, Any]] = []
        self.budget_exhausted = False
        self.event_sink = event_sink
        self.reservation_timeout_seconds = max(
            60,
            int(reservation_timeout_seconds),
        )
        self.sleep_func = sleep_func
        self.runtime_generator = runtime_generator
        self._inflight_lock = threading.Lock()
        self._inflight_calls = {}

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _token_totals(self) -> Dict[str, int]:
        fields = (
            "prompt_tokens",
            "output_tokens",
            "thought_tokens",
            "cached_tokens",
            "total_tokens",
        )
        return {
            field: sum(
                int(row.get(field) or 0)
                for row in self.calls
            )
            for field in fields
        }

    def _emit(
        self,
        event: str,
        row: Mapping[str, Any],
    ) -> None:
        if not callable(self.event_sink):
            return
        totals = self._token_totals()
        payload = {
            "event": event,
            "call_index": int(
                row.get("call_index") or 0
            ),
            "max_calls": self.max_calls,
            "mode": clean(row.get("mode")),
            "model": clean(row.get("model")),
            "status": clean(row.get("status")),
            "prompt_tokens": int(
                row.get("prompt_tokens") or 0
            ),
            "output_tokens": int(
                row.get("output_tokens") or 0
            ),
            "thought_tokens": int(
                row.get("thought_tokens") or 0
            ),
            "cached_tokens": int(
                row.get("cached_tokens") or 0
            ),
            "total_tokens": int(
                row.get("total_tokens") or 0
            ),
            "remaining_calls": max(
                0,
                self.max_calls - self.call_count,
            ),
            "cumulative_calls": self.call_count,
            "cumulative_prompt_tokens": (
                totals["prompt_tokens"]
            ),
            "cumulative_output_tokens": (
                totals["output_tokens"]
            ),
            "cumulative_thought_tokens": (
                totals["thought_tokens"]
            ),
            "cumulative_cached_tokens": (
                totals["cached_tokens"]
            ),
            "cumulative_total_tokens": (
                totals["total_tokens"]
            ),
        }
        self.event_sink(payload)

    def _max_usage_id(self) -> int:
        conn = self.usage_connection_factory()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) "
                "FROM gemini_usage"
            ).fetchone()
            return int(row[0] or 0)
        finally:
            conn.close()

    def _new_provider_rows(
        self,
        *,
        after_id: int,
        client_key: str,
        mode: str,
        model: str,
    ) -> list[Dict[str, Any]]:
        normalized_model = (
            gemini_capacity.normalized_model_name(
                model
            )
        )
        conn = self.usage_connection_factory()
        try:
            rows = conn.execute(
                """
                SELECT
                  id,
                  provider_day,
                  client_key,
                  mode,
                  model,
                  status,
                  prompt_tokens,
                  output_tokens,
                  thought_tokens,
                  total_tokens,
                  latency_ms,
                  failure_status_code,
                  failure_type
                FROM gemini_usage
                WHERE id > ?
                  AND client_key = ?
                  AND mode = ?
                  AND model = ?
                  AND cache_hit = 0
                  AND inflight_join = 0
                ORDER BY id
                """,
                (
                    int(after_id),
                    clean(client_key),
                    clean(mode),
                    normalized_model,
                ),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def _begin_row(
        self,
        *,
        client_key: str,
        mode: str,
        model: str,
    ) -> Dict[str, Any]:
        if self.call_count >= self.max_calls:
            self.budget_exhausted = True
            raise MultimodalGoldenLiveBudgetExceeded(
                "Live golden evaluation reached its "
                "provider call budget before provider dispatch."
            )
        row = {
            "call_index": self.call_count + 1,
            "client_key": clean(client_key),
            "mode": clean(mode),
            "model": clean(model),
            "status": "started",
            "usage_id": 0,
            "provider_day": "",
            "prompt_tokens": 0,
            "output_tokens": 0,
            "thought_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        }
        self.calls.append(row)
        self._emit(
            "provider_call_started",
            row,
        )
        return row

    def _capacity_runtime_call(
        self,
        *,
        client,
        client_key: str,
        mode: str,
        model: str,
        contents,
        on_start: Callable[[], None],
    ):
        policy = (
            gemini_capacity.capacity_policy_for_model(
                model
            )
        )
        global_cap, client_cap = (
            gemini_capacity.sportabase_daily_caps(
                policy
            )
        )
        expire = partial(
            gemini_runtime.expire_stale_gemini_reservations,
            reservation_timeout_seconds=(
                self.reservation_timeout_seconds
            ),
        )
        reserve = partial(
            gemini_runtime.reserve_gemini_call,
            usage_day_resolver=analytics_usage_day,
            connection_factory=(
                self.usage_connection_factory
            ),
            expire_reservations=expire,
            global_daily_call_cap=global_cap,
            client_daily_call_cap=client_cap,
        )
        finish = partial(
            gemini_runtime.finish_gemini_call,
            usage_counter=(
                gemini_runtime.usage_metadata_counts
            ),
            connection_factory=(
                self.usage_connection_factory
            ),
        )
        record_join = partial(
            gemini_runtime.record_inflight_gemini_join,
            connection_factory=(
                self.usage_connection_factory
            ),
            usage_day_resolver=analytics_usage_day,
        )
        proxy = _ProviderStartClient(
            real_client=client,
            on_start=on_start,
        )
        return self.runtime_generator(
            client=proxy,
            client_key=clean(client_key),
            mode=clean(mode),
            model=clean(model),
            contents=contents,
            inflight_lock=self._inflight_lock,
            inflight_calls=self._inflight_calls,
            fingerprint_resolver=(
                gemini_runtime.gemini_request_fingerprint
            ),
            reserve_call=reserve,
            finish_call=finish,
            classify_failure=(
                gemini_runtime.classify_gemini_failure
            ),
            record_join=record_join,
            sleep_func=self.sleep_func,
        )

    def __call__(
        self,
        *,
        client,
        client_key: str,
        mode: str,
        model: str,
        contents,
    ):
        if self.call_count >= self.max_calls:
            self.budget_exhausted = True
            raise MultimodalGoldenLiveBudgetExceeded(
                "Live golden evaluation reached its "
                "provider call budget."
            )
        if client is None or not hasattr(
            client,
            "models",
        ):
            raise MultimodalGoldenLiveProviderError(
                "Gemini client is unavailable."
            )
        if not clean(model):
            raise MultimodalGoldenLiveProviderError(
                "Gemini model name is required."
            )

        before_id = self._max_usage_id()
        started: Dict[str, Any] | None = None

        def on_start() -> None:
            nonlocal started
            if started is not None:
                raise MultimodalGoldenLiveProviderError(
                    "Provider start hook fired more than once."
                )
            started = self._begin_row(
                client_key=client_key,
                mode=mode,
                model=model,
            )

        try:
            response = self._capacity_runtime_call(
                client=client,
                client_key=client_key,
                mode=mode,
                model=model,
                contents=contents,
                on_start=on_start,
            )
        except MultimodalGoldenLiveError:
            if started is not None:
                started["status"] = "failed"
                self._emit(
                    "provider_call_failed",
                    started,
                )
            raise
        except Exception as error:
            if started is not None:
                rows = self._new_provider_rows(
                    after_id=before_id,
                    client_key=client_key,
                    mode=mode,
                    model=model,
                )
                if len(rows) == 1:
                    ledger = rows[0]
                    started["usage_id"] = int(
                        ledger.get("id") or 0
                    )
                    started["provider_day"] = clean(
                        ledger.get("provider_day")
                    )
                    started["status"] = clean(
                        ledger.get("status")
                    ) or "failed"
                else:
                    started["status"] = "failed"
                started["error_type"] = (
                    type(error).__name__
                )
                self._emit(
                    "provider_call_failed",
                    started,
                )
            raise MultimodalGoldenLiveProviderError(
                "#34A-managed Gemini call failed."
            ) from error

        if started is None:
            raise MultimodalGoldenLiveProviderError(
                "Capacity runtime returned without a provider dispatch."
            )

        rows = self._new_provider_rows(
            after_id=before_id,
            client_key=client_key,
            mode=mode,
            model=model,
        )
        if len(rows) != 1:
            raise MultimodalGoldenLiveProviderError(
                "Provider call did not reconcile to exactly one "
                "production Gemini usage row."
            )

        ledger = rows[0]
        if clean(ledger.get("status")) != "success":
            raise MultimodalGoldenLiveProviderError(
                "Provider call ledger row is not successful."
            )

        counts = response_usage_counts(response)
        for field in (
            "prompt_tokens",
            "output_tokens",
            "thought_tokens",
            "total_tokens",
        ):
            if int(ledger.get(field) or 0) != int(
                counts[field]
            ):
                raise MultimodalGoldenLiveProviderError(
                    "Provider usage metadata does not match "
                    "the #34A Gemini ledger: "
                    + field
                )

        started.update(
            {
                "status": "completed",
                "usage_id": int(
                    ledger.get("id") or 0
                ),
                "provider_day": clean(
                    ledger.get("provider_day")
                ),
                **counts,
            }
        )
        self._emit(
            "provider_call_completed",
            started,
        )
        return response

    def summary(self) -> Dict[str, Any]:
        by_mode: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        by_client: Dict[str, int] = {}

        for row in self.calls:
            mode = clean(row.get("mode"))
            model = clean(row.get("model"))
            client_key = clean(row.get("client_key"))
            if mode:
                by_mode[mode] = (
                    by_mode.get(mode, 0) + 1
                )
            if model:
                by_model[model] = (
                    by_model.get(model, 0) + 1
                )
            if client_key:
                by_client[client_key] = (
                    by_client.get(client_key, 0) + 1
                )

        totals = self._token_totals()
        safe_log = []
        for row in self.calls:
            safe = {
                "call_index": int(
                    row.get("call_index") or 0
                ),
                "usage_id": int(
                    row.get("usage_id") or 0
                ),
                "provider_day": clean(
                    row.get("provider_day")
                ),
                "mode": clean(row.get("mode")),
                "model": clean(row.get("model")),
                "status": clean(row.get("status")),
                "prompt_tokens": int(
                    row.get("prompt_tokens") or 0
                ),
                "output_tokens": int(
                    row.get("output_tokens") or 0
                ),
                "thought_tokens": int(
                    row.get("thought_tokens") or 0
                ),
                "cached_tokens": int(
                    row.get("cached_tokens") or 0
                ),
                "total_tokens": int(
                    row.get("total_tokens") or 0
                ),
            }
            if clean(row.get("error_type")):
                safe["error_type"] = clean(
                    row.get("error_type")
                )
            safe_log.append(safe)

        return {
            "call_count": self.call_count,
            "max_calls": self.max_calls,
            "budget_exhausted": self.budget_exhausted,
            "remaining_calls": max(
                0,
                self.max_calls - self.call_count,
            ),
            "calls_by_mode": dict(
                sorted(by_mode.items())
            ),
            "calls_by_model": dict(
                sorted(by_model.items())
            ),
            "calls_by_eval_client": dict(
                sorted(by_client.items())
            ),
            **totals,
            "call_log": safe_log,
            "production_usage_ledger_written": True,
            "capacity_runtime_version": (
                gemini_capacity.GEMINI_CAPACITY_POLICY_VERSION
            ),
        }


__all__ = [
    "DEFAULT_MAX_PROVIDER_CALLS",
    "HARD_MAX_PROVIDER_CALLS",
    "DEFAULT_RESERVATION_TIMEOUT_SECONDS",
    "MultimodalGoldenLiveError",
    "MultimodalGoldenLiveInputError",
    "MultimodalGoldenLiveBudgetExceeded",
    "MultimodalGoldenLiveProviderError",
    "bounded_calls",
    "analytics_usage_day",
    "sqlite_connection_factory",
    "response_usage_counts",
    "capacity_snapshot",
    "BudgetedGeminiGenerator",
]
