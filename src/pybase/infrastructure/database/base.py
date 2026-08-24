from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Alembic 自动生成迁移前，必须导入所有 SQLAlchemy 模型。"""


class IntIdMixin:
    """绝大多数业务实体使用的默认自增整数主键。"""

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True, comment="主键ID"
    )


class TimestampMixin:
    """通用时间戳混入，提供 created_at / updated_at 字段。"""

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="修改时间"
    )