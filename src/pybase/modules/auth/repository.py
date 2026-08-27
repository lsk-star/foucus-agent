from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AppUser


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_username(self, username: str) -> AppUser | None:
        return await self._session.scalar(
            select(AppUser).where(AppUser.username == username)
        )

    async def get_by_id(self, user_id: int) -> AppUser | None:
        return await self._session.get(AppUser, user_id)

    def create(self, user: AppUser) -> None:
        self._session.add(user)

    async def update(self, user: AppUser, **fields) -> AppUser:
        for key, value in fields.items():
            setattr(user, key, value)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_last_login(self, user_id: int) -> None:
        from datetime import datetime, timezone
        await self._session.execute(
            update(AppUser)
            .where(AppUser.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )