from __future__ import annotations

from typing import Any, TypedDict

from ..contracts import load_schema, validate, validate_tree
from ..errors import ContractError
from ..harness import run_structured_harness
from ..model import ModelPort
from .layout import apply_layout, resolve_layouts
from .prompts import SYSTEM_PROMPT


class AutoLayoutState(TypedDict, total=False):
    document: dict[str, Any]
    initial_ui_document: dict[str, Any]
    contract: dict[str, Any]
    plan: list[dict[str, Any]]
    result: dict[str, Any]
    changes: list[dict[str, Any]]
    run_id: str
    layout_requirements: list[dict[str, Any]]
    viewports: list[dict[str, Any]]
    measurements: dict[str, dict[str, Any]]


async def plan(state: AutoLayoutState, *, model: ModelPort) -> AutoLayoutState:
    def validate_plan(response: dict[str, Any]) -> None:
        validate("layout-plan.schema.json", response)
        operations = response.get("operations", [])
        if not isinstance(operations, list) or any(
            not isinstance(item, dict) for item in operations
        ):
            raise ContractError("invalid_layout_plan", "布局计划无效", path="/operations")
        known_viewports = {
            item.get("id")
            for item in state.get("viewports", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if known_viewports:
            for index, operation in enumerate(operations):
                responsive = operation.get("responsive")
                if isinstance(responsive, dict) and any(
                    viewport_id not in known_viewports for viewport_id in responsive
                ):
                    raise ContractError(
                        "layout_viewport_unknown",
                        "布局计划引用未声明的 viewport",
                        path=f"/operations/{index}/responsive",
                    )
        result, _ = apply_layout(state["document"], operations, state["contract"])
        if state.get("measurements"):
            result["resolvedLayouts"] = resolve_layouts(
                result, state.get("viewports"), state["measurements"]
            )
        validate_tree(result, state["contract"])

    response = await run_structured_harness(
        model,
        SYSTEM_PROMPT,
        {
            "initialUiDocument": state["initial_ui_document"],
            "layoutRequirements": state.get("layout_requirements", []),
            "layoutCapabilities": state["contract"].get("layout", {}),
            "viewports": state.get("viewports", []),
            "measuredNodeIds": sorted(state.get("measurements", {})),
        },
        load_schema("layout-plan.schema.json"),
        validate_plan,
        stage="auto_layout",
        run_id=state.get("run_id"),
        trace_contract=state["contract"],
    )
    operations = response.get("operations", [])
    result, changes = apply_layout(state["document"], operations, state["contract"])
    if state.get("measurements"):
        result["resolvedLayouts"] = resolve_layouts(
            result, state.get("viewports"), state["measurements"]
        )
    return {"result": result, "changes": changes, "plan": operations}
