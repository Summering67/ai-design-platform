from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from ..errors import InvalidRequestError

MAX_MESSAGES = 50
MAX_CONTENT_RUNES = 32000
MAX_REQUEST_BYTES = 512 * 1024


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role
    content: str

    @field_validator("content")
    @classmethod
    def valid_content(cls, value: str) -> str:
        if not value.strip() or len(value) > MAX_CONTENT_RUNES:
            raise ValueError("消息内容无效")
        return value


def validate_messages(messages: list[ChatMessage]) -> None:
    if not messages or len(messages) > MAX_MESSAGES or messages[-1].role is not Role.USER:
        raise InvalidRequestError("对话请求无效")
