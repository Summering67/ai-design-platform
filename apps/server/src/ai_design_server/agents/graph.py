from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from ..config import AgentConfig
from .events import AgentRunEvent
from .model import ModelPort
from .state import RootState

EventSink = Callable[[AgentRunEvent], Awaitable[None]]


def build(
    model: ModelPort,
    config: AgentConfig,
    codegen_runner: Callable[[dict[str, Any], ModelPort, AgentConfig], Awaitable[dict[str, Any]]]
    | None = None,
) -> Any:
    async def supervise(state: RootState, runtime: Runtime) -> RootState:
        context: Mapping[str, Any] = runtime.context or {}
        sink = context.get("event_sink")
        if not callable(sink):
            raise TypeError("Agent event sink 未注入")
        from .supervisor import execute

        return await execute(
            state, model=model, config=config, emit=sink, codegen_runner=codegen_runner
        )

    graph = StateGraph(RootState)
    graph.add_node("supervise", supervise)
    graph.add_edge(START, "supervise")
    graph.add_edge("supervise", END)
    return graph.compile()
