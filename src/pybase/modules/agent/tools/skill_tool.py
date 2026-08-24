"""Tools for loading skill instructions into an agent context."""

from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field

from pybase.modules.skills.manger import SkillManger
from pybase.modules.skills.schemas import Skill


def _as_markdown(skill: Skill) -> str:
    """Render a loaded skill back to the complete ``SKILL.md`` shape."""
    description = skill.metadata.description.replace("\n", " ").strip()
    return (
        "---\n"
        f"name: {skill.metadata.name}\n"
        f"description: {description}\n"
        "---\n\n"
        f"{skill.content}"
    )



def create_skill_content_tool(loader: SkillManger) -> BaseTool:
    """Create a tool that loads a skill's complete Markdown document.

    ``SkillLoader`` is injected when the agent is assembled, so the model only
    needs to provide the skill name at invocation time.
    """

    async def load_skill(
        skill_name: Annotated[
            str,
            Field(
                description=(
                    "要加载的技能名称。只能使用系统提示词《Available Skills》中 "
                    "`name` 字段的完整原文；必须逐字复制，不能猜测、翻译、改写或"
                    "创建列表中不存在的名称。"
                )
            ),
        ],
    ) -> str:
        skill_name = skill_name.strip()
        if not skill_name:
            return "技能名称不能为空。"

        skills = await loader.load_skill_content(skill_name)
        if not skills:
            return f"未找到技能: {skill_name}"

        return _as_markdown(skills[0])

    return StructuredTool.from_function(
        coroutine=load_skill,
        name="get_skill_content",
        description=(
            "加载一个已提供的技能的完整 SKILL.md。仅当系统提示词《Available Skills》中"
            "存在所需技能时调用；`skill_name` 必须逐字使用该列表中的 `name`，绝不"
            "猜测、翻译或传入未列出的名称。"
        ),
    )


__all__ = ["create_skill_content_tool"]
