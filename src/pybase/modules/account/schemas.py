from datetime import datetime
from pydantic import BaseModel, ConfigDict

class AdAccountRead(BaseModel):
    """广告账户的读取响应模型"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    platform_account_id: str
    account_name: str
    currency_code: str
    status: str

class UserAdAccountRead(BaseModel):
    """用户与广告账户关联关系的读取响应模型"""
    model_config = ConfigDict(from_attributes=True)

    app_user_id: int
    ad_account_id: int
    role: str
    granted_at: datetime | None = None
    expires_at: datetime | None = None

class UserAdAccountCreate(BaseModel):
    """为用户分配单个广告账户权限的请求模型"""
    ad_account_id: int
    role: str = "VIEWER"

class UserAdAccountBatchCreate(BaseModel):
    """为用户批量分配广告账户权限的请求模型"""
    user_id: int
    accounts: list[UserAdAccountCreate]

class AccountDataScope(BaseModel):
    """用户的数据权限范围模型，包含是否管理员、可访问账户ID列表及账户详情"""
    is_admin: bool
    account_ids: list[int]
    accounts: list[AdAccountRead] = []

    @property
    def has_access(self) -> bool:
        """判断用户是否有任何数据访问权限（管理员或拥有至少一个账户）"""
        return self.is_admin or len(self.account_ids) > 0