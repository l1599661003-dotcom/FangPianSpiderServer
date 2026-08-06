import asyncio
import os

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger

from server.app.schemas.PluginRemoteControl import (
    PluginCommandRequest,
    PluginEvent,
    PluginRegisterRequest,
    PluginRetryRequest,
    PluginUpgradeNotifyRequest,
)


router = APIRouter(prefix="/plugin")


def get_plugin_service():
    from server.app.runtime import plugin_remote_service
    return plugin_remote_service


def require_control_key(x_plugin_control_key: str = Header(default="")):
    expected = os.getenv("PLUGIN_CONTROL_API_KEY", "")
    if not expected or x_plugin_control_key != expected:
        raise HTTPException(status_code=401, detail="invalid plugin control key")


@router.post("/register", summary="浏览器插件实例注册")
async def register_plugin(payload: PluginRegisterRequest, request: Request):
    try:
        client_ip = request.client.host if request.client else ""
        return await get_plugin_service().register(payload.model_dump(), client_ip)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.websocket("/ws")
async def plugin_websocket(websocket: WebSocket):
    service = get_plugin_service()
    device_id = websocket.query_params.get("device_id", "")
    token = websocket.query_params.get("client_token", "")
    client = await service.authenticate(device_id, token)
    if not client:
        await websocket.close(code=4401, reason="invalid browser instance credentials")
        return
    client_id = int(client["id"])
    try:
        await service.manager.connect(websocket, client_id)
        await service.set_online(client_id, True)
        enabled = bool(client.get("status") == 1 and client.get("admin_id") and client.get("computer_id"))
        await service.manager.send(client_id, {
            "cmd": "registration_status",
            "data": {"client_id": client_id, "enabled": enabled},
        })
        upgrade_notice = service.build_upgrade_notice(client)
        if upgrade_notice:
            await service.manager.send(client_id, {
                "cmd": "plugin_upgrade_notice",
                "data": upgrade_notice,
            })
        while True:
            raw = await websocket.receive_text()
            event = PluginEvent.model_validate_json(raw)
            await service.handle_event(client_id, event.model_dump())
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception(f"插件 WebSocket 处理失败 client={client_id}: {exc}")
    finally:
        removed = await service.manager.disconnect(client_id, websocket)
        if removed:
            await service.set_online(client_id, False)
            asyncio.create_task(service.finish_disconnected_executions(client_id))


@router.post("/commands", dependencies=[], summary="批量下发插件指令")
async def create_command(payload: PluginCommandRequest, x_plugin_control_key: str = Header(default="")):
    require_control_key(x_plugin_control_key)
    try:
        return {"ok": True, **await get_plugin_service().create_batch(payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/commands/{batch_id}/stop", summary="停止批量指令")
async def stop_command(batch_id: int, x_plugin_control_key: str = Header(default="")):
    require_control_key(x_plugin_control_key)
    try:
        return {"ok": True, **await get_plugin_service().stop_batch(batch_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/commands/{batch_id}/retry", summary="重试失败项")
async def retry_command(batch_id: int, payload: PluginRetryRequest, x_plugin_control_key: str = Header(default="")):
    require_control_key(x_plugin_control_key)
    try:
        result = await get_plugin_service().retry_failed(batch_id, payload.client_ids, payload.operator_id)
        return {"ok": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/upgrade/notify", summary="推送插件升级提醒")
async def notify_upgrade(payload: PluginUpgradeNotifyRequest, x_plugin_control_key: str = Header(default="")):
    require_control_key(x_plugin_control_key)
    return {"ok": True, **await get_plugin_service().notify_upgrade(payload.client_ids, payload.force)}
