import asyncio
from datetime import datetime
from typing import Set

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from server.app.services.sync.sync_service import MongoToMySQLSyncService


class SyncScheduler:
    """数据同步调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.sync_service = MongoToMySQLSyncService()
        self.max_concurrent_tasks = 1  # 最大并发任务数
        self.running_tasks: Set[str] = set()  # 正在运行的任务集合
        self.task_queue = asyncio.Queue()  # 任务队列
        self.worker_tasks = []  # 工作任务列表
        self.is_sync_running = False  # 同步任务是否正在运行
        self.last_sync_time = None  # 上次同步时间
        
    async def start(self):
        """启动定时任务"""
        # 初始化同步服务
        logger.info("开始初始化同步服务")
        await self.sync_service.initialize()
        
        # 每小时执行一次
        self.scheduler.add_job(
            self.sync_all_tables,
            CronTrigger(hour='*'),
            id='mongo_mysql_sync',
            replace_existing=False
        )
        self.scheduler.start()
        logger.info("数据同步调度器已启动")
        
        # 启动工作线程
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker)
        
    async def sync_all_tables(self):
        """同步所有表"""
        try:
            # 检查是否有同步任务正在运行
            if self.is_sync_running:
                logger.warning("上一个同步任务还在运行中，跳过本次同步")
                return
                
            # 检查上次同步时间
            current_time = datetime.now()
            # 设置同步状态
            self.is_sync_running = True
            self.last_sync_time = current_time
            
            try:
                # 将所有表放入任务队列
                for collection_name in self.sync_service.table_mapper.keys():
                    if self.sync_service.table_mapper[collection_name]['state'] == 1:
                        await self.task_queue.put(collection_name)
                        logger.info(f"表 {collection_name} 已添加到同步队列")
            finally:
                # 同步完成后重置状态
                self.is_sync_running = False
                
        except Exception as e:
            logger.error(f"添加同步任务失败: {str(e)}")
            self.is_sync_running = False
            
    async def _worker(self, worker_id: str):
        """
        工作线程，从队列中获取任务并执行
        
        Args:
            worker_id: 工作线程ID
        """
        logger.info(f"启动工作线程 {worker_id}")
        while True:
            try:
                # 从队列获取任务
                collection_name = await self.task_queue.get()
                
                # 如果是特殊标记，表示需要退出
                if collection_name == "STOP":
                    logger.info(f"工作线程 {worker_id} 收到停止信号，退出")
                    self.task_queue.task_done()
                    break
                
                # 添加到运行任务集合
                self.running_tasks.add(collection_name)
                logger.info(f"工作线程 {worker_id} 开始同步表 {collection_name}")
                
                try:
                    # 执行同步任务
                    await self.sync_service.sync_table(collection_name)
                    logger.info(f"工作线程 {worker_id} 成功同步表 {collection_name}")
                except Exception as e:
                    logger.error(f"工作线程 {worker_id} 同步表 {collection_name} 失败: {str(e)}")
                finally:
                    # 从运行任务集合中移除
                    self.running_tasks.discard(collection_name)
                    # 标记任务完成
                    self.task_queue.task_done()
                    
            except Exception as e:
                logger.error(f"工作线程 {worker_id} 发生异常: {str(e)}")
                # 继续处理下一个任务
                continue
    
    async def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("数据同步调度器已关闭")
            
        # 停止所有工作线程
        for _ in range(len(self.worker_tasks)):
            await self.task_queue.put("STOP")
            
        # 等待所有工作线程完成
        await asyncio.gather(*self.worker_tasks)
        logger.info("所有工作线程已关闭") 