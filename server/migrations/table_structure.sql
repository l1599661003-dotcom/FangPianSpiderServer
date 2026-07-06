-- 爬虫任务表
CREATE TABLE IF NOT EXISTS `fp_spider_task` (
  `id` varchar(36) NOT NULL COMMENT '任务ID',
  `task_name` varchar(100) NOT NULL COMMENT '任务名称',
  `task_desc` varchar(255) DEFAULT NULL COMMENT '任务描述',
  `task_type` tinyint(4) NOT NULL DEFAULT '0' COMMENT '任务类型：0博主信息，1博主详情',
  `status` tinyint(4) NOT NULL DEFAULT '0' COMMENT '任务状态：0停止，1运行中，2完成，3错误',
  `platform_id` int(11) DEFAULT '0' COMMENT '平台ID',
  `target_site` varchar(100) DEFAULT NULL COMMENT '目标站点',
  `schedule_config` text COMMENT '调度配置（JSON格式）',
  `client_limit` int(11) DEFAULT '1' COMMENT '客户端数量限制',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  `create_user` int(11) DEFAULT '0' COMMENT '创建用户',
  `update_user` int(11) DEFAULT '0' COMMENT '更新用户',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_task_name` (`task_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫任务表';

-- 爬虫客户端表
CREATE TABLE IF NOT EXISTS `fp_spider_client` (
  `id` varchar(36) NOT NULL COMMENT '客户端ID',
  `client_name` varchar(100) NOT NULL COMMENT '客户端名称',
  `device_id` varchar(100) DEFAULT NULL COMMENT '设备ID',
  `ip_address` varchar(50) DEFAULT NULL COMMENT 'IP地址',
  `admin_id` int(11) DEFAULT '0' COMMENT '管理员ID',
  `status` tinyint(4) NOT NULL DEFAULT '1' COMMENT '状态：0禁用，1启用',
  `is_online` tinyint(4) NOT NULL DEFAULT '0' COMMENT '是否在线：0离线，1在线',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_device_id` (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫客户端表';

-- 客户端爬虫任务表
CREATE TABLE IF NOT EXISTS `fp_spider_client_task` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '客户端任务ID',
  `task_id` varchar(36) NOT NULL COMMENT '爬虫任务ID',
  `client_id` varchar(36) NOT NULL COMMENT '客户端ID',
  `status` tinyint(4) NOT NULL DEFAULT '0' COMMENT '状态：0未开始，1进行中，2完成，3错误，4取消',
  `progress` int(11) NOT NULL DEFAULT '0' COMMENT '进度（0-100）',
  `result` text COMMENT '结果',
  `error_msg` text COMMENT '错误信息',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  `end_time` datetime DEFAULT NULL COMMENT '结束时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_client` (`task_id`,`client_id`),
  KEY `idx_client_id` (`client_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户端爬虫任务表';

-- 爬虫配置表
CREATE TABLE IF NOT EXISTS `fp_spider_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '配置ID',
  `task_id` varchar(36) NOT NULL COMMENT '任务ID',
  `config_name` varchar(100) NOT NULL COMMENT '配置名称',
  `target_site` varchar(100) DEFAULT NULL COMMENT '目标站点',
  `spider_type` varchar(50) DEFAULT NULL COMMENT '爬虫类型',
  `config_content` text COMMENT '配置内容（JSON格式）',
  `proxy_config` text COMMENT '代理配置（JSON格式）',
  `request_interval` float DEFAULT '1' COMMENT '请求间隔（秒）',
  `request_timeout` int(11) DEFAULT '30' COMMENT '请求超时（秒）',
  `retry_count` int(11) DEFAULT '3' COMMENT '重试次数',
  `user_agent` text COMMENT '用户代理',
  `cookies` text COMMENT 'Cookies',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_task_id` (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='爬虫配置表';

-- 博主信息表
CREATE TABLE IF NOT EXISTS `fp_blogger_info` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `blogger_id` varchar(100) NOT NULL COMMENT '博主ID',
  `blogger_name` varchar(100) DEFAULT NULL COMMENT '博主名称',
  `platform_id` int(11) NOT NULL COMMENT '平台ID',
  `url` varchar(255) DEFAULT NULL COMMENT '主页链接',
  `avatar` varchar(255) DEFAULT NULL COMMENT '头像URL',
  `status` tinyint(4) NOT NULL DEFAULT '0' COMMENT '状态：0未处理，1已处理，2处理失败',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_blogger_platform` (`blogger_id`,`platform_id`),
  KEY `idx_platform_status` (`platform_id`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='博主信息表';

-- 博主详情表
CREATE TABLE IF NOT EXISTS `fp_blogger_detail` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `blogger_id` varchar(100) NOT NULL COMMENT '博主ID',
  `platform_id` int(11) NOT NULL COMMENT '平台ID',
  `content_url` varchar(255) NOT NULL COMMENT '内容链接',
  `content_id` varchar(100) DEFAULT NULL COMMENT '内容ID',
  `status` tinyint(4) NOT NULL DEFAULT '0' COMMENT '状态：0未处理，1已处理，2处理失败',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_content_platform` (`content_id`,`platform_id`),
  KEY `idx_blogger_platform` (`blogger_id`,`platform_id`),
  KEY `idx_platform_status` (`platform_id`,`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='博主详情表';

-- 代理配置表
CREATE TABLE IF NOT EXISTS `fp_proxy_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '配置ID',
  `proxy_name` varchar(100) NOT NULL COMMENT '代理名称',
  `proxy_type` varchar(20) DEFAULT 'http' COMMENT '代理类型',
  `proxy_url` varchar(255) DEFAULT NULL COMMENT '代理URL',
  `username` varchar(100) DEFAULT NULL COMMENT '用户名',
  `password` varchar(100) DEFAULT NULL COMMENT '密码',
  `is_active` tinyint(4) NOT NULL DEFAULT '0' COMMENT '是否激活',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  `update_time` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='代理配置表';

-- 用户代理表
CREATE TABLE IF NOT EXISTS `fp_user_agent` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'ID',
  `user_agent` varchar(500) NOT NULL COMMENT '用户代理字符串',
  `description` varchar(100) DEFAULT NULL COMMENT '描述',
  `is_active` tinyint(4) NOT NULL DEFAULT '1' COMMENT '是否激活',
  `create_time` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户代理表'; 