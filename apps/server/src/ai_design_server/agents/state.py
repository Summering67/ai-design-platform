from __future__ import annotations

from typing import Any, TypedDict


class TaskRecord(TypedDict, total=False):
    task_id: str
    name: str
    parent_task_id: str | None
    status: str
    attempt: int
    error_code: str
    depth: int


class RootState(TypedDict, total=False):
    run_id: str
    generation_id: str | None
    raw_requirement: str
    generation_contract: dict[str, Any]
    profile: dict[str, Any]
    target: str
    task_catalog: dict[str, dict[str, Any]]
    tasks: dict[str, TaskRecord]
    task_history: list[str]
    completed: dict[str, Any]
    active: list[str]
    retry_counts: dict[str, int]
    terminal: str | None
    result: dict[str, Any]
    error: dict[str, str]
