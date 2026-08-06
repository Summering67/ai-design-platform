from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth.router import router as auth_router
from .auth.service import AuthService
from .chat.client import ChatClient
from .config import RuntimeConfig, load_config
from .database import Database, open_database
from .errors import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    NotRetryableError,
    UnauthorizedError,
)
from .logging import configure_logging, request_log
from .project.router import router as project_router
from .project.service import ProjectService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config: RuntimeConfig = getattr(app.state, "config", None) or load_config()
    app.state.config = config
    app.state.logger = configure_logging(config.log)
    database: Database = getattr(app.state, "database", None) or await open_database(config.database)
    app.state.database = database
    client = getattr(app.state, "http_client", None) or httpx.AsyncClient()
    app.state.http_client = client
    app.state.chat_client = getattr(app.state, "chat_client", None) or ChatClient(client, config.ai)
    app.state.auth_service = getattr(app.state, "auth_service", None) or AuthService(config.auth.fixed_user_password)
    app.state.project_service = getattr(app.state, "project_service", None) or ProjectService()
    try:
        yield
    finally:
        if not getattr(app.state, "http_client_injected", False):
            await client.aclose()
        if not getattr(app.state, "database_injected", False):
            await database.close()


def create_app(config: RuntimeConfig | None = None, database: Database | None = None, chat_client: ChatClient | None = None) -> FastAPI:
    app = FastAPI(title="AI Design Server", lifespan=lifespan)
    app.state.active_generations = {}
    if config is not None:
        app.state.config = config
    if database is not None:
        app.state.database = database
        app.state.database_injected = True
    if chat_client is not None:
        app.state.chat_client = chat_client
    app.include_router(auth_router)
    app.include_router(project_router)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        try:
            await request.app.state.database.ping(request.app.state.config.database.ping_timeout)
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return JSONResponse({"status": "ready"})

    @app.middleware("http")
    async def access_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        request_log(request.app.state.logger, request.method, request.url.path, response.status_code, started)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(400, "invalid_request", "请求无效")

    for error_type, status, code, message in (
        (UnauthorizedError, 401, "unauthorized", "请先登录"),
        (NotFoundError, 404, "not_found", "项目不存在"),
        (ConflictError, 409, "generation_in_progress", "项目正在生成"),
        (NotRetryableError, 409, "not_retryable", "消息不可重新生成"),
        (InvalidRequestError, 400, "invalid_request", "请求无效"),
    ):
        app.add_exception_handler(error_type, lambda _, __, status=status, code=code, message=message: _error(status, code, message))
    return app


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)
