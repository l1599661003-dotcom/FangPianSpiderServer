-- 如果存在旧表，将数据迁移到新表
-- 1. 检查 fp_client_task 表是否存在，如果存在则迁移数据

-- 创建备份表
CREATE TABLE IF NOT EXISTS `fp_client_task_backup` LIKE `fp_client_task`;

-- 备份数据
INSERT INTO `fp_client_task_backup` SELECT * FROM `fp_client_task`;

-- 将数据从 fp_client_task 迁移到 fp_spider_client_task
INSERT IGNORE INTO `fp_spider_client_task` (
    `id`, `task_id`, `client_id`, `status`, `progress`, 
    `result`, `error_msg`, `create_time`, `update_time`, `end_time`
)
SELECT 
    `id`, `task_id`, `client_id`, `status`, 
    COALESCE(`progress`, 0) as `progress`, 
    COALESCE(`result`, '') as `result`, 
    COALESCE(`error_msg`, '') as `error_msg`, 
    `create_time`, `update_time`, 
    `end_time`
FROM 
    `fp_client_task`
ON DUPLICATE KEY UPDATE
    `status` = VALUES(`status`),
    `progress` = VALUES(`progress`),
    `result` = VALUES(`result`),
    `error_msg` = VALUES(`error_msg`),
    `update_time` = VALUES(`update_time`),
    `end_time` = VALUES(`end_time`);

-- 删除旧表（请确认数据迁移成功后再执行）
-- DROP TABLE `fp_client_task`;

-- 如果需要保留旧表，可以重命名
-- RENAME TABLE `fp_client_task` TO `fp_client_task_old`; 