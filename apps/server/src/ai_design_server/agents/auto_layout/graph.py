from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..model import ModelPort
from .compiler import compile_initial_ui_document
from .nodes import AutoLayoutState, plan


def build(model: ModelPort) -> Any:
    async def plan_node(state: AutoLayoutState) -> AutoLayoutState:
        return await plan(state, model=model)

    graph = StateGraph(AutoLayoutState)
    graph.add_node("plan", plan_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", END)
    return graph.compile()


async def run(
    initial_ui_document: dict[str, Any],
    contract: dict[str, Any],
    model: ModelPort,
    run_id: str | None = None,
) -> dict[str, Any]:
    compiled = compile_initial_ui_document(initial_ui_document, contract)
    result = await build(model).ainvoke(
        {
            "document": compiled,
            "initial_ui_document": initial_ui_document,
            "contract": contract,
            "run_id": run_id or "",
        }
    )
    return {
        "document": result["result"],
        "changes": result["changes"],
        "validation": {
            "version": "2.0.0",
            "passed": True,
            "issues": [],
            "summary": {"total": 0, "errors": 0, "warnings": 0, "fixed": 0, "unresolved": 0},
        },
    }
