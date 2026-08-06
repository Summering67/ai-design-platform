from __future__ import annotations

from typing import Any, Literal, TypedDict

EventName = Literal["run", "stage", "progress", "result", "failed", "cancelled"]


class AgentRunEvent(TypedDict, total=False):
    version: Literal["2.0.0"]
    event: EventName
    runId: str
    taskId: str
    parentTaskId: str | None
    stage: str
    attempt: int
    payload: dict[str, Any]


def event(
    name: EventName,
    run_id: str,
    stage: str,
    *,
    task_id: str = "root",
    parent_task_id: str | None = None,
    attempt: int = 1,
    payload: dict[str, Any] | None = None,
) -> AgentRunEvent:
    result: AgentRunEvent = {
        "version": "2.0.0",
        "event": name,
        "runId": run_id,
        "taskId": task_id,
        "parentTaskId": parent_task_id,
        "stage": stage,
        "attempt": attempt,
    }
    if payload is not None:
        result["payload"] = payload
    return result
