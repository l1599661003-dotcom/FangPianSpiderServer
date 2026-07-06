from fastapi import APIRouter, HTTPException
from loguru import logger

from server.app.services.MongoDBService import mongodb_service

router = APIRouter()

@router.get("/solar/cooperator/user/blogger/{userId}")
async def blogger_info(userId: str):
    """查询博主信息"""
    try:
        logger.info(f"查询博主信息 博主ID: {userId}")
        blogger_info = await mongodb_service.find_blogger_info(userId)
        logger.info(f"查询博主信息 结果: {blogger_info}")
        return {"success": True, "msg": "成功", "code": 0, "data": blogger_info }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/solar/kol/data_v3/notes_rate")
async def notes_rate(userId: str, business: int, noteType: int, dateType: int, advertiseSwitch: int):
    """查询博主信息"""
    try:
        logger.info(f"查询博主信息 博主ID: {userId}")
        note_rate = await mongodb_service.find_blogger_note_rate(userId, dateType, noteType, advertiseSwitch, business)
        logger.info(f"查询博主信息 结果: {note_rate}")
        return {"success": True, "msg": "成功", "code": 0, "data": note_rate }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/solar/kol/data_v2/notes_detail")
async def notes_detail(userId: str):
    """查询博主信息"""
    try:
        logger.info(f"查询博主信notes_detail息 博主ID: {userId}")
        note_rate = await mongodb_service.find_blogger_note_detail(userId)
        logger.info(f"查询博主信息 结果: {note_rate}")
        return {"success": True, "msg": "成功", "code": 0, "data": note_rate }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solar/kol/data/{userId}/fans_profile")
async def fans_profile(userId: str, task_id:int):
    """查询博主信息"""
    try:
        logger.info(f"查询博主信息 博主ID: {userId}")
        note_rate = await mongodb_service.find_blogger_fans_profile(userId, task_id)
        logger.info(f"查询博主信息 结果: {note_rate}")
        return {"success": True, "msg": "成功", "code": 0, "data": note_rate }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solar/kol/data/{userId}/fans_overall_new_history", summary="粉丝态势")
async def fans_profile(userId: str, dateType: int = 1, increaseType: int = 1):
    """查询博主信息"""
    try:
        logger.info(f"查询博主粉丝汇总 博主ID: {userId}")
        note_rate = await mongodb_service.find_blogger_fans_overall_new_history(userId, dateType, increaseType)
        logger.info(f"查询博主信息 结果: {note_rate}")
        return {"success": True, "msg": "成功", "code": 0, "data": note_rate }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/solar/kol/data_v3/fans_summary", summary="粉丝态势")
async def fans_profile(userId: str):
    """查询查询博主粉丝汇总信息"""
    try:
        logger.info(f"查询博主粉丝汇总 博主ID: {userId}")
        note_rate = await mongodb_service.find_blogger_fans_summary(userId)
        logger.info(f"查询博主信息 结果: {note_rate}")
        return {"success": True, "msg": "成功", "code": 0, "data": note_rate }
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
