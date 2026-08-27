from typing import Annotated

from fastapi import APIRouter, Depends

from .dependencies import CurrentAdminUserDep, CurrentUserDep, get_auth_service
from .models import AppUser
from .schemas import ChangePassword, TokenResponse, UserLogin, UserRead, UserRegister, UserUpdate
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

ServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=UserRead)
async def register(
    data: UserRegister,
    service: ServiceDep,
):
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    service: ServiceDep,
):
    return await service.login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    service: ServiceDep,
):
    return await service.refresh_access_token(refresh_token)


@router.get("/me", response_model=UserRead)
async def get_profile(
    current_user: CurrentUserDep,
    service: ServiceDep,
):
    return await service.get_profile(current_user)


@router.patch("/me", response_model=UserRead)
async def update_profile(
    data: UserUpdate,
    current_user: CurrentUserDep,
    service: ServiceDep,
):
    return await service.update_profile(current_user, data)


@router.post("/change-password")
async def change_password(
    data: ChangePassword,
    current_user: CurrentUserDep,
    service: ServiceDep,
):
    await service.change_password(current_user, data)
    return {"message": "密码修改成功"}


@router.get("/admin-only", response_model=UserRead)
async def admin_only_demo(
    admin_user: CurrentAdminUserDep,
    service: ServiceDep,
):
    return await service.get_profile(admin_user)