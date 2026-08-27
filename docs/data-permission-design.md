# 数据权限设计文档

## 一、每张表的意义与业务背景

### 1. 用户与权限层

| 表 | 意义 | 业务背景 |
|---|---|---|
| **app_user** | 系统登录用户（内部运营人员） | 营销分析系统的使用者，如投放优化师、运营负责人、管理员。**不是广告触达的终端用户**。通过 `role` 区分 admin/user。 |
| **marketing_channel** | 广告渠道 | 如巨量引擎（抖音）、腾讯广告（广点通）、Google Ads、京东快车等。是广告投放的平台级分类。 |
| **ad_account** | 广告平台账户 | 每个渠道下的具体广告账户（如巨量引擎下的"品牌A-主账户"）。**这是数据权限的最小单元**——所有业务数据都挂靠在某个 ad_account 下。 |
| **user_ad_account** | 用户↔广告账户的多对多关联 | 控制哪个运营人员能看哪个广告账户的数据。含角色（OWNER/ANALYST/OPERATOR/VIEWER）和过期时间，支持临时授权。 |

### 2. 广告投放结构层（平台侧镜像）

| 表 | 意义 | 业务背景 |
|---|---|---|
| **campaign** | 广告计划 | 广告平台上的投放计划，属于某个 ad_account。设定营销目标（TRAFFIC/LEAD/SALES）、日预算、投放周期。 |
| **ad_group** | 广告组 | 计划下的投放单元，配置定向方式（自动/手动/人群）、出价策略。 |
| **ad** | 具体广告 | 广告组下的单条广告，关联落地页。 |
| **creative** | 创意素材库 | 图片、视频、轮播等素材，与广告多对多关联（ad_creative）。 |
| **ad_creative** | 广告↔素材多对多 | 一条广告可配多个素材，一个素材可被多条广告复用。 |
| **audience_package** | 人群包 | 定向投放使用的人群包（DMP自定义、Lookalike扩展、兴趣、重定向、排除等），属于某个 ad_account。 |
| **ad_group_audience_relation** | 广告组↔人群包绑定 | INCLUDE（定向）或 EXCLUDE（排除）。 |
| **promotion_target** | 推广对象 | 广告实际推广的商品/店铺/直播间/落地页，属于某个 ad_account。 |
| **ad_group_target_relation** | 广告组↔推广对象绑定 | 电商搜索广告需要绑定具体 SKU。 |
| **ad_group_keyword** | 搜索关键词定向 | 京东快车等搜索广告的关键词出价，精确/短语/广泛匹配。 |

### 3. 数据分析层（事实表）

| 表 | 意义 | 业务背景 |
|---|---|---|
| **ad_performance_daily** | 广告日报核心事实表 | 每天从广告平台拉取的分维度消耗/曝光/点击/转化数据。粒度：日期×广告×创意×人群×位置×地域×年龄×性别×设备。**这是查询最频繁的表**。 |
| **customer** | 终端客户/访客 | 到达企业站点的匿名访客或已识别客户，通过埋点 anonymous_id 或 CRM ID 关联。 |
| **ad_touchpoint** | 广告触点 | 埋点捕获的广告曝光/点击/浏览事件，关联到具体客户和广告链路。 |
| **conversion_event** | 转化事件 | 企业确认的转化（留资、注册、加购、购买），来源可以是 Web/APP/CRM/OMS。 |
| **attribution_result** | 归因结果 | 转化事件与广告触点之间的归因分配，支持末次点击、首次点击、线性、平台上报等多种模型。 |
| **sales_order** | 订单事实 | 企业订单数据，可关联到转化事件，计算净收入（支付-退款）。 |

---

## 二、表之间的关系图

```
marketing_channel ──1:N──> ad_account ──1:N──> campaign ──1:N──> ad_group ──1:N──> ad
                                │                           │                    │
                                │                           ├── ad_group_audience_relation
                                │                           ├── ad_group_target_relation
                                │                           └── ad_group_keyword
                                │
                                ├── audience_package
                                ├── promotion_target
                                └── ad_performance_daily (account_id)

app_user ──M:N──> ad_account  (通过 user_ad_account)

ad ──M:N──> creative  (通过 ad_creative)

customer ──1:N──> ad_touchpoint ──1:N──> attribution_result
customer ──1:N──> conversion_event ──1:N──> attribution_result
conversion_event ──1:N──> sales_order

ad_touchpoint.account_id ──> ad_account
ad_performance_daily.account_id ──> ad_account
```

---

## 三、权限体系下的关系

**核心原则：`ad_account` 是数据权限的最小隔离单元。**

```
app_user (登录用户)
    │
    │  user_ad_account (多对多，含角色+过期时间)
    │
    ▼
ad_account (广告账户)  ←── 数据权限边界
    │
    ├── campaign.account_id
    ├── ad_performance_daily.account_id
    ├── ad_touchpoint.account_id
    ├── audience_package.account_id
    └── promotion_target.account_id
```

**含义**：
- 一个运营人员只能看到他通过 `user_ad_account` 关联的那些 `ad_account` 下的数据
- `campaign`、`ad_performance_daily` 等业务表都通过 `account_id` 外键挂靠到 `ad_account`
- 只要控制住 `account_id` 的可见范围，就控制住了所有业务数据的可见范围
- `admin` 角色绕过此限制，可看全量数据

---

## 四、权限实现详解

### 4.1 整体架构：三层权限模型

```
┌─────────────────────────────────────────────────────┐
│  第一层：身份认证（Authentication）                    │
│  JWT Bearer Token → 解析 user_id → 验证用户状态       │
├─────────────────────────────────────────────────────┤
│  第二层：角色鉴权（Authorization - 粗粒度）            │
│  admin / user → 决定是否能访问管理接口                  │
├─────────────────────────────────────────────────────┤
│  第三层：数据权限（Data-Level Permission - 细粒度）     │
│  user_ad_account → 决定能看哪些 ad_account 的数据      │
│  → SQL AST 改写强制注入 account_id IN (...)            │
└─────────────────────────────────────────────────────┘
```

### 4.2 第一层：身份认证

**实现位置**：`modules/auth/dependencies.py` → `get_current_user`

**流程**：
1. 从请求头 `Authorization: Bearer <token>` 提取 JWT
2. 用 `PyJWT` + `HS256` + 密钥解码，验证签名和过期时间
3. 从 payload 取 `sub`（user_id），查库验证用户存在且 `status=ACTIVE`
4. 注入为 FastAPI 依赖 `CurrentUserDep`，所有需登录的接口自动获取

**关键设计**：
- access_token 短期（30min），refresh_token 长期（7天）
- token 中只存 user_id 和 exp，不存敏感信息
- 用户被禁用后，即使 token 未过期，下次请求也会被拒绝（查库验证状态）

### 4.3 第二层：角色鉴权

**实现位置**：`modules/auth/dependencies.py` → `get_current_admin_user`

**流程**：
1. 先走 `get_current_user` 确保已登录
2. 检查 `user.role == "admin"`
3. 不满足则抛出 `ForbiddenError(403)`

**使用方式**：
```python
# 任何接口只需声明依赖即可保护
@router.post("/grant")
async def grant_access(..., admin_user: CurrentAdminUserDep):
    # 只有 admin 能到这里
```

### 4.4 第三层：数据权限（核心，最复杂）

**这是整个权限系统最关键的部分，解决的是"同一个接口，不同用户看到不同数据"的问题。**

#### 4.4.1 数据模型

```
app_user ──M:N──> ad_account  (通过 user_ad_account)
                              │
                              ├── role: OWNER/ANALYST/OPERATOR/VIEWER
                              └── expires_at: 支持临时授权过期
```

- 一个用户可以被分配多个广告账户
- 每个分配有角色和过期时间
- `ad_account` 是数据权限的**最小隔离单元**——所有业务表都通过 `account_id` 关联到它

#### 4.4.2 双保险机制

**为什么不只靠一层？**

LLM 生成的 SQL 是不可信的——它可能忽略提示、忘记加条件、甚至被 prompt injection 诱导生成不带过滤的 SQL。所以必须有两层保障：

| 层级 | 位置 | 机制 | 作用 |
|------|------|------|------|
| **第一层：提示层** | `DataScopeMiddleware` | 在 LLM 的 system_prompt 中注入数据范围 | 让 LLM **主动**生成带 account_id 条件的 SQL，减少改写开销 |
| **第二层：执行层** | `DataAccessGuard.rewrite_sql()` | SQL AST 改写，强制注入 WHERE 条件 | 即使 LLM 忽略提示，也能**强制**保证数据隔离 |

#### 4.4.3 第一层：DataScopeMiddleware（提示层）

**实现位置**：`modules/agent/middleware/data_scope_middleware.py`

**工作流程**：
1. 拦截每次 LLM 调用
2. 查询当前用户的 `DataScope`（是否 admin + 可访问账户 ID 列表）
3. 根据权限范围生成提示文本，追加到 system_prompt 末尾

- **管理员**：`"当前用户是管理员，可访问所有广告账户数据，无需额外过滤。"`
- **普通用户**：`"当前用户可访问的广告账户ID: [1, 3, 5]，生成SQL时必须加上 account_id IN (1,3,5) 条件"`
- **无权限用户**：`"当前用户没有任何广告账户的数据权限，请直接告知用户联系管理员"`

4. 防重复：检查 `《DataScope》` 标记，已注入则跳过

**意义**：LLM 主动生成正确的 SQL，避免 AST 改写带来的性能开销和潜在语义变化。

#### 4.4.4 第二层：DataAccessGuard.rewrite_sql()（执行层，强制保障）

**实现位置**：`modules/account/data_access_guard.py`

**这是安全底线，不信任任何来自 LLM 的 SQL。**

**工作流程**：

```
原始 SQL（LLM 生成，可能不带 account_id 条件）
    │
    ▼
1. 管理员？→ 直接放行，不改写
    │
    ▼
2. 无权限？→ 抛出 ForbiddenError
    │
    ▼
3. sqlglot.parse_one(sql, dialect="mysql")  ← AST 解析
    │
    ▼
4. 递归遍历 AST：
   ├── FROM 子句中的表 → 若在 ACCOUNT_ID_TABLES 中 → 注入 WHERE account_id IN (...)
   ├── JOIN 子句中的表 → 若在 ACCOUNT_ID_TABLES 中 → 追加 ON account_id IN (...)
   ├── WITH (CTE) 子句 → 递归处理内部的 SELECT
   └── 子查询 → 递归处理
    │
    ▼
5. ast.sql(dialect="mysql")  ← 序列化回 SQL 字符串
    │
    ▼
改写后的 SQL（强制带 account_id 过滤）
```

**ACCOUNT_ID_TABLES 映射**（定义哪些表需要注入、用什么列名）：

```python
ACCOUNT_ID_TABLES = {
    "ad_account": "id",              # ad_account 表用主键 id
    "campaign": "account_id",        # 其他业务表用外键 account_id
    "ad_performance_daily": "account_id",
    "ad_touchpoint": "account_id",
    "audience_package": "account_id",
    "promotion_target": "account_id",
}
```

#### 4.4.5 完整请求流程

```
用户: "帮我看下昨天的消耗"
    │
    ▼
[Agent Router] 从 JWT 解析 current_user（第一层：身份认证）
    │
    ▼
[AgentService.chat(message, user)]
    │
    ▼
[DataScopeMiddleware] 查询 user_ad_account → 注入 system_prompt（第一层保险）
    "当前用户可访问的广告账户ID: [1, 3]，生成SQL时必须加上 account_id IN (1,3)"
    │
    ▼
[LLM] 生成 SQL：
    SELECT stat_date, SUM(cost) FROM ad_performance_daily
    WHERE stat_date = '2026-08-25' AND account_id IN (1,3)
    GROUP BY stat_date
    │
    ▼
[execute_sql_tool]
    1. SqlSafetyGuard.validate()        ← 安全校验（白名单、强制 LIMIT）
    2. DataAccessGuard.rewrite_sql()    ← AST 强制改写（第二层保险，双保险）
    3. ExplainPrecheckService.check()   ← 性能预检
    4. ReadOnlyQueryRunner.execute()    ← 执行
    │
    ▼
返回结果给用户
```

#### 4.4.6 缓存与性能

- 同一请求内，`DataAccessGuard` 实例缓存 `DataScope`，`user_ad_account` 只查一次
- 后续可扩展为 Redis 缓存（TTL 5分钟），避免每次请求都查库

#### 4.4.7 边界情况处理

| 情况 | 处理 |
|------|------|
| SQL 解析失败 | 记录 warning，返回原始 SQL（降级，不阻断查询，但日志可追踪） |
| 非 SELECT 语句 | 不改写（已被 SqlSafetyGuard 拦截） |
| 表不在 ACCOUNT_ID_TABLES 中 | 不注入（如 customer、creative 等不直接关联 account 的表） |
| 管理员 | 跳过所有改写，全量访问 |
| 用户无任何账户 | 中间件层提示 LLM 告知无权限；执行层抛出 ForbiddenError |
| 授权过期 | `expires_at < now` 的记录被过滤，不纳入可访问账户列表 |

### 4.5 设计决策总结

1. **为什么不直接在业务层做过滤？**
   因为数据查询由 LLM 动态生成 SQL，不是预定义的 ORM 查询，无法在 Service 层硬编码 `filter(account_id=...)`。必须在 SQL 执行前做 AST 改写。

2. **为什么需要双保险？**
   LLM 是概率模型，不可信。提示层让 LLM 生成更准确的 SQL（性能优），执行层强制保证安全（安全底线）。

3. **为什么用 sqlglot 而不是正则替换？**
   正则无法可靠处理 SQL 的复杂语法（子查询、CTE、JOIN、嵌套括号）。AST 解析是唯一可靠的方式。

4. **为什么 ad_account.id 而其他表用 account_id？**
   `ad_account` 表本身的主键就是 `id`，过滤"可访问的账户"就是 `WHERE id IN (...)`。其他业务表通过外键 `account_id` 关联到 `ad_account.id`。

5. **为什么 admin 不走数据权限？**
   管理员需要看全量数据做跨账户分析、全局监控。但管理接口仍需角色鉴权（第二层），不是完全无限制。