from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from types import SimpleNamespace
from typing import Any, Protocol, cast

import httpx

from ..config import AIConfig
from .errors import AgentError, InputQuestion, InputRequired

ReasoningSink = Callable[[str], Awaitable[None]]
ActivitySink = Callable[[], Awaitable[None]]


class ModelPort(Protocol):
    async def structured(
        self,
        purpose: str,
        payload: Mapping[str, Any],
        schema: Mapping[str, Any],
        *,
        on_reasoning: ReasoningSink | None = None,
        on_activity: ActivitySink | None = None,
    ) -> dict[str, Any]: ...

    async def select_tasks(
        self, state: Mapping[str, Any], *, on_reasoning: ReasoningSink | None = None, on_activity: ActivitySink | None = None
    ) -> list[str]: ...


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _stream_delta(value: object) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise TypeError("模型流事件无效")
    choices = value.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("模型流事件缺少 choices")
    delta = choices[0].get("delta", {})
    if not isinstance(delta, dict):
        raise TypeError("模型流事件缺少 delta")
    reasoning = delta.get("reasoning_content", "")
    content = delta.get("content", "")
    if reasoning is None:
        reasoning = ""
    if content is None:
        content = ""
    if not isinstance(reasoning, str) or not isinstance(content, str):
        raise TypeError("模型流增量必须是字符串")
    return reasoning, content


async def _stream_completion(
    client: httpx.AsyncClient,
    config: AIConfig,
    messages: list[dict[str, str]],
    on_reasoning: ReasoningSink | None,
    on_activity: ActivitySink | None,
) -> str:
    parts: list[str] = []
    async with client.stream(
        "POST",
        _chat_completions_url(config.base_url),
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={
            "messages": messages,
            "model": config.model,
            "stream": True,
            "thinking": {"type": "enabled"},
        },
        timeout=config.request_timeout,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                raise ValueError("模型流事件格式无效")
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            reasoning, content = _stream_delta(json.loads(data))
            if (reasoning or content) and on_activity is not None:
                await on_activity()
            if reasoning and on_reasoning is not None:
                await on_reasoning(reasoning)
            if content:
                parts.append(content)
    return "".join(parts)


def _response_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "result"],
                "properties": {"kind": {"const": "result"}, "result": schema},
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "questions"],
                "properties": {
                    "kind": {"const": "input_required"},
                    "questions": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["id", "text"],
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "text": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                },
            },
        ]
    }


def _unwrap_response(value: dict[str, Any]) -> dict[str, Any]:
    kind = value.get("kind")
    if kind is None:
        return value
    if kind == "result" and isinstance(value.get("result"), dict):
        return value["result"]
    if kind != "input_required" or not isinstance(value.get("questions"), list):
        raise AgentError("invalid_model_response", "Agent 返回包络无效", retryable=True)
    questions: list[InputQuestion] = []
    seen: set[str] = set()
    for item in value["questions"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("text"), str):
            raise AgentError("invalid_model_response", "Agent 问题格式无效", retryable=True)
        question_id = item["id"].strip()
        text = item["text"].strip()
        if not question_id or not text or question_id in seen:
            raise AgentError("invalid_model_response", "Agent 问题格式无效", retryable=True)
        seen.add(question_id)
        questions.append(InputQuestion(question_id, text))
    if not questions:
        raise AgentError("invalid_model_response", "Agent 问题不能为空", retryable=True)
    raise InputRequired(questions)


def create_openai_model(client: httpx.AsyncClient, config: AIConfig) -> ModelPort:
    async def structured(
        purpose: str,
        payload: Mapping[str, Any],
        schema: Mapping[str, Any],
        *,
        on_reasoning: ReasoningSink | None = None,
        on_activity: ActivitySink | None = None,
    ) -> dict[str, Any]:
        prompt = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        schema_text = json.dumps(_response_schema(schema), ensure_ascii=False, separators=(",", ":"))
        try:
            content = await _stream_completion(
                client,
                config,
                [
                    {"role": "system", "content": f"你是 {purpose}。只返回符合 JSON Schema 的 JSON 对象，不要 Markdown。Schema: {schema_text}"},
                    {"role": "user", "content": prompt},
                ],
                on_reasoning,
                on_activity,
            )
            value = json.loads(content)
            if not isinstance(value, dict):
                raise TypeError("模型返回值不是对象")
            return _unwrap_response(value)
        except Exception as error:
            raise AgentError("model_unavailable", "Agent 模型不可用", retryable=True) from error

    async def select_tasks(
        state: Mapping[str, Any], *, on_reasoning: ReasoningSink | None = None, on_activity: ActivitySink | None = None
    ) -> list[str]:
        schema = {"type": "object", "required": ["tasks"], "properties": {"tasks": {"type": "array", "items": {"type": "string"}}}}
        result = await structured(
            "Root Supervisor",
            {"state": state, "instruction": "选择当前可执行的一个或多个已注册任务"},
            schema,
            on_reasoning=on_reasoning,
            on_activity=on_activity,
        )
        tasks = result.get("tasks")
        if not isinstance(tasks, list) or any(not isinstance(item, str) for item in tasks):
            raise AgentError("invalid_task_selection", "Root 任务选择无效", retryable=True)
        return tasks

    return cast(ModelPort, SimpleNamespace(structured=structured, select_tasks=select_tasks))


def bind_reasoning(model: ModelPort, on_reasoning: ReasoningSink, on_activity: ActivitySink | None = None) -> ModelPort:
    async def structured(
        purpose: str, payload: Mapping[str, Any], schema: Mapping[str, Any], **_: Any
    ) -> dict[str, Any]:
        return await model.structured(
            purpose, payload, schema, on_reasoning=on_reasoning, on_activity=on_activity
        )

    async def select_tasks(state: Mapping[str, Any], **_: Any) -> list[str]:
        return await model.select_tasks(state, on_reasoning=on_reasoning, on_activity=on_activity)

    return cast(ModelPort, SimpleNamespace(structured=structured, select_tasks=select_tasks))
