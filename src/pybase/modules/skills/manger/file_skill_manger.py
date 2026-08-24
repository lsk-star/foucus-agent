import logging
from pathlib import Path

import yaml

from .skill_manger import SkillManger
from pybase.modules.skills.schemas import Skill, SkillMetadata

logger = logging.getLogger(__name__)


class FileSkillManger(SkillManger):
    """从本地文件系统加载技能。

    技能文件为 Markdown 格式，使用 YAML frontmatter 声明元数据：

        ---
        name: text2sql
        description: 将自然语言转换为 SQL...
        ---

        # Text2SQL Skill
        ...

    Args:
        root_dir: 技能文件的根目录，支持嵌套子目录，递归扫描所有 .md 文件。
    """

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._index: dict[str, Path] | None = None

    async def list_skills(self) -> list[str]:
        return list(self._build_index().keys())

    async def load_metadata(self, names: list[str]) -> list[SkillMetadata]:
        index = self._build_index()
        result: list[SkillMetadata] = []

        for name in names:
            path = index.get(name)
            if path is None:
                logger.warning("技能不存在: %s", name)
                continue

            try:
                metadata, _ = self._parse_file(path)
                result.append(metadata)
            except (OSError, ValueError, yaml.YAMLError):
                logger.exception("技能解析失败: %s", path)

        return result

    async def load_skill_content(self, name: str) -> list[Skill]:
        path = self._build_index().get(name)
        if path is None:
            logger.warning("技能不存在: %s", name)
            return []

        metadata, content = self._parse_file(path)
        return [Skill(metadata=metadata, content=content)]

    def invalidate(self) -> None:
        """技能上传、删除或外部文件变更后调用。"""
        self._index = None

    def refresh(self) -> None:
        self._index = self._scan_index()

    def _build_index(self) -> dict[str, Path]:
        if self._index is None:
            self._index = self._scan_index()
        return self._index

    def _scan_index(self) -> dict[str, Path]:
        index: dict[str, Path] = {}

        if not self._root_dir.exists():
            logger.warning("技能目录不存在: %s", self._root_dir)
            return index

        for file_path in self._root_dir.rglob("SKILL.md"):
            try:
                metadata, _ = self._parse_file(file_path)
            except (OSError, ValueError, yaml.YAMLError):
                logger.exception("技能文件解析失败: %s", file_path)
                continue

            if metadata.name in index:
                logger.warning(
                    "发现同名技能，后发现文件覆盖前文件: %s",
                    metadata.name,
                )

            index[metadata.name] = file_path

        return index

    @staticmethod
    def _parse_file(file_path: Path) -> tuple[SkillMetadata, str]:
        text = file_path.read_text(encoding="utf-8")

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError(f"缺少 YAML frontmatter: {file_path}")

        try:
            end_index = next(
                index for index, line in enumerate(lines[1:], start=1)
                if line.strip() == "---"
            )
        except StopIteration as exc:
            raise ValueError(f"frontmatter 未闭合: {file_path}") from exc

        metadata_raw = yaml.safe_load(
            "\n".join(lines[1:end_index])
        )

        if not isinstance(metadata_raw, dict):
            raise ValueError(f"frontmatter 格式错误: {file_path}")

        name = metadata_raw.get("name")
        if not name:
            raise ValueError(f"缺少 name 字段: {file_path}")

        description = metadata_raw.get("description", "")

        return (
            SkillMetadata(
                name=str(name),
                description=str(description),
            ),
            "\n".join(lines[end_index + 1:]).strip(),
        )