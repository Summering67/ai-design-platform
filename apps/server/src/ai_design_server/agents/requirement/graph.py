from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from ..model import ModelPort
from .nodes import RequirementState, parse, repair


def build(model: ModelPort) -> Any:
    async def parse_node(state: RequirementState) -> RequirementState:
        return await parse(state, model=model)

    async def repair_node(state: RequirementState) -> RequirementState:
        return await repair(state, model=model)

    graph = StateGraph(RequirementState)
    graph.add_node("parse", parse_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "parse")
    graph.add_conditional_edges("parse", lambda state: "repair" if state.get("error") else END, {"repair": "repair", END: END})
    graph.add_edge("repair", END)
    return graph.compile()


async def run(value: str, model: ModelPort) -> dict[str, Any]:
    result = await build(model).ainvoke({"input": value, "attempt": 1})
    return dict(result["candidate"])
