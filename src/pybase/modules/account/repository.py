from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AdAccount, UserAdAccount, UserAdAccountRole


class AccountRepository:
    """账户数据访问层，封装对 ad_account 和 user_ad_account 表的查询与持久化操作"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_accessible_account_ids(self, user_id: int) -> list[int]:
        """根据用户ID查询其可访问的广告账户ID列表，自动过滤已过期的授权"""
        now = datetime.now(timezone.utc)
        result = await self._session.scalars(
            select(UserAdAccount.ad_account_id).where(
                UserAdAccount.app_user_id == user_id,
                (UserAdAccount.expires_at == None) | (UserAdAccount.expires_at > now),
            )
        )
        return list(result)

    async def get_accessible_accounts(self, user_id: int) -> list[AdAccount]:
        """根据用户ID查询其可访问的广告账户完整信息列表"""
        account_ids = await self.get_accessible_account_ids(user_id)
        if not account_ids:
            return []
        result = await self._session.scalars(
            select(AdAccount).where(AdAccount.id.in_(account_ids))
        )
        return list(result)

    async def get_account_by_id(self, account_id: int) -> AdAccount | None:
        """根据账户ID查询单个广告账户，不存在返回 None"""
        return await self._session.get(AdAccount, account_id)

    async def list_all_accounts(self) -> list[AdAccount]:
        """查询所有广告账户列表（供管理员使用）"""
        result = await self._session.scalars(select(AdAccount))
        return list(result)

    async def grant_account_access(
            self, user_id: int, ad_account_id: int, role: UserAdAccountRole = UserAdAccountRole.VIEWER
    ) -> UserAdAccount:
        """为用户分配广告账户访问权限，若已存在则更新角色，不存在则新建关联"""
        existing = await self._session.get(UserAdAccount, (user_id, ad_account_id))
        if existing:
            existing.role = role
            return existing
        relation = UserAdAccount(
            app_user_id=user_id,
            ad_account_id=ad_account_id,
            role=role,
        )
        self._session.add(relation)
        return relation

    async def revoke_account_access(self, user_id: int, ad_account_id: int) -> bool:
        """撤销用户对指定广告账户的访问权限，返回是否成功删除"""
        existing = await self._session.get(UserAdAccount, (user_id, ad_account_id))
        if not existing:
            return False
        await self._session.delete(existing)
        return True

    async def get_user_account_relations(self, user_id: int) -> list[UserAdAccount]:
        """查询用户与所有广告账户的关联关系列表"""
        result = await self._session.scalars(
            select(UserAdAccount).where(UserAdAccount.app_user_id == user_id)
        )
        return list(result)

    async def get_account_names(self, account_ids: list[int]) -> list[str]:
        """根据广告账户ID列表查询账户名称列表"""
        result = await self._session.scalars(
            select(AdAccount.account_name).where(AdAccount.id.in_(account_ids))
        )
        return list(result)
