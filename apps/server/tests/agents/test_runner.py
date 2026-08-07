from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_design_server.agents.runner import run_agent
from ai_design_server.config import AgentConfig

ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _fake_model() -> SimpleNamespace:
    prd = _read("packages/design-contract/fixtures/v2/standardized-prd.valid.json")
    document = _read("packages/design-contract/fixtures/v2/login-page.document.json")

    async def structured(purpose: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        if "将产品需求" in purpose:
            return prd
        if "Auto Layout" in purpose:
            return {"operations": [{"nodeId": "root", "mode": "flex", "direction": "column", "gap": 16}]}
        return document

    async def select_tasks(state: dict[str, Any]) -> list[str]:
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
    caplog.set_level(logging.INFO, logger="ai_design_server.agents")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    events = [event async for event in run_agent({"requirement": "设计一个项目列表", "generation_contract": contract}, _fake_model(), AgentConfig())]
    assert events[0]["event"] == "run"
    assert events[-1]["event"] == "result"
    assert events[-1]["payload"]["document"]["version"] == "2.0.0"
    outputs = [event["payload"]["output"] for event in events if event["event"] == "progress" and event["payload"].get("status") == "completed"]
    assert {next(iter(output)) for output in outputs} == {"prd", "initial_document", "validation", "final_document", "result"}
    assert [record.agent for record in caplog.records if record.message == "调用子 Agent"] == ["requirement", "ui_design", "specification", "auto_layout"]
