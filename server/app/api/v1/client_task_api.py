from fastapi import APIRouter, Depends
from loguru import logger

from server.app.schemas.TaskStartPO import TaskStartPO

router = APIRouter()


# 任务管理接口
@router.post("/task/start", response_model=None, summary="开始任务")
async def login(form_data: TaskStartPO = Depends()):
    # 登录逻辑处理并生成token
    logger.info(f"请求参数：{form_data}")
    return None
