from __future__ import annotations

import asyncio
import json
import logging
import time
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


@pytest.fixture(autouse=True)
def agent_output_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr("ai_design_server.agents.supervisor.AGENT_OUTPUT_ROOT", tmp_path)
    return tmp_path


def _fake_model() -> SimpleNamespace:
    prd = _read("packages/design-contract/fixtures/v2/standardized-prd.valid.json")
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")

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
        if schema.get("title") == "Layout Plan v1":
            return {
                "version": "1.0.0",
                "viewport": {"width": 1440, "height": 900},
                "operations": [
                    {"nodeId": "root", "layout": {"mode": "flex", "direction": "column", "gap": 16}}
                ],
            }
        if schema.get("title") == "Initial UI Document v1":
            return initial
        return initial

    async def select_tasks(state: dict[str, Any], on_reasoning: Any = None, **_: Any) -> list[str]:
        if on_reasoning is not None:
            await on_reasoning("Root Supervisor 的 reasoning")
        completed = set(state.get("completed", []))
        if "prd" not in completed:
            return ["requirement"]
        if "initial_ui_document" not in completed:
            return ["ui_design"]
        if "final_document" not in completed:
            return ["auto_layout"]
        return []

    return SimpleNamespace(structured=structured, select_tasks=select_tasks)


@pytest.mark.asyncio
async def test_root_runs_dynamic_v2_pipeline(
    caplog: pytest.LogCaptureFixture,
    agent_output_root: Path,
) -> None:
    caplog.set_level(logging.DEBUG, logger="ai_design_server.agents")
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
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
        "initial_ui_document",
        "final_document",
    }
    assert [
        record.agent
        for record in caplog.records
        if record.getMessage().startswith("调用子 Agent：")
    ] == ["requirement", "ui_design", "auto_layout"]
    assert {
        record.generation_id
        for record in caplog.records
        if record.getMessage().startswith("调用子 Agent：")
    } == {"generation-1"}
    assert {
        record.agent
        for record in caplog.records
        if record.getMessage().startswith("子 Agent 输出：")
    } == {"requirement", "ui_design", "auto_layout"}
    output_root = agent_output_root / "generation-1" / events[0]["runId"]
    output_files = sorted(output_root.glob("*.json"))
    assert [path.name for path in output_files] == [
        "01-requirement-attempt-01.json",
        "02-ui_design-attempt-01.json",
        "03-auto_layout-attempt-01.json",
    ]
    assert set(json.loads(output_files[0].read_text(encoding="utf-8"))) == {"prd"}
    assert set(json.loads(output_files[1].read_text(encoding="utf-8"))) == {"initial_ui_document"}
    assert set(json.loads(output_files[2].read_text(encoding="utf-8"))) == {
        "final_document",
        "result",
        "validation",
    }
    reasoning_events = [event for event in events if event["payload"].get("status") == "reasoning"]
    assert reasoning_events
    assert {event["stage"] for event in reasoning_events} >= {"root", "requirement", "ui_design"}


@pytest.mark.asyncio
async def test_root_model_decides_whether_to_call_codegen() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    model = _fake_model()
    original_select = model.select_tasks
    calls: list[dict[str, Any]] = []

    async def select_tasks(state: dict[str, Any], **kwargs: Any) -> list[str]:
        completed = set(state.get("completed", []))
        if "final_document" in completed:
            assert "生成前端代码" in state["request"]
            assert "codegen" in state["readyCapabilities"]
            return ["codegen"]
        return await original_select(state, **kwargs)

    async def codegen_runner(request: dict[str, Any], _: Any, __: AgentConfig) -> dict[str, Any]:
        calls.append(request)
        return {"files": [{"path": "Page.tsx"}, {"path": "Page.css"}]}

    model.select_tasks = select_tasks
    events = [
        event
        async for event in run_agent(
            {
                "requirement": "设计项目列表并生成前端代码",
                "generation_contract": contract,
                "generation_id": "generation-codegen",
                "codegen_request": {"canvas": {"viewportIds": ["desktop"]}},
            },
            model,
            AgentConfig(),
            codegen_runner=codegen_runner,
        )
    ]

    assert len(calls) == 1
    assert calls[0]["document"]["version"] == "2.0.0"
    assert calls[0]["canvas"]["viewportIds"]
    assert events[-1]["event"] == "result"
    assert events[-1]["stage"] == "codegen"
    assert events[-1]["payload"]["document"]["version"] == "2.0.0"
    assert events[-1]["payload"]["codegen"]["files"][0]["path"] == "Page.tsx"


@pytest.mark.asyncio
async def test_root_does_not_force_codegen_when_model_returns_no_tasks() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    calls = 0

    async def codegen_runner(_: dict[str, Any], __: Any, ___: AgentConfig) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    events = [
        event
        async for event in run_agent(
            {
                "requirement": "只设计项目列表，不生成代码",
                "generation_contract": contract,
                "generation_id": "generation-design-only",
                "codegen_request": {"canvas": {"viewportIds": ["desktop"]}},
            },
            _fake_model(),
            AgentConfig(),
            codegen_runner=codegen_runner,
        )
    ]

    assert calls == 0
    assert events[-1]["event"] == "result"
    assert events[-1]["stage"] == "root"
    assert events[-1]["payload"]["document"]["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_agent_continues_pipeline_after_user_answers_input_request() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
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
    ] == ["requirement", "ui_design", "auto_layout"]
    assert resumed_events[-1]["event"] == "result"
    assert resumed_events[-1]["payload"]["document"]["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_agent_returns_timeout_when_child_agent_does_not_respond() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")

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
async def test_agent_total_timeout_is_not_extended_by_reasoning_activity() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")

    async def structured(*_: Any, on_reasoning: Any = None, **__: Any) -> dict[str, Any]:
        while True:
            await on_reasoning("持续推理")
            await asyncio.sleep(0.005)

    async def select_tasks(_: dict[str, Any], **__: Any) -> list[str]:
        return ["requirement"]

    started = time.monotonic()
    events = [
        event
        async for event in run_agent(
            {"requirement": "设计一个项目列表", "generation_contract": contract},
            SimpleNamespace(structured=structured, select_tasks=select_tasks),
            AgentConfig(node_timeout=0.2, total_timeout=0.03, max_retries=0),
        )
    ]

    assert time.monotonic() - started < 0.2
    assert any(event["payload"].get("status") == "reasoning" for event in events)
    assert events[-1]["event"] == "failed"
    assert events[-1]["payload"]["code"] == "agent_timeout"


@pytest.mark.asyncio
async def test_zero_timeouts_allow_slow_agent_to_finish() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
    model = _fake_model()
    structured = model.structured

    async def slow_structured(*args: Any, **kwargs: Any) -> dict[str, Any]:
        await asyncio.sleep(0.02)
        return await structured(*args, **kwargs)

    model.structured = slow_structured
    events = [
        event
        async for event in run_agent(
            {"requirement": "设计一个项目列表", "generation_contract": contract},
            model,
            AgentConfig(node_timeout=0, total_timeout=0),
        )
    ]

    assert events[-1]["event"] == "result"


@pytest.mark.asyncio
async def test_reasoning_is_truncated_without_blocking_final_output() -> None:
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")
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
    contract = _read("packages/design-contract/fixtures/v2/team-default.generation-contract.json")

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
