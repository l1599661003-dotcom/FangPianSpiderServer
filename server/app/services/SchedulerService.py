from datetime import datetime
from typing import Dict, Any, List
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from server.app.db.base import MySQLBaseDAO
from server.app.services.SpiderTaskService import spider_task_service
from server.app.schedule.CreatorBillReportJob import run_creator_bill_report_task
from server.app.schedule.CreatorXinYaBillReportJob import run_creator_xinya_bill_report_task


class SchedulerService:
    """定时任务服务，负责管理定时任务"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.task_dao = MySQLBaseDAO("fp_spider_task")
    
    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            # 添加每天0点执行的任务
            self.scheduler.add_job(
                self.check_task_status,
                CronTrigger(hour=0, minute=0),
                id='check_task_status',
                replace_existing=True
            )
            
            # 添加创作者账单报告任务 - 每天凌晨2点执行
            # self.scheduler.add_job(
            #     self.run_creator_bill_report,
            #     CronTrigger(hour=2, minute=0),
            #     id='creator_bill_report',
            #     replace_existing=True,
            #     name='创作者账单报告任务'
            # )
            
            # 添加创作者新芽账单报告任务 - 每天凌晨2点30分执行
            # self.scheduler.add_job(
            #     self.run_creator_xinya_bill_report,
            #     CronTrigger(hour=2, minute=30),
            #     id='creator_xinya_bill_report',
            #     replace_existing=True,
            #     name='创作者新芽账单报告任务'
            # )
            
            logger.info("调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("调度器已停止")
    
    async def check_task_status(self):
        """检查任务状态并更新"""
        try:
            # 获取当前时间
            now = datetime.now()
            
            # 查询所有需要检查的任务
            query = """
                SELECT * FROM fp_spider_task 
                WHERE status != 1  -- 排除进行中的任务
                AND start_time <= :now 
                AND end_time >= :now
            """
            tasks = await self.task_dao.fetch_all(query, {"now": now})
            
            for task in tasks:
                # 更新任务状态为进行中
                update_data = {
                    "status": 1,  # 进行中
                    "version": task.get("version", 0) + 1,  # 版本号+1
                    "update_time": now
                }
                await self.task_dao.update(update_data, {"id": task["id"]})
                logger.info(f"任务状态已更新: 任务ID: {task['id']}, 新状态: 进行中, 新版本: {update_data['version']}")
            
            logger.info(f"任务状态检查完成，共更新 {len(tasks)} 个任务")
            
        except Exception as e:
            logger.error(f"检查任务状态失败: {e}")
    
    async def run_creator_bill_report(self):
        """执行创作者账单报告任务"""
        try:
            logger.info("开始执行定时创作者账单报告任务")
            result = await run_creator_bill_report_task()
            logger.info(f"创作者账单报告任务执行完成，返回码: {result}")
        except Exception as e:
            logger.error(f"创作者账单报告任务执行失败: {str(e)}")
    
    async def run_creator_xinya_bill_report(self):
        """执行创作者新芽账单报告任务"""
        try:
            logger.info("开始执行定时创作者新芽账单报告任务")
            result = await run_creator_xinya_bill_report_task()
            logger.info(f"创作者新芽账单报告任务执行完成，返回码: {result}")
        except Exception as e:
            logger.error(f"创作者新芽账单报告任务执行失败: {str(e)}")
    
    def add_job(self, func, trigger, job_id: str, **kwargs):
        """添加任务"""
        try:
            self.scheduler.add_job(
                func,
                trigger,
                id=job_id,
                replace_existing=True,
                **kwargs
            )
            logger.info(f"任务 {job_id} 已添加")
        except Exception as e:
            logger.error(f"添加任务 {job_id} 失败: {str(e)}")
    
    def remove_job(self, job_id: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"任务 {job_id} 已移除")
        except Exception as e:
            logger.error(f"移除任务 {job_id} 失败: {str(e)}")
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """获取所有任务信息"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name or job.id,
                'next_run_time': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"任务 {job_id} 已暂停")
        except Exception as e:
            logger.error(f"暂停任务 {job_id} 失败: {str(e)}")
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"任务 {job_id} 已恢复")
        except Exception as e:
            logger.error(f"恢复任务 {job_id} 失败: {str(e)}")


# 创建全局调度器服务实例
scheduler_service = SchedulerService() 