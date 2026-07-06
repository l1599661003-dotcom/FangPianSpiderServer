from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger

from server.app.schedule.CreatorBillReportJob import run_creator_bill_report_task
from server.app.schedule.CreatorXinYaBillReportJob import run_creator_xinya_bill_report_task
from server.app.services.SchedulerService import scheduler_service

router = APIRouter()


@router.post("/creator-bill/trigger")
async def trigger_creator_bill_report(background_tasks: BackgroundTasks, creator_id: Optional[str] = None):
    """手动触发创作者账单报告任务"""
    try:
        logger.info(f"手动触发创作者账单报告任务, creator_id: {creator_id}")
        
        # 将任务添加到后台任务中执行，避免阻塞API响应
        background_tasks.add_task(run_creator_bill_report_task, creator_id)
        
        return {
            "success": True, 
            "message": "创作者账单报告任务已启动，正在后台运行",
            "creator_id": creator_id
        }
    except Exception as e:
        logger.error(f"手动触发创作者账单报告任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creator-bill/xinya/trigger")
async def trigger_creator_xinya_bill_report(background_tasks: BackgroundTasks, creator_id: Optional[str] = None):
    """手动触发创作者新芽账单报告任务"""
    try:
        logger.info(f"手动触发创作者新芽账单报告任务, creator_id: {creator_id}")
        
        # 将任务添加到后台任务中执行，避免阻塞API响应
        background_tasks.add_task(run_creator_xinya_bill_report_task, creator_id)
        
        return {
            "success": True, 
            "message": "创作者新芽账单报告任务已启动，正在后台运行",
            "creator_id": creator_id
        }
    except Exception as e:
        logger.error(f"手动触发创作者新芽账单报告任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/creator-bill/jobs")
async def get_scheduler_jobs():
    """获取定时任务列表"""
    try:
        jobs = scheduler_service.get_jobs()
        return {"success": True, "data": jobs}
    except Exception as e:
        logger.error(f"获取定时任务列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creator-bill/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """暂停指定任务"""
    try:
        scheduler_service.pause_job(job_id)
        return {"success": True, "message": f"任务 {job_id} 已暂停"}
    except Exception as e:
        logger.error(f"暂停任务 {job_id} 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creator-bill/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """恢复指定任务"""
    try:
        scheduler_service.resume_job(job_id)
        return {"success": True, "message": f"任务 {job_id} 已恢复"}
    except Exception as e:
        logger.error(f"恢复任务 {job_id} 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/creator-bill/jobs/{job_id}")
async def remove_job(job_id: str):
    """移除指定任务"""
    try:
        scheduler_service.remove_job(job_id)
        return {"success": True, "message": f"任务 {job_id} 已移除"}
    except Exception as e:
        logger.error(f"移除任务 {job_id} 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/creator-bill/status")
async def get_task_status():
    """获取任务运行状态"""
    try:
        jobs = scheduler_service.get_jobs()
        creator_bill_job = None
        creator_xinya_bill_job = None
        
        for job in jobs:
            if job['id'] == 'creator_bill_report':
                creator_bill_job = job
            elif job['id'] == 'creator_xinya_bill_report':
                creator_xinya_bill_job = job
        
        return {
            "success": True,
            "data": {
                "creator_bill_report": creator_bill_job,
                "creator_xinya_bill_report": creator_xinya_bill_job
            },
            "status": "configured"
        }
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 