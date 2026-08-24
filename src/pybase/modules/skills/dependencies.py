from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.infrastructure.database.dependencies import get_db_session
from .manger import SkillManger, FileSkillManger

from .service import SkillsService
from ...core.config import get_settings

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
settings = get_settings()


def get_skills_service(session: SessionDep) -> SkillsService:
    """为路由创建请求级 SkillsService。"""
    return SkillsService(session, get_file_skill_loader())


def get_file_skill_loader() -> SkillManger:
    return FileSkillManger(settings.skill.dir)