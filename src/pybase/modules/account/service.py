import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .data_access_guard import DataAccessGuard, DataScope
from .models import UserAdAccountRole
from .repository import AccountRepository
from .schemas import AccountDataScope, AdAccountRead, UserAdAccountRead

logger = logging.getLogger(__name__)

class AccountService:
    """账户业务用例层，封装数据权限查询、账户授权/撤销等业务逻辑"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = AccountRepository(session)

    async def get_data_scope(self, user_id: int, is_admin: bool) -> AccountDataScope:
        """获取用户的数据权限范围，返回是否管理员、可访问账户ID列表及账户详情"""
        guard = DataAccessGuard(self._session)
        scope = await guard.get_data_scope(user_id, is_admin)
        accounts = []
        if not scope.is_admin and scope.account_ids:
            acc_list = await self._repository.get_accessible_accounts(user_id)
            accounts = [AdAccountRead.model_validate(a) for a in acc_list]
        return AccountDataScope(
            is_admin=scope.is_admin,
            account_ids=scope.account_ids,
            accounts=accounts,
        )

    async def get_user_accounts(self, user_id: int) -> list[UserAdAccountRead]:
        """查询用户与所有广告账户的关联关系列表"""
        relations = await self._repository.get_user_account_relations(user_id)
        return [UserAdAccountRead.model_validate(r) for r in relations]

    async def grant_access(self, user_id: int, ad_account_id: int, role: str = "VIEWER") -> UserAdAccountRead:
        """为用户分配指定广告账户的访问权限，若账户不存在则抛出 NotFoundError"""
        account = await self._repository.get_account_by_id(ad_account_id)
        if account is None:
            from pybase.core.exceptions import NotFoundError
            raise NotFoundError(f"广告账户 {ad_account_id} 不存在")
        relation = await self._repository.grant_account_access(
            user_id, ad_account_id, UserAdAccountRole(role)
        )
        await self._session.flush()
        await self._session.refresh(relation)
        return UserAdAccountRead.model_validate(relation)

    async def revoke_access(self, user_id: int, ad_account_id: int) -> bool:
        """撤销用户对指定广告账户的访问权限，返回是否成功"""
        return await self._repository.revoke_account_access(user_id, ad_account_id)

    async def list_all_accounts(self) -> list[AdAccountRead]:
        """查询所有广告账户列表（供管理员使用）"""
        accounts = await self._repository.list_all_accounts()
        return [AdAccountRead.model_validate(a) for a in accounts]