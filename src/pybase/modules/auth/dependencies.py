from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.infrastructure.database.dependencies import get_db_session
from pybase.core.exceptions import ForbiddenError, UnauthorizedError
from .models import AppUser
from .repository import AuthRepository
from .schemas import UserRead
from .service import AuthService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(session)


def _extract_token(request: Request) -> str:
    authorization: str | None = request.headers.get("Authorization")
    if not authorization:
        from pybase.core.exceptions import UnauthorizedError
        raise UnauthorizedError("缺少 Authorization 请求头")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        from pybase.core.exceptions import UnauthorizedError
        raise UnauthorizedError("Authorization 格式错误，应为 Bearer <token>")
    return parts[1]


async def get_current_user(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AppUser:
    token = _extract_token(request)
    return await service.get_current_user(token)


async def get_current_admin_user(
    current_user: Annotated[AppUser, Depends(get_current_user)],
) -> AppUser:
    if current_user.role != "admin":
        from pybase.core.exceptions import ForbiddenError
        raise ForbiddenError("仅管理员可访问此接口")
    return current_user


CurrentUserDep = Annotated[AppUser, Depends(get_current_user)]
CurrentAdminUserDep = Annotated[AppUser, Depends(get_current_admin_user)]


async def get_current_user_read(
    request: Request,
    session: SessionDep,
) -> UserRead:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise UnauthorizedError("未登录")
    cached = getattr(request.state, "_user_read", None)
    if cached is not None:
        return cached
    user = await AuthRepository(session).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("用户不存在")
    user_read = UserRead.model_validate(user)
    request.state._user_read = user_read
    return user_read


async def get_current_admin_user_read(
    current_user: Annotated[UserRead, Depends(get_current_user_read)],
) -> UserRead:
    if current_user.role != "admin":
        raise ForbiddenError("仅管理员可访问此接口")
    return current_user


CurrentUserReadDep = Annotated[UserRead, Depends(get_current_user_read)]
CurrentAdminUserReadDep = Annotated[UserRead, Depends(get_current_admin_user_read)]