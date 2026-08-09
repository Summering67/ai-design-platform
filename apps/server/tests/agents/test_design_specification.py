from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ai_design_server.agents.contracts import validate_tree
from ai_design_server.agents.specification.graph import run as run_specification
from ai_design_server.agents.ui_design.graph import run as run_ui_design


def _read(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_ui_design_returns_initial_json_without_document_validation() -> None:
    initial = {"root": {"id": "root", "type": "page", "children": []}}
    schemas: list[dict[str, Any]] = []

    async def structured(
        _purpose: str, _payload: dict[str, Any], schema: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        schemas.append(schema)
        return initial

    model = type("Model", (), {"structured": staticmethod(structured)})()
    result = await run_ui_design({}, {}, model)

    assert result == initial
    assert schemas == [{"type": "object", "description": "初始化 UI JSON"}]


@pytest.mark.asyncio
async def test_specification_normalizes_initial_json_to_valid_document() -> None:
    initial = {"root": {"id": "root", "type": "page", "children": []}}
    contract = _read("packages/design-contract/fixtures/v1/team-default.generation-contract.json")
    repaired = _read("packages/design-contract/fixtures/v2/login-page.document.json")
    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    async def structured(
        purpose: str, payload: dict[str, Any], schema: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        calls.append((purpose, payload, schema))
        return repaired

    model = type("Model", (), {"structured": staticmethod(structured)})()
    result = await run_specification(initial, {}, contract, model)

    validate_tree(result["document"], contract)
    assert len(calls) == 1
    assert calls[0][1]["document"] == initial
    assert calls[0][1]["generationContract"] == contract
    assert calls[0][2]["title"] == "DesignDocument v2"
