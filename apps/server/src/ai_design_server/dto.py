from __future__ import annotations

from datetime import datetime

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


class InputAnswer(StrictModel):
    question_id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=32000)


class InputAnswersRequest(StrictModel):
    response_id: str = Field(min_length=36, max_length=36)
    answers: list[InputAnswer] = Field(min_length=1, max_length=32)


class ErrorBody(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorBody


class ProjectResponse(StrictModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(StrictModel):
    id: str
    project_id: str
    client_message_id: str | None = None
    role: str
    content: str
    created_at: datetime


class AttemptResponse(StrictModel):
    id: str
    project_id: str
    user_message_id: str
    assistant_message_id: str | None = None
    status: str
    error_code: str | None = None
    lease_expires_at: datetime | None = None
    created_at: datetime
    finished_at: datetime | None = None


class InputRequestResponse(StrictModel):
    id: str
    generation_id: str
    source_stage: str
    source_task_id: str
    round: int
    questions: list[dict[str, str]]
    status: str


class ProjectDetailResponse(StrictModel):
    project: ProjectResponse
    messages: list[MessageResponse]
    pending_input_request: InputRequestResponse | None = None
