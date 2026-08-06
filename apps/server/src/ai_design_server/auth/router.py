from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import UserModel
from ..dependencies import get_session
from ..dto import LoginRequest, UserResponse
from .service import SESSION_COOKIE, SESSION_DURATION, AuthService

router = APIRouter(prefix="/api/auth")


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service  # type: ignore[no-any-return]


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    service: AuthService = Depends(get_auth_service),
) -> UserModel:
    token = request.cookies.get(SESSION_COOKIE, "")
    return await service.current_user(session, token)


@router.post("/login", response_model=UserResponse)
async def login(input: LoginRequest, response: Response, session: AsyncSession = Depends(get_session), service: AuthService = Depends(get_auth_service)) -> UserResponse:
    user, token = await service.login(session, input.email, input.password)
    response.set_cookie(SESSION_COOKIE, token, path="/", httponly=True, samesite="lax", max_age=int(SESSION_DURATION.total_seconds()))
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@router.get("/me", response_model=UserResponse)
async def me(user: UserModel = Depends(current_user)) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: AsyncSession = Depends(get_session), service: AuthService = Depends(get_auth_service)) -> None:
    await service.logout(session, request.cookies.get(SESSION_COOKIE, ""))
    response.delete_cookie(SESSION_COOKIE, path="/")
