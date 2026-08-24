import logging
import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .manger import FileSkillManger, SkillManger
from .models import Skills
from .repository import SkillsRepository
from pybase.common.pagination import PageParams, PageResult
from .schemas import SkillCreate, SkillRead, SkillUpdate, UploadResult
from ...core.config import get_settings
from ...core.exceptions import ConflictError

logger = logging.getLogger(__name__)

settings = get_settings()

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_MAX_UPLOAD_SIZE = 20 * 1024 * 1024

class SkillsService:
    """Skills 模块的业务用例。

    事务由 get_db_session 依赖统一管理（请求结束自动 commit/rollback），
    Service 层只需 flush 以获取自增主键等数据库生成的值。
    """

    def __init__(self, session: AsyncSession, skill_manger:SkillManger) -> None:
        self._session = session
        self._repository = SkillsRepository(session)
        self._loader = skill_manger

    async def upload_zip(self, upload: UploadFile) -> UploadResult:
        if not upload.filename or not upload.filename.lower().endswith(".zip"):
            raise ConflictError("只允许上传 ZIP 文件")

        content = await upload.read()

        if len(content) > _MAX_UPLOAD_SIZE:
            raise ConflictError("ZIP 文件不能超过 20MB")


        # 寻找skill.md 文件
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.namelist()
            skill_file = self._find_skill_file(members)

            if skill_file is None:
                raise ConflictError(
                    "ZIP 必须包含最多三层目录内的 SKILL.md"
                )

            parts = Path(skill_file).parts

            if len(parts) != 2 or parts[1] != "SKILL.md":
                raise ConflictError(
                    "ZIP 目录结构必须为 <skill_name>/SKILL.md"
                )

            skill_name = parts[0]

            if not _SAFE_NAME.fullmatch(skill_name):
                raise ConflictError("技能名称包含非法字符")

            target_dir = (settings.skill.dir/skill_name).resolve()

            if not self._is_inside_root(target_dir):
                raise ConflictError("技能路径非法")


            # 检查技能名称是否已存在
            old_entity = await self._repository.get_by_name(skill_name)
            replaced = old_entity is not None

            # 如果目标目录已存在，先删除
            if target_dir.exists():
                shutil.rmtree(target_dir)

            target_dir.mkdir(parents=True, exist_ok=True)

            for member in members:
                member_path = Path(member)

                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ConflictError("ZIP 包含非法路径")

                destination = (settings.skill.dir / member_path).resolve()

                if not self._is_inside_root(destination):
                    raise ConflictError("ZIP 包含越界路径")

                if member.endswith("/"):
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source:
                        destination.write_bytes(source.read())

        skill_md = target_dir / "SKILL.md"
        metadata, _ = FileSkillManger._parse_file(skill_md)

        if old_entity:
            old_entity.skill_path = str(target_dir)
            old_entity.description = metadata.description
            old_entity.file_name = "SKILL.md"
            old_entity.enabled = True
            entity = old_entity
        else:
            entity = Skills(
                name=metadata.name,
                skill_path=str(target_dir),
                description=metadata.description,
                file_name="SKILL.md",
                enabled=True,
            )
            self._repository.create(entity)

        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("技能名称已存在") from exc

        await self._session.refresh(entity)

        if self._loader:
            self._loader.invalidate()

        return UploadResult(
            **_to_read(entity).model_dump(),
            replaced=replaced,
        )

    async def get_enabled_skills(self) -> list[str]:
        """查询所有已开启的技能名字。"""
        entities = await self._repository.get_enabled_skills()
        return [e.name for e in entities]

    async def update_enabled(self, entity_id: int) -> SkillRead | None:
        """更新指定技能的启用状态。

        Args:
            entity_id: 技能主键ID。

        Returns:
            更新后的技能响应体，不存在时返回 None。
        """
        entity = await self._repository.update_enabled(entity_id)
        if entity is None:
            return None
        return _to_read(entity)

    async def get_by_id(self, entity_id: int) -> SkillRead | None:
        """按主键查询实体。"""
        entity = await self._repository.get_by_id(entity_id)
        return _to_read(entity) if entity is not None else None

    async def get_page(self, params: PageParams, *, enabled: bool | None = None, keyword: str | None = None) -> PageResult[SkillRead]:
        page = await self._repository.get_page(params, enabled=enabled, keyword=keyword)
        return PageResult(items=[_to_read(item) for item in page.items], page=page.page, page_size=page.page_size, total=page.total)

    async def delete_by_id(self, entity_id: int) -> bool:
        """按主键删除实体，实体不存在时返回 False。"""
        return await self._repository.delete_by_id(entity_id)

    def _find_skill_file(self, members: list[str]) -> str | None:
        for member in members:
            path = Path(member)

            if (
                    len(path.parts) <= 4
                    and len(path.parts) >= 2
                    and path.name == "SKILL.md"
            ):
                return member

        return None

    def _is_inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(settings.skill.dir)
            return True
        except ValueError:
            return False

def _to_read(entity: Skills) -> SkillRead:
    """将 ORM 实体转换为 API 响应体。"""
    return SkillRead.model_validate(entity)