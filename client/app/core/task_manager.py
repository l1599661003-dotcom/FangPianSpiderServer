import asyncio
from typing import Dict, Any, List, Optional, Callable, Type
from loguru import logger

from client.app.core.task_base import BaseTask


class TaskManager:
    """任务管理器，用于管理所有任务"""
    
    def __init__(self):
        """初始化任务管理器"""
        # 活跃任务映射 {task_id: task}
        self.active_tasks: Dict[str, BaseTask] = {}
        # 任务工厂映射 {task_type: task_factory}
        self.task_factories: Dict[str, Callable] = {}
        # 任务类型映射 {task_type: task_class}
        self.task_classes: Dict[int, Type[BaseTask]] = {}
        # 命令处理器引用，后续设置
        self.command_handler = None
    
    def set_command_handler(self, command_handler):
        """
        设置命令处理器
        
        Args:
            command_handler: 命令处理器
        """
        self.command_handler = command_handler
    
    def register_task_class(self, task_type: int, task_class: Type[BaseTask]):
        """
        注册任务类型
        
        Args:
            task_type: 任务类型
            task_class: 任务类
        """
        self.task_classes[task_type] = task_class
        logger.info(f"注册任务类型: {task_type} -> {task_class.__name__}")
    
    async def start_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        启动任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            是否启动成功
        """
        try:
            # 如果任务已存在，先停止
            if task_id in self.active_tasks:
                await self.stop_task(task_id)
            
            # 获取任务类型
            task_type = task_data.get("task_type")
            platform_id = task_data.get("platform_id")

            # 检查任务类型是否支持
            if task_type not in self.task_classes:
                logger.error(f"不支持的任务类型: {task_type}, 任务ID: {task_id}")
                return False
            
            # 创建任务实例
            task_class = self.task_classes[task_type]
            task = task_class(task_id, task_data, self.command_handler, platform_id)
            
            # 存储到活跃任务
            self.active_tasks[task_id] = task

            await task.request_token()

            await asyncio.sleep(0.2, 1)

            # 初始化任务
            await task.initialize()
            
            logger.info(f"任务启动成功，任务ID: {task_id}, 类型: {task_type}")
            return True
            
        except Exception as e:
            logger.error(f"启动任务失败: {e}, 任务ID: {task_id}")
            return False
    
    async def stop_task(self, task_id: str) -> bool:
        """
        停止任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否停止成功
        """
        try:
            # 检查任务是否存在
            if task_id not in self.active_tasks:
                logger.warning(f"任务不存在，无法停止: {task_id}")
                return False
            
            # 获取任务实例
            task = self.active_tasks[task_id]
            
            # 停止任务
            await task.stop()
            
            # 从活跃任务中移除
            self.active_tasks.pop(task_id)
            
            logger.info(f"任务停止成功，任务ID: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止任务失败: {e}, 任务ID: {task_id}")
            return False
    
    async def process_data(self, task_id: str, data_list: Any, batch_id: str) -> bool:
        """
        处理任务数据
        
        Args:
            task_id: 任务ID
            data_list: 数据列表
            batch_id: 批次ID
            
        Returns:
            是否处理成功
        """
        try:
            # 检查任务是否存在
            if task_id not in self.active_tasks:
                logger.warning(f"任务不存在，无法处理数据: {task_id}")
                return False
            
            # 获取任务实例
            task = self.active_tasks[task_id]
            logger.info(f"处理任务数据，任务ID: {task_id}, 批次ID: {batch_id}11111")
            # 处理数据
            await task.process_data(data_list, batch_id)
            logger.info(f"处理任务数据，任务ID: {task_id}, 批次ID: {batch_id}22211111")
            
            return True
            
        except Exception as e:
            logger.error(f"处理任务数据失败: {e}, 任务ID: {task_id}")
            return False
    
    async def handle_error(self, task_id: str, error_code: str, error_message: str) -> bool:
        """
        处理任务错误
        
        Args:
            task_id: 任务ID
            error_code: 错误代码
            error_message: 错误消息
            
        Returns:
            是否处理成功
        """
        try:
            # 检查任务是否存在
            if task_id not in self.active_tasks:
                logger.warning(f"任务不存在，无法处理错误: {task_id}")
                return False
            
            # 获取任务实例
            task = self.active_tasks[task_id]
            
            # 处理错误
            await task.handle_error(error_code, error_message)
            
            return True
            
        except Exception as e:
            logger.error(f"处理任务错误失败: {e}, 任务ID: {task_id}")
            return False
    
    def get_task(self, task_id: str) -> Optional[BaseTask]:
        """
        获取任务实例
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务实例，如果不存在则返回None
        """
        return self.active_tasks.get(task_id)
    
    def is_task_active(self, task_id: str) -> bool:
        """
        检查任务是否活跃
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务是否活跃
        """
        return task_id in self.active_tasks
    
    async def stop_all_tasks(self):
        """停止所有任务"""
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)
        
        logger.info(f"所有任务已停止，共停止 {len(task_ids)} 个任务")
    
    async def shutdown(self):
        """关闭任务管理器"""
        await self.stop_all_tasks()
        logger.info("任务管理器已关闭")
    
    async def complete_task(self, task_id: str, data: Dict[str, Any] = None) -> bool:
        """
        完成任务
        
        Args:
            task_id: 任务ID
            data: 任务完成数据
            
        Returns:
            是否处理成功
        """
        try:
            # 检查任务是否存在
            if task_id not in self.active_tasks:
                logger.warning(f"任务不存在，无法标记为完成: {task_id}")
                return False
            
            # 获取任务实例
            task = self.active_tasks[task_id]
            
            # 标记任务为已完成
            await task.complete(data)
            
            # 从活跃任务中移除
            self.active_tasks.pop(task_id)
            
            logger.info(f"任务已标记为完成，任务ID: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"完成任务失败: {e}, 任务ID: {task_id}")
            return False 