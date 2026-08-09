from __future__ import annotations

from typing import Any

from langgraph.graph import START, StateGraph

from ..model import ModelPort
from .nodes import UIDesignState, generate


def build(model: ModelPort) -> Any:
    async def generate_node(state: UIDesignState) -> UIDesignState:
        return await generate(state, model=model)

    graph = StateGraph(UIDesignState)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "generate")
    graph.set_finish_point("generate")
    return graph.compile()


async def run(
    prd: dict[str, Any],
    contract: dict[str, Any],
    model: ModelPort,
    resolved_user_inputs: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    result = await build(model).ainvoke(
        {
            "prd": prd,
            "contract": contract,
            "resolved_user_inputs": resolved_user_inputs or [],
            "run_id": run_id or "",
        }
    )
    return dict(result["candidate"])
