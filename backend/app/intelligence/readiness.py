from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


BACKEND_INTELLIGENCE_READINESS_VERSION = "backend-intelligence-readiness-v1"
_MAX_STRUCTURED_METADATA_ROWS = 5000

_REQUIRED_TABLES = (
    "canonical_entities",
    "intelligence_claims",
    "claim_links",
    "claim_identity_mappings",
    "claim_evolution_links",
    "source_observations",
    "evidence_records",
    "story_claim_links",
)

_REQUIRED_INDEXES = (
    "idx_claim_identity_mappings_canonical",
    "idx_claim_identity_mappings_subject",
    "idx_claim_evolution_predecessor",
    "idx_claim_evolution_successor",
    "idx_claim_evolution_family",
    "idx_claim_evolution_subject",
)


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


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


def _count(conn, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return 0
    return int(row[0])


def _policy() -> dict[str, bool]:
    return {
        "read_only": True,
        "no_provider_call_performed": True,
        "no_model_call_performed": True,
        "raw_content_returned": False,
        "raw_urls_returned": False,
        "affects_live_merit": False,
        "readiness_does_not_establish_truth": True,
        "readiness_does_not_establish_authority": True,
    }


def build_backend_intelligence_readiness(
    *,
    connection_factory,
) -> dict[str, Any]:
    """Return a bounded, privacy-minimized backend readiness report.

    This audit is intentionally read-only. It validates that the durable claim
    identity/evolution schema exists and checks referential/runtime invariants
    that should hold before staging traffic is allowed to rely on the new
    intelligence path.
    """

    if connection_factory is None:
        raise ValueError("Backend readiness requires database access.")

    base = {
        "version": BACKEND_INTELLIGENCE_READINESS_VERSION,
        "status": "not_ready",
        "checks": {},
        "counts": {},
        "issues": [],
        "policy": _policy(),
    }

    try:
        conn = connection_factory()
    except Exception as error:
        return {
            **base,
            "status": "unavailable",
            "issues": ["database_connection_failed"],
            "error_type": type(error).__name__,
        }

    try:
        conn.execute("SELECT 1").fetchone()

        tables = {
            str(row["name"] if hasattr(row, "keys") else row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        indexes = {
            str(row["name"] if hasattr(row, "keys") else row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
            if (row["name"] if hasattr(row, "keys") else row[0])
        }

        missing_tables = [name for name in _REQUIRED_TABLES if name not in tables]
        missing_indexes = [name for name in _REQUIRED_INDEXES if name not in indexes]

        checks: dict[str, Any] = {
            "database_query": "pass",
            "required_tables": "pass" if not missing_tables else "fail",
            "required_indexes": "pass" if not missing_indexes else "fail",
        }
        issues: list[str] = []

        if missing_tables:
            issues.append("missing_required_tables")
        if missing_indexes:
            issues.append("missing_required_indexes")

        counts: dict[str, int] = {}

        if "intelligence_claims" in tables:
            counts["claims"] = _count(conn, "SELECT COUNT(*) FROM intelligence_claims")
            counts["structured_claims"] = _count(
                conn,
                "SELECT COUNT(*) FROM intelligence_claims WHERE claim_type LIKE 'structured_%'",
            )
        else:
            counts["claims"] = 0
            counts["structured_claims"] = 0

        if "claim_identity_mappings" in tables:
            counts["identity_mappings"] = _count(
                conn,
                "SELECT COUNT(*) FROM claim_identity_mappings",
            )
            orphan_mappings = _count(
                conn,
                """
                SELECT COUNT(*)
                FROM claim_identity_mappings m
                LEFT JOIN intelligence_claims p
                  ON p.id = m.production_claim_id
                LEFT JOIN intelligence_claims c
                  ON c.id = m.canonical_claim_id
                WHERE p.id IS NULL OR c.id IS NULL
                """,
            )
        else:
            counts["identity_mappings"] = 0
            orphan_mappings = 0

        if "claim_evolution_links" in tables:
            counts["evolution_links"] = _count(
                conn,
                "SELECT COUNT(*) FROM claim_evolution_links",
            )
            orphan_evolution_links = _count(
                conn,
                """
                SELECT COUNT(*)
                FROM claim_evolution_links e
                LEFT JOIN intelligence_claims p
                  ON p.id = e.predecessor_claim_id
                LEFT JOIN intelligence_claims s
                  ON s.id = e.successor_claim_id
                WHERE p.id IS NULL OR s.id IS NULL
                """,
            )
        else:
            counts["evolution_links"] = 0
            orphan_evolution_links = 0

        counts["orphan_identity_mappings"] = orphan_mappings
        counts["orphan_evolution_links"] = orphan_evolution_links
        checks["identity_mapping_references"] = (
            "pass" if orphan_mappings == 0 else "fail"
        )
        checks["evolution_link_references"] = (
            "pass" if orphan_evolution_links == 0 else "fail"
        )
        if orphan_mappings:
            issues.append("orphan_identity_mappings")
        if orphan_evolution_links:
            issues.append("orphan_evolution_links")

        malformed_structured_metadata = 0
        scanned_structured_metadata = 0
        structured_metadata_truncated = False

        if "intelligence_claims" in tables:
            rows = conn.execute(
                """
                SELECT metadata_json
                FROM intelligence_claims
                WHERE claim_type LIKE 'structured_%'
                ORDER BY first_seen_at, id
                LIMIT ?
                """,
                (_MAX_STRUCTURED_METADATA_ROWS + 1,),
            ).fetchall()
            structured_metadata_truncated = len(rows) > _MAX_STRUCTURED_METADATA_ROWS
            rows = rows[:_MAX_STRUCTURED_METADATA_ROWS]
            scanned_structured_metadata = len(rows)
            for row in rows:
                raw = row["metadata_json"] if hasattr(row, "keys") else row[0]
                metadata = _json_object(raw)
                candidate = metadata.get("structured_claim")
                if (
                    not isinstance(candidate, Mapping)
                    or not _clean(metadata.get("core_fingerprint"), 128)
                ):
                    malformed_structured_metadata += 1

        counts["structured_metadata_rows_scanned"] = scanned_structured_metadata
        counts["malformed_structured_metadata"] = malformed_structured_metadata
        checks["structured_claim_metadata"] = (
            "pass" if malformed_structured_metadata == 0 else "fail"
        )
        if malformed_structured_metadata:
            issues.append("malformed_structured_claim_metadata")

        status = "ready" if not issues else "not_ready"

        return {
            **base,
            "status": status,
            "checks": checks,
            "counts": counts,
            "issues": issues,
            "details": {
                "missing_tables": missing_tables,
                "missing_indexes": missing_indexes,
                "structured_metadata_scan_truncated": structured_metadata_truncated,
                "structured_metadata_scan_limit": _MAX_STRUCTURED_METADATA_ROWS,
            },
        }
    except Exception as error:
        return {
            **base,
            "status": "unavailable",
            "checks": {"database_query": "fail"},
            "issues": ["readiness_query_failed"],
            "error_type": type(error).__name__,
        }
    finally:
        conn.close()


__all__ = [
    "BACKEND_INTELLIGENCE_READINESS_VERSION",
    "build_backend_intelligence_readiness",
]
