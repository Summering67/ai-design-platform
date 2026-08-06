from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import ParamSpec, TypeVar

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import DatabaseConfig
from .errors import PersistenceError

P = ParamSpec("P")
R = TypeVar("R")


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="users_email_key"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionModel(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="user_sessions_token_hash_key"),
        Index("user_sessions_user_id_idx", "user_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("projects_user_updated_at_idx", "user_id", text("updated_at DESC")),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="messages_role_check"),
        CheckConstraint("BTRIM(content) <> ''", name="messages_content_check"),
        UniqueConstraint(
            "project_id",
            "client_message_id",
            name="messages_project_id_client_message_id_key",
        ),
        Index("messages_project_created_at_idx", "project_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    client_message_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttemptModel(Base):
    __tablename__ = "generation_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'interrupted')",
            name="generation_attempts_status_check",
        ),
        UniqueConstraint(
            "assistant_message_id",
            name="generation_attempts_assistant_message_id_key",
        ),
        Index(
            "generation_attempts_one_running_project_idx",
            "project_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "generation_attempts_user_message_idx",
            "user_message_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@dataclass(slots=True)
class Database:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def ping(self, timeout: float) -> None:
        async with asyncio.timeout(timeout):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        return self.sessions()


def _async_dsn(dsn: str) -> str:
    value = dsn.strip()
    if not value:
        raise ValueError("数据库 DSN 无效")
    if any(character.isspace() for character in value):
        raise ValueError("数据库 DSN 无效")
    try:
        parsed = make_url(value)
    except Exception as error:
        raise ValueError("数据库 DSN 无效") from error
    if parsed.drivername not in {"postgres", "postgresql", "postgres+psycopg", "postgresql+psycopg"}:
        raise ValueError("数据库 DSN 必须使用 PostgreSQL")
    if not parsed.host or not parsed.database:
        raise ValueError("数据库 DSN 必须包含主机和数据库名")
    return str(parsed.set(drivername="postgresql+psycopg"))


async def open_database(config: DatabaseConfig) -> Database:
    engine = create_async_engine(
        _async_dsn(config.dsn),
        pool_size=config.max_idle_conns,
        max_overflow=config.max_open_conns - config.max_idle_conns,
        pool_recycle=int(config.conn_max_lifetime),
        pool_pre_ping=True,
    )
    database = Database(engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False))
    try:
        await database.ping(config.ping_timeout)
    except Exception:
        await database.close()
        raise
    return database


async def session_dependency(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.session() as session:
        yield session


def integrity_constraint(error: IntegrityError) -> str | None:
    diagnostics = getattr(error.orig, "diag", None)
    constraint = getattr(diagnostics, "constraint_name", None)
    return str(constraint) if constraint else None


@contextmanager
def database_boundary(
    integrity_error: Callable[[IntegrityError], Exception] | None = None,
) -> Iterator[None]:
    try:
        yield
    except IntegrityError as error:
        raise (integrity_error(error) if integrity_error else PersistenceError()) from error
    except SQLAlchemyError as error:
        raise PersistenceError() from error


def database_operation(
    integrity_error: Callable[[IntegrityError], Exception] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def decorate(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(function)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            with database_boundary(integrity_error):
                return await function(*args, **kwargs)

        return wrapped

    return decorate
