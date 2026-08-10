from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
import pytest

from ai_design_server.agents import model as model_module
from ai_design_server.agents.errors import AgentError, InputRequired
from ai_design_server.agents.model import create_openai_model
from ai_design_server.config import AIConfig


def _config() -> AIConfig:
    return AIConfig(base_url="https://ai.test", api_key="test-key", model="deepseek-v4-flash")


@pytest.mark.asyncio
async def test_structured_streams_reasoning_and_content() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = (
            'data: {"choices":[{"delta":{"reasoning_content":"先分析需求"}}]}\n'
            'data: {"choices":[{"delta":{"reasoning_content":"，再组织结构"}}]}\n'
            'data: {"choices":[{"delta":{"content":"{\\"tasks\\":[\\"requirement\\"]}"}}]}\n'
            "data: [DONE]\n"
        )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body.encode()
        )

    reasoning: list[str] = []

    async def on_reasoning(value: str) -> None:
        reasoning.append(value)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await create_openai_model(client, _config()).structured(
            "Root Supervisor",
            {"input": "后台管理页面"},
            {"type": "object"},
            on_reasoning=on_reasoning,
        )

    assert reasoning == ["先分析需求", "，再组织结构"]
    assert result == {"tasks": ["requirement"]}
    request_payload = json.loads(requests[0].content)
    assert request_payload["stream"] is True
    assert request_payload["thinking"] == {"type": "enabled"}


@pytest.mark.asyncio
async def test_structured_rejects_malformed_stream() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"choices":[]}\n\ndata: [DONE]\n',
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AgentError, match="Agent 模型响应流无效") as raised:
            await create_openai_model(client, _config()).structured(
                "需求分析", {"input": "后台管理页面"}, {"type": "object"}
            )

    assert raised.value.code == "invalid_model_stream"
    assert raised.value.retryable is True


@pytest.mark.asyncio
async def test_structured_input_required_is_a_control_signal() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        value = {
            "kind": "input_required",
            "questions": [
                {
                    "id": "brand-color",
                    "header": "品牌颜色",
                    "question": "品牌主色是什么？",
                    "isOther": True,
                    "options": [
                        {"label": "沿用现有蓝色（推荐）", "description": "保持产品视觉一致。"},
                        {"label": "改用紫色", "description": "增强设计工具的创意感。"},
                    ],
                }
            ],
        }
        body = (
            f"data: {json.dumps({'choices': [{'delta': {'content': json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False)}\n"
            "data: [DONE]\n"
        )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body.encode()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InputRequired) as error:
            await create_openai_model(client, _config()).structured(
                "UI Design", {}, {"type": "object"}
            )

    assert [(item.id, item.text) for item in error.value.questions] == [
        ("brand-color", "品牌主色是什么？")
    ]
    assert error.value.questions[0].header == "品牌颜色"
    assert [item.label for item in error.value.questions[0].options] == [
        "沿用现有蓝色（推荐）",
        "改用紫色",
    ]


@pytest.mark.asyncio
async def test_structured_retries_without_thinking_when_only_reasoning_is_returned() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            body = (
                'data: {"choices":[{"delta":{"reasoning_content":"Q1 请选择业务领域"}}]}\n'
                "data: [DONE]\n"
            )
        else:
            value = {
                "kind": "input_required",
                "questions": [
                    {
                        "id": "business-domain",
                        "header": "业务领域",
                        "question": "这个后台管理页面主要用来管理什么？",
                        "isOther": True,
                        "options": [
                            {
                                "label": "通用数据概览（推荐）",
                                "description": "生成后台首页和仪表盘。",
                            },
                            {
                                "label": "用户/成员管理",
                                "description": "生成用户列表管理页面。",
                            },
                        ],
                    }
                ],
            }
            body = (
                f"data: {json.dumps({'choices': [{'delta': {'content': json.dumps(value, ensure_ascii=False)}}]}, ensure_ascii=False)}\n"
                "data: [DONE]\n"
            )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body.encode()
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InputRequired) as error:
            await create_openai_model(client, _config()).structured(
                "需求分析", {"input": "后台管理页面"}, {"type": "object"}
            )

    assert error.value.questions[0].id == "business-domain"
    assert [json.loads(request.content)["thinking"] for request in requests] == [
        {"type": "enabled"},
        {"type": "disabled"},
    ]


@pytest.mark.asyncio
async def test_structured_propagates_cancellation() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(_: httpx.Request) -> httpx.Response:
        started.set()
        await release.wait()
        return httpx.Response(200, content=b"data: [DONE]\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        task = asyncio.create_task(
            create_openai_model(client, _config()).structured(
                "需求分析", {"input": "后台管理页面"}, {"type": "object"}
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_structured_thinking_is_not_limited_by_request_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activities = 0

    async def stream_slowly(
        _client: Any,
        _config: Any,
        _messages: Any,
        _on_reasoning: Any,
        on_activity: Any,
        *,
        thinking: bool,
        stats: dict[str, Any],
    ) -> str:
        assert thinking is True
        nonlocal activities
        stats["stream_event_count"] += 1
        activities += 1
        if on_activity is not None:
            await on_activity()
        await asyncio.sleep(0.05)
        return '{"kind":"result","result":{}}'

    async def on_activity() -> None:
        return None

    monkeypatch.setattr(model_module, "_stream_completion", stream_slowly)
    config = _config().model_copy(update={"request_timeout": 0.03})
    async with httpx.AsyncClient() as client:
        result = await create_openai_model(client, config).structured(
            "UI Design", {}, {"type": "object"}, on_activity=on_activity
        )

    assert activities == 1
    assert result == {}


@pytest.mark.asyncio
async def test_fallback_read_timeout_keeps_retryable_cause(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="ai_design_server.agents.model")
    requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"choices":[{"delta":{"content":"not-json"}}]}\n\ndata: [DONE]\n',
            )
        raise httpx.ReadTimeout("read timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AgentError) as raised:
            await create_openai_model(client, _config()).structured(
                "UI Design", {}, {"type": "object"}
            )

    traces = [
        record
        for record in caplog.records
        if getattr(record, "event_type", "") == "agent_model_attempt"
    ]
    assert raised.value.code == "model_read_timeout"
    assert raised.value.retryable is True
    assert [(record.model_phase, record.error_code) for record in traces] == [
        ("thinking", "invalid_model_json"),
        ("fallback", "model_read_timeout"),
    ]
    assert traces[0].json_error_position == 0
    assert traces[0].json_error_line == 1
    assert traces[0].json_error_column == 1
    assert traces[0].json_is_fenced is False
    assert all(not hasattr(record, "response_body") for record in traces)


@pytest.mark.asyncio
async def test_authentication_failure_is_not_retried() -> None:
    requests = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(401, content=b'{"error":"unauthorized"}')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AgentError) as raised:
            await create_openai_model(client, _config()).structured(
                "UI Design", {}, {"type": "object"}
            )

    assert requests == 1
    assert raised.value.code == "model_unauthorized"
    assert raised.value.retryable is False
