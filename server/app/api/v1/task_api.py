from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from server.app.services.ClientTaskService import client_task_service
from server.app.services.SpiderClientService import SpiderClientService
from server.app.services.SpiderTaskService import spider_task_service

router = APIRouter()

# 依赖注入函数
async def get_task_scheduler():
    from server.app.main import task_scheduler
    return task_scheduler


@router.post("/tasks/create")
async def create_task(task_data: dict):
    """创建爬虫任务"""
    try:
        task_id = await spider_task_service.create_task(task_data)
        if task_id:
            return {"success": True, "task_id": task_id}
        return {"success": False, "message": "创建任务失败"}
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/client-tasks/create")
async def create_client_task(client_task_data: dict):
    """创建客户端任务分配"""
    try:
        # 检查客户端是否存在
        client = await SpiderClientService().get_client_by_id(client_task_data['client_id'])
        if not client:
            raise HTTPException(status_code=404, detail="客户端不存在")
            
        # 检查任务是否存在
        task = await spider_task_service.get_task_by_id(client_task_data['task_id'])
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
            
        # 检查是否已存在相同的分配
        existing = await client_task_service.get_task_by_client_and_task(
            client_task_data['client_id'],
            client_task_data['task_id']
        )
        if existing:
            raise HTTPException(status_code=400, detail="该任务已分配给此客户端")
        
        # 创建客户端任务分配
        client_task_id = await client_task_service.create_task(client_task_data)
        if client_task_id:
            return {"success": True, "client_task_id": client_task_id}
        return {"success": False, "message": "创建客户端任务分配失败"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"创建客户端任务分配失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/client-tasks/{client_task_id}")
async def update_client_task(client_task_id: str, client_task_data: dict):
    """更新客户端任务分配"""
    try:
        success = await client_task_service.update_task(client_task_id, client_task_data)
        if success:
            return {"success": True, "message": "更新成功"}
        return {"success": False, "message": "更新失败"}
    except Exception as e:
        logger.error(f"更新客户端任务分配失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/client-tasks/{client_task_id}")
async def delete_client_task(client_task_id: str):
    """删除客户端任务分配"""
    try:
        success = await client_task_service.delete_task(client_task_id)
        if success:
            return {"success": True, "message": "删除成功"}
        return {"success": False, "message": "删除失败"}
    except Exception as e:
        logger.error(f"删除客户端任务分配失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client-tasks")
async def get_client_tasks(client_id: Optional[str] = None, task_id: Optional[str] = None):
    """获取客户端任务分配列表"""
    try:
        if client_id:
            tasks = await client_task_service.get_tasks_by_client_id(client_id)
        elif task_id:
            tasks = await client_task_service.get_tasks_by_task_id(task_id)
        else:
            tasks = await client_task_service.get_all_tasks()
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"获取客户端任务分配列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client-tasks/{client_task_id}")
async def get_client_task(client_task_id: str):
    """获取客户端任务分配详情"""
    try:
        task = await client_task_service.get_task_by_id(client_task_id)
        if task:
            return {"success": True, "task": task}
        raise HTTPException(status_code=404, detail="客户端任务分配不存在")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取客户端任务分配详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution-records")
async def get_execution_records(
    client_task_id: Optional[str] = None,
    client_id: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[int] = None
):
    """获取任务执行记录列表"""
    try:
        # 根据条件获取执行记录
        if client_task_id:
            records = [await client_task_service.get_execution_record(client_task_id)]
        else:
            # 获取所有任务
            tasks = await client_task_service.get_all_tasks()
            records = []
            for task in tasks:
                if (not client_id or task["client_id"] == client_id) and \
                   (not task_id or task["task_id"] == task_id) and \
                   (status is None or task["status"] == status):
                    record = await client_task_service.get_execution_record(task["id"])
                    if record:
                        records.append(record)
        
        return {"success": True, "records": records}
    except Exception as e:
        logger.error(f"获取任务执行记录列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution-records/{record_id}")
async def get_execution_record(record_id: str):
    """获取任务执行记录详情"""
    try:
        record = await client_task_service.get_execution_record(record_id)
        if record:
            return {"success": True, "record": record}
        raise HTTPException(status_code=404, detail="执行记录不存在")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取任务执行记录详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/start")
async def start_task(task_id: str, client_id: Optional[str] = None, scheduler = Depends(get_task_scheduler)):
    """启动指定任务"""
    try:
        # 检查任务是否存在
        task = await spider_task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 更新任务状态为运行中
        await spider_task_service.update_task_status(task_id, 1)  # 1表示运行中
        
        # 如果指定了客户端，直接分配任务
        if client_id:
            await scheduler.start_client_task(task, client_id)
            return {"success": True, "message": "任务已分配给指定客户端"}
        
        # 否则等待调度器自动分配
        return {"success": True, "message": "任务已启动，等待分配给可用客户端"}
    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str, reason: str = "手动停止", scheduler = Depends(get_task_scheduler)):
    """停止指定任务"""
    try:
        # 检查任务是否存在
        task = await spider_task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 停止任务
        success = await scheduler.stop_task(task_id, reason)
        if success:
            return {"success": True, "message": "任务已停止"}
        return {"success": False, "message": "停止任务失败"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def get_tasks(status: Optional[int] = None, task_type: Optional[int] = None):
    """获取任务列表"""
    try:
        if status is not None and task_type is not None:
            return {"success": False, "message": "status和task_type参数不能同时提供"}
        
        if status is not None:
            tasks = await spider_task_service.get_tasks_by_status(status)
        elif task_type is not None:
            tasks = await spider_task_service.get_tasks_by_type(task_type)
        else:
            tasks = await spider_task_service.get_all_tasks()
        
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    try:
        task = await spider_task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"success": True, "task": task}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, scheduler = Depends(get_task_scheduler)):
    """删除指定任务"""
    try:
        # 检查任务是否存在
        task = await spider_task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 先停止任务
        await scheduler.stop_task(task_id, "删除任务")
        
        # 删除任务
        success = await spider_task_service.delete_task(task_id)
        if success:
            return {"success": True, "message": "任务已删除"}
        return {"success": False, "message": "删除任务失败"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/clients")
async def get_task_clients(task_id: str):
    """获取任务的客户端列表"""
    try:
        # 检查任务是否存在
        task = await spider_task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取任务的客户端
        clients = await client_task_service.get_tasks_by_task_id(task_id)
        return {"success": True, "clients": clients}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务客户端列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/dispatch")
async def dispatch_task(task_id: str, client_id: Optional[str] = None, scheduler = Depends(get_task_scheduler)):
    """手动分发任务给客户端"""
    try:
        success = await scheduler.dispatch_task(task_id, client_id)
        if success:
            return {"success": True, "message": "任务已分发"}
        return {"success": False, "message": "分发任务失败"}
    except Exception as e:
        logger.error(f"分发任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-tasks")
async def get_available_tasks():
    """获取可分配的任务列表"""
    try:
        from server.app.services.TaskService import TaskService
        tasks = await TaskService().get_available_tasks()
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"获取可分配任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients")
async def get_clients(status: Optional[int] = None):
    """获取客户端列表"""
    try:
        if status is not None:
            clients = await SpiderClientService().get_clients_by_status(status)
        else:
            clients = await SpiderClientService().get_all_clients()
        return {"success": True, "clients": clients}
    except Exception as e:
        logger.error(f"获取客户端列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients/{client_id}/tasks")
async def get_client_tasks(client_id: str):
    """获取客户端的任务列表"""
    try:
        tasks = await client_task_service.get_tasks_by_client_id(client_id)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"获取客户端任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 注意：移除startup_event，因为在main.py中已经启动了全局任务调度器
# @router.on_event("startup")
# async def startup_event():
#     """服务启动时启动任务调度器"""
#     await task_scheduler.start() 