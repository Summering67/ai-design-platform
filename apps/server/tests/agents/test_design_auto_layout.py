from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from ai_design_server.agents.auto_layout.compiler import compile_initial_ui_document
from ai_design_server.agents.auto_layout.graph import run as run_auto_layout
from ai_design_server.agents.contracts import validate_tree
from ai_design_server.agents.errors import ContractError
from ai_design_server.agents.ui_design.graph import run as run_ui_design

ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_ui_design_returns_strict_initial_ui_json() -> None:
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    schemas: list[dict[str, Any]] = []

    async def structured(
        _purpose: str, _payload: dict[str, Any], schema: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        schemas.append(schema)
        return initial

    result = await run_ui_design(
        {}, contract, type("Model", (), {"structured": staticmethod(structured)})()
    )

    assert result == initial
    assert schemas[0]["title"] == "Initial UI Document v1"


@pytest.mark.asyncio
async def test_ui_design_harness_collects_schema_and_semantic_issues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="ai_design_server.agents.harness")
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    initial["root"]["layout"]["gap"] = "8px"
    initial["root"]["children"][1]["id"] = "root"
    initial["root"]["children"][1]["tag"] = "ui.unknown"
    initial["root"]["children"][1]["tokens"] = ["color.unknown"]

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        return initial

    with pytest.raises(ContractError):
        await run_ui_design(
            {}, contract, type("Model", (), {"structured": staticmethod(structured)})()
        )

    traces = [
        record
        for record in caplog.records
        if getattr(record, "event_type", "") == "agent_harness_attempt"
    ]
    issues = json.loads(traces[-1].issues)

    assert traces[-1].failure_phase == "json_schema"
    assert {issue["code"] for issue in issues} >= {
        "schema_type",
        "ui_duplicate_id",
        "ui_component_forbidden",
        "ui_token_forbidden",
    }


def test_auto_layout_compiler_is_deterministic_and_valid() -> None:
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")

    first = compile_initial_ui_document(initial, contract)
    second = compile_initial_ui_document(initial, contract)

    assert first == second
    validate_tree(first, contract)
    assert first["root"]["id"] == initial["root"]["id"]
    assert first["root"]["children"][0]["text"] == "欢迎登录"


@pytest.mark.asyncio
async def test_auto_layout_compiles_before_requesting_layout_plan() -> None:
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    documents: list[dict[str, Any]] = []

    async def structured(
        _purpose: str, payload: dict[str, Any], _schema: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        documents.append(payload["document"])
        return {
            "version": "1.0.0",
            "viewport": {"width": 1440, "height": 900},
            "operations": [
                {
                    "nodeId": "root",
                    "layout": {"mode": "flex", "direction": "column", "gap": 16},
                }
            ],
        }

    result = await run_auto_layout(
        initial,
        {},
        contract,
        type("Model", (), {"structured": staticmethod(structured)})(),
    )

    assert documents[0]["version"] == "2.0.0"
    assert result["validation"]["passed"] is True
    validate_tree(result["document"], contract)


@pytest.mark.asyncio
async def test_auto_layout_does_not_call_model_when_compilation_fails() -> None:
    initial = _read("packages/design-contract/fixtures/v2/initial-ui-document.valid.json")
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    initial["root"]["children"][0]["id"] = "root"
    calls = 0

    async def structured(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {}

    with pytest.raises(ContractError):
        await run_auto_layout(
            initial,
            {},
            contract,
            type("Model", (), {"structured": staticmethod(structured)})(),
        )

    assert calls == 0
