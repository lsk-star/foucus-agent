from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.infrastructure.database.dependencies import get_db_session

from .service import SessionService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_session_service(session: SessionDep) -> SessionService:
    return SessionService(session)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]