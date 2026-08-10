from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import AgentConfig
from .auto_layout.graph import run as run_layout
from .errors import AgentError, InputRequired
from .events import AgentRunEvent, EventName, event
from .model import ModelPort, bind_reasoning
from .requirement.graph import run as run_requirement
from .state import RootState, TaskRecord
from .ui_design.graph import run as run_ui_design

EventSink = Callable[[AgentRunEvent], Awaitable[None]]
LOGGER = logging.getLogger("ai_design_server.agents")
AGENT_LABELS = {
    "requirement": "需求分析",
    "ui_design": "UI 设计",
    "auto_layout": "自动布局",
}
TASK_ORDER = ("requirement", "ui_design", "auto_layout")
AGENT_OUTPUT_ROOT = Path(__file__).resolve().parents[3] / ".agent-outputs"


def _safe_output_segment(value: Any, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "")).strip(".-")
    return normalized[:80] or fallback


async def _save_agent_output(
    state: RootState, name: str, output: dict[str, Any], attempt: int
) -> None:
    generation_id = _safe_output_segment(state.get("generation_id"), "no-generation")
    run_id = _safe_output_segment(state.get("run_id"), "no-run")
    stage_number = TASK_ORDER.index(name) + 1
    target = (
        AGENT_OUTPUT_ROOT
        / generation_id
        / run_id
        / f"{stage_number:02d}-{name}-attempt-{attempt:02d}.json"
    )
    serialized = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def write() -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(target)

    try:
        await asyncio.to_thread(write)
    except OSError:
        LOGGER.warning(
            "保存 Agent JSON 失败",
            extra={
                "generation_id": state.get("generation_id"),
                "run_id": state.get("run_id"),
                "agent": name,
                "attempt": attempt,
            },
        )


def _ready(name: str, state: RootState) -> bool:
    completed = state.get("completed", {})
    return {
        "requirement": "prd" not in completed,
        "ui_design": "prd" in completed and "initial_ui_document" not in completed,
        "auto_layout": "initial_ui_document" in completed and "final_document" not in completed,
    }.get(name, False)


def _ready_tasks(state: RootState) -> list[str]:
    return [name for name in TASK_ORDER if _ready(name, state)]


def _catalog() -> dict[str, dict[str, Any]]:
    return {
        "requirement": {"requires": [], "provides": ["prd"]},
        "ui_design": {"requires": ["prd"], "provides": ["initial_ui_document"]},
        "auto_layout": {
            "requires": ["initial_ui_document", "prd"],
            "provides": ["validation", "final_document", "result"],
        },
    }


async def _emit(
    emit: EventSink,
    name: EventName,
    state: RootState,
    stage: str,
    *,
    task_id: str = "root",
    parent_task_id: str | None = None,
    attempt: int = 1,
    payload: dict[str, Any] | None = None,
) -> None:
    await emit(
        event(
            name,
            state["run_id"],
            stage,
            task_id=task_id,
            parent_task_id=parent_task_id,
            attempt=attempt,
            payload=payload,
        )
    )


async def _emit_input_required(
    emit: EventSink,
    state: RootState,
    error: InputRequired,
    *,
    stage: str,
    task_id: str,
    round_number: int = 1,
    attempt: int = 1,
) -> None:
    await _emit(
        emit,
        "input_required",
        state,
        stage,
        task_id=task_id,
        attempt=attempt,
        payload={
            "questions": [
                {
                    "id": question.id,
                    "header": question.header,
                    "question": question.text,
                    "isOther": question.is_other,
                    "options": [
                        {"label": option.label, "description": option.description}
                        for option in question.options
                    ],
                }
                for question in error.questions
            ],
            "round": round_number,
            "isBlocking": True,
        },
    )


async def _run_task(
    name: str, state: RootState, model: ModelPort, task_id: str, attempt: int
) -> dict[str, Any]:
    completed = state.get("completed", {})
    contract = state["generation_contract"]
    resolved_user_inputs = [
        item for item in state.get("resolved_user_inputs", []) if item.get("source_stage") == name
    ]
    if name == "requirement":
        return {"prd": await run_requirement(state["raw_requirement"], model, resolved_user_inputs)}
    if name == "ui_design":
        return {
            "initial_ui_document": await run_ui_design(
                completed["prd"],
                contract,
                model,
                resolved_user_inputs,
                run_id=state["run_id"],
            )
        }
    if name == "auto_layout":
        result = await run_layout(
            completed["initial_ui_document"],
            contract,
            model,
            run_id=state["run_id"],
            layout_requirements=[
                *completed["prd"].get("responsive", []),
                *completed["prd"].get("constraints", []),
            ],
        )
        return {
            "final_document": result["document"],
            "validation": result["validation"],
            "result": {
                "prd": completed["prd"],
                "validation": result["validation"],
                "document": result["document"],
            },
        }
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
        except InputRequired as required:
            required.source_stage = name
            required.source_task_id = task_id
            required.source_attempt = attempt
            raise
        except AgentError as agent_error:
            error = agent_error
        if not error.retryable or attempt > config.max_retries:
            raise error
        await _emit(
            emit,
            "progress",
            state,
            name,
            task_id=task_id,
            attempt=attempt,
            payload={"status": "retrying", "code": error.code},
        )
    raise AgentError("retry_exhausted", "Agent 重试耗尽")


async def execute(
    state: RootState, *, model: ModelPort, config: AgentConfig, emit: EventSink
) -> RootState:
    state.setdefault("task_catalog", _catalog())
    state.setdefault("completed", {})
    state.setdefault("tasks", {})
    state.setdefault("retry_counts", {})
    state.setdefault("task_history", [])
    state.setdefault("resolved_user_inputs", [])
    input_rounds = lambda stage: sum(
        1 for item in state["resolved_user_inputs"] if item.get("source_stage") == stage
    )
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
            selected = await bind_reasoning(
                model, on_root_reasoning, on_root_activity
            ).select_tasks(
                {
                    "target": state.get("target", "design"),
                    "completed": list(state["completed"]),
                    "resolvedUserInputs": [
                        item
                        for item in state.get("resolved_user_inputs", [])
                        if item.get("source_stage") == "root"
                    ],
                    "catalog": state["task_catalog"],
                    "history": state["task_history"],
                }
            )
            await _emit(
                emit,
                "progress",
                state,
                "root",
                payload={"status": "reasoning_completed"},
            )
        except InputRequired as required:
            round_number = input_rounds("root") + 1
            if round_number > 3:
                state["terminal"] = "failed"
                state["error"] = {"code": "input_round_limit", "message": "Root 追问次数超限"}
                await _emit(emit, "failed", state, "root", payload=state["error"])
                return state
            state["terminal"] = "awaiting_input"
            await _emit_input_required(
                emit, state, required, stage="root", task_id="root", round_number=round_number
            )
            return state
        unknown = [name for name in selected if name not in state["task_catalog"]]
        if unknown:
            state["terminal"] = "failed"
            state["error"] = {
                "code": "capability_unavailable",
                "message": "Root 选择了未注册 Agent 能力",
            }
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        selected = [
            name for name in selected if name in state["task_catalog"] and _ready(name, state)
        ]
        if not selected:
            selected = _ready_tasks(state)
        if not selected:
            state["terminal"] = "failed"
            state["error"] = {"code": "no_executable_task", "message": "Root 没有可执行任务"}
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        selected = selected[: config.max_concurrency]
        task_pairs = [(name, str(uuid4())) for name in selected]
        for name, task_id in task_pairs:
            state["tasks"][task_id] = TaskRecord(
                task_id=task_id,
                name=name,
                parent_task_id="root",
                status="running",
                attempt=1,
                depth=1,
            )
            LOGGER.info(
                "调用子 Agent：%s（%s）",
                AGENT_LABELS[name],
                name,
                extra={
                    "generation_id": state.get("generation_id"),
                    "run_id": state["run_id"],
                    "agent": name,
                    "task_id": task_id,
                    "attempt": 1,
                },
            )
            await _emit(
                emit,
                "stage",
                state,
                name,
                task_id=task_id,
                parent_task_id="root",
                payload={"status": "running"},
            )
        task_handles = [
            asyncio.create_task(_run_task_with_retry(name, state, model, task_id, config, emit))
            for name, task_id in task_pairs
        ]
        try:
            outputs = await asyncio.gather(*task_handles)
        except asyncio.CancelledError:
            for task in task_handles:
                task.cancel()
            await asyncio.gather(*task_handles, return_exceptions=True)
            state["terminal"] = "cancelled"
            await _emit(emit, "cancelled", state, "root")
            raise
        except InputRequired as required:
            for task in task_handles:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*task_handles, return_exceptions=True)
            name = required.source_stage or task_pairs[0][0]
            task_id = required.source_task_id or task_pairs[0][1]
            attempt = required.source_attempt or 1
            round_number = input_rounds(name) + 1
            if round_number > 3:
                state["terminal"] = "failed"
                state["error"] = {
                    "code": "input_round_limit",
                    "message": f"{AGENT_LABELS.get(name, name)} 追问次数超限",
                }
                await _emit(emit, "failed", state, name, task_id=task_id, payload=state["error"])
                return state
            state["terminal"] = "awaiting_input"
            await _emit_input_required(
                emit,
                state,
                required,
                stage=name,
                task_id=task_id,
                round_number=round_number,
                attempt=attempt,
            )
            return state
        except AgentError as error:
            for task in task_handles:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*task_handles, return_exceptions=True)
            state["terminal"] = "failed"
            state["error"] = {"code": error.code, "message": error.message}
            await _emit(emit, "failed", state, "root", payload=state["error"])
            return state
        for (name, task_id), output in zip(task_pairs, outputs, strict=True):
            state["completed"].update(output)
            state["tasks"][task_id]["status"] = "completed"
            state["task_history"].append(name)
            await _save_agent_output(state, name, output, state["tasks"][task_id]["attempt"])
            if LOGGER.isEnabledFor(logging.DEBUG):
                LOGGER.debug(
                    "子 Agent 输出：%s（%s）",
                    AGENT_LABELS[name],
                    name,
                    extra={
                        "generation_id": state.get("generation_id"),
                        "agent": name,
                        "task_id": task_id,
                        "output": json.dumps(output, ensure_ascii=False, separators=(",", ":")),
                    },
                )
            await _emit(
                emit,
                "progress",
                state,
                name,
                task_id=task_id,
                parent_task_id="root",
                payload={"status": "completed", "output": output},
            )
        if "result" in state["completed"]:
            state["result"] = state["completed"]["result"]
            state["terminal"] = "result"
            await _emit(emit, "result", state, "auto_layout", payload=state["result"])
            return state
    state["terminal"] = "failed"
    state["error"] = {"code": "task_limit", "message": "Agent 任务数量超限"}
    await _emit(emit, "failed", state, "root", payload=state["error"])
    return state
