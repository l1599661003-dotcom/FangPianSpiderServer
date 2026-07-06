from fastapi import Request, APIRouter
from loguru import logger
import json

from server.app.core.sign_util import SignUtil
from server.app.services.sync.sync_service import MongoToMySQLSyncService

router = APIRouter()


# 获取爬虫token列表，接收JSON参数
@router.post("/sync/spider/data", summary="同步客户端数据")
async def get_spider_token(request: Request):
    form_data = await request.json()
    result = SignUtil.verify_client_id(form_data)
    logger.info(f"签名验证结果: {result}")
    if not result:
        pass
        # return {"code": 401, "message": "签名验证失败"}

    sync_service = MongoToMySQLSyncService()
    if 'tb_name' in form_data:
        await sync_service.sync_table_by_data(form_data["tb_name"], form_data["tb_data"])
    elif 'apis' in form_data:
        for data in form_data["apis"]:
            tb_data = data["tb_data"]
            if isinstance(tb_data, str):
                tb_data = json.loads(tb_data)
            await sync_service.sync_table_by_data(data["tb_name"], tb_data)
    return {"code": 200, "data": [], "message": "成功"}
