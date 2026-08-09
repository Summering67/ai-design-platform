from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..model import ModelPort
from .nodes import UIDesignState, generate, repair


def build(model: ModelPort) -> Any:
    async def generate_node(state: UIDesignState) -> UIDesignState:
        return await generate(state, model=model)

    async def repair_node(state: UIDesignState) -> UIDesignState:
        return await repair(state, model=model)

    graph = StateGraph(UIDesignState)
    graph.add_node("generate", generate_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "generate")
    graph.add_conditional_edges("generate", lambda state: "repair" if state.get("error") else END, {"repair": "repair", END: END})
    graph.add_edge("repair", END)
    return graph.compile()


async def run(prd: dict[str, Any], contract: dict[str, Any], model: ModelPort, resolved_user_inputs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    result = await build(model).ainvoke({"prd": prd, "contract": contract, "attempt": 1, "resolved_user_inputs": resolved_user_inputs or []})
    return dict(result["candidate"])
