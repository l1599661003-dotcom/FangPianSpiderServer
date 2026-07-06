# WebSocket连接管理器
import asyncio
import json
from datetime import datetime
from typing import List

from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from loguru import logger

from server.app.services.SpiderClientService import SpiderClientService


class WebSocketManager:
    """WebSocket连接管理器，负责管理所有客户端连接"""
    
    # 单例实例
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            # 初始化实例属性
            cls._instance.active_connections = {}
            cls._instance.last_activity = {}
            cls._instance.client_tasks = {}
            cls._instance.heartbeat_task = None
            cls._instance.check_task = None
            # 默认超时配置（秒）
            cls._instance.heartbeat_interval = 60  # 心跳发送间隔，增加到60秒
            cls._instance.connection_timeout = 300  # 连接超时时间，增加到5分钟
            cls._instance.check_interval = 60  # 连接检查间隔
            logger.info("WebSocketManager单例已创建")
        return cls._instance
    
    def __init__(self):
        # 在__new__方法中已经初始化过属性，这里不需要重复初始化
        pass
    
    # 设置WebSocket连接超时配置
    def set_timeout_config(self, heartbeat_interval: int = None, connection_timeout: int = None, check_interval: int = None):
        """设置WebSocket连接超时配置
        
        Args:
            heartbeat_interval: 心跳发送间隔（秒）
            connection_timeout: 连接超时时间（秒）
            check_interval: 连接检查间隔（秒）
        """
        if heartbeat_interval is not None:
            self.heartbeat_interval = heartbeat_interval
        if connection_timeout is not None:
            self.connection_timeout = connection_timeout
        if check_interval is not None:
            self.check_interval = check_interval
        
        logger.info(f"WebSocket超时配置已更新: 心跳间隔={self.heartbeat_interval}秒, "
                   f"连接超时={self.connection_timeout}秒, 检查间隔={self.check_interval}秒")
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """建立WebSocket连接"""
        # 设置WebSocket连接超时时间（如果WebSocket实现支持）
        if hasattr(websocket, "timeout"):
            websocket.timeout = self.connection_timeout
        
        await websocket.accept()
        logger.info(f"客户端 {client_id} 已连接，当前连接数: {len(self.active_connections)}")
        if client_id in self.active_connections:
            # 如果客户端已经连接，关闭旧连接
            try:
                old_websocket = self.active_connections[client_id]
                await old_websocket.close(code=1000, reason="客户端重新连接")
            except Exception as e:
                logger.error(f"关闭旧连接失败: {e}")

        self.active_connections[client_id] = websocket
        logger.info(f"客户端 {client_id} 已连接，当前连接数: {len(self.active_connections)}")
        self.last_activity[client_id] = datetime.now().timestamp()
        self.client_tasks.setdefault(client_id, [])
        
        # 更新客户端在线状态
        await SpiderClientService().update_client_online_status(client_id, True)
        
        # 启动心跳任务（如果未启动）
        if not self.heartbeat_task or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        # 启动连接检查任务（如果未启动）
        if not self.check_task or self.check_task.done():
            self.check_task = asyncio.create_task(self._check_connections_loop())
        
        logger.info(f"客户端 {client_id} 已连接，当前连接数: {len(self.active_connections)}")
    
    async def disconnect(self, client_id: str):
        """断开WebSocket连接"""
        if client_id not in self.active_connections:
            return
            
        try:
            # 先关闭WebSocket连接
            websocket = self.active_connections[client_id]
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1000)
        except Exception as e:
            logger.error(f"关闭WebSocket连接失败: {e}")
        finally:
            # 清理连接相关数据
            self.active_connections.pop(client_id, None)
            self.last_activity.pop(client_id, None)
            self.client_tasks.pop(client_id, None)
            
            # 更新客户端在线状态
            await SpiderClientService().update_client_online_status(client_id, False)
            
            logger.info(f"客户端 {client_id} 已断开连接，当前连接数: {len(self.active_connections)}")
            
            # 如果没有活跃连接，停止心跳任务
            if not self.active_connections and self.heartbeat_task:
                self.heartbeat_task.cancel()
                self.heartbeat_task = None
            
            # 如果没有活跃连接，停止检查任务
            if not self.active_connections and self.check_task:
                self.check_task.cancel()
                self.check_task = None

    async def _heartbeat_loop(self):
        """心跳循环任务"""
        try:
            while True:
                if self.active_connections:
                    await self.send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)  # 使用配置的心跳间隔
        except asyncio.CancelledError:
            logger.info("心跳任务已停止")
        except Exception as e:
            logger.error(f"心跳任务异常: {e}")
            
    async def _check_connections_loop(self):
        """连接检查循环任务"""
        try:
            while True:
                if self.active_connections:
                    await self.check_connections(timeout_seconds=self.connection_timeout)
                await asyncio.sleep(self.check_interval)  # 使用配置的检查间隔
        except asyncio.CancelledError:
            logger.info("连接检查任务已停止")
        except Exception as e:
            logger.error(f"连接检查任务异常: {e}")

    async def handle_disconnect(self, client_id: str, code: int = 1000, reason: str = ""):
        """处理客户端断开连接"""
        if client_id not in self.active_connections:
            logger.debug(f"客户端 {client_id} 已经断开连接，无需重复处理")
            return
            
        logger.info(f"客户端 {client_id} 断开连接，代码: {code}, 原因: {reason}")
        await self.disconnect(client_id)

    async def send_message(self, client_id: str, message: dict):
        """向指定客户端发送消息"""
        if client_id not in self.active_connections:
            logger.warning(f"客户端 {client_id} 未连接，无法发送消息")
            return False
        
        try:
            websocket = self.active_connections[client_id]
            # 检查连接状态
            if websocket.client_state == WebSocketState.DISCONNECTED:
                logger.warning(f"客户端 {client_id} 连接已断开，无法发送消息")
                await self.disconnect(client_id)
                return False
                
            message_str = json.dumps(message)
            await websocket.send_text(message_str)
            self.last_activity[client_id] = datetime.now().timestamp()
            logger.debug(f"向客户端 {client_id} 发送消息: {message.get('cmd')}")
            return True
        except Exception as e:
            logger.error(f"向客户端 {client_id} 发送消息失败: {e}")
            await self.disconnect(client_id)
            return False
    
    async def broadcast(self, message: dict, exclude: List[str] = None):
        """向所有客户端广播消息"""
        exclude = exclude or []
        message_str = json.dumps(message)
        
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            if client_id in exclude:
                continue
                
            try:
                # 检查连接状态
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    disconnected_clients.append(int(client_id))
                    continue
                    
                await websocket.send_text(message_str)
                self.last_activity[client_id] = datetime.now().timestamp()
            except Exception as e:
                logger.error(f"向客户端 {client_id} 广播消息失败: {e}")
                disconnected_clients.append(int(client_id))
        
        # 清理断开连接的客户端
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    async def send_heartbeat(self):
        """发送心跳检测消息给所有客户端"""
        heartbeat_message = {
            "cmd": "heartbeat",
            "data": {},
            "timestamp": datetime.now().timestamp()
        }
        await self.broadcast(heartbeat_message)
    
    async def check_connections(self, timeout_seconds: int = 60):
        """检查超时的连接并断开"""
        current_time = datetime.now().timestamp()
        
        disconnected_clients = []
        for client_id, last_active in self.last_activity.items():
            if current_time - last_active > timeout_seconds:
                logger.warning(f"客户端 {client_id} 超时未活动，断开连接")
                disconnected_clients.append(int(client_id))
        
        # 断开超时连接
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    def get_client_tasks(self, client_id: str) -> List[str]:
        """获取客户端正在执行的任务列表"""
        return self.client_tasks.get(client_id, [])
    
    def add_client_task(self, client_id: str, task_id: str):
        """添加客户端任务"""
        if client_id not in self.client_tasks:
            self.client_tasks[client_id] = []
        
        if task_id not in self.client_tasks[client_id]:
            self.client_tasks[client_id].append(task_id)
    
    def remove_client_task(self, client_id: str, task_id: str):
        """移除客户端任务"""
        if client_id in self.client_tasks and task_id in self.client_tasks[client_id]:
            self.client_tasks[client_id].remove(task_id)
    
    def is_client_connected(self, client_id: str) -> bool:
        """检查客户端是否已连接"""
        return client_id in self.active_connections
    
    def get_connected_clients(self) -> List[str]:
        """获取所有已连接的客户端ID列表"""
        return list(self.active_connections.keys())