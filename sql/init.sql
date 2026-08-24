CREATE TABLE `agentx_skill` (
  `id` bigint NOT NULL,
  `name` varchar(500) NOT NULL,
  `skill_path` varchar(3000) DEFAULT NULL,
  `description` varchar(3000) DEFAULT '',
  `enabled` tinyint NOT NULL DEFAULT 1,
  `file_name` varchar(255) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uk_agentx_skill_name`(`name`)
);