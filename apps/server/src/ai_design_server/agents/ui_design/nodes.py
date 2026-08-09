from __future__ import annotations

from typing import Any, TypedDict

from ..model import ModelPort
from .prompts import SYSTEM_PROMPT


class UIDesignState(TypedDict, total=False):
    prd: dict[str, Any]
    contract: dict[str, Any]
    candidate: dict[str, Any]
    resolved_user_inputs: list[dict[str, Any]]


async def generate(state: UIDesignState, *, model: ModelPort) -> UIDesignState:
    candidate = await model.structured(
        SYSTEM_PROMPT,
        {
            "prd": state["prd"],
            "resolvedUserInputs": state.get("resolved_user_inputs", []),
            "generationContract": state["contract"],
            "instruction": "生成完整初始 UI 树",
        },
        {"type": "object", "description": "初始化 UI JSON"},
    )
    return {"candidate": candidate}
