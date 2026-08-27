import enum

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from pybase.infrastructure.database.base import Base, IntIdMixin, TimestampMixin

class AdAccountStatus(str, enum.Enum):
    """广告账户状态枚举"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"

class AdAccount(IntIdMixin, TimestampMixin, Base):
    """广告平台账户 ORM 模型，映射 ad_account 表，也是数据权限的最小单元"""
    __tablename__ = "ad_account"
    __table_args__ = {"comment": "广告平台账户，也是数据权限最小单元"}

    channel_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="渠道ID"
    )
    platform_account_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="广告平台侧账户ID"
    )
    account_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="账户名称"
    )
    currency_code: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="CNY", comment="货币代码"
    )
    status: Mapped[AdAccountStatus] = mapped_column(
        Enum(AdAccountStatus), nullable=False, default=AdAccountStatus.ACTIVE, server_default="ACTIVE", comment="状态"
    )

class UserAdAccountRole(str, enum.Enum):
    """用户与广告账户关联的角色枚举"""
    OWNER = "OWNER"
    ANALYST = "ANALYST"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

class UserAdAccount(Base):
    """用户与广告账户的多对多关联表 ORM 模型，映射 user_ad_account 表"""
    __tablename__ = "user_ad_account"
    __table_args__ = {"comment": "用户可访问的广告账户；一个用户可拥有多个账户"}

    app_user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="用户ID"
    )
    ad_account_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="广告账户ID"
    )
    role: Mapped[UserAdAccountRole] = mapped_column(
        Enum(UserAdAccountRole), nullable=False, default=UserAdAccountRole.VIEWER, comment="角色"
    )
    granted_at: Mapped[str | None] = mapped_column(
        nullable=True, comment="授权时间"
    )
    expires_at: Mapped[str | None] = mapped_column(
        nullable=True, comment="过期时间"
    )