# 营销 Text2SQL：真实数据模型、业务术语与权限设计

## 1. 设计结论

采用 MySQL 8.0，使用两条可关联但不能混为一谈的数据链路：

```text
广告平台报表链路（平台口径）
Channel -> Ad Account -> Campaign -> Ad Group -> Ad -> Creative
                                         -> Audience
                         -> ad_performance_daily
                         -> platform_conversions / platform_conversion_value

企业一方数据链路（可审计业务事实）
Ad touchpoint -> Customer -> Conversion event -> Attribution result -> Sales order -> Revenue
```

企业主流做法是保留两套事实：平台日报回答“投放平台报告了什么”；企业事件与订单回答“客户实际上做了什么”。两者可以按广告、日期、归因规则对账，但不能直接把平台 `conversions` 当作真实订单数。

平台通常不会提供可识别的用户或逐笔订单。因而若当前只接广告平台数据，`customer`、`ad_touchpoint`、`conversion_event`、`sales_order` 可以暂不接数；但表结构应先准备好。此时 Text2SQL 可以分析平台归因收入和 ROAS，不能回答“某个真实客户买了什么”。

## 2. 真实对象关系

```text
marketing_channel 1--N ad_account 1--N campaign 1--N ad_group 1--N ad
                                                    |                 |
                                                    N                 N
                                                audience          ad_creative N--1 creative

ad / campaign / ad_group / account
     \             |             /
              ad_performance_daily

ad_touchpoint N--1 customer
conversion_event N--1 customer
attribution_result N--1 conversion_event, N--1 ad_touchpoint
sales_order N--1 customer, N--1 conversion_event (optional)
```

`Audience` 是投放时定义或引用的人群包；`Customer` 是企业能够识别或伪匿名化的实际访客/客户，两者不是同一个对象。一个 Audience 有许多 Customer；一个 Customer 也可能属于多个 Audience。

## 3. MySQL 8.0 建表 SQL

执行顺序已处理外键依赖。所有金额使用账户币种或订单币种；跨币种汇总必须先换算到报表币种，第一版应限制在同一币种内查询。

```sql
CREATE TABLE tenant (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_code VARCHAR(64) NOT NULL UNIQUE,
  tenant_name VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='数据隔离边界；一个企业或品牌主体一个租户';

CREATE TABLE app_user (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  user_code VARCHAR(64) NOT NULL,
  user_name VARCHAR(128) NOT NULL,
  user_status ENUM('ACTIVE','DISABLED') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_tenant_code (tenant_id, user_code),
  CONSTRAINT fk_app_user_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id)
) ENGINE=InnoDB COMMENT='登录用户；不存放营销客户信息';

CREATE TABLE marketing_channel (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  channel_code VARCHAR(64) NOT NULL UNIQUE,
  channel_name VARCHAR(128) NOT NULL,
  status ENUM('ACTIVE','INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='广告渠道，如巨量引擎、腾讯广告、Google Ads';

CREATE TABLE ad_account (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  channel_id BIGINT UNSIGNED NOT NULL,
  platform_account_id VARCHAR(128) NOT NULL,
  account_name VARCHAR(255) NOT NULL,
  currency_code CHAR(3) NOT NULL DEFAULT 'CNY',
  status ENUM('ACTIVE','PAUSED','DISABLED') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_account_channel_platform (channel_id, platform_account_id),
  KEY idx_account_tenant (tenant_id),
  CONSTRAINT fk_account_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id),
  CONSTRAINT fk_account_channel FOREIGN KEY (channel_id) REFERENCES marketing_channel(id)
) ENGINE=InnoDB COMMENT='平台广告账户，也是第一版最小数据权限单元';

CREATE TABLE user_ad_account_scope (
  app_user_id BIGINT UNSIGNED NOT NULL,
  ad_account_id BIGINT UNSIGNED NOT NULL,
  permission_level ENUM('READ','ANALYZE','MANAGE') NOT NULL DEFAULT 'READ',
  granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NULL,
  PRIMARY KEY (app_user_id, ad_account_id),
  KEY idx_scope_account (ad_account_id),
  CONSTRAINT fk_scope_user FOREIGN KEY (app_user_id) REFERENCES app_user(id),
  CONSTRAINT fk_scope_account FOREIGN KEY (ad_account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='用户可访问的广告账户集合；一个用户可拥有多个账户';

CREATE TABLE campaign (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  account_id BIGINT UNSIGNED NOT NULL,
  platform_campaign_id VARCHAR(128) NOT NULL,
  campaign_name VARCHAR(255) NOT NULL,
  objective VARCHAR(64) NULL COMMENT '营销目标，如 TRAFFIC、LEAD、SALES',
  optimization_goal VARCHAR(64) NULL COMMENT '优化目标，如 CLICK、FORM_SUBMIT、PURCHASE',
  daily_budget DECIMAL(18,2) NULL,
  status ENUM('ACTIVE','PAUSED','ENDED','DELETED') NOT NULL DEFAULT 'ACTIVE',
  start_date DATE NULL, end_date DATE NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_campaign_account_platform (account_id, platform_campaign_id),
  KEY idx_campaign_account (account_id),
  CONSTRAINT fk_campaign_account FOREIGN KEY (account_id) REFERENCES ad_account(id),
  CONSTRAINT ck_campaign_budget CHECK (daily_budget IS NULL OR daily_budget >= 0)
) ENGINE=InnoDB COMMENT='广告计划';

CREATE TABLE ad_group (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  campaign_id BIGINT UNSIGNED NOT NULL,
  platform_ad_group_id VARCHAR(128) NOT NULL,
  ad_group_name VARCHAR(255) NOT NULL,
  targeting_type ENUM('AUTO','MANUAL','AUDIENCE') NULL,
  bid_strategy VARCHAR(64) NULL,
  bid_amount DECIMAL(18,4) NULL,
  status ENUM('ACTIVE','PAUSED','ENDED','DELETED') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_adgroup_campaign_platform (campaign_id, platform_ad_group_id),
  KEY idx_adgroup_campaign (campaign_id),
  CONSTRAINT fk_adgroup_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id)
) ENGINE=InnoDB COMMENT='广告组；承载定向、出价和人群策略';

CREATE TABLE audience (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  account_id BIGINT UNSIGNED NOT NULL,
  platform_audience_id VARCHAR(128) NULL,
  audience_name VARCHAR(255) NOT NULL,
  audience_type ENUM('CUSTOM','LOOKALIKE','INTEREST','RETARGETING','EXCLUSION','AUTO') NOT NULL,
  definition_json JSON NULL COMMENT '平台定向规则快照，不供 LLM 直接拼 SQL',
  estimated_size BIGINT UNSIGNED NULL,
  status ENUM('ACTIVE','ARCHIVED','DELETED') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_audience_account_platform (account_id, platform_audience_id),
  KEY idx_audience_account (account_id),
  CONSTRAINT fk_audience_account FOREIGN KEY (account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='广告账户内的人群包或定向对象';

CREATE TABLE ad_group_audience (
  ad_group_id BIGINT UNSIGNED NOT NULL,
  audience_id BIGINT UNSIGNED NOT NULL,
  usage_type ENUM('INCLUDE','EXCLUDE') NOT NULL DEFAULT 'INCLUDE',
  PRIMARY KEY (ad_group_id, audience_id),
  CONSTRAINT fk_aga_group FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
  CONSTRAINT fk_aga_audience FOREIGN KEY (audience_id) REFERENCES audience(id)
) ENGINE=InnoDB COMMENT='广告组与人群包的多对多投放关系';

CREATE TABLE creative (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  creative_code VARCHAR(128) NOT NULL,
  creative_name VARCHAR(255) NOT NULL,
  creative_type ENUM('IMAGE','VIDEO','CAROUSEL','TEXT','LIVE','OTHER') NOT NULL,
  title VARCHAR(500) NULL,
  body_text TEXT NULL,
  material_uri TEXT NULL COMMENT '普通分析结果不可返回',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_creative_tenant_code (tenant_id, creative_code),
  KEY idx_creative_tenant_type (tenant_id, creative_type),
  CONSTRAINT fk_creative_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id)
) ENGINE=InnoDB COMMENT='可被一个或多个广告复用的创意资产';

CREATE TABLE ad (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  ad_group_id BIGINT UNSIGNED NOT NULL,
  platform_ad_id VARCHAR(128) NOT NULL,
  ad_name VARCHAR(255) NOT NULL,
  landing_page_url TEXT NULL,
  status ENUM('ACTIVE','PAUSED','ENDED','DELETED') NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_ad_group_platform (ad_group_id, platform_ad_id),
  KEY idx_ad_group (ad_group_id),
  CONSTRAINT fk_ad_group FOREIGN KEY (ad_group_id) REFERENCES ad_group(id)
) ENGINE=InnoDB COMMENT='平台中的具体广告对象';

CREATE TABLE ad_creative (
  ad_id BIGINT UNSIGNED NOT NULL,
  creative_id BIGINT UNSIGNED NOT NULL,
  is_primary TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (ad_id, creative_id),
  KEY idx_adcreative_creative (creative_id),
  CONSTRAINT fk_adcreative_ad FOREIGN KEY (ad_id) REFERENCES ad(id),
  CONSTRAINT fk_adcreative_creative FOREIGN KEY (creative_id) REFERENCES creative(id)
) ENGINE=InnoDB COMMENT='广告和素材的多对多关系，避免 ad.creative_id 的历史错配';

CREATE TABLE ad_performance_daily (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  stat_date DATE NOT NULL,
  account_id BIGINT UNSIGNED NOT NULL,
  campaign_id BIGINT UNSIGNED NOT NULL,
  ad_group_id BIGINT UNSIGNED NOT NULL,
  ad_id BIGINT UNSIGNED NOT NULL,
  creative_id BIGINT UNSIGNED NULL,
  audience_id BIGINT UNSIGNED NULL,
  placement_code VARCHAR(64) NOT NULL DEFAULT '',
  region_code VARCHAR(64) NOT NULL DEFAULT '',
  age_group VARCHAR(32) NOT NULL DEFAULT '',
  gender VARCHAR(16) NOT NULL DEFAULT '',
  device_type VARCHAR(32) NOT NULL DEFAULT '',
  cost DECIMAL(18,2) NOT NULL DEFAULT 0,
  impressions BIGINT UNSIGNED NOT NULL DEFAULT 0,
  clicks BIGINT UNSIGNED NOT NULL DEFAULT 0,
  platform_conversions DECIMAL(18,4) NOT NULL DEFAULT 0,
  platform_conversion_value DECIMAL(18,2) NOT NULL DEFAULT 0,
  currency_code CHAR(3) NOT NULL,
  source_updated_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_perf_grain (stat_date, ad_id, creative_id, audience_id, placement_code, region_code, age_group, gender, device_type),
  KEY idx_perf_account_date (account_id, stat_date),
  KEY idx_perf_campaign_date (campaign_id, stat_date),
  KEY idx_perf_group_date (ad_group_id, stat_date),
  KEY idx_perf_ad_date (ad_id, stat_date),
  KEY idx_perf_creative_date (creative_id, stat_date),
  CONSTRAINT fk_perf_account FOREIGN KEY (account_id) REFERENCES ad_account(id),
  CONSTRAINT fk_perf_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id),
  CONSTRAINT fk_perf_adgroup FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
  CONSTRAINT fk_perf_ad FOREIGN KEY (ad_id) REFERENCES ad(id),
  CONSTRAINT fk_perf_creative FOREIGN KEY (creative_id) REFERENCES creative(id),
  CONSTRAINT fk_perf_audience FOREIGN KEY (audience_id) REFERENCES audience(id),
  CONSTRAINT ck_perf_values CHECK (cost >= 0 AND impressions >= 0 AND clicks >= 0 AND platform_conversions >= 0 AND platform_conversion_value >= 0)
) ENGINE=InnoDB COMMENT='广告平台每日表现；固定粒度为日期、广告及各拆分维度';

CREATE TABLE customer (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  anonymous_id CHAR(64) NULL COMMENT 'Cookie/设备等哈希标识；不保存原始标识',
  customer_ref VARCHAR(128) NULL COMMENT '企业 CRM 主键，不对普通分析用户返回',
  first_seen_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_customer_tenant_anon (tenant_id, anonymous_id),
  KEY idx_customer_tenant (tenant_id),
  CONSTRAINT fk_customer_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id)
) ENGINE=InnoDB COMMENT='企业一方客户或匿名访客；平台数据通常无法填充本表';

CREATE TABLE ad_touchpoint (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  customer_id BIGINT UNSIGNED NULL,
  occurred_at DATETIME NOT NULL,
  touch_type ENUM('IMPRESSION','CLICK','VIEW') NOT NULL,
  account_id BIGINT UNSIGNED NULL, campaign_id BIGINT UNSIGNED NULL,
  ad_group_id BIGINT UNSIGNED NULL, ad_id BIGINT UNSIGNED NULL, creative_id BIGINT UNSIGNED NULL,
  platform_click_id VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_touch_customer_time (customer_id, occurred_at),
  KEY idx_touch_ad_time (ad_id, occurred_at),
  CONSTRAINT fk_touch_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id),
  CONSTRAINT fk_touch_customer FOREIGN KEY (customer_id) REFERENCES customer(id),
  CONSTRAINT fk_touch_account FOREIGN KEY (account_id) REFERENCES ad_account(id),
  CONSTRAINT fk_touch_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id),
  CONSTRAINT fk_touch_group FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
  CONSTRAINT fk_touch_ad FOREIGN KEY (ad_id) REFERENCES ad(id),
  CONSTRAINT fk_touch_creative FOREIGN KEY (creative_id) REFERENCES creative(id)
) ENGINE=InnoDB COMMENT='一方埋点接收的广告曝光/点击触点，数据量大时应按月分区';

CREATE TABLE conversion_event (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  customer_id BIGINT UNSIGNED NULL,
  event_id VARCHAR(128) NOT NULL,
  event_type ENUM('LEAD','REGISTER','ADD_TO_CART','PURCHASE','OTHER') NOT NULL,
  occurred_at DATETIME NOT NULL,
  event_value DECIMAL(18,2) NOT NULL DEFAULT 0,
  currency_code CHAR(3) NULL,
  source_system VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_conversion_tenant_event (tenant_id, event_id),
  KEY idx_conversion_customer_time (customer_id, occurred_at),
  KEY idx_conversion_type_time (event_type, occurred_at),
  CONSTRAINT fk_conversion_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id),
  CONSTRAINT fk_conversion_customer FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB COMMENT='企业确认的原始转化事件，不等于平台归因转化';

CREATE TABLE attribution_result (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  conversion_event_id BIGINT UNSIGNED NOT NULL,
  touchpoint_id BIGINT UNSIGNED NOT NULL,
  attribution_model ENUM('LAST_CLICK','LAST_NON_DIRECT_CLICK','FIRST_CLICK','LINEAR','PLATFORM_REPORTED') NOT NULL,
  click_window_days SMALLINT UNSIGNED NOT NULL,
  view_window_days SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  credit DECIMAL(9,6) NOT NULL COMMENT '同一 conversion + model 下 credit 总和必须为 1，由服务层校验',
  attributed_value DECIMAL(18,2) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_attribution (conversion_event_id, touchpoint_id, attribution_model),
  KEY idx_attr_touch (touchpoint_id),
  CONSTRAINT fk_attr_conversion FOREIGN KEY (conversion_event_id) REFERENCES conversion_event(id),
  CONSTRAINT fk_attr_touch FOREIGN KEY (touchpoint_id) REFERENCES ad_touchpoint(id),
  CONSTRAINT ck_attr_credit CHECK (credit > 0 AND credit <= 1)
) ENGINE=InnoDB COMMENT='归因结果快照；默认分析模型应在请求中明确';

CREATE TABLE sales_order (
  id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT UNSIGNED NOT NULL,
  customer_id BIGINT UNSIGNED NULL,
  conversion_event_id BIGINT UNSIGNED NULL,
  order_no VARCHAR(128) NOT NULL,
  order_status ENUM('PENDING','PAID','CANCELLED','REFUNDED','PARTIALLY_REFUNDED') NOT NULL,
  paid_at DATETIME NULL,
  gross_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  refund_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
  currency_code CHAR(3) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_order_tenant_no (tenant_id, order_no),
  KEY idx_order_paid_at (paid_at),
  KEY idx_order_conversion (conversion_event_id),
  CONSTRAINT fk_order_tenant FOREIGN KEY (tenant_id) REFERENCES tenant(id),
  CONSTRAINT fk_order_customer FOREIGN KEY (customer_id) REFERENCES customer(id),
  CONSTRAINT fk_order_conversion FOREIGN KEY (conversion_event_id) REFERENCES conversion_event(id),
  CONSTRAINT ck_order_amount CHECK (gross_amount >= 0 AND refund_amount >= 0 AND refund_amount <= gross_amount)
) ENGINE=InnoDB COMMENT='企业订单事实；净收入 = gross_amount - refund_amount';
```

### 粒度与落地规则

- `ad_performance_daily` 是主分析表。一行是 `统计日期 + ad + 素材 + 人群 + 版位 + 地域 + 年龄 + 性别 + 设备` 的平台汇总值；缺失维度统一写空字符串，避免 MySQL 的 `NULL` 使唯一约束失效。
- 平台未返回某个拆分维度时，采集任务不得伪造其值。
- 报表表有 account/campaign/ad_group 冗余外键以加速分析，但 ETL 必须校验其层级关系与 `ad` 当前归属一致。
- `ad_touchpoint` 是高基数流水，不应让任意 Text2SQL 全表扫描；要求时间范围、账户范围和 `LIMIT`，生产上按月分区或进入 OLAP 引擎。
- 默认归因模型建议为 **last non-direct click，点击窗口 7 天、曝光窗口 1 天**。这是常见可解释的企业自归因默认值；平台口径须单独标为 `PLATFORM_REPORTED`，不可与它混合求和。

## 4. 业务术语（business-glossary.yaml）

以下内容可直接存为 Skill 知识。`sqlFragment` 以主事实表别名 `p` 为基准；需要订单事实时会明确给出表别名。

```yaml
- term: 消耗
  description: 广告平台报告的实际花费。跨日期和层级汇总时只能累加原始 cost。
  sqlFragment: "SUM(p.cost) AS total_cost"
  synonyms: [花费, 广告费, 广告消耗, spend, cost]
- term: 曝光量
  description: 广告成功展示的次数，使用广告平台日报口径。
  sqlFragment: "SUM(p.impressions) AS total_impressions"
  synonyms: [曝光, 展现量, 展示量, impressions, impression]
- term: 点击量
  description: 广告被点击的次数，跨维度汇总时使用 SUM(clicks)。
  sqlFragment: "SUM(p.clicks) AS total_clicks"
  synonyms: [点击数, clicks, 点击次数, click]
- term: 平台归因转化
  description: 广告平台按其归因设置报告的转化数量，可能与企业订单数不同。
  sqlFragment: "SUM(p.platform_conversions) AS platform_conversions"
  synonyms: [转化, 转化量, conversions, 平台转化]
- term: 平台归因收入
  description: 广告平台报告的归因转化价值；仅可与同币种的消耗计算平台 ROAS。
  sqlFragment: "SUM(p.platform_conversion_value) AS platform_conversion_value"
  synonyms: [归因收入, 平台收入, conversion value]
- term: 点击率
  description: 汇总点击量除以汇总曝光量，绝不能平均各天或各广告的 CTR。
  sqlFragment: "SUM(p.clicks) / NULLIF(SUM(p.impressions), 0) AS ctr"
  synonyms: [CTR, 点击率]
- term: 点击成本
  description: 汇总消耗除以汇总点击量。
  sqlFragment: "SUM(p.cost) / NULLIF(SUM(p.clicks), 0) AS cpc"
  synonyms: [CPC, 单次点击成本]
- term: 千次曝光成本
  description: 每 1000 次曝光的平均消耗。
  sqlFragment: "SUM(p.cost) * 1000 / NULLIF(SUM(p.impressions), 0) AS cpm"
  synonyms: [CPM, 千次展示成本]
- term: 平台转化率
  description: 平台归因转化除以点击量；这是点击到平台转化的比率。
  sqlFragment: "SUM(p.platform_conversions) / NULLIF(SUM(p.clicks), 0) AS platform_cvr"
  synonyms: [CVR, 转化率, 点击转化率]
- term: 平台转化成本
  description: 汇总消耗除以汇总平台归因转化。
  sqlFragment: "SUM(p.cost) / NULLIF(SUM(p.platform_conversions), 0) AS platform_cpa"
  synonyms: [CPA, 转化成本, 单次转化成本]
- term: 平台ROAS
  description: 平台归因收入除以平台消耗；查询必须限制为同一币种或先进行汇率换算。
  sqlFragment: "SUM(p.platform_conversion_value) / NULLIF(SUM(p.cost), 0) AS platform_roas"
  synonyms: [ROAS, 投产比, 广告回报]
- term: 净收入
  description: 企业已支付订单的实收金额扣除退款，不是广告平台回传收入。
  sqlFragment: "SUM(CASE WHEN o.order_status IN ('PAID','PARTIALLY_REFUNDED') THEN o.gross_amount - o.refund_amount ELSE 0 END) AS net_revenue"
  synonyms: [收入, 实收, 净营收, net revenue]
- term: 营销目标
  description: Campaign 希望实现的业务目标；与优化目标不同。
  sqlFragment: "c.objective"
  synonyms: [投放目标, campaign目标, objective]
- term: 优化目标
  description: 平台实际优化的事件，例如点击、表单提交或购买。
  sqlFragment: "c.optimization_goal"
  synonyms: [投放优化目标, optimization goal]
- term: 定向
  description: 广告组用于选择或排除受众的规则；结构化细节保存在 audience.definition_json。
  sqlFragment: "ag.targeting_type"
  synonyms: [人群定向, 广告定向, targeting]
- term: 人群包
  description: 账户定义、平台扩展或再营销使用的人群集合；不能等同于实际客户。
  sqlFragment: "a.audience_name"
  synonyms: [audience, audience segment, 用户群]
- term: 素材
  description: 广告展示的图片、视频、文案等创意资产；一个广告可关联多个素材。
  sqlFragment: "cr.creative_name"
  synonyms: [创意, 广告素材, creative]
- term: 起量
  description: 达到业务约定的最小消耗、曝光或点击门槛的状态，不是 status=ACTIVE。必须在 Skill 配置具体阈值后才能生成过滤条件。
  sqlFragment: null
  synonyms: [开始放量, 起投]
- term: 跑量
  description: 在连续时间段取得较大投放规模，强调规模而非 CPA 表现。必须配置规模阈值和连续天数。
  sqlFragment: null
  synonyms: [放量, 大量投放]
- term: 归因窗口
  description: 转化事件可归属于此前广告触点的时间范围。企业默认点击7天、曝光1天；平台口径以平台配置为准。
  sqlFragment: "ar.click_window_days, ar.view_window_days"
  synonyms: [attribution window, attribution period]
```

### 必须写入 SQL 规则的约束

1. 所有比率先 `SUM` 分子和分母，再除法；不得 `AVG(ctr/cpc/cpa/roas)`。
2. “成本”单独出现时必须追问是 CPC、CPA、CPM 还是总消耗。
3. “转化”应优先澄清是平台归因转化还是企业确认转化；默认回答必须标注所用口径。
4. “收入/订单”默认为企业订单事实；用户明确说“平台报表”时才使用 `platform_conversion_value`。
5. 不同 `currency_code` 不能相加、相除；未提供汇率表时要求限定币种。
6. “最近 7 天”定义为含今天的自然日：`p.stat_date BETWEEN CURDATE() - INTERVAL 6 DAY AND CURDATE()`。若业务使用完整自然日，应改为昨天结束并在报告标注。
7. 素材维度查询通过 `ad_creative` 或日报中的 `creative_id`；不得假设每条广告只有一个素材。

## 5. 数据权限：以广告账户为最小授权单元

这是当前最简单且符合主流营销数据平台的第一版 ABAC 实现。组织、区域、项目权限可在后续作为附加条件，不能取代租户和账户边界。

```text
登录会话: { app_user_id: 42, tenant_id: 8 }
           |
           v
user_ad_account_scope: [101, 105, 106]
           |
           v
SQL 改写: 所有投放事实必须满足 p.account_id IN (101,105,106)
           且 ad_account.tenant_id = 8
```

一个用户可以拥有多个账户，这是常态：投放主管往往管理品牌的抖音、腾讯和 Google 账户；代理商人员可能同时被授予多个客户账户。未拥有任何授权账户时返回空集，不能回退为全租户数据。

### Harness 的强制执行方式

LLM 不能收到账号白名单，也不能自行决定权限。Harness 从登录态读取 `app_user_id` 和 `tenant_id`，查询 `user_ad_account_scope` 后，用 SQL AST 改写，而不是字符串拼接：

```sql
-- LLM 生成（不得直接执行）
SELECT ch.channel_name, SUM(p.cost) / NULLIF(SUM(p.platform_conversions), 0) AS cpa
FROM ad_performance_daily p
JOIN ad_account aa ON aa.id = p.account_id
JOIN marketing_channel ch ON ch.id = aa.channel_id
WHERE p.stat_date BETWEEN CURDATE() - INTERVAL 6 DAY AND CURDATE()
GROUP BY ch.channel_name;

-- Harness 注入后（才可执行）
... WHERE p.stat_date BETWEEN CURDATE() - INTERVAL 6 DAY AND CURDATE()
      AND aa.tenant_id = :session_tenant_id
      AND p.account_id IN (:authorized_account_ids)
```

对 `campaign`、`ad_group`、`ad`、`creative`、`audience`、`ad_touchpoint` 及订单查询也必须追溯到 `ad_account.tenant_id` 和授权账户。无法追溯的 `customer` 与 `sales_order` 查询，第一版应禁止直接面向 Text2SQL 开放，直到增加订单/客户的账户归属或可验证的归因连接。

SQL 网关还必须：只允许单条 `SELECT` / 已批准的只读视图；拒绝 DDL/DML、跨租户 JOIN、未限定时间的大表扫描；将 `material_uri`、`customer_ref`、`anonymous_id` 列入禁止返回列。即使当前“不处理敏感信息”，也不应把这些列给 LLM 或通用分析结果。

## 6. 具体应用场景、用户与价值

| 使用人 | 提问示例 | Text2SQL 使用的数据 | 输出与作用 |
|---|---|---|---|
| 投放优化师 | “最近7天，哪个 Campaign 的平台 CPA 高且消耗超过 5000 元？” | `ad_performance_daily + campaign` | 找到优先降价、暂停或换素材的计划；避免只看高 CPA 但样本极小的误判。 |
| 创意策略师 | “视频和图片素材中，哪个类型的 CTR、CPA 更好？” | `ad_performance_daily + creative` | 指导下一批素材生产。先看 CTR 判断吸引力，再看 CPA 判断业务结果，避免只追求高点击。 |
| 渠道负责人 | “本月各渠道消耗、平台归因收入和 ROAS 排名。” | `ad_performance_daily + ad_account + marketing_channel` | 分配渠道预算，识别低回报渠道；系统强制同币种，避免跨币种得到错误投产比。 |
| 人群运营 | “再营销人群与相似人群的 CPA 和 CVR 对比。” | `ad_performance_daily + audience + ad_group_audience` | 判断应扩展相似人群还是加大再营销；人群包仅解释投放对象，不把它误认为真实客户列表。 |
| 增长负责人 | “哪个优化目标的计划带来的企业确认购买最多？” | `conversion_event + attribution_result + ad_touchpoint + campaign` | 校验平台优化目标与真实购买之间是否一致，调整 Campaign 的优化目标。此场景需要企业一方事件数据。 |
| 电商运营/财务 | “上月投放带来的已支付净收入、退款和真实 ROAS。” | `sales_order + conversion_event + attribution_result + ad_touchpoint` | 用可审计订单衡量业务收益，避免用平台估算转化价值代替财务收入。 |
| 账户管理员 | “我能看哪些账户的投放数据？” | `user_ad_account_scope + ad_account` | 清楚展示授权范围；多账户授权降低跨品牌误查和手工权限维护成本。 |

最终价值不在于“让模型写出一条 SQL”，而在于让不同角色使用同一套可追溯口径：投放人员优化效率，负责人分配预算，业务侧验证真实收入，同时通过账户级权限确保每个人只能看到被授予的投放资产。

## 7. 建议的 Agent 执行链路

```text
用户问题
 -> 识别对象、时间、指标、维度、排序
 -> 查 glossary 与 schema
 -> 若“成本/转化/收入”口径含糊则追问
 -> 生成只读 SQL
 -> AST 安全校验
 -> 从当前登录态取得账户授权并注入 tenant/account 条件
 -> 执行
 -> 校验空数据、零分母、币种、异常数量级与指标口径
 -> 返回数据、口径、时间范围和结论
```

第一版应优先上线平台日报链路和账户权限。等企业埋点、订单、退款数据稳定后，再开放真实用户和订单归因分析；这样可避免系统在数据不完整时对“收入”和“转化”给出看似精确但实际错误的答案。
