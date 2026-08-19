from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    control_room_admin,
    multimodal_admin,
    product_api,
    usage_admin,
)
from app.workflows import browser_capture_automation


APP_TITLE = "Sportabase API (RSS-first)"
APP_VERSION = "0.3.0"


def create_application() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def register_startup_handler(
    app: FastAPI,
    handler: Callable[[], Any],
) -> None:
    app.add_event_handler(
        "startup",
        handler,
    )


def compose_application(
    *,
    app: FastAPI,
    health_handler: Callable[..., Any],
    ingest_handler: Callable[..., Any],
    stories_handler: Callable[..., Any],
    resolve_content_handler: Callable[..., Any],
    browser_capture_handler: Callable[..., Any],
    analyze_video_handler: Callable[..., Any],
    analyze_handler: Callable[..., Any],
    usage_summary_handler: Callable[..., Any],
    multimodal_shadow_api_enabled: bool,
    require_admin: Callable[..., Any],
    connection_factory: Callable[..., Any],
    gemini_client_factory: Callable[..., Any],
    request_client_key_resolver: Callable[..., Any],
    gemini_generator: Callable[..., Any],
    analysis_version: str,
    scoring_version: str,
    control_room_guard: Callable[..., Any] | None = None,
) -> None:
    app.include_router(
        product_api.build_router(
            health_handler=health_handler,
            ingest_handler=ingest_handler,
            stories_handler=stories_handler,
            resolve_content_handler=(
                resolve_content_handler
            ),
            browser_capture_handler=(
                browser_capture_handler
            ),
            analyze_video_handler=(
                analyze_video_handler
            ),
            analyze_handler=analyze_handler,
        )
    )

    app.include_router(
        usage_admin.build_router(
            usage_summary_handler=(
                usage_summary_handler
            ),
        )
    )

    app.include_router(
        control_room_admin.build_router(
            require_control_room=control_room_guard,
        )
    )

    app.include_router(
        multimodal_admin.build_router(
            multimodal_shadow_api_enabled,
            require_admin,
            connection_factory,
            gemini_client_factory,
            request_client_key_resolver,
            gemini_generator,
            analysis_version,
            scoring_version,
        )
    )

    browser_capture_automation.register_browser_capture_automation_lifecycle(
        app=app,
        connection_factory=connection_factory,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        gemini_client_factory=(
            gemini_client_factory
        ),
        gemini_generator=gemini_generator,
    )
