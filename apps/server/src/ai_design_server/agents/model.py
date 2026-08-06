from __future__ import annotations

import json
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, Protocol, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ..config import AIConfig
from .errors import AgentError


class ModelPort(Protocol):
    async def structured(self, purpose: str, payload: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]: ...

    async def select_tasks(self, state: Mapping[str, Any]) -> list[str]: ...


def _content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(item.get("text", "") for item in value if isinstance(item, dict))
    return str(value)


def create_openai_model(config: AIConfig) -> ModelPort:
    llm = ChatOpenAI(
        api_key=SecretStr(config.api_key),
        base_url=config.base_url,
        model=config.model,
        timeout=config.request_timeout,
        max_retries=0,
    )

    async def structured(
        purpose: str, payload: Mapping[str, Any], schema: Mapping[str, Any]
    ) -> dict[str, Any]:
        prompt = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        schema_text = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        try:
            response = await llm.ainvoke(
                [
                    SystemMessage(content=f"你是 {purpose}。只返回符合 JSON Schema 的 JSON 对象，不要 Markdown。Schema: {schema_text}"),
                    HumanMessage(content=prompt),
                ]
            )
            value = json.loads(_content(response.content))
            if not isinstance(value, dict):
                raise TypeError("模型返回值不是对象")
            return value
        except Exception as error:
            raise AgentError("model_unavailable", "Agent 模型不可用", retryable=True) from error

    async def select_tasks(state: Mapping[str, Any]) -> list[str]:
        schema = {"type": "object", "required": ["tasks"], "properties": {"tasks": {"type": "array", "items": {"type": "string"}}}}
        result = await structured("Root Supervisor", {"state": state, "instruction": "选择当前可执行的一个或多个已注册任务"}, schema)
        tasks = result.get("tasks")
        if not isinstance(tasks, list) or any(not isinstance(item, str) for item in tasks):
            raise AgentError("invalid_task_selection", "Root 任务选择无效", retryable=True)
        return tasks

    return cast(ModelPort, SimpleNamespace(structured=structured, select_tasks=select_tasks))
