from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .agents.codegen.agent import run_codegen
from .agents.codegen.tools import (
    UnavailableCanvasCapture,
    UnavailablePreviewRenderer,
    UnavailableStaticVerifier,
)
from .agents.errors import AgentError
from .agents.graph import build as build_agent_graph
from .agents.model import ModelPort, create_openai_model
from .auth.router import router as auth_router
from .auth.service import AuthService
from .codegen_router import router as codegen_router
from .config import AgentConfig, RuntimeConfig, load_config
from .database import Database, open_database
from .errors import (
    ConflictError,
    InvalidCredentialsError,
    InvalidRequestError,
    NotFoundError,
    NotRetryableError,
    PersistenceError,
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
    database: Database = getattr(app.state, "database", None) or await open_database(
        config.database
    )
    app.state.database = database
    client = getattr(app.state, "http_client", None) or httpx.AsyncClient()
    app.state.http_client = client
    app.state.agent_model = getattr(app.state, "agent_model", None) or create_openai_model(
        client, config.ai
    )
    app.state.codegen_verifier = getattr(app.state, "codegen_verifier", None)
    app.state.codegen_renderer = getattr(app.state, "codegen_renderer", None)
    app.state.codegen_canvas_capture = getattr(app.state, "codegen_canvas_capture", None)

    async def run_root_codegen(
        payload: dict[str, object], model: ModelPort, agent_config: AgentConfig
    ) -> dict[str, object]:
        capture = app.state.codegen_canvas_capture or UnavailableCanvasCapture()
        images = await capture.capture(
            payload["document"] if isinstance(payload["document"], Mapping) else {},
            payload["canvas"] if isinstance(payload["canvas"], Mapping) else {},
        )
        internal = {"document": payload["document"], "canvasImages": images}
        if isinstance(payload.get("options"), Mapping):
            internal["options"] = payload["options"]
        return await run_codegen(
            internal,
            model,  # type: ignore[arg-type]
            agent_config,
            verifier=app.state.codegen_verifier or UnavailableStaticVerifier(),
            renderer=app.state.codegen_renderer or UnavailablePreviewRenderer(),
        )

    app.state.codegen_runner = run_root_codegen
    app.state.agent_graph = getattr(app.state, "agent_graph", None) or build_agent_graph(
        app.state.agent_model, config.agent, run_root_codegen
    )
    app.state.active_agent_runs = getattr(app.state, "active_agent_runs", {})
    app.state.auth_service = getattr(app.state, "auth_service", None) or AuthService(
        config.auth.fixed_user_password
    )
    app.state.project_service = getattr(app.state, "project_service", None) or ProjectService()
    try:
        yield
    finally:
        # 资源释放必须彼此隔离：数据库关闭异常不应阻断 HTTP 客户端清理，
        # 否则进程在优雅退出后仍可能遗留连接和后台任务。
        try:
            if not getattr(app.state, "http_client_injected", False):
                await client.aclose()
        finally:
            if not getattr(app.state, "database_injected", False):
                await database.close()


def create_app(
    config: RuntimeConfig | None = None,
    database: Database | None = None,
    agent_model: ModelPort | None = None,
) -> FastAPI:
    app = FastAPI(title="AI Design Server", lifespan=lifespan)
    app.state.active_generations = {}
    app.state.active_agent_runs = {}
    if config is not None:
        app.state.config = config
    if database is not None:
        app.state.database = database
        app.state.database_injected = True
    if agent_model is not None:
        app.state.agent_model = agent_model
    app.include_router(auth_router)
    app.include_router(project_router)
    app.include_router(codegen_router)

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
    async def access_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        request_log(
            request.app.state.logger,
            request.method,
            request.url.path,
            response.status_code,
            started,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        message = "登录信息无效" if request.url.path == "/api/auth/login" else "请求无效"
        return _error(400, "invalid_request", message)

    for error_type, status, code, message in (
        (InvalidCredentialsError, 401, "invalid_credentials", "邮箱或密码错误"),
        (UnauthorizedError, 401, "unauthorized", "请先登录"),
        (NotFoundError, 404, "not_found", "项目不存在"),
        (ConflictError, 409, "generation_in_progress", "项目正在生成"),
        (NotRetryableError, 409, "not_retryable", "消息不可重新生成"),
        (InvalidRequestError, 400, "invalid_request", "请求无效"),
        (PersistenceError, 500, "internal_error", "内部错误"),
    ):
        app.add_exception_handler(
            error_type,
            lambda _, __, status=status, code=code, message=message: _error(status, code, message),
        )

    async def codegen_error_handler(_: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, AgentError):
            return _error(500, "internal_error", "内部错误")
        status = (
            422
            if error.code.endswith("invalid")
            else 408
            if error.code == "codegen_timeout"
            else 503
        )
        return _error(status, error.code, error.message)

    app.add_exception_handler(AgentError, codegen_error_handler)
    return app


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)
