from pydantic import BaseModel, ConfigDict, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageResult[T](BaseModel):
    """通用分页结果，允许 items 为任意类型（包括 SQLAlchemy ORM 模型）。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    page: int
    page_size: int
    total: int