import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from pybase.infrastructure.database.base import Base, IntIdMixin, TimestampMixin


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AppUser(IntIdMixin, TimestampMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = {"comment": "营销分析系统的登录用户，不是广告触达用户"}

    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="登录账号"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="仅存 bcrypt 哈希，绝不存明文密码"
    )
    real_name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="真实姓名"
    )
    mobile: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="手机号"
    )
    email: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="邮箱"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像URL"
    )
    job_title: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="如投放优化师、运营负责人"
    )
    role: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="admin/user"
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE, server_default="ACTIVE", comment="状态"
    )
    last_login_at: Mapped[str | None] = mapped_column(
        nullable=True, comment="最后登录时间"
    )