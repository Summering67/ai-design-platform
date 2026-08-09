from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..model import ModelPort
from .nodes import SpecificationState, check, repair


def build(model: ModelPort, contract: dict[str, Any]) -> Any:
    def check_node(state: SpecificationState) -> SpecificationState:
        return check(state, contract=contract)

    async def repair_node(state: SpecificationState) -> SpecificationState:
        return await repair(state, model=model, contract=contract)

    graph = StateGraph(SpecificationState)
    graph.add_node("check", check_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "check")
    graph.add_conditional_edges(
        "check",
        lambda state: (
            "repair"
            if state["report"]["issues"]
            and all(issue["repairable"] for issue in state["report"]["issues"])
            else END
        ),
        {"repair": "repair", END: END},
    )
    graph.add_edge("repair", END)
    return graph.compile()


async def run(
    document: dict[str, Any],
    prd: dict[str, Any],
    contract: dict[str, Any],
    model: ModelPort,
    resolved_user_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = await build(model, contract).ainvoke(
        {
            "document": document,
            "prd": prd,
            "contract": contract,
            "resolved_user_inputs": resolved_user_inputs or [],
        }
    )
    return {"report": result["report"], "document": result["corrected"]}
