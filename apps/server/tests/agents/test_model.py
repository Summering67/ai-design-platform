from __future__ import annotations

import asyncio
import json

import httpx
import pytest

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
        with pytest.raises(AgentError, match="Agent 模型不可用"):
            await create_openai_model(client, _config()).structured(
                "需求分析", {"input": "后台管理页面"}, {"type": "object"}
            )


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
