from typing import Annotated

from langchain_core.tools import StructuredTool
from pydantic import Field

from pybase.modules.sql_processing.yaml_provider.schemas import GlossaryTerm

# 【优化】 （术语过多导致上下文爆炸）
# 1：两阶段加载，将此工具分为两个阶段：
#  - 第一阶段：加载所有术语，生成术语列表 ，即使我们有200个术语，平均每个术语7个字符,一共1400个字符，也不会导致上下文爆炸
#  - 第二阶段：根据用户输入查询术语标准口径

# 2：分级展示 如果术语有几百个，但分类只有十几个，模型不需要知道具体的叶子节点，只需要知道“有哪些筐”
# -在工具描述中，只注入分类列表和每个分类下的示例
# -模型在查询时，先根据分类进行筛选，再根据术语进行查询

# 3：提前将术语向量存储，每次查询时进行检索


# （sakila 是历史样本库，所有相对时间必须基于 MAX(rental_date) 而非 NOW()）
TOOL_DESCRIPTION_TEMPLATE = """
查询业务术语的标准口径（含定义 + 可复用 SQL 片段 + 同义词）。
            
            何时使用本工具：
            - 用户问题涉及"活跃客户""VIP""热门影片""高消费客户""租金"等业务指标术语时
            - 用户问题涉及"近 N 个月""最近""本月""上月""今年"等相对时间时
              
            <可用术语列表>
            {terms}
            </可用术语列表>
            
            传入上述术语名或其同义词即可命中。未命中会返回全部术语供你重试。
"""


def create_lookup_glossary_tool(all_terms: list[GlossaryTerm]):
    def format_miss(query: str) -> str:
        if not all_terms:
            return (
                f"未找到术语「{query}」的标准口径。当前 glossary 为空——"
                "可能是 schema 字典未正确加载，请检查 dodo_agentx.yml 的 glossary section。"
            )
        lines = [f"未找到术语「{query}」的标准口径。", "", "当前已登记的术语（用准确名或同义词重试）："]
        for g in all_terms:
            line = f"- {g.term}"
            if g.synonyms:
                line += f"（同义词：{'/'.join(g.synonyms)}）"
            lines.append(line)
        return "\n".join(lines)

    def format_terms_list() -> str:
        lines: list[str] = []
        for g in all_terms:
            line = f"- {g.term}"
            if g.synonyms:
                line += f"（同义词：{'、'.join(g.synonyms)}）"
            lines.append(line)
        return "\n".join(lines)

    def format_hit(g: GlossaryTerm) -> str:
        parts: list[str] = [f"【术语】{g.term}"]
        if g.description:
            parts.append(f"【标准口径】{g.description}")
        if g.sql_fragment:
            parts.append(f"【SQL 片段（可直接复用）】\n{g.sql_fragment}")
        if g.synonyms:
            parts.append(f"【同义词】{'、'.join(g.synonyms)}")
        return "\n\n".join(parts)

    terms = format_terms_list()
    term_index: dict[str, GlossaryTerm] = {}
    synonym_index: dict[str, GlossaryTerm] = {}
    description = TOOL_DESCRIPTION_TEMPLATE.format(terms=terms)

    for g in all_terms:
        if g.term and g.term.strip():
            term_index[g.term.strip().lower()] = g
        for syn in g.synonyms:
            if syn and syn.strip():
                synonym_index[syn.strip().lower()] = g


    async def lookup_glossary_tool(
            term: Annotated[str, Field(description='要查的术语名或同义词，必传，如 "活跃客户"、"VIP"、"近3个月"、"最近"')],
    ) -> str:
        if not term.strip():
            return '入参为空，请必须传入具体术语名（如 "活跃客户"），参考工具说明中的可用术语列表，再次尝试调用本工具。'

        termed = term.strip()
        lower = termed.lower()

        hit = term_index.get(lower)
        if not hit:
            hit = synonym_index.get(lower)

        return format_hit(hit) if hit else format_miss(term)

    return StructuredTool.from_function(
        coroutine=lookup_glossary_tool,
        name="lookupGlossary",
        description=description,
    )
