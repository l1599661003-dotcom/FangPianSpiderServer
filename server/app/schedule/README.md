# 创作者账单报告任务

## 概述

这个模块包含两个任务，用于自动从小红书创作者平台获取不同类型的账单数据：
1. **创作者账单报告任务** - 获取广告内容相关的账单数据
2. **创作者新芽账单报告任务** - 获取分销商相关的账单数据

两个任务都已集成到系统现有的定时任务调度器中。

## 功能特性

1. **自动获取账单**: 支持多个账号的账单数据获取
2. **定时执行**: 
   - 创作者账单报告：每天凌晨2点自动执行
   - 创作者新芽账单报告：每天凌晨2点30分自动执行
3. **增量更新**: 自动跳过已存在的账单记录
4. **Excel解析**: 自动下载并解析Excel账单文件
5. **数据库存储**: 将解析的数据存储到MySQL数据库
6. **统一管理**: 与其他定时任务统一在SchedulerService中管理
7. **双重数据源**: 支持广告内容和分销商两种不同的数据源

## API接口

### 手动触发任务
```
POST /api/v1/creator-bill/trigger          # 触发创作者账单报告任务
POST /api/v1/creator-bill/xinya/trigger    # 触发创作者新芽账单报告任务
```

### 获取任务状态
```
GET /api/v1/creator-bill/status
```

### 获取所有定时任务
```
GET /api/v1/creator-bill/jobs
```

### 暂停任务
```
POST /api/v1/creator-bill/jobs/{job_id}/pause
```

### 恢复任务
```
POST /api/v1/creator-bill/jobs/{job_id}/resume
```

### 移除任务
```
DELETE /api/v1/creator-bill/jobs/{job_id}
```

## 配置要求

### 必需的Python包
```
pandas>=2.1.0
openpyxl>=3.1.0
```
## 使用方法

### 1. 自动定时执行
任务已集成到系统的SchedulerService中，会在每天凌晨2点自动执行，与其他定时任务一起管理。

### 2. 手动触发
```bash
# 触发创作者账单报告任务
curl -X POST "http://localhost:8080/api/v1/creator-bill/trigger"

# 触发创作者新芽账单报告任务
curl -X POST "http://localhost:8080/api/v1/creator-bill/xinya/trigger"
```

### 3. 查看任务状态
```bash
curl -X GET "http://localhost:8080/api/v1/creator-bill/status"
```

### 4. 查看所有定时任务
```bash
curl -X GET "http://localhost:8080/api/v1/creator-bill/jobs"
```

## 日志

任务执行日志会记录在应用日志中，可以通过日志查看任务执行情况：
- 任务开始和结束时间
- 处理的账号和数据量
- 错误信息和异常处理

## 注意事项

1. **请求频率**: 任务会控制请求频率，避免对目标服务器造成过大压力
2. **数据去重**: 自动检查并跳过重复的账单记录
3. **异常处理**: 完善的异常处理机制，确保任务稳定运行
4. **临时文件**: 下载的Excel文件会自动清理临时文件

## 故障排查

1. **Token失效**: 检查token是否有效
2. **网络问题**: 确保服务器可以访问小红书API
3. **数据库连接**: 检查数据库连接配置
4. **磁盘空间**: 确保有足够的临时文件空间 