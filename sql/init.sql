# CREATE TABLE `agentx_skill` (
#   `id` bigint NOT NULL AUTO_INCREMENT,
#   `name` varchar(500) NOT NULL,
#   `skill_path` varchar(3000) DEFAULT NULL,
#   `description` varchar(3000) DEFAULT '',
#   `enabled` tinyint NOT NULL DEFAULT 1,
#   `file_name` varchar(255) DEFAULT NULL,
#   `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
#   `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
#   PRIMARY KEY (`id`),
#   UNIQUE INDEX `uk_agentx_skill_name`(`name`)
# );


CREATE TABLE app_user (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE COMMENT '登录账号',
    password_hash VARCHAR(255) NOT NULL COMMENT '仅存 Argon2/bcrypt 哈希，绝不存明文密码',
    real_name VARCHAR(64) NOT NULL,
    mobile VARCHAR(32) NULL,
    email VARCHAR(128) NULL,
    avatar_url VARCHAR(500) NULL,
    job_title VARCHAR(64) NULL COMMENT '如投放优化师、运营负责人',
    role VARCHAR(64) NULL COMMENT 'admin/user',
    status ENUM('ACTIVE', 'DISABLED') NOT NULL DEFAULT 'ACTIVE',
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='营销分析系统的登录用户，不是广告触达用户';

CREATE TABLE marketing_channel (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    channel_code VARCHAR(64) NOT NULL UNIQUE,
    channel_name VARCHAR(128) NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='广告渠道，如巨量引擎、腾讯广告、Google Ads';

CREATE TABLE ad_account (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    channel_id BIGINT UNSIGNED NOT NULL,
    platform_account_id VARCHAR(128) NOT NULL COMMENT '广告平台侧账户 ID',
    account_name VARCHAR(255) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'CNY',
    status ENUM('ACTIVE', 'PAUSED', 'DISABLED') NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_channel_platform_account (channel_id, platform_account_id),
    KEY idx_account_channel (channel_id),
    CONSTRAINT fk_account_channel
        FOREIGN KEY (channel_id) REFERENCES marketing_channel(id)
) ENGINE=InnoDB COMMENT='广告平台账户，也是数据权限最小单元';

CREATE TABLE user_ad_account (
    app_user_id BIGINT UNSIGNED NOT NULL,
    ad_account_id BIGINT UNSIGNED NOT NULL,
    role ENUM('OWNER', 'ANALYST', 'OPERATOR', 'VIEWER') NOT NULL DEFAULT 'VIEWER',
    granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NULL,
    PRIMARY KEY (app_user_id, ad_account_id),
    KEY idx_user_ad_account_account (ad_account_id),
    CONSTRAINT fk_user_account_user
        FOREIGN KEY (app_user_id) REFERENCES app_user(id),
    CONSTRAINT fk_user_account_account
        FOREIGN KEY (ad_account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='用户可访问的广告账户；一个用户可拥有多个账户';

CREATE TABLE campaign (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    account_id BIGINT UNSIGNED NOT NULL,
    platform_campaign_id VARCHAR(128) NOT NULL,
    campaign_name VARCHAR(255) NOT NULL,
    objective VARCHAR(64) NULL COMMENT '营销目标：TRAFFIC、LEAD、SALES 等',
    optimization_goal VARCHAR(64) NULL COMMENT '优化目标：CLICK、PURCHASE、FORM_SUBMIT 等',
    daily_budget DECIMAL(18,2) NULL,
    status ENUM('ACTIVE', 'PAUSED', 'ENDED', 'DELETED') NOT NULL DEFAULT 'ACTIVE',
    start_date DATE NULL,
    end_date DATE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_campaign_account_platform (account_id, platform_campaign_id),
    KEY idx_campaign_account (account_id),
    CONSTRAINT fk_campaign_account
        FOREIGN KEY (account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='广告计划 Campaign';

CREATE TABLE ad_group (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    campaign_id BIGINT UNSIGNED NOT NULL,
    platform_ad_group_id VARCHAR(128) NOT NULL,
    ad_group_name VARCHAR(255) NOT NULL,
    targeting_type ENUM('AUTO', 'MANUAL', 'AUDIENCE') NULL,
    bid_strategy VARCHAR(64) NULL COMMENT '如 LOWEST_COST、TARGET_CPA',
    bid_amount DECIMAL(18,4) NULL,
    status ENUM('ACTIVE', 'PAUSED', 'ENDED', 'DELETED') NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ad_group_campaign_platform (campaign_id, platform_ad_group_id),
    KEY idx_ad_group_campaign (campaign_id),
    CONSTRAINT fk_ad_group_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaign(id)
) ENGINE=InnoDB COMMENT='广告组，配置定向、出价与人群';

CREATE TABLE audience_package (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    package_id VARCHAR(128) NOT NULL UNIQUE COMMENT '系统人群包编码',
    account_id BIGINT UNSIGNED NOT NULL,
    platform_package_id VARCHAR(128) NULL COMMENT '平台侧人群包ID',
    package_name VARCHAR(255) NOT NULL,
    package_type ENUM(
        'DMP', 'CUSTOM', 'LOOKALIKE', 'INTEREST',
        'RETARGETING', 'EXCLUSION', 'AUTO'
    ) NOT NULL,
    source_platform VARCHAR(64) NULL COMMENT '数坊、京腾魔方、DMP、平台人群中心',
    estimated_size BIGINT UNSIGNED NULL,
    definition_json JSON NULL,
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1有效，0失效',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_audience_account_platform (
        account_id, platform_package_id
    ),
    CONSTRAINT fk_audience_package_account
        FOREIGN KEY (account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='广告定向使用的人群包';

CREATE TABLE ad_group_audience_relation (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ad_group_id BIGINT UNSIGNED NOT NULL,
    package_id VARCHAR(128) NOT NULL,
    usage_type ENUM('INCLUDE', 'EXCLUDE') NOT NULL DEFAULT 'INCLUDE',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1有效，0解绑或失效',
    bound_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_ad_group_package (ad_group_id, package_id),
    KEY idx_relation_package (package_id),

    CONSTRAINT fk_relation_ad_group
        FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
    CONSTRAINT fk_relation_package
        FOREIGN KEY (package_id) REFERENCES audience_package(package_id)
) ENGINE=InnoDB COMMENT='广告单元与定向人群包的绑定关系';

CREATE TABLE creative (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    creative_code VARCHAR(128) NOT NULL UNIQUE,
    creative_name VARCHAR(255) NOT NULL,
    creative_type ENUM('IMAGE', 'VIDEO', 'CAROUSEL', 'TEXT', 'LIVE', 'OTHER') NOT NULL,
    title VARCHAR(500) NULL,
    body_text TEXT NULL,
    material_url TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='创意素材库';

CREATE TABLE ad (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ad_group_id BIGINT UNSIGNED NOT NULL,
    platform_ad_id VARCHAR(128) NOT NULL,
    ad_name VARCHAR(255) NOT NULL,
    landing_page_url TEXT NULL,
    status ENUM('ACTIVE', 'PAUSED', 'ENDED', 'DELETED') NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ad_group_platform_ad (ad_group_id, platform_ad_id),
    KEY idx_ad_group (ad_group_id),
    CONSTRAINT fk_ad_group
        FOREIGN KEY (ad_group_id) REFERENCES ad_group(id)
) ENGINE=InnoDB COMMENT='具体广告对象';

CREATE TABLE ad_creative (
    ad_id BIGINT UNSIGNED NOT NULL,
    creative_id BIGINT UNSIGNED NOT NULL,
    is_primary TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (ad_id, creative_id),
    CONSTRAINT fk_ad_creative_ad
        FOREIGN KEY (ad_id) REFERENCES ad(id),
    CONSTRAINT fk_ad_creative_creative
        FOREIGN KEY (creative_id) REFERENCES creative(id)
) ENGINE=InnoDB COMMENT='广告与素材的多对多关系';

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

    UNIQUE KEY uk_performance_grain (
        stat_date, ad_id, creative_id, audience_id, placement_code,
        region_code, age_group, gender, device_type
    ),
    KEY idx_perf_account_date (account_id, stat_date),
    KEY idx_perf_campaign_date (campaign_id, stat_date),
    KEY idx_perf_group_date (ad_group_id, stat_date),
    KEY idx_perf_ad_date (ad_id, stat_date),

    CONSTRAINT fk_perf_account FOREIGN KEY (account_id) REFERENCES ad_account(id),
    CONSTRAINT fk_perf_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id),
    CONSTRAINT fk_perf_ad_group FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
    CONSTRAINT fk_perf_ad FOREIGN KEY (ad_id) REFERENCES ad(id),
    CONSTRAINT fk_perf_creative FOREIGN KEY (creative_id) REFERENCES creative(id),
    CONSTRAINT fk_perf_audience FOREIGN KEY (audience_id) REFERENCES audience_package(id)
) ENGINE=InnoDB COMMENT='广告平台日报核心事实表';

CREATE TABLE customer (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    anonymous_id CHAR(64) NULL COMMENT '埋点生成的匿名访客标识或哈希标识',
    crm_customer_id VARCHAR(128) NULL COMMENT 'CRM 客户 ID',
    first_seen_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_customer_anonymous_id (anonymous_id),
    UNIQUE KEY uk_customer_crm_id (crm_customer_id)
) ENGINE=InnoDB COMMENT='实际到达企业站点的匿名访客或客户';

CREATE TABLE ad_touchpoint (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NULL,
    occurred_at DATETIME NOT NULL,
    touch_type ENUM('IMPRESSION', 'CLICK', 'VIEW') NOT NULL,
    account_id BIGINT UNSIGNED NULL,
    campaign_id BIGINT UNSIGNED NULL,
    ad_group_id BIGINT UNSIGNED NULL,
    ad_id BIGINT UNSIGNED NULL,
    creative_id BIGINT UNSIGNED NULL,
    platform_click_id VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    KEY idx_touch_customer_time (customer_id, occurred_at),
    KEY idx_touch_ad_time (ad_id, occurred_at),

    CONSTRAINT fk_touch_customer FOREIGN KEY (customer_id) REFERENCES customer(id),
    CONSTRAINT fk_touch_account FOREIGN KEY (account_id) REFERENCES ad_account(id),
    CONSTRAINT fk_touch_campaign FOREIGN KEY (campaign_id) REFERENCES campaign(id),
    CONSTRAINT fk_touch_ad_group FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
    CONSTRAINT fk_touch_ad FOREIGN KEY (ad_id) REFERENCES ad(id),
    CONSTRAINT fk_touch_creative FOREIGN KEY (creative_id) REFERENCES creative(id)
) ENGINE=InnoDB COMMENT='企业埋点收到的广告曝光、点击或浏览触点';

CREATE TABLE conversion_event (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NULL,
    event_id VARCHAR(128) NOT NULL UNIQUE,
    event_type ENUM('LEAD', 'REGISTER', 'ADD_TO_CART', 'PURCHASE', 'OTHER') NOT NULL,
    occurred_at DATETIME NOT NULL,
    event_value DECIMAL(18,2) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NULL,
    source_system VARCHAR(64) NOT NULL COMMENT 'WEB、APP、CRM、OMS',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    KEY idx_conversion_customer_time (customer_id, occurred_at),
    KEY idx_conversion_type_time (event_type, occurred_at),

    CONSTRAINT fk_conversion_customer
        FOREIGN KEY (customer_id) REFERENCES customer(id)
) ENGINE=InnoDB COMMENT='企业确认的原始转化事件';

CREATE TABLE attribution_result (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    conversion_event_id BIGINT UNSIGNED NOT NULL,
    touchpoint_id BIGINT UNSIGNED NOT NULL,
    attribution_model ENUM(
        'LAST_CLICK', 'LAST_NON_DIRECT_CLICK',
        'FIRST_CLICK', 'LINEAR', 'PLATFORM_REPORTED'
    ) NOT NULL,
    click_window_days SMALLINT UNSIGNED NOT NULL DEFAULT 7,
    view_window_days SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    credit DECIMAL(9,6) NOT NULL,
    attributed_value DECIMAL(18,2) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_attribution (
        conversion_event_id, touchpoint_id, attribution_model
    ),

    CONSTRAINT fk_attribution_conversion
        FOREIGN KEY (conversion_event_id) REFERENCES conversion_event(id),
    CONSTRAINT fk_attribution_touchpoint
        FOREIGN KEY (touchpoint_id) REFERENCES ad_touchpoint(id)
) ENGINE=InnoDB COMMENT='转化事件与广告触点之间的归因结果';

CREATE TABLE sales_order (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT UNSIGNED NULL,
    conversion_event_id BIGINT UNSIGNED NULL,
    order_no VARCHAR(128) NOT NULL UNIQUE,
    order_status ENUM(
        'PENDING', 'PAID', 'CANCELLED',
        'REFUNDED', 'PARTIALLY_REFUNDED'
    ) NOT NULL,
    paid_at DATETIME NULL,
    gross_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
    refund_amount DECIMAL(18,2) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    KEY idx_order_paid_at (paid_at),

    CONSTRAINT fk_order_customer
        FOREIGN KEY (customer_id) REFERENCES customer(id),
    CONSTRAINT fk_order_conversion
        FOREIGN KEY (conversion_event_id) REFERENCES conversion_event(id)
) ENGINE=InnoDB COMMENT='企业订单事实；净收入=支付金额-退款金额';



CREATE TABLE promotion_target (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    account_id BIGINT UNSIGNED NOT NULL,
    target_type ENUM('SKU', 'SPU', 'SHOP', 'LIVE_ROOM', 'LANDING_PAGE') NOT NULL,
    platform_target_id VARCHAR(128) NOT NULL,
    target_name VARCHAR(255) NOT NULL,
    target_price DECIMAL(18,2) NULL,
    status TINYINT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_target_platform (
        account_id, target_type, platform_target_id
    ),
    CONSTRAINT fk_target_account
        FOREIGN KEY (account_id) REFERENCES ad_account(id)
) ENGINE=InnoDB COMMENT='广告实际推广对象，如京东SKU、快手直播间、落地页';

CREATE TABLE ad_group_target_relation (
    ad_group_id BIGINT UNSIGNED NOT NULL,
    promotion_target_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (ad_group_id, promotion_target_id),

    CONSTRAINT fk_group_target_group
        FOREIGN KEY (ad_group_id) REFERENCES ad_group(id),
    CONSTRAINT fk_group_target_target
        FOREIGN KEY (promotion_target_id) REFERENCES promotion_target(id)
) ENGINE=InnoDB COMMENT='广告单元绑定的商品、店铺或直播间';


CREATE TABLE ad_group_keyword (
    id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    ad_group_id BIGINT UNSIGNED NOT NULL,
    keyword_text VARCHAR(255) NOT NULL,
    match_type ENUM('EXACT', 'PHRASE', 'BROAD') NOT NULL,
    bid_amount DECIMAL(18,4) NULL,
    status TINYINT NOT NULL DEFAULT 1,

    UNIQUE KEY uk_group_keyword (ad_group_id, keyword_text),
    CONSTRAINT fk_keyword_group
        FOREIGN KEY (ad_group_id) REFERENCES ad_group(id)
) ENGINE=InnoDB COMMENT='京东搜索快车等搜索广告的关键词定向';



