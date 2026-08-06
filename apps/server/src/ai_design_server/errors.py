from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    status: int
    code: str
    message: str


INVALID_REQUEST = ApiError(400, "invalid_request", "请求无效")
UNAUTHORIZED = ApiError(401, "unauthorized", "请先登录")
NOT_FOUND = ApiError(404, "not_found", "项目不存在")
GENERATION_IN_PROGRESS = ApiError(409, "generation_in_progress", "项目正在生成")
INTERNAL_ERROR = ApiError(500, "internal_error", "内部错误")


class UnauthorizedError(Exception):
    """Stable authentication-domain error."""


class InvalidCredentialsError(Exception):
    """Stable invalid-login error."""


class NotFoundError(Exception):
    """Stable not-found domain error."""


class ConflictError(Exception):
    """Stable conflict-domain error."""


class InvalidRequestError(Exception):
    """Stable validation-domain error."""


class NotRetryableError(Exception):
    """Stable non-retryable generation error."""


class PersistenceError(Exception):
    """Stable internal persistence error."""


class UnavailableError(Exception):
    """Stable upstream-unavailable error."""


class TimeoutError(Exception):
    """Stable upstream-timeout error."""
