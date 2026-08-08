from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate_tree
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class UIDesignState(TypedDict, total=False):
    prd: dict[str, Any]
    contract: dict[str, Any]
    candidate: dict[str, Any]
    error: str
    attempt: int


def _document_schema() -> dict[str, Any]:
    return load_schema("design-document.schema.json")


async def generate(state: UIDesignState, *, model: ModelPort) -> UIDesignState:
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"prd": state["prd"], "generationContract": state["contract"], "instruction": "生成完整初始 UI 树"},
        _document_schema(),
    )
    try:
        validate_tree(candidate, state["contract"])
    except Exception as error:
        if state.get("attempt", 1) > 1:
            raise
        return {**state, "error": str(error), "attempt": 2}
    return {"candidate": candidate, "attempt": state.get("attempt", 1)}


async def repair(state: UIDesignState, *, model: ModelPort) -> UIDesignState:
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"prd": state["prd"], "candidate": state.get("candidate"), "error": state.get("error"), "instruction": "只修复契约错误，保持业务节点 ID"},
        _document_schema(),
    )
    validate_tree(candidate, state["contract"])
    return {"candidate": candidate, "attempt": 2}
