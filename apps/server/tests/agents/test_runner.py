from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_design_server.agents.errors import InputQuestion, InputQuestionOption, InputRequired
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
            return {
                "operations": [{"nodeId": "root", "mode": "flex", "direction": "column", "gap": 16}]
            }
        return document

    async def select_tasks(state: dict[str, Any], on_reasoning: Any = None, **_: Any) -> list[str]:
        if on_reasoning is not None:
            await on_reasoning("Root Supervisor 的 reasoning")
        completed = set(state.get("completed", []))
        return [
            "requirement"
            if "prd" not in completed
            else "ui_design"
            if "initial_document" not in completed
            else "specification"
            if "corrected_document" not in completed
            else "auto_layout"
            if "final_document" not in completed
            else "final_gate"
        ]

    return SimpleNamespace(structured=structured, select_tasks=select_tasks)


@pytest.mark.asyncio
async def test_root_runs_dynamic_v2_pipeline(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="ai_design_server.agents")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    events = [
        event
        async for event in run_agent(
            {
                "requirement": "设计一个项目列表",
                "generation_contract": contract,
                "generation_id": "generation-1",
            },
            _fake_model(),
            AgentConfig(),
        )
    ]
    assert events[0]["event"] == "run"
    assert events[-1]["event"] == "result"
    assert events[-1]["payload"]["document"]["version"] == "2.0.0"
    outputs = [
        event["payload"]["output"]
        for event in events
        if event["event"] == "progress" and event["payload"].get("status") == "completed"
    ]
    assert {next(iter(output)) for output in outputs} == {
        "prd",
        "initial_document",
        "validation",
        "final_document",
        "result",
    }
    assert [
        record.agent
        for record in caplog.records
        if record.getMessage().startswith("调用子 Agent：")
    ] == ["requirement", "ui_design", "specification", "auto_layout"]
    assert {
        record.generation_id
        for record in caplog.records
        if record.getMessage().startswith("调用子 Agent：")
    } == {"generation-1"}
    assert {
        record.agent
        for record in caplog.records
        if record.getMessage().startswith("子 Agent 输出：")
    } == {"requirement", "ui_design", "specification", "auto_layout"}
    reasoning_events = [event for event in events if event["payload"].get("status") == "reasoning"]
    assert reasoning_events
    assert {event["stage"] for event in reasoning_events} >= {"root", "requirement", "ui_design"}


@pytest.mark.asyncio
async def test_agent_continues_pipeline_after_user_answers_input_request() -> None:
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    model = _fake_model()
    structured = model.structured

    async def require_answer(
        purpose: str, payload: dict[str, Any], schema: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        if "需求解析 Agent" in purpose and not payload.get("resolvedUserInputs"):
            raise InputRequired(
                [
                    InputQuestion(
                        "business-domain",
                        "后台管理主要管理哪类业务对象？",
                        "业务领域",
                        [
                            InputQuestionOption("用户与权限（推荐）", "生成用户权限后台。"),
                            InputQuestionOption("订单与交易", "生成订单交易后台。"),
                        ],
                        True,
                    )
                ]
            )
        return await structured(purpose, payload, schema, **kwargs)

    model.structured = require_answer
    waiting_events = [
        event
        async for event in run_agent(
            {
                "requirement": "设计一个项目列表",
                "generation_contract": contract,
                "generation_id": "generation-1",
            },
            model,
            AgentConfig(),
        )
    ]
    assert waiting_events[-1]["event"] == "input_required"
    assert all(event["event"] not in {"result", "failed"} for event in waiting_events)

    resumed_events = [
        event
        async for event in run_agent(
            {
                "requirement": "设计一个项目列表",
                "generation_contract": contract,
                "generation_id": "generation-1",
                "resolved_user_inputs": [
                    {
                        "source_stage": "requirement",
                        "questions": waiting_events[-1]["payload"]["questions"],
                        "answers": [
                            {
                                "question_id": "business-domain",
                                "content": "用户与权限（推荐）",
                            }
                        ],
                    }
                ],
            },
            model,
            AgentConfig(),
        )
    ]

    assert all(event["event"] != "input_required" for event in resumed_events)
    assert [
        event["stage"]
        for event in resumed_events
        if event["event"] == "progress" and event["payload"].get("status") == "completed"
    ] == ["requirement", "ui_design", "specification", "auto_layout", "final_gate"]
    assert resumed_events[-1]["event"] == "result"
    assert resumed_events[-1]["payload"]["document"]["version"] == "2.0.0"


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

    assert any(
        event["event"] == "progress" and event["payload"].get("status") == "requesting"
        for event in events
    )
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


@pytest.mark.asyncio
async def test_any_agent_input_request_stops_pipeline() -> None:
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        raise InputRequired(
            [
                InputQuestion(
                    "brand-color",
                    "品牌主色是什么？",
                    "品牌颜色",
                    [
                        InputQuestionOption("沿用现有蓝色（推荐）", "保持产品视觉一致。"),
                        InputQuestionOption("改用紫色", "增强设计工具的创意感。"),
                    ],
                    True,
                )
            ]
        )

    async def select_tasks(_: dict[str, Any], **__: Any) -> list[str]:
        return ["requirement"]

    events = [
        event
        async for event in run_agent(
            {"requirement": "设计一个项目列表", "generation_contract": contract},
            SimpleNamespace(structured=structured, select_tasks=select_tasks),
            AgentConfig(max_retries=0),
        )
    ]

    request = next(item for item in events if item["event"] == "input_required")
    assert request["stage"] == "requirement"
    assert request["payload"]["questions"] == [
        {
            "id": "brand-color",
            "header": "品牌颜色",
            "question": "品牌主色是什么？",
            "isOther": True,
            "options": [
                {"label": "沿用现有蓝色（推荐）", "description": "保持产品视觉一致。"},
                {"label": "改用紫色", "description": "增强设计工具的创意感。"},
            ],
        }
    ]
    assert all(item["event"] not in {"result", "failed"} for item in events)
