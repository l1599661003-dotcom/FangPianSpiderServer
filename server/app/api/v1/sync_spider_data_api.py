from fastapi import APIRouter, HTTPException, Request
from loguru import logger
import json

from server.app.runtime import plugin_remote_service
from server.app.services.sync.sync_service import MongoToMySQLSyncService

router = APIRouter()


async def require_plugin_instance(request: Request):
    device_id = (request.headers.get("X-Plugin-Device-Id") or "").strip()
    client_token = (request.headers.get("X-Plugin-Client-Token") or "").strip()
    if not device_id or not client_token:
        raise HTTPException(status_code=401, detail="缺少插件实例凭证")

    client = await plugin_remote_service.authenticate(device_id, client_token)
    if not client:
        raise HTTPException(status_code=401, detail="插件实例凭证无效")
    if not plugin_remote_service._is_enabled_client(client):
        raise HTTPException(status_code=403, detail="plugin instance is not enabled or not bound to an employee/computer group")
    return client


def ensure_table_rows(raw_value, field_name: str):
    if isinstance(raw_value, list):
        if not all(isinstance(item, dict) for item in raw_value):
            raise HTTPException(status_code=422, detail=f"{field_name} 中的每一项都必须是对象")
        return raw_value
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"{field_name} 不是有效 JSON") from exc
        if isinstance(parsed, list):
            if not all(isinstance(item, dict) for item in parsed):
                raise HTTPException(status_code=422, detail=f"{field_name} 中的每一项都必须是对象")
            return parsed
    raise HTTPException(status_code=422, detail=f"{field_name} 必须是数组")


# 同步星图数据，接收JSON参数
@router.post("/sync/spider/data", summary="同步客户端数据")
async def get_spider_token(request: Request):
    client = await require_plugin_instance(request)
    form_data = await request.json()
    if not isinstance(form_data, dict):
        raise HTTPException(status_code=422, detail="请求体必须是 JSON 对象")
    logger.info(f"星图同步请求已通过插件实例认证: client_id={client.get('id')}")

    sync_service = MongoToMySQLSyncService()
    if 'tb_name' in form_data:
        tb_name = str(form_data["tb_name"] or "").strip()
        if not tb_name:
            raise HTTPException(status_code=422, detail="tb_name 不能为空")
        await sync_service.sync_table_by_data(tb_name, ensure_table_rows(form_data.get("tb_data"), "tb_data"))
    elif 'apis' in form_data:
        apis = form_data.get("apis")
        if not isinstance(apis, list):
            raise HTTPException(status_code=422, detail="apis 必须是数组")
        for data in apis:
            if not isinstance(data, dict):
                raise HTTPException(status_code=422, detail="apis 中的每一项都必须是对象")
            tb_name = str(data.get("tb_name") or "").strip()
            if not tb_name:
                raise HTTPException(status_code=422, detail="apis 中存在空的 tb_name")
            tb_data = ensure_table_rows(data.get("tb_data"), f"{tb_name}.tb_data")
            await sync_service.sync_table_by_data(tb_name, tb_data)
    else:
        raise HTTPException(status_code=422, detail="请求体必须包含 tb_name 或 apis")
    return {"code": 200, "data": [], "message": "成功"}
