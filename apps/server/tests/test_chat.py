import httpx
import pytest

from ai_design_server.chat.client import ChatClient
from ai_design_server.chat.models import ChatMessage, Role
from ai_design_server.config import AIConfig


@pytest.mark.asyncio
async def test_chat_stream_emits_sse_deltas() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content='data: {"choices":[{"delta":{"content":"你好"}}]}\n\ndata: [DONE]\n\n'.encode())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    chat = ChatClient(client, AIConfig(base_url="https://ai.test", api_key="key"))
    chunks: list[str] = []
    async def collect(delta: str) -> None:
        chunks.append(delta)
    await chat.stream([ChatMessage(role=Role.USER, content="hi")], collect)
    await client.aclose()
    assert chunks == ["你好"]
