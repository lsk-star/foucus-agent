import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AppUser, UserStatus
from .repository import AuthRepository
from .schemas import ChangePassword, TokenResponse, UserLogin, UserRead, UserRegister, UserUpdate
from .security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from ...core.exceptions import ConflictError, ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = AuthRepository(session)

    async def register(self, data: UserRegister) -> UserRead:
        existing = await self._repository.get_by_username(data.username)
        if existing is not None:
            raise ConflictError(f"用户名 {data.username} 已存在")
        user = AppUser(
            username=data.username,
            password_hash=hash_password(data.password),
            real_name=data.real_name,
            mobile=data.mobile,
            email=data.email,
            role=data.role or "user",
            status=UserStatus.ACTIVE,
        )
        self._repository.create(user)
        await self._session.flush()
        await self._session.refresh(user)
        return UserRead.model_validate(user)

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self._repository.get_by_username(data.username)
        if user is None:
            raise UnauthorizedError("用户名或密码错误")
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenError("该账号已被禁用")
        if not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("用户名或密码错误")
        await self._repository.update_last_login(user.id)
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def get_current_user(self, token: str) -> AppUser:
        payload = decode_token(token, expected_type="access")
        user_id = int(payload["sub"])
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("用户不存在")
        if user.status != UserStatus.ACTIVE:
            raise UnauthorizedError("该账号已被禁用")
        return user

    async def get_profile(self, user: AppUser) -> UserRead:
        return UserRead.model_validate(user)

    async def update_profile(self, user: AppUser, data: UserUpdate) -> UserRead:
        update_fields = data.model_dump(exclude_unset=True)
        if not update_fields:
            return UserRead.model_validate(user)
        await self._repository.update(user, **update_fields)
        return UserRead.model_validate(user)

    async def change_password(self, user: AppUser, data: ChangePassword) -> None:
        if not verify_password(data.old_password, user.password_hash):
            raise UnauthorizedError("旧密码错误")
        new_hash = hash_password(data.new_password)
        await self._repository.update(user, password_hash=new_hash)

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = int(payload["sub"])
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("用户不存在")
        if user.status != UserStatus.ACTIVE:
            raise UnauthorizedError("该账号已被禁用")
        access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)
        return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)