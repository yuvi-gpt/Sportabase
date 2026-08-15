import ipaddress
import json
import os
import secrets

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path

from typing import (
    Literal,
    Optional,
)


import uvicorn

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
)

from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)

from pydantic import (
    BaseModel,
    Field,
)


from app.db.connection import (
    connect_database,
)

from app.db.migrations import (
    initialize_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.reviews import (
    resolve_review_queue_item,
)

from app.services.reviewer_data import (
    get_reviewer_item,
    list_reviewer_items,
)


REVIEWER_APP_VERSION = (
    "local-reviewer-v1"
)

BACKEND_DIR = (
    Path(
        __file__
    ).resolve().parent.parent
)

DEFAULT_DB_PATH = (
    BACKEND_DIR
    / "data"
    / "sportabase.db"
)

REVIEW_DB_PATH = Path(
    os.getenv(
        "SPORTABASE_REVIEW_DB_PATH",
        str(
            DEFAULT_DB_PATH
        ),
    )
).expanduser().resolve()

REVIEW_UI_PATH = (
    Path(
        __file__
    ).resolve().with_name(
        "reviewer_ui.html"
    )
)

REVIEWER_SESSION_TOKEN = (
    secrets.token_urlsafe(
        32
    )
)


def connection_factory():
    return connect_database(
        REVIEW_DB_PATH
    )


def ensure_reviewer_database():
    initialize_database(
        connection_factory,
        SCHEMA,
    )


def is_loopback_host(
    host: str,
) -> bool:
    normalized = str(
        host or ""
    ).strip().lower()

    if normalized == "localhost":
        return True

    if (
        normalized.startswith(
            "["
        )
        and normalized.endswith(
            "]"
        )
    ):
        normalized = (
            normalized[
                1:-1
            ]
        )

    try:
        return bool(
            ipaddress.ip_address(
                normalized
            ).is_loopback
        )

    except ValueError:
        return False


def require_reviewer_token(
    token: str,
) -> None:
    supplied = str(
        token or ""
    )

    if (
        not supplied
        or not secrets.compare_digest(
            supplied,
            REVIEWER_SESSION_TOKEN,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Invalid local reviewer token."
            ),
        )


class ReviewResolutionRequest(
    BaseModel
):
    value: str = Field(
        min_length=1,
        max_length=200,
    )

    reason: str = Field(
        min_length=3,
        max_length=4000,
    )

    corrected_by: str = Field(
        min_length=1,
        max_length=200,
    )

    corrected_at: Optional[
        str
    ] = None

    scope: Literal[
        "case_only",
        "pattern_candidate",
        "entity_mapping_candidate",
        "global_rule_candidate",
    ] = "case_only"


app = FastAPI(
    title=(
        "Sportabase Local Reviewer"
    ),
    version=(
        REVIEWER_APP_VERSION
    ),
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.middleware(
    "http"
)
async def local_only_middleware(
    request: Request,
    call_next,
):
    host = ""

    if request.client is not None:
        host = request.client.host

    if not is_loopback_host(
        host
    ):
        return JSONResponse(
            status_code=403,
            content={
                "detail": (
                    "Sportabase reviewer "
                    "accepts loopback clients only."
                )
            },
        )

    return await call_next(
        request
    )


@app.on_event(
    "startup"
)
def reviewer_startup():
    ensure_reviewer_database()


@app.get(
    "/api/health"
)
def api_health():
    return {
        "status": "ok",
        "version": (
            REVIEWER_APP_VERSION
        ),
        "local_only": True,
        "db_path": str(
            REVIEW_DB_PATH
        ),
    }


@app.get(
    "/api/reviews"
)
def api_list_reviews(
    status: str = Query(
        default="pending"
    ),
    claim_id: str = Query(
        default=""
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
):
    try:
        return list_reviewer_items(
            status=status,
            claim_id=claim_id,
            limit=limit,
            connection_factory=(
                connection_factory
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc


@app.get(
    "/api/reviews/{review_id}"
)
def api_get_review(
    review_id: str,
):
    try:
        return get_reviewer_item(
            review_id=review_id,
            connection_factory=(
                connection_factory
            ),
        )

    except ValueError as exc:
        message = str(
            exc
        )

        status_code = (
            404
            if (
                "does not exist"
                in message
            )
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


@app.post(
    "/api/reviews/{review_id}/resolve"
)
def api_resolve_review(
    review_id: str,
    body: ReviewResolutionRequest,
    x_sportabase_reviewer_token: str = Header(
        default="",
        alias=(
            "X-Sportabase-Reviewer-Token"
        ),
    ),
):
    require_reviewer_token(
        x_sportabase_reviewer_token
    )

    corrected_at = (
        str(
            body.corrected_at
            or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    try:
        resolution = (
            resolve_review_queue_item(
                review_id=review_id,
                value=body.value,
                reason=body.reason,
                corrected_by=(
                    body.corrected_by
                ),
                corrected_at=(
                    corrected_at
                ),
                scope=body.scope,
                connection_factory=(
                    connection_factory
                ),
            )
        )

        detail = get_reviewer_item(
            review_id=review_id,
            connection_factory=(
                connection_factory
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(
                exc
            ),
        ) from exc

    return {
        "resolution": (
            resolution
        ),
        "item": (
            detail
        ),
    }


@app.get(
    "/",
    response_class=(
        HTMLResponse
    ),
)
def reviewer_home():
    if not REVIEW_UI_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Reviewer UI file "
                "is missing."
            ),
        )

    html_text = (
        REVIEW_UI_PATH.read_text(
            encoding="utf-8"
        )
    )

    placeholder = (
        "__SPORTABASE_REVIEWER_TOKEN__"
    )

    if html_text.count(
        placeholder
    ) != 1:
        raise HTTPException(
            status_code=500,
            detail=(
                "Reviewer UI token "
                "placeholder is invalid."
            ),
        )

    html_text = html_text.replace(
        placeholder,
        json.dumps(
            REVIEWER_SESSION_TOKEN
        ),
        1,
    )

    return HTMLResponse(
        content=(
            html_text
        )
    )


def run():
    port = int(
        os.getenv(
            "SPORTABASE_REVIEWER_PORT",
            "8765",
        )
    )

    uvicorn.run(
        "app.reviewer_app:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run()
