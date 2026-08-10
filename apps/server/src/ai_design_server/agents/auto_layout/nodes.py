from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate, validate_tree
from ..errors import ContractError
from ..harness import run_structured_harness
from ..model import ModelPort
from .layout import apply_layout
from .prompts import SYSTEM_PROMPT


class AutoLayoutState(TypedDict, total=False):
    document: dict[str, Any]
    initial_ui_document: dict[str, Any]
    contract: dict[str, Any]
    plan: list[dict[str, Any]]
    result: dict[str, Any]
    changes: list[dict[str, Any]]
    run_id: str


async def plan(state: AutoLayoutState, *, model: ModelPort) -> AutoLayoutState:
    def validate_plan(response: dict[str, Any]) -> None:
        validate("layout-plan.schema.json", response)
        operations = response.get("operations", [])
        if not isinstance(operations, list) or any(
            not isinstance(item, dict) for item in operations
        ):
            raise ContractError("invalid_layout_plan", "布局计划无效", path="/operations")
        result, _ = apply_layout(state["document"], operations, state["contract"])
        validate_tree(result, state["contract"])

    response = await run_structured_harness(
        model,
        SYSTEM_PROMPT,
        {"initialUiDocument": state["initial_ui_document"]},
        load_schema("layout-plan.schema.json"),
        validate_plan,
        stage="auto_layout",
        run_id=state.get("run_id"),
        trace_contract=state["contract"],
    )
    operations = response.get("operations", [])
    result, changes = apply_layout(state["document"], operations, state["contract"])
    return {"result": result, "changes": changes, "plan": operations}
