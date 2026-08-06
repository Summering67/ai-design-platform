from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..model import ModelPort
from .nodes import AutoLayoutState, plan


def build(model: ModelPort) -> Any:
    async def plan_node(state: AutoLayoutState) -> AutoLayoutState:
        return await plan(state, model=model)

    graph = StateGraph(AutoLayoutState)
    graph.add_node("plan", plan_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", END)
    return graph.compile()


async def run(document: dict[str, Any], prd: dict[str, Any], contract: dict[str, Any], model: ModelPort) -> dict[str, Any]:
    result = await build(model).ainvoke({"document": document, "prd": prd, "contract": contract})
    return {"document": result["result"], "changes": result["changes"]}
