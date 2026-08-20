from __future__ import annotations

from fastapi.testclient import TestClient

from app.application.composition import (
    SPORTABASE_LIFESPAN_VERSION,
    create_application,
    register_shutdown_handler,
    register_startup_handler,
)


def test_lifespan_version_is_v1():
    assert (
        SPORTABASE_LIFESPAN_VERSION
        == "sportabase-fastapi-lifespan-v1"
    )


def test_registered_lifespan_handlers_run_at_startup_and_shutdown():
    events: list[str] = []
    app = create_application()

    register_startup_handler(
        app,
        lambda: events.append("startup"),
    )
    register_shutdown_handler(
        app,
        lambda: events.append("shutdown"),
    )

    @app.get("/lifespan-probe")
    def lifespan_probe():
        return {"ok": True}

    assert events == []

    with TestClient(app) as client:
        assert events == ["startup"]
        response = client.get("/lifespan-probe")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    assert events == ["startup", "shutdown"]


def test_lifespan_supports_async_handlers():
    events: list[str] = []
    app = create_application()

    async def startup():
        events.append("async-startup")

    async def shutdown():
        events.append("async-shutdown")

    register_startup_handler(app, startup)
    register_shutdown_handler(app, shutdown)

    with TestClient(app):
        assert events == ["async-startup"]

    assert events == [
        "async-startup",
        "async-shutdown",
    ]


def test_legacy_event_registration_is_bridged_to_lifespan():
    events: list[str] = []
    app = create_application()

    app.add_event_handler(
        "startup",
        lambda: events.append("legacy-startup"),
    )
    app.add_event_handler(
        "shutdown",
        lambda: events.append("legacy-shutdown"),
    )

    with TestClient(app):
        assert events == ["legacy-startup"]

    assert events == [
        "legacy-startup",
        "legacy-shutdown",
    ]


def test_legacy_event_registration_rejects_other_event_types():
    app = create_application()

    try:
        app.add_event_handler("ready", lambda: None)
    except ValueError as error:
        assert "startup/shutdown" in str(error)
    else:
        raise AssertionError(
            "Unsupported lifecycle event was accepted."
        )
