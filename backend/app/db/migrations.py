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
