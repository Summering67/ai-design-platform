from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import (
    AttemptModel,
    MessageModel,
    ProjectModel,
    database_operation,
    integrity_constraint,
)
from ..errors import (
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    NotRetryableError,
    PersistenceError,
)
from ..errors import TimeoutError as AiTimeoutError

MAX_CONTENT_RUNES = 32000
MAX_HISTORY_RUNES = 120000
LEASE_DURATION = timedelta(minutes=2)
RUNNING_ATTEMPT_CONSTRAINT = "generation_attempts_one_running_project_idx"


def _project_integrity_error(error: IntegrityError) -> Exception:
    return ConflictError() if integrity_constraint(error) == RUNNING_ATTEMPT_CONSTRAINT else PersistenceError()


class ProjectService:
    @database_operation(_project_integrity_error)
    async def recent(self, session: AsyncSession, user_id: str) -> list[ProjectModel]:
        result = await session.scalars(select(ProjectModel).where(ProjectModel.user_id == user_id).order_by(ProjectModel.updated_at.desc(), ProjectModel.id.desc()).limit(20))
        return list(result)

    @database_operation(_project_integrity_error)
    async def get(self, session: AsyncSession, user_id: str, project_id: str) -> tuple[ProjectModel, list[MessageModel]]:
        _validate_uuid(project_id)
        project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id, ProjectModel.user_id == user_id))
        if project is None:
            raise NotFoundError
        messages = list(await session.scalars(select(MessageModel).where(MessageModel.project_id == project_id).order_by(MessageModel.created_at.asc(), MessageModel.id.asc())))
        return project, messages

    @database_operation(_project_integrity_error)
    async def create_with_message(self, session: AsyncSession, user_id: str, message_id: str, content: str) -> tuple[ProjectModel, MessageModel, AttemptModel]:
        _validate(content, message_id)
        now = _now()
        project = ProjectModel(id=str(uuid4()), user_id=user_id, title=_title(content), created_at=now, updated_at=now)
        message = MessageModel(id=str(uuid4()), project_id=project.id, client_message_id=message_id, role="user", content=content.strip(), created_at=now)
        attempt = _new_attempt(project.id, message.id, now)
        async with session.begin():
            session.add(project)
            await session.flush()
            session.add(message)
            await session.flush()
            session.add(attempt)
        return project, message, attempt

    @database_operation(_project_integrity_error)
    async def add_message(self, session: AsyncSession, user_id: str, project_id: str, message_id: str, content: str) -> tuple[MessageModel, AttemptModel, bool]:
        _validate(content, message_id)
        _validate_uuid(project_id)
        now = _now()
        async with session.begin():
            project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id, ProjectModel.user_id == user_id).with_for_update())
            if project is None:
                raise NotFoundError
            await _interrupt_expired(session, project_id, now)
            existing = await session.scalar(select(MessageModel).where(MessageModel.project_id == project_id, MessageModel.client_message_id == message_id))
            if existing is not None:
                attempt = await session.scalar(select(AttemptModel).where(AttemptModel.user_message_id == existing.id).order_by(AttemptModel.created_at.desc(), AttemptModel.id.desc()))
                if attempt is None:
                    raise RuntimeError("消息生成记录不存在")
                return existing, attempt, True
            running = await session.scalar(select(AttemptModel).where(AttemptModel.project_id == project_id, AttemptModel.status == "running"))
            if running is not None:
                raise ConflictError
            message = MessageModel(id=str(uuid4()), project_id=project_id, client_message_id=message_id, role="user", content=content.strip(), created_at=now)
            attempt = _new_attempt(project_id, message.id, now)
            session.add(message)
            await session.flush()
            session.add(attempt)
            project.updated_at = now
            return message, attempt, False

    @database_operation(_project_integrity_error)
    async def retry(self, session: AsyncSession, user_id: str, project_id: str, message_id: str) -> tuple[ProjectModel, MessageModel, AttemptModel]:
        _validate_uuid(project_id)
        _validate_uuid(message_id)
        now = _now()
        async with session.begin():
            project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id, ProjectModel.user_id == user_id).with_for_update())
            if project is None:
                raise NotFoundError
            await _interrupt_expired(session, project_id, now)
            message = await session.scalar(select(MessageModel).where(MessageModel.id == message_id, MessageModel.project_id == project_id, MessageModel.role == "user"))
            if message is None:
                raise NotRetryableError("消息不可重新生成")
            completed = await session.scalar(select(func.count()).select_from(AttemptModel).where(AttemptModel.user_message_id == message.id, AttemptModel.status == "completed"))
            if completed:
                raise NotRetryableError("消息不可重新生成")
            running = await session.scalar(select(AttemptModel).where(AttemptModel.project_id == project_id, AttemptModel.status == "running"))
            if running is not None:
                raise ConflictError
            attempt = _new_attempt(project_id, message.id, now)
            session.add(attempt)
            return project, message, attempt

    @database_operation(_project_integrity_error)
    async def context(self, session: AsyncSession, project_id: str, message_id: str) -> list[MessageModel]:
        target = await session.scalar(select(MessageModel).where(MessageModel.id == message_id, MessageModel.project_id == project_id, MessageModel.role == "user"))
        if target is None:
            raise InvalidRequestError("消息无效")
        attempts = list(await session.scalars(select(AttemptModel).where(AttemptModel.project_id == project_id, AttemptModel.status == "completed", AttemptModel.assistant_message_id.is_not(None)).order_by(AttemptModel.created_at.desc(), AttemptModel.id.desc()).limit(24)))
        messages: list[MessageModel] = []
        for attempt in reversed(attempts):
            pair = list(await session.scalars(select(MessageModel).where(MessageModel.id.in_([attempt.user_message_id, attempt.assistant_message_id])).order_by(MessageModel.created_at.asc(), MessageModel.id.asc())))
            messages.extend(pair)
        while len(messages) >= 2 and _length(messages) + len(target.content) > MAX_HISTORY_RUNES:
            messages = messages[2:]
        return [*messages, target]

    @database_operation(_project_integrity_error)
    async def finish(self, session: AsyncSession, attempt_id: str, content: str, failure: BaseException | None = None) -> tuple[MessageModel | None, AttemptModel]:
        now = _now()
        async with session.begin():
            attempt = await session.scalar(select(AttemptModel).where(AttemptModel.id == attempt_id).with_for_update())
            if attempt is None:
                raise NotFoundError
            if attempt.status != "running":
                return None, attempt
            attempt.lease_expires_at = None
            attempt.finished_at = now
            if failure is not None or not content.strip():
                attempt.status = "failed"
                attempt.error_code = "ai_timeout" if isinstance(failure, (AiTimeoutError, asyncio.TimeoutError)) else "ai_unavailable"
                return None, attempt
            assistant = MessageModel(id=str(uuid4()), project_id=attempt.project_id, role="assistant", content=content.strip(), created_at=now)
            session.add(assistant)
            await session.flush()
            attempt.status = "completed"
            attempt.assistant_message_id = assistant.id
            project = await session.scalar(select(ProjectModel).where(ProjectModel.id == attempt.project_id))
            if project is not None:
                project.updated_at = now
            return assistant, attempt

    @database_operation(_project_integrity_error)
    async def interrupt(
        self,
        session: AsyncSession,
        project_id: str,
        attempt_id: str,
        user_id: str | None = None,
    ) -> AttemptModel:
        _validate_uuid(project_id)
        _validate_uuid(attempt_id)
        async with session.begin():
            if user_id is not None:
                project = await session.scalar(
                    select(ProjectModel)
                    .where(ProjectModel.id == project_id, ProjectModel.user_id == user_id)
                    .with_for_update()
                )
                if project is None:
                    raise NotFoundError
            attempt = await session.scalar(select(AttemptModel).where(AttemptModel.id == attempt_id, AttemptModel.project_id == project_id).with_for_update())
            if attempt is None:
                raise NotFoundError
            if attempt.status == "running":
                attempt.status = "interrupted"
                attempt.finished_at = _now()
                attempt.lease_expires_at = None
            return attempt


def _now() -> datetime:
    return datetime.now(UTC)


def _validate(content: str, message_id: str) -> None:
    if not content.strip() or len(content) > MAX_CONTENT_RUNES:
        raise InvalidRequestError("消息无效")
    _validate_uuid(message_id)


def _validate_uuid(value: str) -> None:
    try:
        UUID(value)
    except (ValueError, AttributeError):
        raise InvalidRequestError("消息无效") from None


def _title(content: str) -> str:
    value = " ".join(content.split())
    return value if len(value) <= 30 else value[:30] + "..."


def _new_attempt(project_id: str, message_id: str, now: datetime) -> AttemptModel:
    return AttemptModel(id=str(uuid4()), project_id=project_id, user_message_id=message_id, status="running", lease_expires_at=now + LEASE_DURATION, created_at=now)


async def _interrupt_expired(session: AsyncSession, project_id: str, now: datetime) -> None:
    await session.execute(update(AttemptModel).where(AttemptModel.project_id == project_id, AttemptModel.status == "running", AttemptModel.lease_expires_at <= now).values(status="interrupted", finished_at=now, lease_expires_at=None))


def _length(messages: list[MessageModel]) -> int:
    return sum(len(message.content) for message in messages)
