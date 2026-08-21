from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
)
from app.operations.persistent_summary import (
    summarize_persistent_operations,
)


def build_router(
    *,
    require_admin,
    database_url: str,
    timeout_seconds: int | float,
    summary_reader=summarize_persistent_operations,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/operations/summary")
    def admin_operations_summary(
        request: Request,
        days: int = Query(7, ge=1, le=30),
    ):
        require_admin(request)

        try:
            return summary_reader(
                database_url=database_url,
                days=days,
                timeout_seconds=timeout_seconds,
            )
        except PersistentOperationsStoreMisconfigured as error:
            raise HTTPException(
                status_code=503,
                detail="Persistent operations telemetry is misconfigured.",
            ) from error
        except PersistentOperationsStoreUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail="Persistent operations telemetry is unavailable.",
            ) from error

    return router


__all__ = ["build_router"]
