import asyncio
import json
from datetime import datetime
from typing import Dict, Optional

from fastapi import WebSocket
from loguru import logger
from starlette.websockets import WebSocketState


class PluginWebSocketManager:
    """Manages browser-extension connections independently from legacy crawler clients."""

    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.last_activity: Dict[int, float] = {}
        self.busy_executions: Dict[int, int] = {}
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.heartbeat_interval = 20
        self.connection_timeout = 75

    async def connect(self, websocket: WebSocket, client_id: int):
        await websocket.accept()
        old_socket = self.active_connections.get(client_id)
        if old_socket and old_socket.client_state != WebSocketState.DISCONNECTED:
            try:
                await old_socket.close(code=4001, reason="browser instance reconnected")
            except Exception:
                pass
        self.active_connections[client_id] = websocket
        self.last_activity[client_id] = datetime.now().timestamp()
        if not self.heartbeat_task or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"插件浏览器实例 {client_id} 已连接")

    async def disconnect(self, client_id: int, websocket: Optional[WebSocket] = None):
        current = self.active_connections.get(client_id)
        if websocket is not None and current is not websocket:
            return False
        socket = self.active_connections.pop(client_id, None)
        self.last_activity.pop(client_id, None)
        if socket and socket.client_state != WebSocketState.DISCONNECTED:
            try:
                await socket.close(code=1000)
            except Exception:
                pass
        logger.info(f"插件浏览器实例 {client_id} 已断开")
        return True

    def is_connected(self, client_id: int) -> bool:
        socket = self.active_connections.get(client_id)
        return bool(socket and socket.client_state != WebSocketState.DISCONNECTED)

    def touch(self, client_id: int):
        self.last_activity[client_id] = datetime.now().timestamp()

    def claim_execution(self, client_id: int, execution_id: int) -> bool:
        if client_id in self.busy_executions:
            return False
        self.busy_executions[client_id] = execution_id
        return True

    def release_execution(self, client_id: int, execution_id: Optional[int] = None):
        current = self.busy_executions.get(client_id)
        if execution_id is None or current == execution_id:
            self.busy_executions.pop(client_id, None)

    async def send(self, client_id: int, message: dict) -> bool:
        socket = self.active_connections.get(client_id)
        if not socket or socket.client_state == WebSocketState.DISCONNECTED:
            return False
        try:
            await socket.send_text(json.dumps(message, ensure_ascii=False, default=str))
            self.touch(client_id)
            return True
        except Exception as exc:
            logger.warning(f"向插件实例 {client_id} 发送消息失败: {exc}")
            await self.disconnect(client_id)
            return False

    async def shutdown(self):
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        for client_id in list(self.active_connections):
            await self.disconnect(client_id)

    async def _heartbeat_loop(self):
        try:
            while self.active_connections:
                now = datetime.now().timestamp()
                for client_id in list(self.active_connections):
                    last_active = self.last_activity.get(client_id, 0)
                    if now - last_active > self.connection_timeout:
                        await self.disconnect(client_id)
                        continue
                    await self.send(client_id, {
                        "cmd": "heartbeat",
                        "timestamp": now,
                    })
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            pass
        finally:
            self.heartbeat_task = None
