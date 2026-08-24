from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from pybase.infrastructure.database.base import Base, IntIdMixin, TimestampMixin


class Skills(IntIdMixin, TimestampMixin, Base):
    """技能表 —— 存储技能基本信息。"""

    __tablename__ = "agentx_skill"
    __table_args__ = {"comment": "技能表"}

    name: Mapped[str] = mapped_column(
        String(500), unique=True, comment="技能名称"
    )
    skill_path: Mapped[str | None] = mapped_column(
        String(3000), comment="技能路径"
    )
    description: Mapped[str] = mapped_column(
        String(3000), default="", server_default="", comment="技能描述"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", comment="是否启用"
    )
    file_name: Mapped[str | None] = mapped_column(
        String(255), comment="文件名"
    )