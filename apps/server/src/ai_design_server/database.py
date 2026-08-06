from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import DatabaseConfig


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionModel(Base):
    __tablename__ = "user_sessions"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectModel(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    client_message_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AttemptModel(Base):
    __tablename__ = "generation_attempts"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    assistant_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="RESTRICT"), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
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
        pool_size=config.max_open_conns,
        max_overflow=0,
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
