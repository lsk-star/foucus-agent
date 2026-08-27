from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.infrastructure.database.dependencies import get_db_session
from .data_access_guard import DataAccessGuard
from .service import AccountService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

def get_account_service(session: SessionDep) -> AccountService:
    """从请求级数据库会话构建 AccountService 实例"""
    return AccountService(session)

async def get_data_access_guard(session: SessionDep) -> DataAccessGuard:
    """从请求级数据库会话构建 DataAccessGuard 实例"""
    return DataAccessGuard(session)

AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]
DataAccessGuardDep = Annotated[DataAccessGuard, Depends(get_data_access_guard)]