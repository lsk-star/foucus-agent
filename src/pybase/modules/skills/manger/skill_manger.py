from typing import Protocol

from pybase.modules.skills.schemas import SkillMetadata, Skill


class SkillManger(Protocol):
    """技能加载器协议 —— 定义技能的发现与加载接口。"""

    async def list_skills(self) -> list[str]:
        """列出所有可用的技能名称。"""
        ...

    async def load_metadata(self, names: list[str]) -> list[SkillMetadata]:
        """加载指定技能的元数据。

        Args:
            names: 技能名称列表，按名称匹配 frontmatter 中的 name 字段。

        Returns:
            匹配到的技能元数据列表，未找到的名称会被跳过。
        """
        ...

    async def load_skill_content(self, name: str) -> list[Skill]:
        """加载指定技能的完整内容（元数据 + 正文）。

        Args:
            name: 技能名称列表，按名称匹配 frontmatter 中的 name 字段。

        Returns:
            匹配到的技能列表，未找到的名称会被跳过。
        """
        ...

    def invalidate(self) -> None:
        """技能上传、删除或外部文件变更后调用。"""
        ...
