from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_design_server.agents.runner import run_agent
from ai_design_server.agents.state import TaskRecord
from ai_design_server.agents.supervisor import _run_task_with_retry
from ai_design_server.config import AgentConfig

ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _fake_model() -> SimpleNamespace:
    prd = _read("packages/design-contract/fixtures/v2/standardized-prd.valid.json")
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")

    async def structured(
        purpose: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        on_reasoning: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        if on_reasoning is not None:
            await on_reasoning(f"{purpose} 的 reasoning")
        if "需求解析 Agent" in purpose:
            return prd
        if "Auto Layout" in purpose:
            return {"operations": [{"nodeId": "root", "mode": "flex", "direction": "column", "gap": 16}]}
        return document

    async def select_tasks(state: dict[str, Any], on_reasoning: Any = None, **_: Any) -> list[str]:
        if on_reasoning is not None:
            await on_reasoning("Root Supervisor 的 reasoning")
        completed = set(state.get("completed", []))
        return [
            "requirement" if "prd" not in completed else
            "ui_design" if "initial_document" not in completed else
            "specification" if "corrected_document" not in completed else
            "auto_layout" if "final_document" not in completed else
            "final_gate"
        ]

    return SimpleNamespace(structured=structured, select_tasks=select_tasks)


@pytest.mark.asyncio
async def test_root_runs_dynamic_v2_pipeline(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ai_design_server.agents")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    events = [event async for event in run_agent({"requirement": "设计一个项目列表", "generation_contract": contract, "generation_id": "generation-1"}, _fake_model(), AgentConfig())]
    assert events[0]["event"] == "run"
    assert events[-1]["event"] == "result"
    assert events[-1]["payload"]["document"]["version"] == "2.0.0"
    outputs = [event["payload"]["output"] for event in events if event["event"] == "progress" and event["payload"].get("status") == "completed"]
    assert {next(iter(output)) for output in outputs} == {"prd", "initial_document", "validation", "final_document", "result"}
    assert [record.agent for record in caplog.records if record.getMessage().startswith("调用子 Agent：")] == ["requirement", "ui_design", "specification", "auto_layout"]
    assert {record.generation_id for record in caplog.records if record.getMessage().startswith("调用子 Agent：")} == {"generation-1"}
    assert {record.agent for record in caplog.records if record.getMessage().startswith("子 Agent 输出：")} == {"requirement", "ui_design", "specification", "auto_layout"}
    reasoning_events = [event for event in events if event["payload"].get("status") == "reasoning"]
    assert reasoning_events
    assert {event["stage"] for event in reasoning_events} >= {"root", "requirement", "ui_design"}


@pytest.mark.asyncio
async def test_agent_returns_timeout_when_child_agent_does_not_respond() -> None:
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {}

    async def select_tasks(_: dict[str, Any], **__: Any) -> list[str]:
        return ["requirement"]

    model = SimpleNamespace(structured=structured, select_tasks=select_tasks)
    events = [
        event
        async for event in run_agent(
            {"requirement": "设计一个项目列表", "generation_contract": contract},
            model,
            AgentConfig(node_timeout=0.01, total_timeout=1, max_retries=0),
        )
    ]

    assert any(event["event"] == "progress" and event["payload"].get("status") == "requesting" for event in events)
    assert events[-1]["event"] == "failed"
    assert events[-1]["payload"]["code"] == "agent_timeout"


@pytest.mark.asyncio
async def test_reasoning_is_truncated_without_blocking_final_output() -> None:
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    prd = _read("packages/design-contract/fixtures/v2/standardized-prd.valid.json")
    task_id = "task-1"
    state: dict[str, Any] = {
        "run_id": "run-1",
        "raw_requirement": "设计一个项目列表",
        "generation_contract": contract,
        "completed": {},
        "tasks": {
            task_id: TaskRecord(
                task_id=task_id,
                name="requirement",
                parent_task_id="root",
                status="running",
                attempt=1,
                depth=1,
            )
        },
    }

    async def structured(*_: Any, on_reasoning: Any = None, **__: Any) -> dict[str, Any]:
        await on_reasoning("这是很长的 reasoning")
        return prd

    async def select_tasks(_: dict[str, Any], **__: Any) -> list[str]:
        return ["requirement"]

    model = SimpleNamespace(structured=structured, select_tasks=select_tasks)
    events: list[dict[str, Any]] = []

    async def emit(item: dict[str, Any]) -> None:
        events.append(item)

    result = await _run_task_with_retry(
        "requirement",
        state,
        model,
        task_id,
        AgentConfig(max_output_bytes=4, max_retries=0),
        emit,
    )

    assert result == {"prd": prd}
    assert [item["payload"]["status"] for item in events] == [
        "requesting",
        "reasoning",
        "reasoning_truncated",
    ]
