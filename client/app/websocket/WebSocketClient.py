import asyncio
import json
import os
import queue
import time
from datetime import datetime
from typing import Dict, Callable

import websockets
from loguru import logger

from client.app.utils import TimeUtil


class WebSocketClient:
    """WebSocket客户端，负责与服务端建立WebSocket连接，处理消息收发"""
    
    def __init__(self, token, message_queue: queue.Queue):
        self.url = os.getenv('WEBSOCKET_URL', 'ws://127.0.0.1:8000/ws')
        self.websocket = None
        self.token = token
        self.lock = asyncio.Lock()  # 锁，防止并发线程冲突
        self.message_queue = message_queue  # 接收到的消息队列
        self.running = True
        self.connected = False
        
        # 心跳相关设置
        self.last_heartbeat_sent = 0
        self.last_heartbeat_received = 0
        self.heartbeat_interval = 20  # 心跳间隔，缩短为20秒
        self.heartbeat_timeout = 45   # 心跳超时时间，缩短为45秒
        
        # 重连设置
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 0  # 最大重连次数，0：不限制
        self.reconnect_delay = 5  # 初始重连延迟(秒)
        self.max_reconnect_delay = 60  # 最大重连延迟(秒)
        
        # 状态回调函数
        self.status_callback = None
        
        # 消息ID计数器
        self.message_id_counter = 0
        # 消息确认字典 {message_id: (timestamp, message)}
        self.pending_messages: Dict[int, tuple] = {}
        # 消息重试次数 {message_id: retry_count}
        self.message_retry_counts: Dict[int, int] = {}
        # 最大重试次数
        self.max_message_retries = 3

    def set_status_callback(self, callback: Callable[[bool], None]):
        """设置连接状态回调函数"""
        self.status_callback = callback

    async def connect(self):
        """建立WebSocket连接并保持监听"""
        while self.running:
            try:
                # 准备连接头信息
                headers = {
                    "Authorization": f"Bearer {self.token}"
                }
                
                # 尝试连接
                logger.info(f"正在连接到WebSocket服务器: {self.url}")
                # 使用兼容性更好的方式连接
                try:
                    # 首先尝试使用extra_headers参数（更新版本的websockets库）
                    self.websocket = await websockets.connect(self.url, extra_headers=headers)
                except TypeError as e:
                    if "extra_headers" in str(e):
                        # 如果不支持extra_headers，使用兼容方式
                        logger.info("websockets库不支持extra_headers参数，尝试使用替代方式")
                        uri = f"{self.url}?token={self.token}"
                        self.websocket = await websockets.connect(uri)
                    else:
                        # 其他类型错误，重新抛出
                        raise
                
                self.connected = True
                self.reconnect_attempts = 0
                self.reconnect_delay = 5
                self.last_heartbeat_sent = time.time()
                self.last_heartbeat_received = time.time()
                logger.info("WebSocket连接成功")
                
                # 调用状态回调
                if self.status_callback:
                    self.status_callback(True)
                
                # 启动心跳任务
                heartbeat_task = asyncio.create_task(self.send_heartbeat())
                
                # 启动消息重试任务
                retry_task = asyncio.create_task(self.retry_pending_messages())
                
                # 启动连接监控任务
                monitor_task = asyncio.create_task(self.monitor_connection())
                
                # 消息接收循环
                while self.running and self.connected:
                    try:
                        # 设置接收超时
                        message = await asyncio.wait_for(self.websocket.recv(), timeout=self.heartbeat_interval + 5)
                        
                        # 处理接收到的消息
                        try:
                            message_obj = json.loads(message)
                            
                            # 处理心跳消息
                            if message_obj.get("cmd") == "heartbeat":
                                self.last_heartbeat_received = time.time()
                                # 响应心跳
                                await self.send_heartbeat_response()
                                continue
                            
                            # 处理心跳响应消息
                            if message_obj.get("cmd") == "heartbeat_response":
                                self.last_heartbeat_received = time.time()
                                continue
                            
                            # 处理消息确认
                            if message_obj.get("cmd") == "confirm_message":
                                message_id = message_obj.get("message_id")
                                if message_id is not None:
                                    self.confirm_message(message_id)
                                continue
                            
                            # 将其他消息放入队列
                            logger.debug(f"接收到消息: {message_obj.get('cmd', '')}")
                            self.message_queue.put(message_obj)
                            
                        except json.JSONDecodeError:
                            logger.error(f"无效的JSON消息: {message}")
                    
                    except asyncio.TimeoutError:
                        # 接收超时，不做处理，连接监控任务会检查连接状态
                        pass
                    
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(f"WebSocket连接已关闭: 代码 {e.code}, 原因: {e.reason}")
                        self.connected = False
                        break
                
                # 取消任务
                for task in [heartbeat_task, retry_task, monitor_task]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                
                # 重置连接状态
                self.connected = False
                
                # 调用状态回调
                if self.status_callback:
                    self.status_callback(False)
                
                # 如果客户端仍在运行，则尝试重连
                if self.running:
                    await self.reconnect()
                
            except Exception as e:
                logger.error(f"WebSocket连接失败: {e}")
                self.connected = False
                
                # 调用状态回调
                if self.status_callback:
                    self.status_callback(False)
                
                # 如果客户端仍在运行，则尝试重连
                if self.running:
                    await self.reconnect()

    async def reconnect(self):
        """重连逻辑"""
        if not self.running:
            return
            
        # 增加重连延迟，指数退避策略
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), self.max_reconnect_delay)
        
        logger.info(f"将在 {delay} 秒后尝试重新连接 (第 {self.reconnect_attempts} 次尝试)")
        await asyncio.sleep(delay)
        
        # 检查最大重试次数
        if self.max_reconnect_attempts > 0 and self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error(f"达到最大重连尝试次数 ({self.max_reconnect_attempts})，停止重连")
            self.running = False
            return

    async def monitor_connection(self):
        """监控连接状态"""
        while self.running and self.connected:
            try:
                await asyncio.sleep(10)  # 每10秒检查一次
                
                # 主动检测连接状态
                is_connected = await self.check_connection()
                if not is_connected:
                    continue
                    
                current_time = time.time()
                # 如果长时间未收到心跳响应
                if current_time - self.last_heartbeat_received > self.heartbeat_timeout:
                    logger.warning(f"心跳超时：{int(current_time - self.last_heartbeat_received)}秒未收到心跳响应")
                    # 标记连接已断开
                    self.connected = False
                    # 尝试关闭连接
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    # 终止循环
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"连接监控异常: {e}")

    async def check_connection(self):
        """主动检查连接状态"""
        try:
            if self.websocket and self.connected:
                # 发送ping帧检测连接
                pong_waiter = await self.websocket.ping()
                await asyncio.wait_for(pong_waiter, timeout=5)
                return True
        except Exception as e:
            logger.warning(f"连接检测失败: {e}")
            # 连接已断开
            self.connected = False
            return False
        return self.connected

    async def send(self, message, require_confirmation=False):
        """发送消息到服务器"""
        if not self.connected or self.websocket is None:
            logger.warning("WebSocket未连接，无法发送消息")
            return False
            
        try:
            # 如果输入是字典，转换为JSON字符串
            if isinstance(message, dict):
                # 添加时间戳
                if "timestamp" not in message:
                    message["timestamp"] = datetime.now().timestamp()
                
                message_str = json.dumps(message)
            else:
                message_str = message
                
            # 发送消息
            async with self.lock:
                await self.websocket.send(message_str)
                
            # 如果需要确认，记录消息
            if require_confirmation and isinstance(message, dict):
                message_id = self.get_next_message_id()
                message["message_id"] = message_id
                self.pending_messages[message_id] = (time.time(), message)
                self.message_retry_counts[message_id] = 0
            
            logger.debug(f"已发送消息: {message.get('cmd', '')} task_id: {message.get('task_id')}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False
            return False

    async def send_heartbeat(self):
        """定期发送心跳消息"""
        while self.running and self.connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self.connected or not self.running:
                    logger.debug("连接已断开或客户端已停止，心跳任务退出")
                    break
                    
                if self.connected and self.websocket is not None:
                    heartbeat_message = {
                        "cmd": "heartbeat_response",
                        "data": {},
                        "timestamp": datetime.now().timestamp()
                    }
                    success = await self.send(heartbeat_message)
                    if success:
                        self.last_heartbeat_sent = time.time()
                        logger.debug(f"已发送心跳消息，上次接收心跳时间: {datetime.fromtimestamp(self.last_heartbeat_received).strftime('%H:%M:%S')}")
            except asyncio.CancelledError:
                # 协程被取消，退出循环
                break
            except Exception as e:
                logger.error(f"发送心跳失败: {e}")
                # 如果连接有问题，等待一小段时间
                await asyncio.sleep(1)

    async def send_heartbeat_response(self):
        """响应服务器心跳"""
        heartbeat_response = {
            "cmd": "heartbeat_response",
            "data": {},
            "timestamp": datetime.now().timestamp()
        }
        await self.send(heartbeat_response)

    async def retry_pending_messages(self):
        """重发未确认的消息"""
        while self.running and self.connected:
            try:
                # 每5秒检查一次
                await asyncio.sleep(5)
                
                current_time = time.time()
                message_ids_to_remove = []
                
                # 检查所有待确认消息
                for message_id, (timestamp, message) in self.pending_messages.items():
                    # 如果消息已经超过30秒未收到确认
                    if current_time - timestamp > 30:
                        retry_count = self.message_retry_counts.get(message_id, 0)
                        
                        # 检查是否超过最大重试次数
                        if retry_count >= self.max_message_retries:
                            logger.warning(f"消息 {message_id} 达到最大重试次数，放弃重试")
                            message_ids_to_remove.append(message_id)
                        else:
                            # 增加重试次数
                            self.message_retry_counts[message_id] = retry_count + 1
                            # 更新时间戳
                            self.pending_messages[message_id] = (current_time, message)
                            # 重新发送消息
                            logger.info(f"重新发送消息 {message_id} (第 {retry_count + 1} 次尝试)")
                            await self.send(message, require_confirmation=False)
                
                # 移除已放弃的消息
                for message_id in message_ids_to_remove:
                    self.pending_messages.pop(message_id, None)
                    self.message_retry_counts.pop(message_id, None)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"重试消息异常: {e}")

    def get_next_message_id(self):
        """获取下一个消息ID"""
        self.message_id_counter += 1
        return self.message_id_counter

    def confirm_message(self, message_id):
        """确认消息已收到"""
        logger.debug(f"确认消息 {message_id}")
        self.pending_messages.pop(message_id, None)
        self.message_retry_counts.pop(message_id, None)

    async def close(self):
        """关闭WebSocket连接"""
        logger.info("关闭WebSocket连接")
        self.running = False
        self.connected = False
        
        # 关闭主WebSocket连接
        if self.websocket is not None:
            try:
                await self.websocket.close()
                self.websocket = None
            except Exception as e:
                logger.error(f"关闭主WebSocket连接失败: {e}")

    def start(self):
        """启动客户端（非阻塞方式）"""
        logger.info("启动WebSocket客户端")
        self.running = True
