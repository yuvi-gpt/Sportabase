from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, Request

from app.intelligence.article_product_runtime import (
    attach_article_product_intelligence,
)
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
from app.operations.telemetry_context import (
    invoke_with_operational_event_recorder,
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
    connection_factory=None,
) -> APIRouter:
    router = APIRouter()

    def track(request, req, kind):
        account = getattr(request.state, "account", None)
        if account and connection_factory:
            from app.accounts.store import record_analysis_best_effort
            record_analysis_best_effort(connection_factory, account["id"], request.state.device_id,
                                        kind, getattr(req, "title", ""), req.url)


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
        def invoke_handler(value):
            return invoke_with_operational_event_recorder(
                handler=browser_capture_handler,
                recorder=operational_event_recorder,
                args=(value,),
            )

        return execute_browser_capture_with_operational_telemetry(
            handler=invoke_handler,
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
        response = execute_analysis_with_operational_telemetry(
            handler=analyze_video_handler,
            req=req,
            request=request,
            mode="video",
            event_recorder=operational_event_recorder,
        )
        track(request, req, "video")
        return response

    @router.post(
        "/analyze",
        response_model=AnalyzeResponse,
    )
    def analyze(
        req: AnalyzeRequest,
        request: Request,
    ):
        response = execute_analysis_with_operational_telemetry(
            handler=analyze_handler,
            req=req,
            request=request,
            mode="article",
            event_recorder=operational_event_recorder,
        )

        track(request, req, "article")
        return attach_article_product_intelligence(
            response=response,
            url=req.url,
            connection_factory=connection_factory,
        )

    return router
