import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

from loguru import logger

from server.app.core.WebSocketManager import WebSocketManager
from server.app.core.command_generator import CommandGenerator
from server.app.services.ClientTaskService import ClientTaskService, client_task_service
from server.app.services.SpiderClientService import SpiderClientService
from server.app.services.SpiderTaskService import SpiderTaskService, spider_task_service


class TaskScheduler:
    """任务调度器，负责任务的自动调度和分发"""
    
    # 单例实例
    _instance = None
    
    def __new__(cls, websocket_manager: WebSocketManager = None):
        if cls._instance is None:
            cls._instance = super(TaskScheduler, cls).__new__(cls)
            # 在这里初始化一次，避免在__init__中重复初始化
            cls._instance.websocket_manager = websocket_manager or WebSocketManager()
            cls._instance.command_generator = CommandGenerator()
            cls._instance.running = False
            cls._instance.schedule_task = None
            cls._instance.check_interval = 15  # 检查任务的周期（秒）
            cls._instance.heartbeat_interval = 30  # 心跳检测周期（秒）
            cls._instance.assigned_tasks = {}
            logger.info("TaskScheduler单例已创建")
        elif websocket_manager is not None:
            # 确保WebSocketManager也是单例
            cls._instance.websocket_manager = websocket_manager
        return cls._instance
    
    def __init__(self, websocket_manager: WebSocketManager = None):
        # 已在__new__中初始化，这里不需要重复初始化
        pass
    
    async def start(self):
        """启动任务调度器"""
        if self.running:
            logger.warning("任务调度器已在运行中")
            return
        
        self.running = True
        
        # 创建调度任务
        self.schedule_task = asyncio.create_task(self.schedule_loop())
        
        # 创建心跳任务
        asyncio.create_task(self.heartbeat_loop())
        
        logger.info("任务调度器已启动")
    
    async def stop(self):
        """停止任务调度器"""
        if not self.running:
            logger.warning("任务调度器未在运行")
            return
        
        self.running = False
        
        if self.schedule_task:
            self.schedule_task.cancel()
            try:
                await self.schedule_task
            except asyncio.CancelledError:
                pass
            self.schedule_task = None
        
        logger.info("任务调度器已停止")
    
    async def schedule_loop(self):
        """调度循环"""
        try:
            while self.running:
                try:
                    # 检查可用任务
                    await self.check_available_tasks()
                    
                    # 定期检查连接状态
                    await self.websocket_manager.check_connections()
                    
                except Exception as e:
                    logger.error(f"任务调度循环出错: {e}")
                
                # 等待下一次调度
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("任务调度循环已取消")
        except Exception as e:
            logger.error(f"任务调度循环异常: {e}")
    
    async def heartbeat_loop(self):
        """心跳检测循环"""
        try:
            while self.running:
                try:
                    # 发送心跳
                    await self.websocket_manager.send_heartbeat()
                except Exception as e:
                    logger.error(f"心跳发送失败: {e}")
                
                # 等待下一次心跳
                await asyncio.sleep(self.heartbeat_interval)
                
        except asyncio.CancelledError:
            logger.info("心跳检测循环已取消")
        except Exception as e:
            logger.error(f"心跳检测循环异常: {e}")
    
    async def check_available_tasks(self):
        """检查可用任务并分配"""
        try:
            # 获取符合条件的任务
            available_tasks = await spider_task_service.get_tasks_by_status(1)  # 1表示运行中
            
            if not available_tasks:
                return
            
            logger.info(f"找到 {len(available_tasks)} 个可用任务")
            
            # 获取当前连接的客户端
            connected_clients = self.websocket_manager.get_connected_clients()
            
            if not connected_clients:
                logger.warning(f"没有可用的客户端连接，无法分配任务: {connected_clients}")
                return
            
            # 分配任务
            for task in available_tasks:
                await self.assign_task(task, connected_clients)
            
        except Exception as e:
            logger.error(f"检查可用任务失败: {e}")
    
    async def assign_task(self, task: Dict[str, Any], connected_clients: List[str]):
        """
        分配任务给客户端
        
        Args:
            task: 任务信息
            connected_clients: 已连接的客户端列表
        """
        task_id = str(task.get("id"))
        
        try:
            # 获取已分配的客户端任务记录
            client_tasks = await client_task_service.get_tasks_by_task_id(task_id)
            
            # 筛选状态为"未开始"的任务记录且对应的客户端当前在线
            available_clients = []
            for ct in client_tasks:
                client_id = str(ct["client_id"])
                
                # 只选择状态为"未开始"的任务记录
                if ct.get("status") != 0:  # 0表示未开始
                    continue
                
                logger.info(f"客户端ID: {client_id} 是否在线: {client_id in connected_clients}，{connected_clients}")
                # 检查客户端是否在线
                if client_id not in connected_clients:
                    continue
                
                # 检查客户端当前运行的任务数量
                current_tasks = self.websocket_manager.get_client_tasks(client_id)
                
                # 限制每个客户端最多执行3个任务
                if len(current_tasks) >= 3:
                    continue
                
                available_clients.append({"client_id": client_id, "client_task_id": ct["id"]})
            
            if not available_clients:
                logger.info(f"没有可用的客户端来执行任务: {task_id}")
                return
            
            logger.info(f"任务 {task_id} 将分配给 {len(available_clients)} 个客户端")
            
            # 分配任务给选定的客户端
            for client_info in available_clients:
                await self.start_client_task(task, client_info["client_id"], client_info["client_task_id"])
            asyncio.sleep(6)
        except Exception as e:
            logger.error(f"分配任务失败: {e}, 任务ID: {task_id}")
    
    async def start_client_task(self, task: Dict[str, Any], client_id: str, client_task_id: str):
        """
        启动客户端任务
        
        Args:
            task: 任务信息
            client_id: 客户端ID
            client_task_id: 客户端任务ID
        """
        task_id = str(task.get("id"))
        
        try:
            # 创建任务执行日志
            execution_log_id = await self.create_task_execution_log(task_id, client_id, client_task_id)
            
            if not execution_log_id:
                logger.error(f"创建任务执行日志失败, 任务ID: {task_id}, 客户端ID: {client_id}")
                return
            
            # 确保execution_log_id是字符串
            execution_log_id_str = str(execution_log_id)
            
            # 将client_task_id转换为整数（如果它是数字字符串）
            client_task_id_int = int(client_task_id) if isinstance(client_task_id, str) and client_task_id.isdigit() else client_task_id
            
            # 使用字符串格式的当前时间
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新客户端任务状态
            update_data = {
                "status": 1,  # 1表示运行中
                "start_time": now,
                "task_log_id": execution_log_id  # 记录日志ID
            }
            success = await client_task_service.update_task(client_task_id_int, update_data)
            
            if not success:
                logger.error(f"更新客户端任务状态失败, 任务ID: {task_id}, 客户端ID: {client_id}")
                return
            
            # 记录任务分配
            if task_id not in self.assigned_tasks:
                self.assigned_tasks[task_id] = {}
            self.assigned_tasks[task_id][client_id] = 1  # 1表示正在执行
            
            # 在WebSocketManager中记录任务
            self.websocket_manager.add_client_task(client_id, task_id)
            
            # 构建任务数据
            task_data = {
                "task_id": task_id,
                "task_type": task.get("task_type"),
                "platform_id": task.get("platform_id"),
                "client_task_id": str(client_task_id),  # 确保是字符串
                "execution_log_id": execution_log_id_str,  # 确保是字符串
                "title": task.get("spider_task_title", ""),
                "start_time": task.get("start_time").strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": task.get("end_time").strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 生成任务开始指令
            start_message = self.command_generator.generate_task_start(task_id, task_data)
            # 发送任务开始指令
            success = await self.websocket_manager.send_message(client_id, start_message)
            
            if success:
                logger.info(f"已向客户端 {client_id} 发送任务开始指令, 任务ID: {task_id}")
            else:
                logger.error(f"向客户端 {client_id} 发送任务开始指令失败, 任务ID: {task_id}")
                
                # 发送失败，更新任务状态
                await client_task_service.update_task_status(client_task_id, 3)  # 3表示失败
                
                # 移除任务记录
                self.assigned_tasks[task_id].pop(client_id, None)
                self.websocket_manager.remove_client_task(client_id, task_id)
            
        except Exception as e:
            logger.error(f"启动客户端任务失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
    
    async def create_task_execution_log(self, task_id: int, client_id: int, client_task_id: int) -> Optional[int]:
        """
        创建任务执行日志
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            client_task_id: 客户端任务ID
            
        Returns:
            执行日志ID (整数)
        """
        try:
            
            # 使用格式化字符串而不是datetime对象
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_data = {
                "client_task_id": client_task_id,
                "client_id": client_id,
                "task_id": task_id,
                "start_time": now,
                "total_num": 0,    # 初始化为0，后续更新
                "fail_num": 0,     # 初始化为0，后续更新
                "succ_num": 0,     # 初始化为0，后续更新
                "status": 1,       # 1表示运行中
                "create_time": now,
                "update_time": now
            }
            
            # 使用DAO方法创建记录
            log_id = await client_task_service.create_execution_log(log_data)
            logger.info(f"创建执行日志成功: ID = {log_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"创建任务执行日志失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return None
    
    async def stop_client_task(self, task_id: str, client_id: str, reason: str = ""):
        """
        停止客户端任务
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            reason: 停止原因
        """
        try:
            # 检查客户端是否仍然连接
            if not self.websocket_manager.is_client_connected(client_id):
                logger.warning(f"客户端 {client_id} 已断开连接，无法停止任务 {task_id}")
                return False
            
            # 生成任务停止指令
            stop_message = self.command_generator.generate_task_stop(task_id, reason)
            
            # 发送任务停止指令
            success = await self.websocket_manager.send_message(client_id, stop_message)
            
            if success:
                logger.info(f"已向客户端 {client_id} 发送任务停止指令, 任务ID: {task_id}")
                
                # 获取客户端任务信息
                client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
                if client_task:
                    # 更新客户端任务状态
                    await client_task_service.update_task_status(client_task["id"], 3)  # 3表示停止/失败
                    
                    # 使用字符串格式的当前时间
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 如果有任务执行日志ID，更新执行日志状态
                    task_log_id = client_task.get("task_log_id")
                    if task_log_id:
                        execution_data = {
                            "status": 3,  # 3表示停止/失败
                            "completed_time": now,
                            "result": f"任务被手动停止: {reason}" if reason else "任务被手动停止",
                            "update_time": now
                        }
                        await client_task_service.update_execution_record(task_log_id, execution_data)
                
                # 移除任务记录
                if task_id in self.assigned_tasks and client_id in self.assigned_tasks[task_id]:
                    self.assigned_tasks[task_id].pop(client_id)
                
                self.websocket_manager.remove_client_task(client_id, task_id)
                
                return True
            else:
                logger.error(f"向客户端 {client_id} 发送任务停止指令失败, 任务ID: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"停止客户端任务失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False
    
    async def stop_task(self, task_id: str, reason: str = ""):
        """
        停止任务的所有客户端执行
        
        Args:
            task_id: 任务ID
            reason: 停止原因
        """
        try:
            # 获取正在执行该任务的所有客户端
            if task_id in self.assigned_tasks:
                client_ids = list(self.assigned_tasks[task_id].keys())
                
                logger.info(f"将停止任务 {task_id} 在 {len(client_ids)} 个客户端上的执行")
                
                # 停止所有客户端上的任务
                for client_id in client_ids:
                    await self.stop_client_task(task_id, client_id, reason)
                
                # 清理任务记录
                self.assigned_tasks.pop(task_id, None)
            
            # 获取所有与该任务相关的客户端任务记录，包括那些可能未分配的记录
            client_tasks = await client_task_service.get_tasks_by_task_id(task_id)
            
            # 使用字符串格式的当前时间
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新所有未完成的客户端任务状态为停止
            for client_task in client_tasks:
                if client_task.get("status") in [0, 1]:  # 0未开始，1运行中
                    client_task_id = client_task.get("id")
                    await client_task_service.update_task_status(client_task_id, 3)  # 3表示停止/失败
                    
                    # 如果有任务执行日志ID，更新执行日志状态
                    task_log_id = client_task.get("task_log_id")
                    if task_log_id:
                        execution_data = {
                            "status": 3,  # 3表示停止/失败
                            "completed_time": now,
                            "result": f"任务被手动停止: {reason}" if reason else "任务被手动停止",
                            "update_time": now
                        }
                        await client_task_service.update_execution_record(task_log_id, execution_data)
            
            # 更新任务状态
            await spider_task_service.update_task_status(task_id, 0)  # 0表示停止
            
            return True
            
        except Exception as e:
            logger.error(f"停止任务失败: {e}, 任务ID: {task_id}")
            return False
    
    async def update_execution_progress(self, execution_id: int, progress: int, status: int, result: str = "", total_num: int = 0, succ_num: int = 0, fail_num: int = 0) -> bool:
        """
        更新任务执行进度
        
        Args:
            execution_id: 执行记录ID
            progress: 进度(0-100)
            status: 状态
            result: 执行结果
            total_num: 总数据量
            succ_num: 成功数
            fail_num: 失败数
            
        Returns:
            是否更新成功
        """
        try:
            # 使用字符串格式的当前时间
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 更新执行记录
            execution_data = {
                "status": status,
                "update_time": now
            }

            logger.info(f"更新执行记录 {execution_id} 的进度为 {progress}")
            # 只有在提供了有效值时才更新这些字段
            if progress is not None and progress > 0:
                execution_data["progress"] = progress
            
            if total_num is not None and total_num > 0:
                execution_data["total_num"] = total_num
            
            if succ_num is not None and succ_num > 0:
                execution_data["succ_num"] = succ_num
                
            if fail_num is not None and fail_num > 0:
                execution_data["fail_num"] = fail_num
                
            if result:
                execution_data["result"] = result
            
            if status in [2, 3, 4]:  # 已完成、已停止、执行失败
                execution_data["completed_time"] = now
            
            # 获取执行记录信息
            record = await client_task_service.get_execution_record(execution_id)
            if not record:
                logger.error(f"获取执行记录失败: {execution_id}")
                return False
                
            # 更新执行记录
            success = await client_task_service.update_execution_record(execution_id, execution_data)
            
            if success:
                # 获取client_task_id并确保它是整数形式（如果它是数字字符串）
                client_task_id = record['client_task_id']
                client_task_id_int = int(client_task_id) if isinstance(client_task_id, str) and client_task_id.isdigit() else client_task_id
                
                # 更新客户端任务的最新状态
                client_task_data = {
                    "status": status,
                    "progress": progress,
                    "update_time": now
                }
                
                if status in [2, 3, 4]:  # 已完成、已停止、执行失败
                    client_task_data["end_time"] = now
                    
                if result:
                    client_task_data["result"] = result
                
                await client_task_service.update_task(client_task_id_int, client_task_data)
            
            return success
            
        except Exception as e:
            logger.error(f"更新任务执行进度失败: {e}")
            return False

    async def dispatch_task(self, task_id: str, client_id: Optional[str] = None) -> bool:
        """
        手动分发任务
        
        Args:
            task_id: 任务ID
            client_id: 指定的客户端ID，如果为None则自动选择可用客户端
            
        Returns:
            是否分发成功
        """
        try:
            # 获取任务信息
            task = await spider_task_service.get_task_by_id(task_id)
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return False
            
            # 如果未指定客户端，选择一个可用的客户端
            if not client_id:
                available_clients = await SpiderClientService().get_available_clients()
                if not available_clients:
                    logger.error("没有可用的客户端")
                    return False
                client = available_clients[0]
                client_id = client['id']
            
            # 检查客户端是否在线
            if not self.websocket_manager.is_client_connected(client_id):
                logger.error(f"客户端 {client_id} 不在线")
                return False
            
            # 检查客户端当前任务数
            current_tasks = len(self.websocket_manager.get_client_tasks(client_id))
            if current_tasks >= 3:
                logger.error(f"客户端 {client_id} 任务数已达上限")
                return False
            
            # 创建客户端任务
            client_task_data = {
                "client_id": client_id,
                "task_id": task_id,
                "status": 0,
                "start_time": datetime.now()
            }
            
            client_task_id = await client_task_service.create_task(client_task_data)
            
            if client_task_id:
                # 更新任务状态为执行中
                await spider_task_service.update_task_status(task_id, 1)
                
                # 发送任务到客户端
                task_message = self.command_generator.generate_message(
                    cmd="execute_task",
                    data={
                        "task_id": task_id,
                        "client_task_id": str(client_task_id),  # 转为字符串确保兼容性
                        "task_config": task
                    },
                    client_id=client_id
                )
                
                await self.websocket_manager.send_message(client_id, task_message)
                logger.info(f"已将任务 {task_id} 分配给客户端 {client_id}")
                
                # 添加到客户端任务列表
                self.websocket_manager.add_client_task(client_id, task_id)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"手动分发任务失败: {e}")
            return False
            
    async def resume_client_tasks(self, client_id: str):
        """
        恢复客户端正在执行的任务
        
        Args:
            client_id: 客户端ID
        """
        try:
            # 获取该客户端所有状态为"正在执行"的任务
            client_tasks = await client_task_service.get_tasks_by_client_id(client_id)
            running_tasks = [task for task in client_tasks if task.get("status") == 1]  # 状态1表示正在执行
            
            if not running_tasks:
                logger.info(f"客户端 {client_id} 没有正在执行的任务")
                return
            
            logger.info(f"客户端 {client_id} 有 {len(running_tasks)} 个正在执行的任务，将恢复执行")
            
            # 恢复任务执行
            for task in running_tasks:
                task_id = task.get("task_id")
                
                # 获取完整的任务信息
                spider_task = await spider_task_service.get_task_by_id(task_id)
                if not spider_task:
                    logger.warning(f"找不到任务信息: {task_id}")
                    continue
                    
                # 检查任务是否仍在运行状态
                if spider_task.get("status") != 1:  # 状态1表示运行中
                    logger.info(f"任务 {task_id} 状态不是运行中，跳过")
                    continue
                
                # 恢复客户端任务
                await self.resume_client_task(spider_task, client_id, task)
                
        except Exception as e:
            logger.error(f"恢复客户端任务失败: {e}, 客户端ID: {client_id}")
            
    async def resume_client_task(self, spider_task: Dict[str, Any], client_id: str, client_task: Dict[str, Any]):
        """
        恢复单个客户端任务
        
        Args:
            spider_task: 爬虫任务信息
            client_id: 客户端ID
            client_task: 客户端任务信息
        """
        try:
            task_id = str(spider_task.get("id"))
            client_task_id = client_task.get("id")
            
            # 在WebSocketManager中记录任务
            self.websocket_manager.add_client_task(client_id, task_id)
            
            # 记录任务分配
            if task_id not in self.assigned_tasks:
                self.assigned_tasks[task_id] = {}
            self.assigned_tasks[task_id][client_id] = 1  # 1表示正在执行
            
            # 处理task_config，可能是JSON字符串或已经是字典
            task_config = spider_task.get("task_config", {})
            if isinstance(task_config, str):
                try:
                    task_config = json.loads(task_config)
                except json.JSONDecodeError:
                    logger.warning(f"任务配置解析失败: {task_id}")
                    task_config = {}
            
            # 生成任务开始指令
            task_start_message = self.command_generator.generate_task_start(
                task_id, 
                {
                    "spider_task_title": spider_task.get("spider_task_title", ""),
                    "task_config": task_config,
                    "platform_id": spider_task.get("platform_id"),
                    "task_type": spider_task.get("task_type", 0),
                    "priority": spider_task.get("priority", 0),
                    "client_task_id": str(client_task_id),
                    "resume": True  # 标记这是恢复的任务
                }
            )
            
            # 发送任务开始指令
            success = await self.websocket_manager.send_message(client_id, task_start_message)
            
            if success:
                logger.info(f"已向客户端 {client_id} 发送任务 {task_id} 的恢复指令")
                
                # 更新执行记录状态
                task_log_id = client_task.get("task_log_id")
                if task_log_id:
                    # 更新执行记录状态为运行中
                    await self.update_execution_progress(
                        task_log_id,
                        progress=client_task.get("progress", 0),
                        status=1,  # 状态1表示运行中
                        result="任务已恢复执行"
                    )
            else:
                logger.error(f"向客户端 {client_id} 发送任务恢复指令失败, 任务ID: {task_id}")
                
                # 发送失败，更新任务状态
                await client_task_service.update_task_status(client_task_id, 3)  # 3表示失败
                
                # 移除任务记录
                self.assigned_tasks[task_id].pop(client_id, None)
                self.websocket_manager.remove_client_task(client_id, task_id)
                
        except Exception as e:
            logger.error(f"恢复客户端任务失败: {e}, 任务ID: {spider_task.get('id')}, 客户端ID: {client_id}") 