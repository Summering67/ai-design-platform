from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ai_design_server.agents.codegen.agent import run_codegen
from ai_design_server.agents.codegen.prompts import (
    GENERATE_INSTRUCTION,
    REPAIR_INSTRUCTION,
    VISUAL_REVIEW_INSTRUCTION,
)
from ai_design_server.agents.errors import AgentError
from ai_design_server.config import AgentConfig

ROOT = Path(__file__).resolve().parents[4]


def _request() -> dict[str, Any]:
    return json.loads(
        (ROOT / "packages/design-contract/fixtures/v2/codegen-request.valid.json").read_text(
            encoding="utf-8"
        )
    )


class FakeModel:
    supports_vision = True

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self.purposes: list[str] = []

    async def structured_multimodal(self, purpose: str, parts: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
        self.purposes.append(purpose)
        self.calls.append(parts)
        if len(self.calls) == 1:
            return {
                "viewportIds": ["desktop"],
                "componentMappings": [{"nodeId": "root", "renderAs": "div"}],
                "layoutStrategy": "使用 flex 保留结构化布局事实",
                "styleStrategy": "使用 Tailwind 和作用域 CSS 表达视觉样式",
                "assets": [],
                "risks": [],
                "summary": "使用语义容器生成展示型页面。",
            }
        if len(self.calls) in {2, 3}:
            return {
                "files": [
                    {"path": "CodegenFixture.tsx", "content": "import './CodegenFixture.css'; export default function CodegenFixture() { return <div />; }"},
                    {"path": "CodegenFixture.css", "content": ".codegen-fixture {}"},
                ],
                "summary": "生成 React 展示型组件。",
            }
        return {"issues": []}


class FakeVerifier:
    async def verify(self, workspace: Any) -> list[dict[str, Any]]:
        return []


class RepairVerifier:
    def __init__(self) -> None:
        self.calls = 0

    async def verify(self, workspace: Any) -> list[dict[str, Any]]:
        self.calls += 1
        return [] if self.calls > 1 else [{"tool": "tsc", "rule": "TS2322", "file": "CodegenFixture.tsx", "line": 1, "message": "type mismatch"}]


class ExhaustingVerifier:
    async def verify(self, workspace: Any) -> list[dict[str, Any]]:
        return [{"tool": "eslint", "rule": "no-error", "file": "CodegenFixture.tsx", "line": 1, "message": "still invalid"}]


class FakeRenderer:
    async def render(self, workspace: Any, viewport_id: str, width: int, height: int) -> bytes:
        return b"preview"


@pytest.mark.asyncio
async def test_codegen_agent_passes_json_and_image_through_visual_loop() -> None:
    model = FakeModel()
    result = await run_codegen(
        _request(),
        model,
        AgentConfig(max_retries=1),
        verifier=FakeVerifier(),
        renderer=FakeRenderer(),
    )

    assert {file["path"] for file in result["files"]} == {"CodegenFixture.tsx", "CodegenFixture.css"}
    assert len(model.calls) == 3
    assert any(part["type"] == "image_url" for part in model.calls[0])
    assert model.calls[1][-1] == {"type": "text", "text": GENERATE_INSTRUCTION}
    assert model.calls[2][-1] == {"type": "text", "text": VISUAL_REVIEW_INSTRUCTION}
    assert model.calls[2][-2]["image_url"]["url"].startswith("data:image/png;base64,")
    assert result["verification"]["checks"][-1]["name"] == "visual"


@pytest.mark.asyncio
async def test_codegen_agent_rejects_non_visual_model_before_generation() -> None:
    model = SimpleNamespace(supports_vision=False)

    with pytest.raises(Exception, match="视觉输入"):
        await run_codegen(
            _request(),
            model,
            AgentConfig(max_retries=1),
            verifier=FakeVerifier(),
            renderer=FakeRenderer(),
        )


@pytest.mark.asyncio
async def test_codegen_agent_repairs_static_diagnostics_with_bounded_attempts() -> None:
    model = FakeModel()
    verifier = RepairVerifier()
    result = await run_codegen(
        _request(),
        model,
        AgentConfig(max_retries=1, codegen_repair_attempts=1),
        verifier=verifier,
        renderer=FakeRenderer(),
    )

    assert result["verification"]["repairAttempts"] == 1
    assert verifier.calls == 2
    assert model.purposes[1:3] == ["多模态 Codegen Agent", "多模态 Codegen Agent"]
    assert model.calls[1][:-1] == model.calls[2][: len(model.calls[1]) - 1]
    assert model.calls[2][-1] == {"type": "text", "text": REPAIR_INSTRUCTION}


@pytest.mark.asyncio
async def test_codegen_agent_stops_when_static_repairs_are_exhausted() -> None:
    with pytest.raises(AgentError) as error:
        await run_codegen(
            _request(),
            FakeModel(),
            AgentConfig(max_retries=1, codegen_repair_attempts=1),
            verifier=ExhaustingVerifier(),
            renderer=FakeRenderer(),
        )

    assert error.value.code == "codegen_verification_failed"
