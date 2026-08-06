from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import validate_tree
from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class UIDesignState(TypedDict, total=False):
    prd: dict[str, Any]
    contract: dict[str, Any]
    candidate: dict[str, Any]
    error: str
    attempt: int


async def generate(state: UIDesignState, *, model: ModelPort) -> UIDesignState:
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {"prd": state["prd"], "generationContract": state["contract"], "instruction": "生成完整初始 UI 树"},
        {"type": "object", "description": "DesignDocument v2"},
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
        {"type": "object", "description": "DesignDocument v2"},
    )
    validate_tree(candidate, state["contract"])
    return {"candidate": candidate, "attempt": 2}
