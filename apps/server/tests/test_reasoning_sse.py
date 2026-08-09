from __future__ import annotations

import importlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import Request

from ai_design_server.agents.events import event
from ai_design_server.database import AttemptModel, MessageModel, ProjectModel

project_router = importlib.import_module("ai_design_server.project.router")

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


class FakeDatabase:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeService:
    async def finish(
        self, _: object, attempt_id: str, content: str, failure: BaseException | None = None
    ) -> tuple[MessageModel, AttemptModel]:
        assert (attempt_id, content, failure) == ("attempt-1", "设计已生成。", None)
        return (
            MessageModel(
                id="assistant-1",
                project_id="project-1",
                client_message_id=None,
                role="assistant",
                content=content,
                created_at=NOW,
            ),
            AttemptModel(
                id=attempt_id,
                project_id="project-1",
                user_message_id="message-1",
                assistant_message_id="assistant-1",
                status="completed",
                error_code=None,
                lease_expires_at=None,
                created_at=NOW,
                finished_at=NOW,
            ),
        )


@pytest.mark.asyncio
async def test_project_sse_forwards_reasoning_and_keeps_final_result_separate(monkeypatch) -> None:
    async def fake_run_agent(*_: object, **__: object):
        yield event(
            "progress",
            "run-1",
            "requirement",
            task_id="task-1",
            attempt=1,
            payload={"status": "reasoning", "delta": "先分析需求"},
        )
        yield event(
            "progress",
            "requirement",
            "requirement",
            task_id="task-1",
            attempt=1,
            payload={"status": "completed", "output": {"prd": {}}},
        )
        yield event(
            "result",
            "run-1",
            "auto_layout",
            payload={"document": {"version": "2.0.0"}},
        )

    monkeypatch.setattr(project_router, "run_agent", fake_run_agent)
    app = SimpleNamespace(
        state=SimpleNamespace(
            database=FakeDatabase(),
            logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
            active_generations={},
            agent_model=object(),
            config=SimpleNamespace(agent=SimpleNamespace()),
        )
    )
    request = Request({"type": "http", "app": app})
    project = ProjectModel(id="project-1", user_id="user-1", title="测试", created_at=NOW, updated_at=NOW)
    message = MessageModel(id="message-1", project_id="project-1", client_message_id="client-1", role="user", content="设计后台", created_at=NOW)
    attempt = AttemptModel(id="attempt-1", project_id="project-1", user_message_id="message-1", assistant_message_id=None, status="running", error_code=None, lease_expires_at=None, created_at=NOW, finished_at=None)
    events = "".join([item async for item in project_router._events(request, FakeService(), project, message, attempt)])
    chunks = [chunk for chunk in events.split("\n\n") if chunk]
    parsed = [json.loads(chunk.split("data: ", 1)[1]) for chunk in chunks]

    assert any(item.get("payload", {}).get("status") == "reasoning" for item in parsed)
    assert any(item.get("payload", {}).get("output") == {"prd": {}} for item in parsed)
    assert "reasoning" not in parsed[-1]
