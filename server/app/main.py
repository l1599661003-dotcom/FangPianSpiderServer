import asyncio
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from server.app.api.v1 import login, websocket, task_api, pgy_blogger_api, creator_bill_api, spider_token_controller, \
    sync_spider_data_api, plugin_remote_control
from server.app.core.PluginWebSocketManager import PluginWebSocketManager
from server.app.services.PluginRemoteControlService import PluginRemoteControlService
from server.app.services.PluginTriggerScheduler import PluginTriggerScheduler
from server.app.core.config import settings
from server.app.db.context import DatabaseManager
from server.app.core.WebSocketManager import WebSocketManager
from server.app.core.TaskScheduler import TaskScheduler
from server.app.services.SchedulerService import scheduler_service
from server.app.services.sync.sync_task import SyncScheduler

load_dotenv()

# 创建全局单例对象
ws_manager = WebSocketManager()
task_scheduler = TaskScheduler(ws_manager)
plugin_ws_manager = PluginWebSocketManager()
plugin_remote_service = PluginRemoteControlService(plugin_ws_manager)
plugin_trigger_scheduler = PluginTriggerScheduler(plugin_remote_service)

# 全局变量
sync_scheduler = None

# 定义lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动")
    # 启动时执行的操作
    try:
        # 初始化数据库连接池
        await DatabaseManager.initialize()
        await plugin_remote_service.reset_online_state()
        asyncio.create_task(plugin_remote_service.recover_stale_executions())
        await plugin_trigger_scheduler.start()
        logger.info("数据库连接池初始化成功")
        
        # 配置WebSocket超时时间
        # 增加超时时间以支持耗时任务
        ws_manager.set_timeout_config(
            heartbeat_interval=60,     # 1分钟发送一次心跳
            connection_timeout=1800,   # 30分钟超时（适合耗时任务）
            check_interval=90          # 1.5分钟检查一次连接
        )
        logger.info("WebSocket超时配置设置成功")
        
        # 启动任务调度器
        # await task_scheduler.start()
        logger.info("任务调度器启动成功")
        
        # 启动定时任务调度器（包含创作者账单报告任务）
        # scheduler_service.start()
        logger.info("定时任务调度器启动成功")

        # 初始化数据同步调度器
        global sync_scheduler
        sync_scheduler = SyncScheduler()
        # await sync_scheduler.start()
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise
    yield
    """应用关闭时的清理操作"""
    try:
        # 停止任务调度器
        await task_scheduler.stop()
        logger.info("任务调度器已停止")
        await plugin_trigger_scheduler.stop()
        
        # 停止定时任务调度器
        scheduler_service.stop()
        logger.info("定时任务调度器已停止")
        
        plugin_client_ids = list(plugin_ws_manager.active_connections.keys())
        await plugin_ws_manager.shutdown()
        for client_id in plugin_client_ids:
            await plugin_remote_service.set_online(client_id, False)

        # 关闭数据库连接池
        await DatabaseManager.close()
        logger.info("数据库连接池已关闭")

        # 关闭数据同步调度器
        if sync_scheduler:
            await sync_scheduler.shutdown()
    except Exception as e:
        logger.error(f"应用关闭时发生错误: {e}")

# 创建FastAPI应用实例，添加lifespan参数
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(login.router, prefix="/api/v1", tags=["登录"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(task_api.router, prefix="/api/v1", tags=["任务"])
app.include_router(pgy_blogger_api.router, prefix="/api/v1", tags=["博主采集接口"])
app.include_router(creator_bill_api.router, prefix="/api/v1", tags=["创作者账单报告"])
app.include_router(spider_token_controller.router, prefix="/api/v1", tags=["爬虫token"])
app.include_router(sync_spider_data_api.router, prefix="/api/v1", tags=["同步爬虫数据"])
app.include_router(plugin_remote_control.router, prefix="/api/v1", tags=["插件远程控制"])

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    # ... 其他初始化代码 ...

    # 初始化数据同步调度器
    global sync_scheduler
    sync_scheduler = SyncScheduler()
    await sync_scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    # ... 其他清理代码 ...

    # 关闭数据同步调度器
    if sync_scheduler:
        await sync_scheduler.shutdown()

if __name__ == "__main__":
    logger.add("data/logs/server_{time}.log", rotation="1 day", retention="7 days", level="INFO")

    print(sys.path)
    import uvicorn

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    uvicorn.run(app, host=host, port=port)
