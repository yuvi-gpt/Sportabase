from __future__ import annotations

from typing import Any

from app.intelligence.readiness import build_backend_intelligence_readiness
from app.operations.persistent_runtime import (
    PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
)


BACKEND_READINESS_VERSION = "sportabase-backend-readiness-v1"


def build_backend_readiness(
    *,
    app: Any,
    connection_factory,
    operations_database_url: str = "",
) -> dict[str, Any]:
    intelligence = build_backend_intelligence_readiness(
        connection_factory=connection_factory,
    )

    state = getattr(app, "state", None)
    operations_status = str(
        getattr(
            state,
            PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
            "unknown",
        )
        if state is not None
        else "unknown"
    ).strip().casefold() or "unknown"
    operations_configured = bool(str(operations_database_url or "").strip())

    issues: list[str] = []
    intelligence_status = str(intelligence.get("status") or "").strip().casefold()
    if intelligence_status != "ready":
        issues.append("intelligence_store_not_ready")

    if operations_configured and operations_status == "unavailable":
        issues.append("operations_store_unavailable")

    if intelligence_status != "ready":
        status = "not_ready"
    elif operations_configured and operations_status == "unavailable":
        status = "degraded"
    else:
        status = "ready"

    return {
        "version": BACKEND_READINESS_VERSION,
        "status": status,
        "issues": issues,
        "components": {
            "intelligence": intelligence,
            "persistent_operations": {
                "configured": operations_configured,
                "runtime_status": operations_status,
                "required_for_product_requests": False,
            },
        },
        "policy": {
            "read_only": True,
            "no_provider_call_performed": True,
            "operations_telemetry_fails_open": True,
            "intelligence_schema_required": True,
            "raw_content_returned": False,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "BACKEND_READINESS_VERSION",
    "build_backend_readiness",
]
