from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pybase.common.pagination import PageResult


class SkillCreate(BaseModel):
    """创建技能的请求体。"""

    name: str
    skill_path: str | None = None
    description: str = ""
    enabled: bool = True
    file_name: str | None = None


class SkillUpdate(BaseModel):
    """更新技能的请求体（部分更新，仅传入需要修改的字段）。"""

    name: str | None = None
    skill_path: str | None = None
    description: str | None = None
    enabled: bool | None = None
    file_name: str | None = None


class SkillRead(BaseModel):
    """技能的 API 响应体，从 ORM 模型转换而来。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    skill_path: str | None = None
    description: str = ""
    enabled: bool = True
    file_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillPage(PageResult[SkillRead]):
    """技能分页响应。"""


class SkillStatusUpdate(BaseModel):
    enabled: bool


class SkillMetadata(BaseModel):
    """技能元数据，从 Markdown frontmatter 中提取。"""

    name: str
    description: str


class Skill(BaseModel):
    """技能完整内容，包含元数据和正文。"""

    metadata: SkillMetadata
    content: str

class UploadResult(SkillRead):
    replaced: bool = False


