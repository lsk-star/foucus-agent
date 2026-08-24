from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pybase.common.pagination import PageParams, PageResult

from .models import Skills
from ...core.exceptions import NotFoundError


class SkillsRepository:
    """Skills 的通用数据访问，不负责提交事务。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> Skills | None:
        result = await self._session.scalar(
            select(Skills).where(Skills.name == name)
        )
        return result

    async def get_enabled_skills(self) -> list[Skills]:
        """查询所有已启用（enabled=True）的技能。"""
        result = await self._session.scalars(
            select(Skills).where(Skills.enabled.is_(True))
        )
        return list(result)

    async def update_enabled(self, entity_id: int) -> Skills | None:
        """更新指定技能的启用状态，返回更新后的实体或 None（不存在时）。"""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(f"技能不存在")
        await self._session.execute(
            update(Skills)
            .where(Skills.id == entity_id)
            .values(enabled=not entity.enabled)
        )
        await self._session.refresh(entity)
        return entity

    def create(self, entity: Skills) -> None:
        self._session.add(entity)

    async def get_by_id(self, entity_id: int) -> Skills | None:
        return await self._session.get(Skills, entity_id)

    async def get_page(self, params: PageParams, *, enabled: bool | None = None, keyword: str | None = None) -> PageResult[Skills]:
        filters = []
        if enabled is not None:
            filters.append(Skills.enabled.is_(enabled))
        if keyword:
            filters.append(Skills.name.ilike(f"%{keyword}%"))
        total = await self._session.scalar(
            select(func.count()).select_from(Skills).where(*filters)
        )
        result = await self._session.scalars(
            select(Skills)
            .where(*filters)
            .order_by(Skills.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return PageResult(
            items=list(result),
            page=params.page,
            page_size=params.page_size,
            total=total or 0,
        )

    async def delete_by_id(self, entity_id: int) -> bool:
        """按主键删除实体；返回是否实际删除。"""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        await self._session.delete(entity)
        return True