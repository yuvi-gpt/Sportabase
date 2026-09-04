from __future__ import annotations

from contextlib import asynccontextmanager
from inspect import isawaitable
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.config import (
    PERSISTENT_OPERATIONS_CONNECT_TIMEOUT_SECONDS,
    PERSISTENT_OPERATIONS_DATABASE_URL,
    PERSISTENT_OPERATIONS_EVENT_TIMEOUT_SECONDS,
    PERSISTENT_OPERATIONS_SERVICE_NAME,
)
from app.operations import job_worker_runtime as browser_capture_automation
from app.operations.persistent_runtime import (
    build_persistent_operations_event_recorder,
    build_persistent_operations_startup_handler,
)
from app.routes import (
    control_room_admin,
    intelligence_admin,
    intelligence_product,
    intelligence_runtime_admin,
    multimodal_admin,
    operations_admin,
    product_api,
    usage_admin,
    watchlists_product,
)
from app.security.control_room_runtime import (
    build_default_control_room_guard,
)


APP_TITLE = "Sportabase API (RSS-first)"
APP_VERSION = "0.3.0"
SPORTABASE_LIFESPAN_VERSION = "sportabase-fastapi-lifespan-v1"

_LIFESPAN_MANAGED_STATE = "_sportabase_lifespan_managed"
_STARTUP_HANDLERS_STATE = "_sportabase_startup_handlers"
_SHUTDOWN_HANDLERS_STATE = "_sportabase_shutdown_handlers"


def _managed_lifespan_handlers(
    app: FastAPI,
    state_name: str,
) -> list[Callable[[], Any]]:
    state = getattr(app, "state", None)
    if state is None:
        raise RuntimeError(
            "Sportabase application lifecycle requires FastAPI state."
        )

    handlers = getattr(state, state_name, None)
    if handlers is None:
        handlers = []
        setattr(state, state_name, handlers)

    return handlers


async def _run_lifecycle_handler(
    handler: Callable[[], Any],
) -> None:
    result = handler()
    if isawaitable(result):
        await result


@asynccontextmanager
async def _application_lifespan(app: FastAPI):
    startup_handlers = tuple(
        _managed_lifespan_handlers(
            app,
            _STARTUP_HANDLERS_STATE,
        )
    )

    for handler in startup_handlers:
        await _run_lifecycle_handler(handler)

    try:
        yield
    finally:
        shutdown_handlers = tuple(
            _managed_lifespan_handlers(
                app,
                _SHUTDOWN_HANDLERS_STATE,
            )
        )
        for handler in shutdown_handlers:
            await _run_lifecycle_handler(handler)


def _uses_managed_lifespan(app: object) -> bool:
    state = getattr(app, "state", None)
    return bool(
        state is not None
        and getattr(state, _LIFESPAN_MANAGED_STATE, False)
    )


def register_startup_handler(
    app: FastAPI,
    handler: Callable[[], Any],
) -> None:
    if not callable(handler):
        raise TypeError("Startup handler must be callable.")

    if _uses_managed_lifespan(app):
        _managed_lifespan_handlers(
            app,
            _STARTUP_HANDLERS_STATE,
        ).append(handler)
        return

    legacy_registrar = getattr(app, "add_event_handler", None)

    if not callable(legacy_registrar):
        router = getattr(app, "router", None)
        legacy_registrar = getattr(
            router,
            "add_event_handler",
            None,
        )

    if callable(legacy_registrar):
        legacy_registrar("startup", handler)
        return

    raise RuntimeError(
        "Application does not support Sportabase startup registration."
    )


def register_shutdown_handler(
    app: FastAPI,
    handler: Callable[[], Any],
) -> None:
    if not callable(handler):
        raise TypeError("Shutdown handler must be callable.")

    if _uses_managed_lifespan(app):
        _managed_lifespan_handlers(
            app,
            _SHUTDOWN_HANDLERS_STATE,
        ).append(handler)
        return

    legacy_registrar = getattr(app, "add_event_handler", None)

    if not callable(legacy_registrar):
        router = getattr(app, "router", None)
        legacy_registrar = getattr(
            router,
            "add_event_handler",
            None,
        )

    if callable(legacy_registrar):
        legacy_registrar("shutdown", handler)
        return

    raise RuntimeError(
        "Application does not support Sportabase shutdown registration."
    )


def _install_event_handler_compatibility(app: FastAPI) -> None:
    """Bridge legacy internal registrars onto the supported lifespan API."""

    def add_event_handler(
        event_type: str,
        handler: Callable[[], Any],
    ) -> None:
        normalized = str(event_type or "").strip().casefold()
        if normalized == "startup":
            register_startup_handler(app, handler)
            return
        if normalized == "shutdown":
            register_shutdown_handler(app, handler)
            return
        raise ValueError(
            "Sportabase lifecycle compatibility only supports startup/shutdown."
        )

    setattr(app, "add_event_handler", add_event_handler)


def create_application() -> FastAPI:
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        lifespan=_application_lifespan,
    )

    setattr(app.state, _LIFESPAN_MANAGED_STATE, True)
    _managed_lifespan_handlers(app, _STARTUP_HANDLERS_STATE)
    _managed_lifespan_handlers(app, _SHUTDOWN_HANDLERS_STATE)
    _install_event_handler_compatibility(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


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
    effective_control_room_guard = (
        control_room_guard
        if callable(control_room_guard)
        else build_default_control_room_guard()
    )

    persistent_event_recorder = (
        build_persistent_operations_event_recorder(
            app=app,
            database_url=PERSISTENT_OPERATIONS_DATABASE_URL,
            service_name=PERSISTENT_OPERATIONS_SERVICE_NAME,
            timeout_seconds=PERSISTENT_OPERATIONS_EVENT_TIMEOUT_SECONDS,
        )
    )

    app.include_router(
        product_api.build_router(
            health_handler=health_handler,
            ingest_handler=ingest_handler,
            stories_handler=stories_handler,
            resolve_content_handler=resolve_content_handler,
            browser_capture_handler=browser_capture_handler,
            analyze_video_handler=analyze_video_handler,
            analyze_handler=analyze_handler,
            operational_event_recorder=persistent_event_recorder,
            connection_factory=connection_factory,
        )
    )

    app.include_router(
        intelligence_product.build_router(
            connection_factory=connection_factory,
        )
    )

    app.include_router(
        watchlists_product.build_router(
            connection_factory=connection_factory,
        )
    )

    app.include_router(
        usage_admin.build_router(
            usage_summary_handler=usage_summary_handler,
        )
    )

    app.include_router(
        operations_admin.build_router(
            require_admin=require_admin,
            database_url=PERSISTENT_OPERATIONS_DATABASE_URL,
            timeout_seconds=PERSISTENT_OPERATIONS_EVENT_TIMEOUT_SECONDS,
        )
    )

    app.include_router(
        intelligence_admin.build_router(
            require_admin=require_admin,
            connection_factory=connection_factory,
        )
    )

    app.include_router(
        intelligence_runtime_admin.build_router(
            app=app,
            require_admin=require_admin,
            connection_factory=connection_factory,
            operations_database_url=PERSISTENT_OPERATIONS_DATABASE_URL,
        )
    )

    app.include_router(
        control_room_admin.build_router(
            require_control_room=effective_control_room_guard,
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

    register_startup_handler(
        app,
        build_persistent_operations_startup_handler(
            app=app,
            database_url=PERSISTENT_OPERATIONS_DATABASE_URL,
            timeout_seconds=PERSISTENT_OPERATIONS_CONNECT_TIMEOUT_SECONDS,
        ),
    )

    browser_capture_automation.register_browser_capture_automation_lifecycle(
        app=app,
        connection_factory=connection_factory,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        gemini_client_factory=gemini_client_factory,
        gemini_generator=gemini_generator,
        operational_event_recorder=persistent_event_recorder,
    )
