from __future__ import annotations

from fastapi import APIRouter, Query, Request


def build_router(
    *,
    usage_summary_handler,
) -> APIRouter:
    router = APIRouter()

    @router.get("/admin/usage/summary")
    def admin_usage_summary(
        request: Request,
        days: int = Query(7, ge=1, le=30),
    ):
        return usage_summary_handler(
            request,
            days,
        )

    return router
