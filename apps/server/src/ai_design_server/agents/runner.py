from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypedDict
from uuid import uuid4

from ..config import AgentConfig
from .contracts import validate_event, validate_profile_contract
from .events import AgentRunEvent, event
from .graph import build
from .model import ModelPort


class AgentInput(TypedDict, total=False):
    requirement: str
    generation_contract: dict[str, Any]
    generation_id: str
    target: str
    resolved_user_inputs: list[dict[str, Any]]
    codegen_request: dict[str, Any]


async def run_agent(
    value: AgentInput,
    model: ModelPort,
    config: AgentConfig,
    *,
    codegen_runner: Callable[[dict[str, Any], ModelPort, AgentConfig], Awaitable[dict[str, Any]]]
    | None = None,
) -> AsyncIterator[AgentRunEvent]:
    run_id = str(uuid4())
    requirement = value.get("requirement", "").strip()
    if not requirement or len(requirement.encode()) > config.max_input_bytes:
        yield event(
            "failed",
            run_id,
            "root",
            payload={"code": "invalid_requirement", "message": "产品需求为空或超出大小限制"},
        )
        return
    contract = value.get("generation_contract")
    if not isinstance(contract, dict):
        yield event(
            "failed",
            run_id,
            "root",
            payload={"code": "invalid_generation_contract", "message": "生成契约无效"},
        )
        return
    try:
        validate_profile_contract(contract)
    except Exception as error:
        yield event(
            "failed",
            run_id,
            "root",
            payload={
                "code": getattr(error, "code", "invalid_generation_contract"),
                "message": "生成契约无效",
            },
        )
        return
    queue: asyncio.Queue[AgentRunEvent | None] = asyncio.Queue()

    async def emit(item: AgentRunEvent) -> None:
        validate_event(item)
        if len(json.dumps(item, ensure_ascii=False).encode()) > config.max_output_bytes:
            raise RuntimeError("Agent 输出超出大小限制")
        await queue.put(item)

    state = {
        "run_id": run_id,
        "generation_id": value.get("generation_id"),
        "raw_requirement": requirement,
        "generation_contract": contract,
        "target": value.get("target", "design"),
        "resolved_user_inputs": value.get("resolved_user_inputs", []),
        "codegen_request": value.get("codegen_request", {}),
    }

    async def execute_graph() -> Any:
        return await build(model, config, codegen_runner).ainvoke(
            state, context={"event_sink": emit}
        )

    task = asyncio.create_task(execute_graph())
    task.add_done_callback(lambda _: queue.put_nowait(None))
    await queue.put(event("run", run_id, "root", payload={"status": "started"}))
    terminal_emitted = False
    timed_out = False
    deadline = (
        asyncio.get_running_loop().time() + config.total_timeout
        if config.total_timeout > 0
        else None
    )
    try:
        while True:
            if task.done() and queue.empty():
                break
            remaining = (
                deadline - asyncio.get_running_loop().time() if deadline is not None else None
            )
            if remaining is not None and remaining <= 0:
                timed_out = True
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if not terminal_emitted:
                    yield event(
                        "failed",
                        run_id,
                        "root",
                        payload={"code": "agent_timeout", "message": "Agent 运行超时"},
                    )
                break
            try:
                timeouts = [
                    timeout
                    for timeout in (config.node_timeout, remaining)
                    if timeout is not None and timeout > 0
                ]
                item = (
                    await asyncio.wait_for(queue.get(), min(timeouts))
                    if timeouts
                    else await queue.get()
                )
            except TimeoutError:
                timed_out = True
                total_expired = (
                    deadline is not None and asyncio.get_running_loop().time() >= deadline
                )
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if not terminal_emitted:
                    yield event(
                        "failed",
                        run_id,
                        "root",
                        payload={
                            "code": "agent_timeout",
                            "message": "Agent 运行超时"
                            if total_expired
                            else "Agent 长时间未返回内容",
                        },
                    )
                break
            if item is None:
                break
            terminal_emitted = item.get("event") in {
                "result",
                "input_required",
                "failed",
                "cancelled",
            }
            yield item
        try:
            if not timed_out:
                await task
        except TimeoutError:
            if not terminal_emitted:
                yield event(
                    "failed",
                    run_id,
                    "root",
                    payload={"code": "agent_timeout", "message": "Agent 运行超时"},
                )
        except Exception:
            if not terminal_emitted:
                yield event(
                    "failed",
                    run_id,
                    "root",
                    payload={"code": "agent_failed", "message": "Agent 运行失败"},
                )
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        yield event("cancelled", run_id, "root")
        raise
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
