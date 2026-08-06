from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import SessionModel, UserModel
from ..errors import UnauthorizedError

FIXED_USER_ID = "00000000-0000-0000-0000-000000000001"
FIXED_USER_EMAIL = "developer@local.test"
SESSION_COOKIE = "aidp_session"
SESSION_DURATION = timedelta(days=7)


class AuthService:
    def __init__(self, password: str) -> None:
        if not password.strip():
            raise ValueError("认证服务配置无效")
        self.password = password

    async def login(self, session: AsyncSession, email: str, password: str) -> tuple[UserModel, str]:
        if email.strip() != FIXED_USER_EMAIL or not hmac.compare_digest(password, self.password):
            raise UnauthorizedError
        user = await session.scalar(select(UserModel).where(UserModel.id == FIXED_USER_ID))
        if user is None:
            raise RuntimeError("固定用户不存在")
        token = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        session.add(SessionModel(id=str(uuid4()), user_id=user.id, token_hash=_token_hash(token), expires_at=_now() + SESSION_DURATION))
        await session.commit()
        return user, token

    async def current_user(self, session: AsyncSession, token: str) -> UserModel:
        if not token.strip():
            raise UnauthorizedError
        entry = await session.scalar(select(SessionModel).where(SessionModel.token_hash == _token_hash(token), SessionModel.expires_at > _now()))
        if entry is None:
            raise UnauthorizedError
        user = await session.scalar(select(UserModel).where(UserModel.id == entry.user_id))
        if user is None:
            raise UnauthorizedError
        return user

    async def logout(self, session: AsyncSession, token: str) -> None:
        if token.strip():
            await session.execute(delete(SessionModel).where(SessionModel.token_hash == _token_hash(token)))
            await session.commit()


def _now() -> datetime:
    return datetime.now(UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
