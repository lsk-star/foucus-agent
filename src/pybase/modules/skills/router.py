from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from pybase.common.pagination import PageParams
from pybase.modules.auth.dependencies import get_current_admin_user
from .dependencies import get_skills_service
from .schemas import SkillPage, SkillRead, SkillStatusUpdate, UploadResult
from .service import SkillsService

router = APIRouter(prefix="/skills", tags=["skills"])

admin_router = APIRouter(
    prefix="/skills",
    tags=["skills-admin"],
    dependencies=[Depends(get_current_admin_user)],
)

ServiceDep = Annotated[SkillsService, Depends(get_skills_service)]


@router.get("", response_model=SkillPage)
async def list_skills(
    service: ServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    enabled: bool | None = Query(None),
    keyword: str | None = Query(None, max_length=100),
):
    return await service.get_page(
        PageParams(page=page, page_size=page_size),
        enabled=enabled,
        keyword=keyword,
    )


@admin_router.patch(
    "/{skill_id}/status",
    response_model=SkillRead,
)
async def update_skill_status(
    skill_id: int,
    service: ServiceDep,
):
    return await service.update_enabled(skill_id)


@admin_router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: int, service: ServiceDep):
    await service.delete_by_id(skill_id)
    return Response(status_code=204)


@admin_router.post("/upload", response_model=UploadResult)
async def upload_skill(
    service: ServiceDep,
    file: UploadFile = File(...),
):
    return await service.upload_zip(file)