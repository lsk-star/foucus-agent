from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelRequest,
    ModelResponse,
)

from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.service import SkillsService


class SkillMiddleware(
    AgentMiddleware
):

    def __init__(
        self,
        service: SkillsService,
        loader: SkillManger,
    ):
        super().__init__()
        self.service = service
        self.loader = loader

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[
            [ModelRequest],
            Awaitable[ModelResponse],
        ],
    ) -> ModelResponse:
        # 1. 防御性检查：如果系统提示词中已经包含了技能列表，直接放行，避免无限膨胀
        if "《Available Skills》" in request.system_prompt:
            return await handler(request)

        # 2. 从数据库中查询所有已开启的技能名字
        enabled_skills = (
            await self.service
            .get_enabled_skills()
        )

        if not enabled_skills:
            return await handler(request)

        # 3. 加载 skill 元信息
        skills_metadata = await self.loader.load_metadata(enabled_skills)

        # if not skills_metadata:
        #     return await handler(request)

        skills = "《Available Skills》"+"\n".join([f"name：{skill.name} description：{skill.description}" for skill in skills_metadata])+"《Available Skills/》\n 。使用技能必须调用 get_skill_content 这个工具"

        request = request.override(
            system_message=(
                request.system_prompt
                + "\n\n"
                + skills
            )
        )

        return await handler(request)