from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import httpx
import pytest
from fastapi import Request

from ai_design_server.app import create_app
from ai_design_server.auth.router import current_user, get_auth_service
from ai_design_server.config import AIConfig, AuthConfig, DatabaseConfig, RuntimeConfig
from ai_design_server.database import AttemptModel, Database, MessageModel, ProjectModel
from ai_design_server.dependencies import get_auth_session, get_session
from ai_design_server.errors import InvalidCredentialsError
from ai_design_server.project.router import _events, get_project_service

USER_ID = "00000000-0000-0000-0000-000000000001"
PROJECT_ID = "10000000-0000-0000-0000-000000000001"
USER_MESSAGE_ID = "20000000-0000-0000-0000-000000000001"
CLIENT_MESSAGE_ID = "30000000-0000-0000-0000-000000000001"
ASSISTANT_MESSAGE_ID = "40000000-0000-0000-0000-000000000001"
ATTEMPT_ID = "50000000-0000-0000-0000-000000000001"
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
WEB_ROOT = Path(__file__).resolve().parents[2] / "web/app"


class FakeDatabase:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeAuthService:
    def __init__(self, invalid: bool = False) -> None:
        self.invalid = invalid
        self.logged_out_token: str | None = None

    async def login(self, _: object, email: str, password: str) -> tuple[object, str]:
        if self.invalid:
            raise InvalidCredentialsError
        assert (email, password) == ("developer@local.test", "test-password")
        return _user(), "test-session-token"

    async def logout(self, _: object, token: str) -> None:
        self.logged_out_token = token


class FakeChatClient:
    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure

    async def stream(self, _: object, on_delta: object) -> None:
        if self.failure is not None:
            raise self.failure
        await on_delta("你好，")  # type: ignore[operator]
        await on_delta("世界")  # type: ignore[operator]


class FakeProjectService:
    async def recent(self, _: object, __: str) -> list[ProjectModel]:
        return [_project()]

    async def get(
        self, _: object, __: str, project_id: str
    ) -> tuple[ProjectModel, list[MessageModel]]:
        assert project_id == PROJECT_ID
        return _project(), [_user_message(), _assistant_message()]

    async def create_with_message(
        self,
        _: object,
        user_id: str,
        message_id: str,
        content: str,
    ) -> tuple[ProjectModel, MessageModel, AttemptModel]:
        assert (user_id, message_id, content) == (USER_ID, CLIENT_MESSAGE_ID, "设计一个工作台")
        return _project(), _user_message(), _attempt()

    async def add_message(
        self,
        _: object,
        user_id: str,
        project_id: str,
        message_id: str,
        content: str,
    ) -> tuple[MessageModel, AttemptModel, bool]:
        assert (user_id, project_id, message_id, content) == (
            USER_ID,
            PROJECT_ID,
            CLIENT_MESSAGE_ID,
            "设计一个工作台",
        )
        return _user_message(), _attempt(), False

    async def retry(
        self,
        _: object,
        user_id: str,
        project_id: str,
        message_id: str,
    ) -> tuple[ProjectModel, MessageModel, AttemptModel]:
        assert (user_id, project_id, message_id) == (USER_ID, PROJECT_ID, USER_MESSAGE_ID)
        return _project(), _user_message(), _attempt()

    async def interrupt(
        self,
        _: object,
        project_id: str,
        attempt_id: str,
        user_id: str | None = None,
    ) -> AttemptModel:
        assert (project_id, attempt_id) == (PROJECT_ID, ATTEMPT_ID)
        assert user_id in {None, USER_ID}
        return _attempt(status="interrupted", finished_at=NOW)

    async def context(self, _: object, project_id: str, message_id: str) -> list[MessageModel]:
        assert (project_id, message_id) == (PROJECT_ID, USER_MESSAGE_ID)
        return [_user_message()]

    async def finish(
        self,
        _: object,
        attempt_id: str,
        content: str,
        failure: BaseException | None = None,
    ) -> tuple[MessageModel | None, AttemptModel]:
        assert attempt_id == ATTEMPT_ID
        if failure is not None:
            return None, _attempt(status="failed", error_code="ai_unavailable", finished_at=NOW)
        assert content == "你好，世界"
        return _assistant_message(), _attempt(
            status="completed",
            assistant_message_id=ASSISTANT_MESSAGE_ID,
            finished_at=NOW,
        )


def _config() -> RuntimeConfig:
    return RuntimeConfig(
        database=DatabaseConfig(dsn="postgresql://localhost/parity"),
        ai=AIConfig(base_url="https://ai.test", api_key="test"),
        auth=AuthConfig(fixed_user_password="test-password"),
    )


def _user() -> object:
    return SimpleNamespace(id=USER_ID, email="developer@local.test", display_name="开发者")


def _project() -> ProjectModel:
    return ProjectModel(
        id=PROJECT_ID,
        user_id=USER_ID,
        title="设计一个工作台",
        created_at=NOW,
        updated_at=NOW,
    )


def _user_message() -> MessageModel:
    return MessageModel(
        id=USER_MESSAGE_ID,
        project_id=PROJECT_ID,
        client_message_id=CLIENT_MESSAGE_ID,
        role="user",
        content="设计一个工作台",
        created_at=NOW,
    )


def _assistant_message() -> MessageModel:
    return MessageModel(
        id=ASSISTANT_MESSAGE_ID,
        project_id=PROJECT_ID,
        client_message_id=None,
        role="assistant",
        content="你好，世界",
        created_at=NOW,
    )


def _attempt(
    status: str = "running",
    error_code: str | None = None,
    assistant_message_id: str | None = None,
    finished_at: datetime | None = None,
) -> AttemptModel:
    return AttemptModel(
        id=ATTEMPT_ID,
        project_id=PROJECT_ID,
        user_message_id=USER_MESSAGE_ID,
        assistant_message_id=assistant_message_id,
        status=status,
        error_code=error_code,
        lease_expires_at=None if finished_at else NOW + timedelta(minutes=2),
        created_at=NOW,
        finished_at=finished_at,
    )


async def _session_override() -> AsyncIterator[object]:
    yield object()


def _app(auth: FakeAuthService | None = None, chat: FakeChatClient | None = None) -> object:
    auth_service = auth or FakeAuthService()
    chat_client = chat or FakeChatClient()
    app = create_app(
        _config(),
        cast(Database, FakeDatabase()),
        cast(object, chat_client),  # type: ignore[arg-type]
    )
    app.state.chat_client = chat_client
    app.state.logger = logging.getLogger("test-api-contract-parity")
    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_auth_session] = _session_override
    app.dependency_overrides[current_user] = _user
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_project_service] = FakeProjectService
    return app


def _cookie(header: str) -> dict[str, object]:
    parsed = SimpleCookie()
    parsed.load(header)
    value = parsed["aidp_session"]
    return {
        "value": value.value,
        "path": value["path"],
        "max_age": value["max-age"],
        "httponly": bool(value["httponly"]),
        "samesite": value["samesite"].lower(),
    }


def _sse(value: str) -> list[dict[str, object]]:
    events = []
    for chunk in value.split("\n\n"):
        if not chunk:
            continue
        lines = dict(line.split(": ", 1) for line in chunk.splitlines())
        events.append({"event": lines["event"], "data": json.loads(lines["data"])})
    return events


def test_contract_fixtures_follow_current_web_chat_api_request_shapes() -> None:
    chat_api = (WEB_ROOT / "workspace/chat-api.ts").read_text(encoding="utf-8")
    workspace = (WEB_ROOT / "workspace/workspace-chat.tsx").read_text(encoding="utf-8")

    for request in (
        "fetch(`${api}/projects/${projectId}`)",
        "fetch(`${api}/auth/login`, {",
        "fetch(`${api}/auth/me`)",
        'fetch(`${api}/auth/logout`, { method: "POST" })',
        "`${api}/projects/${projectId}/generations/${generationId}/stop`",
        "body: body ? JSON.stringify(body) : undefined",
    ):
        assert request in chat_api
    assert "body: JSON.stringify({ email, password })" in chat_api
    assert "{ message_id: messageId, content }" in workspace
    assert "`/projects/${project.id}/messages/${messageId}/generations`" in workspace
    assert "undefined," in workspace


@pytest.mark.asyncio
async def test_auth_status_json_and_cookie_match_go_contract() -> None:
    auth = FakeAuthService()
    app = _app(auth)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": "developer@local.test", "password": "test-password"},
        )
        current = await client.get("/api/auth/me")
        logout = await client.post("/api/auth/logout")

    expected_user = {"id": USER_ID, "email": "developer@local.test", "display_name": "开发者"}
    assert (login.status_code, login.json()) == (200, expected_user)
    assert (current.status_code, current.json()) == (200, expected_user)
    assert _cookie(login.headers["set-cookie"]) == {
        "value": "test-session-token",
        "path": "/",
        "max_age": "604800",
        "httponly": True,
        "samesite": "lax",
    }
    assert logout.status_code == 204
    assert _cookie(logout.headers["set-cookie"]) == {
        "value": "",
        "path": "/",
        "max_age": "0",
        "httponly": True,
        "samesite": "",
    }
    assert auth.logged_out_token == "test-session-token"


@pytest.mark.asyncio
async def test_login_errors_match_go_status_and_json() -> None:
    malformed_app = _app()
    invalid_app = _app(FakeAuthService(invalid=True))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=malformed_app), base_url="http://test"
    ) as client:
        malformed = await client.post(
            "/api/auth/login",
            json={"email": "developer@local.test", "password": "test-password", "extra": True},
        )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=invalid_app), base_url="http://test"
    ) as client:
        invalid = await client.post(
            "/api/auth/login",
            json={"email": "developer@local.test", "password": "wrong"},
        )

    assert (malformed.status_code, malformed.json()) == (
        400,
        {"error": {"code": "invalid_request", "message": "登录信息无效"}},
    )
    assert (invalid.status_code, invalid.json()) == (
        401,
        {"error": {"code": "invalid_credentials", "message": "邮箱或密码错误"}},
    )


@pytest.mark.asyncio
async def test_web_project_request_shapes_match_go_json_and_sse() -> None:
    app = _app()
    body = {"message_id": CLIENT_MESSAGE_ID, "content": "设计一个工作台"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        loaded = await client.get(f"/api/projects/{PROJECT_ID}")
        created = await client.post("/api/projects", json=body)
        generated = await client.post(f"/api/projects/{PROJECT_ID}/generations", json=body)
        retried = await client.post(
            f"/api/projects/{PROJECT_ID}/messages/{USER_MESSAGE_ID}/generations"
        )
        stopped = await client.post(f"/api/projects/{PROJECT_ID}/generations/{ATTEMPT_ID}/stop")

    assert loaded.status_code == 200
    assert set(loaded.json()["project"]) == {"id", "user_id", "title", "created_at", "updated_at"}
    assert set(loaded.json()["messages"][0]) == {
        "id",
        "project_id",
        "client_message_id",
        "role",
        "content",
        "created_at",
    }
    assert set(loaded.json()["messages"][1]) == {
        "id",
        "project_id",
        "role",
        "content",
        "created_at",
    }
    for response in (created, generated, retried):
        assert response.status_code == 200
        events = _sse(response.text)
        assert [event["event"] for event in events] == ["generation", "delta", "delta", "completed"]
        assert events[0]["data"] == {
            "project_id": PROJECT_ID,
            "message_id": USER_MESSAGE_ID,
            "generation_id": ATTEMPT_ID,
        }
        assert events[1]["data"] == {"content": "你好，"}
        assert events[2]["data"] == {"content": "世界"}
        assert set(events[3]["data"]["message"]) == {
            "id",
            "project_id",
            "role",
            "content",
            "created_at",
        }
    assert stopped.status_code == 200
    assert set(stopped.json()["generation"]) == {
        "id",
        "project_id",
        "user_message_id",
        "status",
        "created_at",
        "finished_at",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "terminal", "payload"),
    [
        (
            RuntimeError("upstream"),
            "failed",
            {"generation_id": ATTEMPT_ID, "code": "ai_unavailable"},
        ),
        (asyncio.CancelledError(), "interrupted", {"generation_id": ATTEMPT_ID}),
    ],
)
async def test_sse_has_one_go_equivalent_terminal_event(
    failure: BaseException,
    terminal: str,
    payload: dict[str, str],
) -> None:
    app = _app(chat=FakeChatClient(failure))
    request = Request({"type": "http", "app": app})
    events = _events(request, FakeProjectService(), _project(), _user_message(), _attempt())
    parsed = _sse("".join([event async for event in events]))

    assert [event["event"] for event in parsed] == ["generation", terminal]
    assert parsed[-1]["data"] == payload
