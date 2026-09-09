from fastapi import HTTPException, Request
import os
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.accounts.auth import configured_verifier
from app.accounts.store import ensure_account, installation, owner_key, transaction, try_record_event


def is_private(path):
    return (path == "/analyze" or path.startswith("/analyze/") or path == "/resolve-content" or
            path == "/content/browser-capture" or
            any(path == prefix or path.startswith(prefix + "/") for prefix in ("/account", "/watchlists", "/notifications")))


def authenticated_owner(request: Request, legacy_value, *, legacy_resolver):
    # Standalone legacy routers are retained for internal compatibility tests.
    # The composed application ALWAYS installs AccountBoundary before exposing them.
    account = getattr(request.state, "account", None)
    return owner_key(account["id"]) if account else legacy_resolver(legacy_value)


class AccountBoundary:
    def __init__(self, app, *, connection_factory, verifier=None):
        self.app, self.factory = app, connection_factory
        self.verifier = verifier or configured_verifier()

    def authenticate(self, request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Sign in to continue.")
        claims = self.verifier.verify(authorization[7:])
        device_id = request.headers.get("x-sportabase-device-id", "")
        import uuid
        try:
            device_id = str(uuid.UUID(device_id))
        except ValueError as exc:
            raise HTTPException(422, "A valid installation ID is required.") from exc
        with transaction(self.factory) as conn:
            account = ensure_account(conn, claims["sub"], allow_deleting=request.method == "DELETE" and request.url.path == "/account")
            bootstrap = request.method == "POST" and request.url.path == "/account/bootstrap"
            deleting = request.method == "DELETE" and request.url.path == "/account"
            if not bootstrap and not deleting:
                device = installation(conn, account["id"], device_id)
                request.state.account_device = device
                try_record_event(conn, account["id"], "session_active", device["platform"])
                if request.method == "POST" and request.url.path in ("/analyze", "/analyze/video"):
                    try_record_event(conn, account["id"], "analysis_initiated", device["platform"])
            request.state.account, request.state.device_id, request.state.clerk_claims = account, device_id, claims

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] != "OPTIONS" and is_private(scope["path"].rstrip("/")):
            request = Request(scope)
            try:
                await run_in_threadpool(self.authenticate, request)
            except HTTPException as exc:
                # This boundary is intentionally outside the application's CORS
                # middleware. Mirror its credential-free wildcard policy so a
                # browser can read the opaque sign-in error and render the gate.
                headers = {"Cache-Control": "no-store", **(exc.headers or {})}
                configured = tuple(value.strip() for value in os.getenv("SPORTABASE_ALLOWED_ORIGINS", "").split(",") if value.strip())
                origin = request.headers.get("origin", "")
                if configured:
                    if origin in configured:
                        headers["Access-Control-Allow-Origin"] = origin
                        headers["Vary"] = "Origin"
                elif os.getenv("SPORTABASE_ENV", "development").strip().lower() != "production":
                    headers["Access-Control-Allow-Origin"] = "*"
                await JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                   headers=headers)(scope, receive, send)
                return
            async def private_send(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", []).append((b"cache-control", b"no-store"))
                await send(message)
            await self.app(scope, receive, private_send)
        else:
            await self.app(scope, receive, send)
