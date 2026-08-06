from __future__ import annotations

import json
import os
import re
from http.cookies import SimpleCookie
from typing import Any
from uuid import UUID

import httpx
import pytest

GO_API_URL = os.getenv("GO_PARITY_API_URL", "").rstrip("/")
PYTHON_API_URL = os.getenv("PYTHON_PARITY_API_URL", "").rstrip("/")
PASSWORD = os.getenv("API_PARITY_PASSWORD", "")
ISOLATED = os.getenv("API_PARITY_ISOLATED") == "1"
READY = bool(GO_API_URL and PYTHON_API_URL and PASSWORD and ISOLATED)

pytestmark = pytest.mark.skipif(
    not READY,
    reason=(
        "需要 GO_PARITY_API_URL、PYTHON_PARITY_API_URL、API_PARITY_PASSWORD，"
        "并显式设置 API_PARITY_ISOLATED=1 确认双端使用隔离数据"
    ),
)

FIRST_MESSAGE_ID = "71000000-0000-0000-0000-000000000001"
SECOND_MESSAGE_ID = "71000000-0000-0000-0000-000000000002"
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def _sse(value: str) -> list[dict[str, Any]]:
    events = []
    for chunk in value.split("\n\n"):
        if not chunk.strip():
            continue
        lines = dict(line.split(": ", 1) for line in chunk.splitlines() if ": " in line)
        events.append({"event": lines["event"], "data": json.loads(lines["data"])})
    return events


def _cookie(header: str) -> dict[str, object]:
    parsed = SimpleCookie()
    parsed.load(header)
    morsel = parsed["aidp_session"]
    return {
        "value": "<token>" if morsel.value else "",
        "path": morsel["path"],
        "max_age": morsel["max-age"],
        "httponly": bool(morsel["httponly"]),
        "samesite": morsel["samesite"].lower(),
    }


def _response(response: httpx.Response, sse: bool = False) -> dict[str, object]:
    result: dict[str, object] = {"status": response.status_code}
    if response.headers.get("set-cookie"):
        result["cookie"] = _cookie(response.headers["set-cookie"])
    if sse:
        result["sse"] = _sse(response.text)
    elif response.content:
        result["json"] = response.json()
    return result


async def _snapshot(base_url: str) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=20) as client:
        snapshots.append(_response(await client.get("/health/live")))
        snapshots.append(_response(await client.get("/api/auth/me")))
        snapshots.append(
            _response(
                await client.post(
                    "/api/auth/login",
                    json={"email": "developer@local.test", "password": PASSWORD, "extra": True},
                )
            )
        )
        snapshots.append(
            _response(
                await client.post(
                    "/api/auth/login",
                    json={"email": "developer@local.test", "password": "wrong"},
                )
            )
        )
        snapshots.append(
            _response(
                await client.post(
                    "/api/auth/login",
                    json={"email": "developer@local.test", "password": PASSWORD},
                )
            )
        )
        snapshots.append(_response(await client.get("/api/auth/me")))

        created_response = await client.post(
            "/api/projects",
            json={"message_id": FIRST_MESSAGE_ID, "content": "等价验证首条消息"},
        )
        created_events = _sse(created_response.text)
        snapshots.append(_response(created_response, sse=True))
        generation = created_events[0]["data"]
        assert isinstance(generation, dict)
        project_id = generation["project_id"]
        first_message_id = generation["message_id"]

        snapshots.append(_response(await client.get(f"/api/projects/{project_id}")))
        generated_response = await client.post(
            f"/api/projects/{project_id}/generations",
            json={"message_id": SECOND_MESSAGE_ID, "content": "等价验证后续消息"},
        )
        generated_events = _sse(generated_response.text)
        snapshots.append(_response(generated_response, sse=True))
        second_generation = generated_events[0]["data"]
        assert isinstance(second_generation, dict)
        generation_id = second_generation["generation_id"]

        snapshots.append(
            _response(
                await client.post(
                    f"/api/projects/{project_id}/messages/{first_message_id}/generations"
                )
            )
        )
        snapshots.append(
            _response(
                await client.post(f"/api/projects/{project_id}/generations/{generation_id}/stop")
            )
        )
        snapshots.append(_response(await client.get(f"/api/projects/{project_id}")))
        snapshots.append(_response(await client.post("/api/auth/logout")))
        snapshots.append(_response(await client.get("/api/auth/me")))
    return snapshots


def _normalize(value: object, uuids: dict[str, str] | None = None) -> object:
    mapping = uuids if uuids is not None else {}
    if isinstance(value, dict):
        return {key: _normalize(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item, mapping) for item in value]
    if not isinstance(value, str):
        return value
    if TIMESTAMP.fullmatch(value):
        return "<timestamp>"
    try:
        UUID(value)
    except ValueError:
        return value
    mapping.setdefault(value, f"<uuid-{len(mapping) + 1}>")
    return mapping[value]


@pytest.mark.asyncio
async def test_go_and_python_match_for_web_chat_api_requests() -> None:
    go = _normalize(await _snapshot(GO_API_URL))
    python = _normalize(await _snapshot(PYTHON_API_URL))
    assert python == go
