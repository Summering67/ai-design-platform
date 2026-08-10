from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from ..config import AIConfig
from ..errors import TimeoutError, UnavailableError
from .models import ChatMessage, Role, validate_messages

MAX_UPSTREAM_RESPONSE_BYTES = 1024 * 1024
DeltaCallback = Callable[[str], Awaitable[None]]


class ChatClient:
    def __init__(self, client: httpx.AsyncClient, config: AIConfig) -> None:
        self.client = client
        self.api_key = config.api_key
        self.model = config.model
        self.timeout = config.request_timeout if config.request_timeout > 0 else None
        base = config.base_url.rstrip("/") + "/"
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("AI BaseURL 无效")
        self.endpoint = urljoin(base, "chat/completions")

    async def complete(self, messages: Sequence[ChatMessage]) -> ChatMessage:
        validate_messages(list(messages))
        try:
            response = await self.client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"messages": [message.model_dump() for message in messages], "model": self.model, "stream": False},
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
            message = body["choices"][0]["message"]
            result = ChatMessage.model_validate(message)
            if result.role is not Role.ASSISTANT or not result.content.strip():
                raise ValueError("empty completion")
            return result.model_copy(update={"content": result.content.strip()})
        except httpx.TimeoutException as error:
            raise TimeoutError("AI 服务响应超时") from error
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if isinstance(error, (TimeoutError, UnavailableError)):
                raise
            raise UnavailableError("AI 服务不可用") from error

    async def stream(self, messages: Sequence[ChatMessage], on_delta: DeltaCallback) -> None:
        validate_messages(list(messages))
        seen = False
        try:
            async with self.client.stream(
                "POST",
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"messages": [message.model_dump() for message in messages], "model": self.model, "stream": True},
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                total = 0
                async for line in response.aiter_lines():
                    total += len(line.encode())
                    if total > MAX_UPSTREAM_RESPONSE_BYTES:
                        raise UnavailableError("上游响应过大")
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    event: dict[str, Any] = json.loads(data)
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {}).get("content", "")
                        if delta:
                            seen = True
                            await on_delta(delta)
        except httpx.TimeoutException as error:
            raise TimeoutError("AI 服务响应超时") from error
        except asyncio.CancelledError:
            raise
        except (TimeoutError, UnavailableError):
            raise
        except Exception as error:
            raise UnavailableError("AI 服务不可用") from error
        if not seen:
            raise UnavailableError("上游回复为空")
