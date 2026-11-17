"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from protopitch import __version__
from protopitch.api import jobs, projects, system
from protopitch.auth import build_auth_provider, require_principal
from protopitch.context import AppContext, build_context
from protopitch.errors import PlatformError
from protopitch.logging_setup import get_logger
from protopitch.settings import Settings

log = get_logger("api")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSP = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def _error(status: int, code: str, message: str, next_actions: list[str]) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "next_actions": next_actions}},
    )


def create_app(settings: Settings | None = None, context: AppContext | None = None) -> FastAPI:
    ctx = context or build_context(settings)
    settings = ctx.settings
    app = FastAPI(title="ProtoPitch", version=__version__, docs_url="/api/docs", redoc_url=None,
                  openapi_url="/api/openapi.json")  # fmt: skip
    app.state.ctx = ctx
    app.state.auth = build_auth_provider(settings)

    allowed_origins = set(settings.server.allowed_origins)

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # A local API without login must not be drivable by another website in the owner's
        # browser: refuse state-changing requests whose Origin is neither ours nor allowed.
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and origin not in allowed_origins:
                if urlparse(origin).netloc != request.headers.get("host"):
                    return _error(403, "forbidden", "Cross-site requests are not accepted.", [])
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Content-Security-Policy", CSP)
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.server.allowed_hosts)

    @app.exception_handler(PlatformError)
    async def platform_error(_request: Request, exc: PlatformError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.next_actions)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()
        )
        return _error(
            422, "validation_failed", f"The request is not valid: {problems}.",
            ["Correct the highlighted fields and try again."],
        )  # fmt: skip

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return _error(
            500, "internal_error", "Something went wrong inside ProtoPitch.",
            ["Check the server log for details."],
        )  # fmt: skip

    protected = [Depends(require_principal)]
    app.include_router(system.router, prefix="/api", dependencies=protected)
    app.include_router(projects.router, prefix="/api", dependencies=protected)
    app.include_router(jobs.router, prefix="/api", dependencies=protected)

    dist = settings.frontend_dist
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> Response:
        if path.startswith("api/"):
            return _error(404, "not_found", "No such API endpoint.", [])
        if not index.is_file():
            return _error(
                404, "frontend_not_built",
                "The web interface has not been built yet.",
                ["Run `make start`, or `make dev` for the development server."],
            )  # fmt: skip
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

    return app
