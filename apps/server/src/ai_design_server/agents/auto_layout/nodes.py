from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import validate_tree
from ..model import ModelPort
from .layout import apply_layout
from .prompts import SYSTEM_PROMPT


class AutoLayoutState(TypedDict, total=False):
    document: dict[str, Any]
    prd: dict[str, Any]
    contract: dict[str, Any]
    plan: list[dict[str, Any]]
    result: dict[str, Any]
    changes: list[dict[str, Any]]


async def plan(state: AutoLayoutState, *, model: ModelPort) -> AutoLayoutState:
    response = await model.structured(
        SYSTEM_PROMPT,
        {"document": state["document"], "prd": state["prd"], "contract": state["contract"], "instruction": "只生成合法 Flex operations"},
        {"type": "object", "required": ["operations"], "properties": {"operations": {"type": "array", "items": {"type": "object"}}}},
    )
    operations = response.get("operations", [])
    if not isinstance(operations, list) or any(not isinstance(item, dict) for item in operations):
        raise ValueError("布局计划无效")
    result, changes = apply_layout(state["document"], operations, state["contract"])
    validate_tree(result, state["contract"])
    return {"result": result, "changes": changes, "plan": operations}
