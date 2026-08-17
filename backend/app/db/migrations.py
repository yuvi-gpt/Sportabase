from datetime import datetime, timezone
from zoneinfo import ZoneInfo


_PROVIDER_TIMEZONE = ZoneInfo(
    "America/Los_Angeles"
)


def _provider_day_for_created_at(
    value,
) -> str:
    try:
        parsed = datetime.fromisoformat(
            str(value or "")
        )
    except (TypeError, ValueError):
        return ""

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc,
        )

    return (
        parsed
        .astimezone(_PROVIDER_TIMEZONE)
        .date()
        .isoformat()
    )


def initialize_database(
    connection_factory,
    schema: str,
) -> None:
    conn = connection_factory()

    try:
        conn.executescript(schema)

        existing_columns = {
            str(row["name"])
            for row in conn.execute(
                "PRAGMA table_info(gemini_usage)"
            ).fetchall()
        }

        migration_columns = {
            "provider_day": (
                "TEXT NOT NULL DEFAULT ''"
            ),
            "estimated_prompt_tokens": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "inflight_join": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "latency_ms": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "failure_status_code": "INTEGER",
            "failure_type": (
                "TEXT NOT NULL DEFAULT ''"
            ),
            "failure_detail": (
                "TEXT NOT NULL DEFAULT ''"
            ),
        }

        for (
            column_name,
            column_definition,
        ) in migration_columns.items():
            if column_name in existing_columns:
                continue

            conn.execute(
                "ALTER TABLE gemini_usage "
                f"ADD COLUMN {column_name} "
                f"{column_definition}"
            )

        legacy_provider_rows = conn.execute(
            """
            SELECT id, created_at
            FROM gemini_usage
            WHERE provider_day = ''
              AND cache_hit = 0
              AND inflight_join = 0
            """
        ).fetchall()

        for row in legacy_provider_rows:
            if hasattr(row, "keys"):
                usage_id = int(row["id"])
                created_at = row["created_at"]
            else:
                usage_id = int(row[0])
                created_at = row[1]

            provider_day = (
                _provider_day_for_created_at(
                    created_at
                )
            )

            if not provider_day:
                continue

            conn.execute(
                """
                UPDATE gemini_usage
                SET provider_day = ?
                WHERE id = ?
                """,
                (
                    provider_day,
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

        snapshot_columns = {
            str(row["name"])
            for row in conn.execute(
                (
                    "PRAGMA table_info("
                    "analysis_snapshots)"
                )
            ).fetchall()
        }

        if (
            "context_hash"
            not in snapshot_columns
        ):
            conn.execute(
                (
                    "ALTER TABLE "
                    "analysis_snapshots "
                    "ADD COLUMN context_hash "
                    "TEXT NOT NULL DEFAULT ''"
                )
            )

        conn.execute(
            "DROP INDEX IF EXISTS "
            "idx_analysis_snapshots_identity"
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX
            idx_analysis_snapshots_identity
            ON analysis_snapshots(
              media_item_id,
              mode,
              content_hash,
              context_hash,
              analysis_version,
              scoring_version
            )
            """
        )

        conn.commit()

    finally:
        conn.close()
