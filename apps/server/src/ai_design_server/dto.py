from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("邮箱不能为空")
        return value

    @field_validator("password")
    @classmethod
    def valid_password(cls, value: str) -> str:
        if not value:
            raise ValueError("密码不能为空")
        return value


class UserResponse(StrictModel):
    id: str
    email: str
    display_name: str


class ClientMessageRequest(StrictModel):
    message_id: str = Field(min_length=36, max_length=36)
    content: str


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody


class ProjectResponse(StrictModel):
    id: str
    title: str


class MessageResponse(StrictModel):
    id: str
    role: str
    content: str


class ProjectDetailResponse(StrictModel):
    project: ProjectResponse
    messages: list[MessageResponse]
