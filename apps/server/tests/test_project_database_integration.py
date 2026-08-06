from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai_design_server.app import create_app
from ai_design_server.config import AIConfig, AuthConfig, DatabaseConfig, RuntimeConfig
from ai_design_server.database import (
    AttemptModel,
    Database,
    MessageModel,
    ProjectModel,
    _async_dsn,
)
from ai_design_server.errors import ConflictError, PersistenceError
from ai_design_server.project.service import ProjectService

TEST_DSN = os.getenv("API_TEST_DATABASE_DSN", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="未配置隔离 PostgreSQL 测试 DSN")


@pytest_asyncio.fixture
async def database() -> AsyncIterator[Database]:
    schema = f"test_python_migration_{uuid4().hex}"
    engine = create_async_engine(_async_dsn(TEST_DSN))
    migration = (
        Path(__file__).resolve().parents[2]
        / "api/migrations/20260803090000_add_single_user_authentication.up.sql"
    ).read_text(encoding="utf-8")
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        for statement in migration.split(";"):
            statement.strip() and await connection.exec_driver_sql(statement)
    await engine.dispose()

    scoped_engine = create_async_engine(
        _async_dsn(TEST_DSN),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    result = Database(
        scoped_engine,
        async_sessionmaker(scoped_engine, expire_on_commit=False, autoflush=False),
    )
    try:
        yield result
    finally:
        await scoped_engine.dispose()
        cleanup = create_async_engine(_async_dsn(TEST_DSN))
        async with cleanup.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await cleanup.dispose()


@pytest.mark.asyncio
async def test_create_project_rolls_back_all_rows_on_constraint_failure(
    database: Database,
) -> None:
    service = ProjectService()
    async with database.session() as session:
        before = await _counts(session)
    async with database.session() as session:
        with pytest.raises(PersistenceError):
            await service.create_with_message(
                session,
                str(uuid4()),
                str(uuid4()),
                "不会部分提交",
            )
    async with database.session() as session:
        assert await _counts(session) == before


@pytest.mark.asyncio
async def test_create_and_finish_commit_foreign_keys_in_order(database: Database) -> None:
    service = ProjectService()
    async with database.session() as session:
        project, message, attempt = await service.create_with_message(
            session,
            "00000000-0000-0000-0000-000000000001",
            str(uuid4()),
            "完整事务",
        )
    async with database.session() as session:
        assistant, finished = await service.finish(session, attempt.id, "生成结果")

    assert assistant is not None
    assert finished.status == "completed"
    assert finished.assistant_message_id == assistant.id
    async with database.session() as session:
        assert await _counts(session) == (1, 2, 1)
        stored_message = await session.get(MessageModel, message.id)
        assert stored_message is not None
        assert stored_message.project_id == project.id


@pytest.mark.asyncio
async def test_authenticated_stop_uses_separate_auth_and_business_sessions(
    database: Database,
) -> None:
    project_id, _, attempt_id = await _seed_project(
        database,
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    config = RuntimeConfig(
        database=DatabaseConfig(dsn=TEST_DSN),
        ai=AIConfig(base_url="https://ai.test", api_key="test"),
        auth=AuthConfig(fixed_user_password="test-password"),
    )
    app = create_app(config, database)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        login = await client.post(
            "/api/auth/login",
            json={"email": "developer@local.test", "password": "test-password"},
        )
        response = await client.post(
            f"/api/projects/{project_id}/generations/{attempt_id}/stop",
        )

    assert login.status_code == 200
    assert response.status_code == 200
    assert response.json()["generation"]["status"] == "interrupted"


@pytest.mark.asyncio
async def test_expired_lease_is_interrupted_before_new_attempt(database: Database) -> None:
    service = ProjectService()
    project_id, message_id, attempt_id = await _seed_project(
        database,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    async with database.session() as session:
        _, attempt, existing = await service.add_message(
            session,
            "00000000-0000-0000-0000-000000000001",
            project_id,
            str(uuid4()),
            "租约接管",
        )

    async with database.session() as session:
        expired = await session.get(AttemptModel, attempt_id)
        assert expired is not None
        assert expired.status == "interrupted"
        assert expired.finished_at is not None
        assert expired.lease_expires_at is None
        assert attempt.status == "running"
        assert attempt.user_message_id != message_id
        assert existing is False


@pytest.mark.asyncio
async def test_concurrent_messages_leave_one_running_attempt(database: Database) -> None:
    service = ProjectService()
    project_id, _, _ = await _seed_project(database)

    async def add(content: str) -> str:
        async with database.session() as session:
            try:
                await service.add_message(
                    session,
                    "00000000-0000-0000-0000-000000000001",
                    project_id,
                    str(uuid4()),
                    content,
                )
            except ConflictError:
                return "conflict"
            return "created"

    assert sorted(await asyncio.gather(add("并发一"), add("并发二"))) == [
        "conflict",
        "created",
    ]
    async with database.session() as session:
        running = await session.scalar(
            select(func.count())
            .select_from(AttemptModel)
            .where(AttemptModel.project_id == project_id, AttemptModel.status == "running")
        )
        messages = await session.scalar(
            select(func.count())
            .select_from(MessageModel)
            .where(MessageModel.project_id == project_id, MessageModel.role == "user")
        )
        assert running == 1
        assert messages == 2
    async with database.session() as session:
        with pytest.raises(IntegrityError):
            async with session.begin():
                user_message_id = await session.scalar(
                    select(MessageModel.id).where(MessageModel.project_id == project_id)
                )
                assert user_message_id is not None
                session.add(
                    AttemptModel(
                        id=str(uuid4()),
                        project_id=project_id,
                        user_message_id=user_message_id,
                        status="running",
                        lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
                        created_at=datetime.now(UTC),
                    )
                )


@pytest.mark.asyncio
async def test_concurrent_duplicate_message_is_idempotent(database: Database) -> None:
    service = ProjectService()
    project_id, _, _ = await _seed_project(database)
    client_message_id = str(uuid4())

    async def add() -> tuple[str, str, bool]:
        async with database.session() as session:
            message, attempt, existing = await service.add_message(
                session,
                "00000000-0000-0000-0000-000000000001",
                project_id,
                client_message_id,
                "相同请求",
            )
            return message.id, attempt.id, existing

    first, second = await asyncio.gather(add(), add())
    assert first[:2] == second[:2]
    assert sorted((first[2], second[2])) == [False, True]
    async with database.session() as session:
        messages = await session.scalar(
            select(func.count())
            .select_from(MessageModel)
            .where(
                MessageModel.project_id == project_id,
                MessageModel.client_message_id == client_message_id,
            )
        )
        attempts = await session.scalar(
            select(func.count())
            .select_from(AttemptModel)
            .where(AttemptModel.project_id == project_id)
        )
        assert messages == 1
        assert attempts == 1


async def _counts(session: AsyncSession) -> tuple[int, int, int]:
    values = []
    for model in (ProjectModel, MessageModel, AttemptModel):
        values.append(await session.scalar(select(func.count()).select_from(model)) or 0)
    return values[0], values[1], values[2]


async def _seed_project(
    database: Database,
    lease_expires_at: datetime | None = None,
) -> tuple[str, str, str]:
    project_id, message_id, attempt_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = datetime.now(UTC)
    async with database.session() as session, session.begin():
        session.add(
            ProjectModel(
                id=project_id,
                user_id="00000000-0000-0000-0000-000000000001",
                title="测试项目",
                created_at=now,
                updated_at=now,
            )
        )
        await session.flush()
        session.add(
            MessageModel(
                id=message_id,
                project_id=project_id,
                client_message_id=str(uuid4()),
                role="user",
                content="初始消息",
                created_at=now,
            )
        )
        await session.flush()
        if lease_expires_at is not None:
            session.add(
                AttemptModel(
                    id=attempt_id,
                    project_id=project_id,
                    user_message_id=message_id,
                    status="running",
                    lease_expires_at=lease_expires_at,
                    created_at=now,
                )
            )
    return project_id, message_id, attempt_id
