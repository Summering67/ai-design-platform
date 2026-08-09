from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from ..config import AgentConfig
from .auto_layout.graph import run as run_layout
from .contracts import validate_tree
from .errors import AgentError, InputRequired
from .events import AgentRunEvent, EventName, event
from .model import ModelPort, bind_reasoning
from .requirement.graph import run as run_requirement
from .specification.graph import run as run_specification
from .state import RootState, TaskRecord
from .ui_design.graph import run as run_ui_design

EventSink = Callable[[AgentRunEvent], Awaitable[None]]
LOGGER = logging.getLogger("ai_design_server.agents")
AGENT_LABELS = {
    "requirement": "需求分析",
    "ui_design": "UI 设计",
    "specification": "规范校验",
    "auto_layout": "自动布局",
}


def _ready(name: str, state: RootState) -> bool:
    completed = state.get("completed", {})
    return {
        "requirement": "prd" not in completed,
        "ui_design": "prd" in completed and "initial_document" not in completed,
        "specification": "initial_document" in completed and "corrected_document" not in completed,
        "auto_layout": "corrected_document" in completed and completed.get("validation", {}).get("passed") is True and "final_document" not in completed,
        "final_gate": "final_document" in completed,
    }.get(name, False)


def _catalog() -> dict[str, dict[str, Any]]:
    return {
        "requirement": {"requires": [], "provides": ["prd"]},
        "ui_design": {"requires": ["prd"], "provides": ["initial_document"]},
        "specification": {"requires": ["initial_document", "prd"], "provides": ["validation", "corrected_document"]},
        "auto_layout": {"requires": ["corrected_document", "prd"], "provides": ["final_document"]},
        "final_gate": {"requires": ["final_document"], "provides": ["result"]},
    }


async def _emit(emit: EventSink, name: EventName, state: RootState, stage: str, *, task_id: str = "root", parent_task_id: str | None = None, attempt: int = 1, payload: dict[str, Any] | None = None) -> None:
    await emit(event(name, state["run_id"], stage, task_id=task_id, parent_task_id=parent_task_id, attempt=attempt, payload=payload))


async def _emit_input_required(emit: EventSink, state: RootState, error: InputRequired, *, stage: str, task_id: str, attempt: int = 1) -> None:
    await _emit(
        emit,
        "input_required",
        state,
        stage,
        task_id=task_id,
        attempt=attempt,
        payload={
            "questions": [{"id": question.id, "text": question.text} for question in error.questions],
            "isBlocking": True,
        },
    )


async def _run_task(name: str, state: RootState, model: ModelPort, task_id: str, attempt: int) -> dict[str, Any]:
    completed = state.get("completed", {})
    contract = state["generation_contract"]
    if name == "requirement":
        return {"prd": await run_requirement(state["raw_requirement"], model)}
    if name == "ui_design":
        return {"initial_document": await run_ui_design(completed["prd"], contract, model)}
    if name == "specification":
        result = await run_specification(completed["initial_document"], completed["prd"], contract, model)
        return {"validation": result["report"], "corrected_document": result["document"]}
    if name == "auto_layout":
        return {"final_document": (await run_layout(completed["corrected_document"], completed["prd"], contract, model))["document"]}
    if name == "final_gate":
        validate_tree(completed["final_document"], contract)
        return {"result": {"prd": completed["prd"], "validation": completed["validation"], "document": completed["final_document"]}}
    raise AgentError("capability_unavailable", "Agent 能力未注册")


async def _run_task_with_retry(
    name: str,
    state: RootState,
    model: ModelPort,
    task_id: str,
    config: AgentConfig,
    emit: EventSink,
) -> dict[str, Any]:
    for attempt in range(1, config.max_retries + 2):
        try:
            state["tasks"][task_id]["attempt"] = attempt
            await _emit(
                emit,
                "progress",
                state,
                name,
                task_id=task_id,
                attempt=attempt,
                payload={"status": "requesting"},
            )
            forwarded = 0
            truncated = False

            async def on_reasoning(
                delta: str,
                *,
                task_name: str = name,
                task_attempt: int = attempt,
                task_task_id: str = task_id,
            ) -> None:
                nonlocal forwarded, truncated
                if truncated or not delta:
                    return
                encoded = delta.encode()
                remaining = config.max_output_bytes - forwarded
                if remaining <= 0:
                    truncated = True
                    await _emit(
                        emit,
                        "progress",
                        state,
                        task_name,
                        task_id=task_task_id,
                        attempt=task_attempt,
                        payload={"status": "reasoning_truncated"},
                    )
                    return
                visible = encoded[:remaining].decode(errors="ignore")
                if visible:
                    forwarded += len(visible.encode())
                    await _emit(
                        emit,
                        "progress",
                        state,
                        task_name,
                        task_id=task_task_id,
                        attempt=task_attempt,
                        payload={"status": "reasoning", "delta": visible},
                    )
                if forwarded < len(encoded):
                    truncated = True
                    await _emit(
                        emit,
                        "progress",
                        state,
                        task_name,
                        task_id=task_task_id,
                        attempt=task_attempt,
                        payload={"status": "reasoning_truncated"},
                    )

            async def on_activity(*, task_attempt: int = attempt) -> None:
                await _emit(
                    emit,
                    "progress",
                    state,
                    name,
                    task_id=task_id,
                    attempt=task_attempt,
                    payload={"status": "activity"},
                )

            return await _run_task(
                name,
                state,
                bind_reasoning(model, on_reasoning, on_activity),
                task_id,
                attempt,
            )
        except AgentError as agent_error:
            error = agent_error
        if not error.retryable or attempt > config.max_retries:
            raise error
        await _emit(emit, "progress", state, name, task_id=task_id, attempt=attempt, payload={"status": "retrying", "code": error.code})
    raise AgentError("retry_exhausted", "Agent 重试耗尽")


async def execute(state: RootState, *, model: ModelPort, config: AgentConfig, emit: EventSink) -> RootState:
    state.setdefault("task_catalog", _catalog())
    state.setdefault("completed", {})
    state.setdefault("tasks", {})
    state.setdefault("retry_counts", {})
    state.setdefault("task_history", [])
    for _ in range(config.max_tasks):
        if state.get("terminal"):
            return state
        async def on_root_reasoning(delta: str) -> None:
            if delta:
                await _emit(
                    emit,
                    "progress",
                    state,
                    "root",
                    payload={"status": "reasoning", "delta": delta},
                )

        async def on_root_activity() -> None:
            await _emit(emit, "progress", state, "root", payload={"status": "activity"})

        try:
            selected = await bind_reasoning(model, on_root_reasoning, on_root_activity).select_tasks(
                {"target": state.get("target", "design"), "completed": list(state["completed"]), "catalog": state["task_catalog"], "history": state["task_history"]}
            )
        except InputRequired as required:
            state["terminal"] = "awaiting_input"
            await _emit_input_required(emit, state, required, stage="root", task_id="root")
            return state
        unknown = [name for name in selected if name not in state["task_catalog"]]
        if unknown:
            state["terminal"] = "failed"
            state["error"] = {"code": "capability_unavailable", "message": "Root 选择了未注册 Agent 能力"}
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        selected = [name for name in selected if name in state["task_catalog"] and _ready(name, state)]
        if not selected:
            selected = [name for name in ("requirement", "ui_design", "specification", "auto_layout", "final_gate") if _ready(name, state)]
        if not selected:
            state["terminal"] = "failed"
            state["error"] = {"code": "no_executable_task", "message": "Root 没有可执行任务"}
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        selected = selected[: config.max_concurrency]
        task_pairs = [(name, str(uuid4())) for name in selected]
        for name, task_id in task_pairs:
            state["tasks"][task_id] = TaskRecord(task_id=task_id, name=name, parent_task_id="root", status="running", attempt=1, depth=1)
            if name != "final_gate":
                LOGGER.info(
                    "调用子 Agent：%s（%s）",
                    AGENT_LABELS[name],
                    name,
                    extra={"generation_id": state.get("generation_id"), "run_id": state["run_id"], "agent": name, "task_id": task_id, "attempt": 1},
                )
            await _emit(emit, "stage", state, name, task_id=task_id, parent_task_id="root", payload={"status": "running"})
        try:
            outputs = await asyncio.gather(*[_run_task_with_retry(name, state, model, task_id, config, emit) for name, task_id in task_pairs])
        except asyncio.CancelledError:
            state["terminal"] = "cancelled"
            await _emit(emit, "cancelled", state, "root")
            raise
        except InputRequired as required:
            state["terminal"] = "awaiting_input"
            name, task_id = task_pairs[0]
            await _emit_input_required(emit, state, required, stage=name, task_id=task_id)
            return state
        except AgentError as error:
            state["terminal"] = "failed"
            state["error"] = {"code": error.code, "message": error.message}
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        for (name, task_id), output in zip(task_pairs, outputs, strict=True):
            state["completed"].update(output)
            state["tasks"][task_id]["status"] = "completed"
            state["task_history"].append(name)
            if name != "final_gate" and LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug(
                    "子 Agent 输出：%s（%s）",
                    AGENT_LABELS[name],
                    name,
                    extra={"generation_id": state.get("generation_id"), "agent": name, "task_id": task_id, "output": json.dumps(output, ensure_ascii=False, separators=(",", ":"))},
                )
            await _emit(emit, "progress", state, name, task_id=task_id, parent_task_id="root", payload={"status": "completed", "output": output})
        if "result" in state["completed"]:
            state["result"] = state["completed"]["result"]
            state["terminal"] = "result"
            await _emit(emit, "result", state, "final_gate", payload=state["result"])
            return state
    state["terminal"] = "failed"
    state["error"] = {"code": "task_limit", "message": "Agent 任务数量超限"}
    await _emit(emit, "failed", state, "root", payload=state["error"])
    return state
