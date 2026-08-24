from fastapi import APIRouter

router = APIRouter(prefix="/schema_provider", tags=["schema_provider"])

# 路由只负责协议转换和依赖注入，业务规则应委托给 Service。
# 例如（启用数据库后）：
# from fastapi import Depends
# from .dependencies import get_schema_provider_service
#
# @router.get("/{entity_id}")
# async def get_schema_provider(entity_id: int, service = Depends(get_schema_provider_service)):
#     return await service.get_by_id(entity_id)
