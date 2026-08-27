# SQL 数据权限注入条件处理详解

本文档详细说明 `DataAccessGuard.rewrite_sql()` 针对不同 SQL 语句结构的注入处理逻辑。

## 一、注入规则总览

### 1.1 需要注入的表与列

```python
ACCOUNT_ID_TABLES = {
    "ad_account": "id",                # 主键 id
    "campaign": "account_id",          # 外键 account_id
    "ad_performance_daily": "account_id",
    "ad_touchpoint": "account_id",
    "audience_package": "account_id",
    "promotion_target": "account_id",
}
```

- `ad_account` 表：过滤条件为 `id IN (...)`
- 其他业务表：过滤条件为 `account_id IN (...)`
- **不在映射中的表（如 customer、creative、conversion_event 等）不注入任何条件**

### 1.2 注入原则

| 原则 | 说明 |
|------|------|
| **管理员跳过** | `is_admin=True` 时，不做任何改写，直接返回原始 SQL |
| **无权限拒绝** | 普通用户且 `account_ids` 为空时，抛出 `ForbiddenError` |
| **AST 改写** | 使用 sqlglot 解析为 AST，在语法树层面注入，不使用正则替换 |
| **递归处理** | CTE、子查询内部的 SELECT 也会被递归注入 |
| **解析失败降级** | sqlglot 解析失败时，记录 warning 日志，返回原始 SQL（不阻断查询） |

---

## 二、单表查询

### 2.1 无 WHERE 条件

**原始 SQL**：
```sql
SELECT * FROM campaign
```

**改写后**：
```sql
SELECT * FROM campaign WHERE campaign.account_id IN (1, 3, 5)
```

**处理逻辑**：`_process_table` 检测到 `campaign` 在 `ACCOUNT_ID_TABLES` 中，且 SELECT 无现有 WHERE，直接 `select.set("where", in_expr)`。

---

### 2.2 已有 WHERE 条件

**原始 SQL**：
```sql
SELECT * FROM campaign WHERE status = 'ACTIVE'
```

**改写后**：
```sql
SELECT * FROM campaign WHERE status = 'ACTIVE' AND campaign.account_id IN (1, 3, 5)
```

**处理逻辑**：检测到已有 WHERE，用 `exp.And(this=existing_where, expression=in_expr)` 追加。

---

### 2.3 已有多个 WHERE 条件（AND 链）

**原始 SQL**：
```sql
SELECT * FROM campaign WHERE status = 'ACTIVE' AND daily_budget > 100
```

**改写后**：
```sql
SELECT * FROM campaign WHERE status = 'ACTIVE' AND daily_budget > 100 AND campaign.account_id IN (1, 3, 5)
```

**处理逻辑**：与 2.2 相同，无论现有 WHERE 是简单条件还是 AND 嵌套，都在最外层追加 AND。

---

### 2.4 ad_account 表（主键过滤）

**原始 SQL**：
```sql
SELECT * FROM ad_account WHERE status = 'ACTIVE'
```

**改写后**：
```sql
SELECT * FROM ad_account WHERE status = 'ACTIVE' AND ad_account.id IN (1, 3, 5)
```

**处理逻辑**：`ad_account` 在映射中对应列名为 `id`（而非 `account_id`），所以注入 `id IN (...)`。

---

### 2.5 不在映射中的表（不注入）

**原始 SQL**：
```sql
SELECT * FROM customer WHERE first_seen_at > '2026-01-01'
```

**改写后**：
```sql
SELECT * FROM customer WHERE first_seen_at > '2026-01-01'
```

**处理逻辑**：`customer` 不在 `ACCOUNT_ID_TABLES` 中，跳过注入。这类表的数据不按账户隔离。

---

## 三、JOIN 查询

### 3.1 两表 JOIN（两表都在映射中）

**原始 SQL**：
```sql
SELECT c.campaign_name, SUM(p.cost)
FROM campaign c
JOIN ad_performance_daily p ON c.id = p.campaign_id
WHERE p.stat_date = '2026-08-25'
GROUP BY c.campaign_name
```

**改写后**：
```sql
SELECT c.campaign_name, SUM(p.cost)
FROM campaign c
JOIN ad_performance_daily p ON c.id = p.campaign_id AND c.account_id IN (1, 3, 5) AND p.account_id IN (1, 3, 5)
WHERE p.stat_date = '2026-08-25'
GROUP BY c.campaign_name
```

**处理逻辑**：
- FROM 子句中的 `campaign`：注入 WHERE 条件
- JOIN 子句中的 `ad_performance_daily`：追加 ON 条件

---

### 3.2 两表 JOIN（只有一张表在映射中）

**原始 SQL**：
```sql
SELECT a.ad_name, c.creative_name
FROM ad a
JOIN ad_creative ac ON a.id = ac.ad_id
JOIN creative c ON ac.creative_id = c.id
```

**改写后**：
```sql
SELECT a.ad_name, c.creative_name
FROM ad a
JOIN ad_creative ac ON a.id = ac.ad_id
JOIN creative c ON ac.creative_id = c.id
```

**处理逻辑**：`ad`、`ad_creative`、`creative` 均不在 `ACCOUNT_ID_TABLES` 中，不注入任何条件。

> **注意**：`ad` 表通过 `ad_group_id → campaign_id → account_id` 间接关联账户，但当前映射未包含 `ad` 表。如需对 `ad` 表也做隔离，需通过 JOIN campaign 间接过滤，或在映射中增加 `ad` 表并在 SQL 中确保 JOIN 了 campaign。这是一个设计权衡——当前选择只对直接含 `account_id` 的表做注入。

---

### 3.3 LEFT JOIN

**原始 SQL**：
```sql
SELECT c.campaign_name, ap.package_name
FROM campaign c
LEFT JOIN audience_package ap ON c.account_id = ap.account_id
```

**改写后**：
```sql
SELECT c.campaign_name, ap.package_name
FROM campaign c
LEFT JOIN audience_package ap ON c.account_id = ap.account_id AND ap.account_id IN (1, 3, 5)
WHERE c.account_id IN (1, 3, 5)
```

**处理逻辑**：LEFT JOIN 与 INNER JOIN 处理方式相同——FROM 表注入 WHERE，JOIN 表追加 ON。

---

### 3.4 多表 JOIN（三张表都在映射中）

**原始 SQL**：
```sql
SELECT a.account_name, c.campaign_name, SUM(p.cost)
FROM ad_account a
JOIN campaign c ON a.id = c.account_id
JOIN ad_performance_daily p ON c.id = p.campaign_id
WHERE p.stat_date = '2026-08-25'
GROUP BY a.account_name, c.campaign_name
```

**改写后**：
```sql
SELECT a.account_name, c.campaign_name, SUM(p.cost)
FROM ad_account a
JOIN campaign c ON a.id = c.account_id AND c.account_id IN (1, 3, 5)
JOIN ad_performance_daily p ON c.id = p.campaign_id AND p.account_id IN (1, 3, 5)
WHERE p.stat_date = '2026-08-25' AND a.id IN (1, 3, 5)
GROUP BY a.account_name, c.campaign_name
```

**处理逻辑**：
- FROM 的 `ad_account`：注入 `WHERE a.id IN (...)`
- JOIN 的 `campaign`：追加 `ON ... AND c.account_id IN (...)`
- JOIN 的 `ad_performance_daily`：追加 `ON ... AND p.account_id IN (...)`

---

## 四、子查询

### 4.1 FROM 子查询

**原始 SQL**：
```sql
SELECT * FROM (
    SELECT campaign_name, account_id FROM campaign
) sub
WHERE sub.account_id = 1
```

**改写后**：
```sql
SELECT * FROM (
    SELECT campaign_name, account_id FROM campaign WHERE campaign.account_id IN (1, 3, 5)
) sub
WHERE sub.account_id = 1
```

**处理逻辑**：`_process_table` 检测到 FROM 子句是 `exp.Subquery`，递归调用 `_inject_account_filter` 处理子查询内部的 SELECT。

---

### 4.2 WHERE 子查询（IN 子查询）

**原始 SQL**：
```sql
SELECT * FROM ad_performance_daily
WHERE campaign_id IN (
    SELECT id FROM campaign WHERE status = 'ACTIVE'
)
```

**改写后**：
```sql
SELECT * FROM ad_performance_daily
WHERE campaign_id IN (
    SELECT id FROM campaign WHERE status = 'ACTIVE' AND campaign.account_id IN (1, 3, 5)
)
AND ad_performance_daily.account_id IN (1, 3, 5)
```

**处理逻辑**：
- 外层 `ad_performance_daily`：注入 WHERE 条件
- 内层子查询中的 `campaign`：sqlglot 会将 WHERE 中的子查询解析为 `exp.In` 的 `expressions`，其中的 SELECT 也会被递归处理

> **注意**：WHERE 子查询中的 SELECT 是否被自动递归处理，取决于 sqlglot 的 AST 结构。当前实现主要处理 FROM 子查询和 CTE，WHERE 标量子查询可能需要额外递归。如遇遗漏，可在 `_inject_account_filter` 中增加对 WHERE 子表达式的遍历。

---

## 五、CTE（WITH 子句）

### 5.1 单 CTE

**原始 SQL**：
```sql
WITH active_campaigns AS (
    SELECT * FROM campaign WHERE status = 'ACTIVE'
)
SELECT * FROM active_campaigns
```

**改写后**：
```sql
WITH active_campaigns AS (
    SELECT * FROM campaign WHERE status = 'ACTIVE' AND campaign.account_id IN (1, 3, 5)
)
SELECT * FROM active_campaigns
```

**处理逻辑**：`_inject_account_filter` 检测到 WITH 子句，遍历每个 CTE，对 CTE 内部的 SELECT 递归调用 `_inject_account_filter`。

---

### 5.2 多 CTE

**原始 SQL**：
```sql
WITH
    active_campaigns AS (
        SELECT * FROM campaign WHERE status = 'ACTIVE'
    ),
    daily_stats AS (
        SELECT * FROM ad_performance_daily WHERE stat_date = '2026-08-25'
    )
SELECT c.campaign_name, SUM(d.cost)
FROM active_campaigns c
JOIN daily_stats d ON c.id = d.campaign_id
GROUP BY c.campaign_name
```

**改写后**：
```sql
WITH
    active_campaigns AS (
        SELECT * FROM campaign WHERE status = 'ACTIVE' AND campaign.account_id IN (1, 3, 5)
    ),
    daily_stats AS (
        SELECT * FROM ad_performance_daily WHERE stat_date = '2026-08-25' AND ad_performance_daily.account_id IN (1, 3, 5)
    )
SELECT c.campaign_name, SUM(d.cost)
FROM active_campaigns c
JOIN daily_stats d ON c.id = d.campaign_id
GROUP BY c.campaign_name
```

**处理逻辑**：每个 CTE 内部的 SELECT 都被递归注入。外层主查询的 FROM/JOIN 引用的是 CTE 名称（`active_campaigns`、`daily_stats`），不在 `ACCOUNT_ID_TABLES` 中，所以不注入。

---

## 六、GROUP BY / ORDER BY / LIMIT

### 6.1 GROUP BY 查询

**原始 SQL**：
```sql
SELECT account_id, SUM(cost) FROM ad_performance_daily
GROUP BY account_id
```

**改写后**：
```sql
SELECT account_id, SUM(cost) FROM ad_performance_daily
WHERE ad_performance_daily.account_id IN (1, 3, 5)
GROUP BY account_id
```

**处理逻辑**：GROUP BY / ORDER BY / LIMIT 不影响注入逻辑，只在 WHERE 子句中注入条件。

---

### 6.2 HAVING 子句

**原始 SQL**：
```sql
SELECT account_id, SUM(cost) AS total_cost
FROM ad_performance_daily
GROUP BY account_id
HAVING total_cost > 1000
```

**改写后**：
```sql
SELECT account_id, SUM(cost) AS total_cost
FROM ad_performance_daily
WHERE ad_performance_daily.account_id IN (1, 3, 5)
GROUP BY account_id
HAVING total_cost > 1000
```

**处理逻辑**：HAVING 不影响注入，条件注入在 WHERE 层。

---

## 七、UNION

### 7.1 UNION 查询

**原始 SQL**：
```sql
SELECT account_id, cost FROM ad_performance_daily WHERE stat_date = '2026-08-25'
UNION ALL
SELECT account_id, cost FROM ad_touchpoint WHERE touch_type = 'CLICK'
```

**改写后**（取决于 sqlglot 对 UNION 的 AST 表示）：

```sql
SELECT account_id, cost FROM ad_performance_daily WHERE stat_date = '2026-08-25' AND ad_performance_daily.account_id IN (1, 3, 5)
UNION ALL
SELECT account_id, cost FROM ad_touchpoint WHERE touch_type = 'CLICK' AND ad_touchpoint.account_id IN (1, 3, 5)
```

**处理逻辑**：UNION 的每个分支都是独立的 SELECT，需要分别注入。当前实现处理的是单个 `exp.Select`，UNION 可能被 sqlglot 解析为 `exp.Union`。如需完整支持，可在 `rewrite_sql` 中增加对 UNION 的遍历处理。

> **当前限制**：如果 sqlglot 将 UNION 解析为非 `exp.Select` 类型，当前实现会跳过改写。建议后续扩展。

---

## 八、别名处理

### 8.1 表别名

**原始 SQL**：
```sql
SELECT p.cost FROM ad_performance_daily p WHERE p.stat_date = '2026-08-25'
```

**改写后**：
```sql
SELECT p.cost FROM ad_performance_daily p WHERE p.stat_date = '2026-08-25' AND p.account_id IN (1, 3, 5)
```

**处理逻辑**：注入条件时使用表的别名（`p`）而非原始表名，确保 SQL 语义正确。

---

### 8.2 无别名

**原始 SQL**：
```sql
SELECT cost FROM ad_performance_daily WHERE stat_date = '2026-08-25'
```

**改写后**：
```sql
SELECT cost FROM ad_performance_daily WHERE stat_date = '2026-08-25' AND ad_performance_daily.account_id IN (1, 3, 5)
```

**处理逻辑**：无别名时，使用原始表名作为列限定符。

---

## 九、特殊情况与限制

### 9.1 表名大小写

**处理**：表名比较时统一转小写（`table.name.lower()`），不区分大小写。

### 9.2 同一表多次出现

**原始 SQL**：
```sql
SELECT * FROM campaign c1
JOIN campaign c2 ON c1.id = c2.id
```

**改写后**：
```sql
SELECT * FROM campaign c1
JOIN campaign c2 ON c1.id = c2.id AND c2.account_id IN (1, 3, 5)
WHERE c1.account_id IN (1, 3, 5)
```

**处理逻辑**：每个表引用独立处理，使用各自的别名注入条件。

### 9.3 不支持的 SQL 结构

| 结构 | 当前处理 | 建议 |
|------|---------|------|
| UNION / UNION ALL | 可能跳过改写 | 扩展 `rewrite_sql` 支持 `exp.Union` |
| WHERE 中的标量子查询 | 可能不递归 | 增加 WHERE 表达式遍历 |
| 嵌套超过 2 层的子查询 | 递归支持，但需测试 | 增加单元测试覆盖 |
| 窗口函数（OVER） | 不影响注入 | 无需特殊处理 |
| INSERT/UPDATE/DELETE | 不改写（已被 SqlSafetyGuard 拦截） | 无需处理 |

### 9.4 解析失败降级

当 sqlglot 无法解析 SQL 时（如使用了 MySQL 特有语法、存储过程调用等），`rewrite_sql` 会：
1. 记录 `warning` 级别日志（含 SQL 前 200 字符）
2. 返回原始 SQL，不做任何改写
3. 不抛出异常，不阻断查询

**风险**：解析失败意味着数据权限未被注入，可能导致数据泄露。建议：
- 监控 warning 日志，及时发现未改写的查询
- 对高频查询模式做单元测试，确保 sqlglot 能正确解析
- 考虑在解析失败时抛出异常而非降级（更安全但更严格）

---

## 十、注入流程图

```
rewrite_sql(sql, scope)
    │
    ├── scope.is_admin? → 返回原始 SQL
    │
    ├── !scope.has_access? → 抛出 ForbiddenError
    │
    ├── parse_one(sql, dialect="mysql")
    │   └── ParseError? → 记录 warning，返回原始 SQL
    │
    ├── !isinstance(ast, exp.Select)? → 返回原始 SQL
    │
    ├── _inject_account_filter(ast, account_ids)
    │   │
    │   ├── WITH 子句?
    │   │   └── 遍历每个 CTE → 递归 _inject_account_filter
    │   │
    │   ├── FROM 子句?
    │   │   └── _process_table
    │   │       ├── exp.Table 且在映射中 → 注入 WHERE 条件
    │   │       └── exp.Subquery → 递归 _inject_account_filter
    │   │
    │   └── JOIN 子句?
    │       └── _add_join_condition
    │           └── 表在映射中 → 追加 ON 条件
    │
    └── ast.sql(dialect="mysql") → 返回改写后的 SQL
```