from typing import Dict, Any, Callable
import json
from datetime import datetime
from loguru import logger

from client.app.websocket.WebSocketClient import WebSocketClient
from client.app.core.task_manager import TaskManager


class CommandHandler:
    """命令处理器，用于处理接收到的指令"""
    
    def __init__(self, websocket_client: WebSocketClient, task_manager: TaskManager):
        """
        初始化命令处理器
        
        Args:
            websocket_client: WebSocket客户端
            task_manager: 任务管理器
        """
        self.websocket_client = websocket_client
        self.task_manager = task_manager
        
        # 命令处理映射
        self.command_map: Dict[str, Callable] = {
            "task_start": self.handle_task_start,
            "task_stop": self.handle_task_stop,
            "data_push": self.handle_data_push,
            "heartbeat": self.handle_heartbeat,
            "system_message": self.handle_system_message,
            "error": self.handle_error,
            "token_response": self.handle_token_response,
            "task_complete": self.handle_task_complete
        }
    
    async def handle_command(self, command: Dict[str, Any]) -> bool:
        """
        处理命令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            cmd_type = command.get("cmd")
            
            # 检查命令ID并确认
            if "message_id" in command:
                message_id = command.get("message_id")
                self.websocket_client.confirm_message(message_id)
            
            # 分发处理
            handler = self.command_map.get(cmd_type)
            if handler:
                return await handler(command)
            else:
                logger.warning(f"未知的命令类型: {cmd_type}")
                return False
                
        except Exception as e:
            task_id = command.get("task_id", "未知")
            logger.error(f"处理命令失败: {e}, 任务ID: {task_id}")
            return False
    
    async def handle_task_start(self, command: Dict[str, Any]) -> bool:
        """
        处理任务开始指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            task_id = command.get("task_id")
            task_data = command.get("data", {})
            
            logger.info(f"接收到任务开始指令，任务ID: {task_id}")
            
            # 启动任务
            success = await self.task_manager.start_task(task_id, task_data)
            
            # 如果启动成功，请求数据
            if success:
                await self.request_data(task_id)
                
            return success
            
        except Exception as e:
            logger.error(f"处理任务开始指令失败: {e}")
            return False
    
    async def handle_task_stop(self, command: Dict[str, Any]) -> bool:
        """
        处理任务停止指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            task_id = command.get("task_id")
            reason = command.get("data", {}).get("reason", "")
            
            logger.info(f"接收到任务停止指令，任务ID: {task_id}, 原因: {reason}")
            
            # 停止任务
            return await self.task_manager.stop_task(task_id)
            
        except Exception as e:
            logger.error(f"处理任务停止指令失败: {e}")
            return False
    
    async def handle_data_push(self, command: Dict[str, Any]) -> bool:
        """
        处理数据推送指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            logger.info(f"接收到数据推送指令: {command}")
            task_id = command.get("task_id")
            data = command.get("data", {})
            data_list = data.get("data_list", {})
            result = data_list.get("items", [])
            batch_id = data.get("batch_id")
            
            logger.info(f"接收到数据推送指令，任务ID: {task_id}, 数据量: {len(data_list)}")
            
            # 处理数据
            await self.task_manager.process_data(task_id, result, batch_id)
            
            return True
            
        except Exception as e:
            logger.error(f"处理数据推送指令失败: {e}")
            return False
    
    async def handle_heartbeat(self, command: Dict[str, Any]) -> bool:
        """
        处理心跳检测指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            # 发送心跳响应
            await self.websocket_client.send_heartbeat_response()
            return True
            
        except Exception as e:
            logger.error(f"处理心跳检测指令失败: {e}")
            return False
    
    async def handle_system_message(self, command: Dict[str, Any]) -> bool:
        """
        处理系统消息指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            message = command.get("data", {}).get("message", "")
            logger.info(f"系统消息: {message}")
            return True
            
        except Exception as e:
            logger.error(f"处理系统消息指令失败: {e}")
            return False
    
    async def handle_error(self, command: Dict[str, Any]) -> bool:
        """
        处理错误指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            error_data = command.get("data", {})
            error_code = error_data.get("code", "UNKNOWN_ERROR")
            error_message = error_data.get("message", "未知错误")
            task_id = command.get("task_id")
            
            logger.error(f"服务端错误: [{error_code}] {error_message}, 任务ID: {task_id}")
            
            # 如果与任务相关，尝试停止任务
            if task_id:
                await self.task_manager.handle_error(task_id, error_code, error_message)
                
            return True
            
        except Exception as e:
            logger.error(f"处理错误指令失败: {e}")
            return False
    
    async def handle_token_response(self, command: Dict[str, Any]) -> bool:
        """
        处理令牌分配响应
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            task_id = command.get("task_id")
            data = command.get("data", {})
            token_id = data.get("token_id")
            token_content = data.get("token_content")
            
            logger.info(f"收到令牌分配响应, 任务ID: {task_id}, 令牌ID: {token_id}，令牌：{token_content}")
            
            # 检查任务是否存在
            task = self.task_manager.get_task(task_id)
            if not task:
                logger.warning(f"任务不存在，无法处理令牌响应: {task_id}")
                return False
            
            # 设置任务的令牌信息
            task.token_id = token_id
            task.token_content = token_content
            
            return True
            
        except Exception as e:
            logger.error(f"处理令牌分配响应失败: {e}")
            return False
    
    async def handle_task_complete(self, command: Dict[str, Any]) -> bool:
        """
        处理任务完成指令
        
        Args:
            command: 命令对象
            
        Returns:
            处理是否成功
        """
        try:
            task_id = command.get("task_id")
            data = command.get("data", {})
            message = data.get("message", "")
            
            logger.info(f"接收到任务完成指令，任务ID: {task_id}, 消息: {message}")
            
            # 标记任务为已完成
            success = await self.task_manager.complete_task(task_id, data)
            
            # 上报任务完成
            if success:
                await self.report_task_complete(task_id, data)
            
            return success
            
        except Exception as e:
            logger.error(f"处理任务完成指令失败: {e}")
            return False
    
    async def request_data(self, task_id: str, batch_size: int = 100):
        """
        请求任务数据
        
        Args:
            task_id: 任务ID
            batch_size: 数据批次大小
            
        Returns:
            是否发送成功
        """
        try:
            # 构建数据请求消息
            data_request = {
                "cmd": "data_request",
                "task_id": task_id,
                "data": {
                    "batch_size": batch_size
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # 发送请求
            return await self.websocket_client.send(data_request, require_confirmation=False)
            
        except Exception as e:
            logger.error(f"请求任务数据失败: {e}, 任务ID: {task_id}")
            return False
    
    async def report_progress(self, task_id: str, progress: float, batch_id: str = None):
        """
        上报任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度百分比
            batch_id: 批次ID
            
        Returns:
            是否发送成功
        """
        try:
            # 构建进度上报消息
            progress_report = {
                "cmd": "progress_report",
                "task_id": task_id,
                "data": {
                    "progress": progress,
                    "batch_id": batch_id
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # 发送上报
            return await self.websocket_client.send(progress_report)
            
        except Exception as e:
            logger.error(f"上报任务进度失败: {e}, 任务ID: {task_id}")
            return False
    
    async def report_error(self, task_id: str, error_code: str, error_message: str, batch_id: str = None):
        """
        上报任务错误
        
        Args:
            task_id: 任务ID
            error_code: 错误代码
            error_message: 错误消息
            batch_id: 批次ID
            
        Returns:
            是否发送成功
        """
        try:
            # 构建错误上报消息
            error_report = {
                "cmd": "error_report",
                "task_id": task_id,
                "data": {
                    "code": error_code,
                    "message": error_message,
                    "batch_id": batch_id
                },
                "timestamp": datetime.now().timestamp()
            }
            
            # 发送上报
            return await self.websocket_client.send(error_report, require_confirmation=False)
            
        except Exception as e:
            logger.error(f"上报任务错误失败: {e}, 任务ID: {task_id}")
            return False
    
    async def report_task_complete(self, task_id: str, result_data: Dict[str, Any] = None):
        """
        上报任务完成
        
        Args:
            task_id: 任务ID
            result_data: 结果数据
            
        Returns:
            是否发送成功
        """
        try:
            # 构建任务完成消息
            complete_report = {
                "cmd": "task_complete",
                "task_id": task_id,
                "data": result_data or {},
                "timestamp": datetime.now().timestamp()
            }
            
            # 发送上报
            return await self.websocket_client.send(complete_report, require_confirmation=False)
            
        except Exception as e:
            logger.error(f"上报任务完成失败: {e}, 任务ID: {task_id}")
            return False 