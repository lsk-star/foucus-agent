from fastapi import APIRouter

from pybase.modules.auth.dependencies import CurrentUserReadDep, CurrentAdminUserReadDep
from pybase.presentation.responses import success_response

from .dependencies import AccountServiceDep
from .schemas import UserAdAccountCreate, UserAdAccountBatchCreate

router = APIRouter(prefix="/account", tags=["account"])

@router.get("/scope")
async def get_my_scope(service: AccountServiceDep, current_user: CurrentUserReadDep):
    """获取当前登录用户的数据权限范围（是否管理员、可访问账户列表）"""
    scope = await service.get_data_scope(current_user.id, current_user.role == "admin")
    return success_response(scope)

@router.get("/my-accounts")
async def get_my_accounts(service: AccountServiceDep, current_user: CurrentUserReadDep):
    """获取当前登录用户关联的所有广告账户列表"""
    accounts = await service.get_user_accounts(current_user.id)
    return success_response(accounts)

@router.get("/all-accounts")
async def list_all_accounts(service: AccountServiceDep, admin_user: CurrentAdminUserReadDep):
    """管理员接口：获取所有广告账户列表"""
    accounts = await service.list_all_accounts()
    return success_response(accounts)

@router.post("/grant")
async def grant_access(
    user_id: int,
    data: UserAdAccountCreate,
    service: AccountServiceDep,
    admin_user: CurrentAdminUserReadDep,
):
    """管理员接口：为指定用户分配单个广告账户的访问权限"""
    result = await service.grant_access(user_id, data.ad_account_id, data.role)
    return success_response(result)

@router.post("/grant-batch")
async def grant_batch_access(
    data: UserAdAccountBatchCreate,
    service: AccountServiceDep,
    admin_user: CurrentAdminUserReadDep,
):
    """管理员接口：为指定用户批量分配多个广告账户的访问权限"""
    results = []
    for item in data.accounts:
        r = await service.grant_access(data.user_id, item.ad_account_id, item.role)
        results.append(r)
    return success_response(results)

@router.delete("/revoke")
async def revoke_access(
    user_id: int,
    ad_account_id: int,
    service: AccountServiceDep,
    admin_user: CurrentAdminUserReadDep,
):
    """管理员接口：撤销指定用户对某个广告账户的访问权限"""
    ok = await service.revoke_access(user_id, ad_account_id)
    return success_response(ok)