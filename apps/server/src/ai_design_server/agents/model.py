from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from types import SimpleNamespace
from typing import Any, Protocol, TypedDict, cast

import httpx

from ..config import AIConfig
from .errors import AgentError, InputQuestion, InputQuestionOption, InputRequired

ReasoningSink = Callable[[str], Awaitable[None]]
ActivitySink = Callable[[], Awaitable[None]]
LOGGER = logging.getLogger("ai_design_server.agents.model")


class _StreamStats(TypedDict):
    response_bytes: int
    stream_event_count: int
    http_status: int | None


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
        self,
        state: Mapping[str, Any],
        *,
        on_reasoning: ReasoningSink | None = None,
        on_activity: ActivitySink | None = None,
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
    *,
    thinking: bool = True,
    stats: _StreamStats,
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
            "thinking": {"type": "enabled" if thinking else "disabled"},
        },
        timeout=httpx.Timeout(
            connect=config.request_timeout,
            read=None,
            write=config.request_timeout,
            pool=config.request_timeout,
        ),
    ) as response:
        stats["http_status"] = response.status_code
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
            stats["stream_event_count"] += 1
            reasoning, content = _stream_delta(json.loads(data))
            if (reasoning or content) and on_activity is not None:
                await on_activity()
            if thinking and reasoning and on_reasoning is not None:
                await on_reasoning(reasoning)
            if content:
                stats["response_bytes"] += len(content.encode())
                parts.append(content)
    return "".join(parts)


def _classify_model_error(error: Exception) -> AgentError:
    if isinstance(error, AgentError):
        return error
    if isinstance(error, httpx.ConnectTimeout):
        return AgentError("model_connect_timeout", "Agent 模型连接超时", retryable=True)
    if isinstance(error, httpx.ReadTimeout):
        return AgentError("model_read_timeout", "Agent 模型读取超时", retryable=True)
    if isinstance(error, httpx.TimeoutException):
        return AgentError("model_transport_timeout", "Agent 模型传输超时", retryable=True)
    if isinstance(error, TimeoutError):
        return AgentError("model_request_timeout", "Agent 模型请求超时", retryable=True)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            return AgentError("model_rate_limited", "Agent 模型请求被限流", retryable=True)
        if status in {401, 403}:
            return AgentError("model_unauthorized", "Agent 模型认证失败")
        return AgentError(
            "model_http_error",
            "Agent 模型服务响应异常",
            retryable=status >= 500,
        )
    if isinstance(error, (json.JSONDecodeError, TypeError, ValueError)):
        return AgentError("invalid_model_stream", "Agent 模型响应流无效", retryable=True)
    if isinstance(error, httpx.TransportError):
        return AgentError("model_transport_error", "Agent 模型传输失败", retryable=True)
    return AgentError("model_unavailable", "Agent 模型不可用")


def _log_model_attempt(
    config: AIConfig,
    phase: str,
    status: str,
    started: float,
    stats: _StreamStats,
    error: AgentError | None = None,
) -> None:
    extra = {
        "event_type": "agent_model_attempt",
        "model_phase": phase,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "response_bytes": stats["response_bytes"],
        "stream_event_count": stats["stream_event_count"],
        "http_status": stats["http_status"] or 0,
        "error_code": error.code if error is not None else "",
        "retryable": error.retryable if error is not None else False,
        "model": config.model,
    }
    log = LOGGER.info if error is None else LOGGER.warning
    log("Agent 模型子调用完成", extra=extra)


async def _structured_attempt(
    client: httpx.AsyncClient,
    config: AIConfig,
    messages: list[dict[str, str]],
    on_reasoning: ReasoningSink | None,
    on_activity: ActivitySink | None,
    *,
    phase: str,
    thinking: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    stats: _StreamStats = {
        "response_bytes": 0,
        "stream_event_count": 0,
        "http_status": None,
    }
    try:
        content = await _stream_completion(
            client,
            config,
            messages,
            on_reasoning,
            on_activity,
            thinking=thinking,
            stats=stats,
        )
        if not content.strip():
            raise AgentError("model_empty_response", "Agent 模型返回空响应", retryable=True)
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise AgentError(
                "invalid_model_json", "Agent 模型返回非 JSON", retryable=True
            ) from error
        if not isinstance(value, dict):
            raise AgentError("invalid_model_json", "Agent 模型返回值不是对象", retryable=True)
    except AgentError as error:
        _log_model_attempt(config, phase, "failed", started, stats, error)
        raise
    except Exception as error:
        classified = _classify_model_error(error)
        _log_model_attempt(config, phase, "failed", started, stats, classified)
        raise classified from error
    _log_model_attempt(config, phase, "success", started, stats)
    return value


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
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["id", "header", "question", "isOther", "options"],
                            "properties": {
                                "id": {"type": "string", "minLength": 1},
                                "header": {"type": "string", "minLength": 1, "maxLength": 40},
                                "question": {"type": "string", "minLength": 1},
                                "isOther": {"type": "boolean"},
                                "options": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 3,
                                    "items": {
                                        "type": "object",
                                        "additionalProperties": False,
                                        "required": ["label", "description"],
                                        "properties": {
                                            "label": {"type": "string", "minLength": 1},
                                            "description": {"type": "string", "minLength": 1},
                                        },
                                    },
                                },
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
        return cast(dict[str, Any], value["result"])
    if kind != "input_required" or not isinstance(value.get("questions"), list):
        raise AgentError("invalid_model_response", "Agent 返回包络无效", retryable=True)
    questions: list[InputQuestion] = []
    seen: set[str] = set()
    if not 1 <= len(value["questions"]) <= 3:
        raise AgentError("invalid_model_response", "Agent 问题数量无效", retryable=True)
    for item in value["questions"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not isinstance(item.get("header"), str)
            or not isinstance(item.get("question"), str)
            or not isinstance(item.get("isOther"), bool)
            or not isinstance(item.get("options"), list)
        ):
            raise AgentError("invalid_model_response", "Agent 问题格式无效", retryable=True)
        question_id = item["id"].strip()
        header = item["header"].strip()
        text = item["question"].strip()
        raw_options = item["options"]
        options: list[InputQuestionOption] = []
        option_labels: set[str] = set()
        for option in raw_options:
            if (
                not isinstance(option, dict)
                or not isinstance(option.get("label"), str)
                or not isinstance(option.get("description"), str)
            ):
                raise AgentError("invalid_model_response", "Agent 选项格式无效", retryable=True)
            label = option["label"].strip()
            description = option["description"].strip()
            if not label or not description or label in option_labels:
                raise AgentError("invalid_model_response", "Agent 选项格式无效", retryable=True)
            option_labels.add(label)
            options.append(InputQuestionOption(label, description))
        if (
            not question_id
            or not header
            or not text
            or question_id in seen
            or not 2 <= len(options) <= 3
        ):
            raise AgentError("invalid_model_response", "Agent 问题格式无效", retryable=True)
        seen.add(question_id)
        questions.append(InputQuestion(question_id, text, header, options, item["isOther"]))
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
        schema_text = json.dumps(
            _response_schema(schema), ensure_ascii=False, separators=(",", ":")
        )
        messages = [
            {
                "role": "system",
                "content": f"你是 {purpose}。只返回符合 JSON Schema 的 JSON 对象，不要 Markdown。若缺少必须由用户确认且无法安全推断的信息，返回 kind=input_required；每个问题提供 2-3 个互斥选项，将推荐项放在第一项并在 label 标注（推荐），选项仍不足时可用 isOther 开放自定义回答。否则返回 kind=result 并将业务对象放入 result。不得重复询问 resolvedUserInputs 已回答的问题，reasoning 中不要向用户提问。Schema: {schema_text}",
            },
            {"role": "user", "content": prompt},
        ]
        try:
            value = await _structured_attempt(
                client,
                config,
                messages,
                on_reasoning,
                on_activity,
                phase="thinking",
                thinking=True,
            )
        except AgentError as error:
            if error.code not in {"model_empty_response", "invalid_model_json"}:
                raise
            value = await _structured_attempt(
                client,
                config,
                messages,
                None,
                on_activity,
                phase="fallback",
                thinking=False,
            )
        return _unwrap_response(value)

    async def select_tasks(
        state: Mapping[str, Any],
        *,
        on_reasoning: ReasoningSink | None = None,
        on_activity: ActivitySink | None = None,
    ) -> list[str]:
        schema = {
            "type": "object",
            "required": ["tasks"],
            "properties": {"tasks": {"type": "array", "items": {"type": "string"}}},
        }
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

    return cast(
        ModelPort,
        SimpleNamespace(
            structured=structured,
            select_tasks=select_tasks,
            model_name=config.model,
        ),
    )


def bind_reasoning(
    model: ModelPort, on_reasoning: ReasoningSink, on_activity: ActivitySink | None = None
) -> ModelPort:
    async def structured(
        purpose: str, payload: Mapping[str, Any], schema: Mapping[str, Any], **_: Any
    ) -> dict[str, Any]:
        result = await model.structured(
            purpose, payload, schema, on_reasoning=on_reasoning, on_activity=on_activity
        )
        return _unwrap_response(result)

    async def select_tasks(state: Mapping[str, Any], **_: Any) -> list[str]:
        return await model.select_tasks(state, on_reasoning=on_reasoning, on_activity=on_activity)

    return cast(
        ModelPort,
        SimpleNamespace(
            structured=structured,
            select_tasks=select_tasks,
            model_name=getattr(model, "model_name", type(model).__name__),
        ),
    )
