from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, Request

from app.models.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    BrowserCaptureRequest,
    BrowserCaptureResponse,
    ContentResolveRequest,
    ContentResolveResponse,
    IngestResponse,
    Story,
    VideoAnalyzeRequest,
    VideoAnalyzeResponse,
)
from app.operations.analysis_runtime import (
    execute_analysis_with_operational_telemetry,
)
from app.operations.pipeline_runtime import (
    execute_browser_capture_with_operational_telemetry,
)


def build_router(
    *,
    health_handler,
    ingest_handler,
    stories_handler,
    resolve_content_handler,
    browser_capture_handler,
    analyze_video_handler,
    analyze_handler,
    operational_event_recorder=None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        return health_handler()

    @router.post(
        "/ingest",
        response_model=IngestResponse,
    )
    def ingest():
        return ingest_handler()

    @router.get(
        "/stories",
        response_model=List[Story],
    )
    def stories(
        sport: Optional[str] = Query(default=None),
        source: Optional[str] = Query(default=None),
        limit: int = Query(default=30, ge=1, le=200),
    ):
        return stories_handler(
            sport=sport,
            source=source,
            limit=limit,
        )

    @router.post(
        "/resolve-content",
        response_model=ContentResolveResponse,
    )
    def resolve_content(
        req: ContentResolveRequest,
    ):
        return resolve_content_handler(req)

    @router.post(
        "/content/browser-capture",
        response_model=BrowserCaptureResponse,
    )
    def browser_capture_preview(
        req: BrowserCaptureRequest,
    ):
        return execute_browser_capture_with_operational_telemetry(
            handler=browser_capture_handler,
            req=req,
            event_recorder=operational_event_recorder,
        )

    @router.post(
        "/analyze/video",
        response_model=VideoAnalyzeResponse,
    )
    def analyze_video(
        req: VideoAnalyzeRequest,
        request: Request,
    ):
        return execute_analysis_with_operational_telemetry(
            handler=analyze_video_handler,
            req=req,
            request=request,
            mode="video",
            event_recorder=operational_event_recorder,
        )

    @router.post(
        "/analyze",
        response_model=AnalyzeResponse,
    )
    def analyze(
        req: AnalyzeRequest,
        request: Request,
    ):
        return execute_analysis_with_operational_telemetry(
            handler=analyze_handler,
            req=req,
            request=request,
            mode="article",
            event_recorder=operational_event_recorder,
        )

    return router
