import logging
from dataclasses import dataclass, field

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError
from sqlalchemy.ext.asyncio import AsyncSession

from .repository import AccountRepository

logger = logging.getLogger(__name__)

# 需要注入 account_id 过滤条件的表名与对应列名的映射
# ad_account 表的主键是 id，其他业务表的外键是 account_id
ACCOUNT_ID_TABLES: dict[str, str] = {
    "ad_account": "id",
    "campaign": "account_id",
    "ad_performance_daily": "account_id",
    "ad_touchpoint": "account_id",
    "audience_package": "account_id",
    "promotion_target": "account_id",
}


@dataclass
class DataScope:
    """数据权限范围，标识用户是否为管理员以及可访问的广告账户ID列表"""
    is_admin: bool
    account_ids: list[int] = field(default_factory=list)

    @property
    def has_access(self) -> bool:
        """判断用户是否有任何数据访问权限（管理员或拥有至少一个账户）"""
        return self.is_admin or len(self.account_ids) > 0


class DataAccessGuard:
    """数据权限守卫，负责查询用户数据范围并强制改写 SQL 注入账户过滤条件"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = AccountRepository(session)
        self._scope_cache: dict[int, DataScope] = {}

    async def get_data_scope(self, user_id: int, is_admin: bool) -> DataScope:
        """获取用户的数据权限范围，管理员返回全量权限，普通用户查询其可访问账户列表，结果缓存在实例中"""
        if user_id in self._scope_cache:
            return self._scope_cache[user_id]

        if is_admin:
            scope = DataScope(is_admin=True, account_ids=[])
        else:
            account_ids = await self._repository.get_accessible_account_ids(user_id)
            scope = DataScope(is_admin=False, account_ids=account_ids)

        self._scope_cache[user_id] = scope
        return scope

    async def get_account_names(self, account_ids: list[int]) -> list[str]:
        """获取用户可访问的广告账户名称列表"""
        return await self._repository.get_account_names(account_ids)

    async def rewrite_sql(self, sql: str, scope: DataScope) -> str:
        """根据数据权限范围改写 SQL，对涉及账户的表强制注入 account_id IN (...) 条件

        - 管理员：不做任何改写，允许全量访问
        - 无权限用户：抛出 ForbiddenError
        - 普通用户：使用 sqlglot AST 解析并注入 WHERE/JOIN ON 条件
        """
        if scope.is_admin:
            return sql

        if not scope.has_access:
            from ...core.exceptions import ForbiddenError
            raise ForbiddenError("❌ 您没有任何广告账户的数据权限，无法执行查询。请联系管理员分配广告账户。")

        if not scope.account_ids:
            return sql

        try:
            ast = parse_one(sql, dialect="mysql")
        except ParseError:
            logger.warning("DataAccessGuard: SQL 解析失败，跳过数据权限改写: %s", sql[:200])
            return sql

        if not isinstance(ast, exp.Select):
            return sql

        self._inject_account_filter(ast, scope.account_ids)

        rewritten = ast.sql(dialect="mysql")
        logger.info("DataAccessGuard: SQL 已改写注入账户过滤, account_ids=%s", scope.account_ids)
        return rewritten

    def _inject_account_filter(self, select: exp.Select, account_ids: list[int]) -> None:
        """递归处理 SELECT 语句，对 CTE、FROM 子句、JOIN 子句中涉及的账户表注入过滤条件"""
        with_clause = select.args.get("with")
        if with_clause:
            for cte in with_clause.expressions if hasattr(with_clause, "expressions") else [with_clause]:
                if isinstance(cte, exp.CTE) and isinstance(cte.this, exp.Select):
                    self._inject_account_filter(cte.this, account_ids)

        from_clause = select.args.get("from")
        if from_clause:
            self._process_table(select, from_clause.this, account_ids)

        for join in select.args.get("joins") or []:
            join_table = join.this
            alias = join_table.alias if isinstance(join_table, exp.Table) else None
            if alias:
                self._add_join_condition(select, join, alias, account_ids)

    def _process_table(self, select: exp.Select, table: exp.Expression, account_ids: list[int]) -> None:
        """处理 FROM 子句中的表引用，若表在 ACCOUNT_ID_TABLES 中则注入 WHERE 条件；若是子查询则递归处理"""
        if isinstance(table, exp.Table):
            table_name = table.name.lower()
            alias = table.alias or table.name

            if table_name in ACCOUNT_ID_TABLES:
                column_name = ACCOUNT_ID_TABLES[table_name]
                in_expr = exp.In(
                    this=exp.Column(
                        this=exp.to_identifier(column_name),
                        table=exp.to_identifier(alias),
                    ),
                    expressions=[exp.Literal.number(aid) for aid in account_ids],
                )
                existing_where = select.args.get("where")
                if existing_where:
                    select.set("where", exp.Where(this=exp.And(this=existing_where.this, expression=in_expr)))
                else:
                    select.set("where", exp.Where(this=in_expr))

        elif isinstance(table, exp.Subquery):
            if isinstance(table.this, exp.Select):
                self._inject_account_filter(table.this, account_ids)

    def _add_join_condition(self, select: exp.Select, join: exp.Join, alias: str, account_ids: list[int]) -> None:
        """处理 JOIN 子句中的表引用，若表在 ACCOUNT_ID_TABLES 中则追加 ON 条件"""
        join_table = join.this
        if not isinstance(join_table, exp.Table):
            return
        table_name = join_table.name.lower()
        if table_name not in ACCOUNT_ID_TABLES:
            return

        column_name = ACCOUNT_ID_TABLES[table_name]
        in_expr = exp.In(
            this=exp.Column(
                this=exp.to_identifier(column_name),
                table=exp.to_identifier(alias),
            ),
            expressions=[exp.Literal.number(aid) for aid in account_ids],
        )
        existing_on = join.args.get("on")
        if existing_on:
            join.set("on", exp.And(this=existing_on, expression=in_expr))
        else:
            join.set("on", in_expr)