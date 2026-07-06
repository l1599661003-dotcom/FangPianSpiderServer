import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger


class BaseTask(ABC):
    """任务基类，所有具体任务需要继承此类并实现相关方法"""

    def __init__(self, task_id: str, task_data: Dict[str, Any], command_handler, platform_id: str):
        """
        初始化任务基类
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            command_handler: 命令处理器
        """
        self.task_id = task_id
        self.platform_id = task_id
        self.task_data = task_data
        self.command_handler = command_handler

        # 任务状态 0: 未开始, 1: 正在运行, 2: 已完成, 3: 已停止, 4: 出错
        self.status = 0

        # 进度信息
        self.progress = 0.0
        self.total_count = 0
        self.success_count = 0
        self.fail_count = 0

        # 当前批次信息
        self.current_batch_id = None
        self.current_batch_data = None

        # 任务开始和结束时间
        self.start_time = None
        self.end_time = None

        # 任务执行线程
        self.task_thread = None
        self.running = False

    async def initialize(self):
        """
        初始化任务
        
        在任务开始执行前调用，进行必要的初始化工作
        """
        self.status = 1
        self.start_time = datetime.now()
        self.running = True

        # 调用子类的初始化方法
        await self.on_initialize()

        logger.info(f"任务初始化成功，任务ID: {self.task_id}")

    async def process_data(self, data: Any, batch_id: str):
        """
        处理任务数据
        
        Args:
            data: 数据（任意类型）
            batch_id: 批次ID
        """
        if self.status != 1:
            logger.warning(f"任务状态不是正在运行，无法处理数据，任务ID: {self.task_id}, 状态: {self.status}")
            return

        # 更新当前批次信息
        self.current_batch_id = batch_id
        self.current_batch_data = data
        # 调用子类的数据预处理方法
        processed_data = await self.preprocess_data(data)

        # 获取数据总量（由子类决定如何计算）
        data_count = await self.calculate_data_count(processed_data)

        self.total_count += data_count

        logger.info(f"开始处理数据，任务ID: {self.task_id}, 批次ID: {batch_id}, 数据量: {data_count}")

        if data_count == 0:
            logger.info(f"当前批次没有数据，任务ID: {self.task_id}, 批次ID: {batch_id}")
            return
        # 创建处理线程（如果尚未创建）
        if self.task_thread is None:
            self.task_thread = asyncio.create_task(self.process_thread())

    async def process_thread(self):
        """数据处理线程"""
        try:
            while self.running:
                # 如果没有数据或数据已被处理，等待下一批
                if not await self.has_pending_data():
                    await asyncio.sleep(0.1)
                    continue

                # 获取当前批次数据和ID
                current_data = self.current_batch_data
                batch_id = self.current_batch_id

                # 清空当前批次，准备处理下一批
                await self.clear_current_batch()

                # 调用子类的执行方法处理整个批次数据
                success, processed_count, failed_count = await self.process_batch(current_data, batch_id)

                # 更新统计信息
                self.success_count += processed_count
                self.fail_count += failed_count

                # 批次处理完成，上报最终进度
                progress = await self.calculate_progress()
                await self.report_progress(progress)

                # 批次处理完成，调用子类的批次完成钩子
                await self.on_batch_complete(batch_id, success, processed_count, failed_count)

                # 批次处理完成，请求下一批数据
                if await self.should_request_next_batch():
                    await self.request_next_batch()

        except Exception as e:
            logger.error(f"数据处理线程异常: {e}, 任务ID: {self.task_id}")

            # 上报错误
            await self.report_error("PROCESS_THREAD_ERROR", f"数据处理线程异常: {str(e)}")

            # 设置任务状态为出错
            self.status = 4

    async def request_token(self):
        pass

    async def release_token(self):
        pass

    async def stop(self):
        """停止任务"""
        if self.status != 1:
            logger.warning(f"任务状态不是正在运行，无需停止，任务ID: {self.task_id}, 状态: {self.status}")
            return

        self.running = False
        self.status = 3
        self.end_time = datetime.now()

        # 等待处理线程结束
        if self.task_thread is not None:
            try:
                # 等待线程结束，最多等待5秒
                await asyncio.wait_for(self.task_thread, timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"等待任务线程结束超时，任务ID: {self.task_id}")
            except Exception as e:
                logger.error(f"等待任务线程结束失败: {e}, 任务ID: {self.task_id}")

            self.task_thread = None

        # 调用子类的停止方法
        await self.on_stop()

        logger.info(f"任务已停止，任务ID: {self.task_id}")

    async def complete(self, data: Dict[str, Any] = None):
        """
        完成任务
        
        Args:
            data: 完成任务的额外数据
        """
        self.status = 2
        self.end_time = datetime.now()
        self.running = False

        # 等待处理线程结束
        if self.task_thread is not None:
            try:
                # 等待线程结束，最多等待5秒
                await asyncio.wait_for(self.task_thread, timeout=5)
            except asyncio.TimeoutError:
                logger.warning(f"等待任务线程结束超时，任务ID: {self.task_id}")
            except Exception as e:
                logger.error(f"等待任务线程结束失败: {e}, 任务ID: {self.task_id}")

            self.task_thread = None

        # 调用子类的完成方法
        await self.on_complete()

        # 上报任务完成
        result_data = {
            "total_count": self.total_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None
        }

        # 合并额外数据
        if data:
            result_data.update(data)

        await self.command_handler.report_task_complete(self.task_id, result_data)

        logger.info(
            f"任务已完成，任务ID: {self.task_id}, 总数据量: {self.total_count}, 成功: {self.success_count}, 失败: {self.fail_count}")

    async def handle_error(self, error_code: str, error_message: str):
        """
        处理任务错误
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
        """
        logger.error(f"任务出错: [{error_code}] {error_message}, 任务ID: {self.task_id}")

        # 某些错误可能需要停止任务
        if error_code in ["TASK_CANCELED", "AUTHENTICATION_FAILED", "SERVER_ERROR"]:
            await self.stop()

        # 调用子类的错误处理方法
        await self.on_error(error_code, error_message)

    async def report_progress(self, batch_progress: float):
        """
        上报任务进度
        
        Args:
            batch_progress: 当前批次的进度百分比
        """
        # 更新任务总体进度
        self.progress = batch_progress

        # 上报进度
        await self.command_handler.report_progress(self.task_id, self.progress, self.current_batch_id)

    async def report_error(self, error_code: str, error_message: str, batch_id: Optional[str] = None):
        """
        上报任务错误
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
            batch_id: 批次ID
        """
        await self.command_handler.report_error(self.task_id, error_code, error_message, batch_id)

    async def request_next_batch(self):
        """请求下一批数据"""
        await self.command_handler.request_data(self.task_id)

    # 新增方法 - 由子类实现的数据处理相关方法

    @abstractmethod
    async def preprocess_data(self, data: Any) -> Any:
        """
        预处理数据
        
        Args:
            data: 原始数据
            
        Returns:
            处理后的数据，用于后续处理
        """
        pass

    @abstractmethod
    async def calculate_data_count(self, data: Any) -> int:
        """
        计算数据总量
        
        Args:
            data: 预处理后的数据
            
        Returns:
            数据总量
        """
        pass

    @abstractmethod
    async def has_pending_data(self) -> bool:
        """
        检查是否有待处理的数据
        
        Returns:
            是否有待处理的数据
        """
        pass

    @abstractmethod
    async def clear_current_batch(self):
        """
        清除当前批次数据
        """
        pass

    @abstractmethod
    async def process_batch(self, data: Any, batch_id: str) -> Tuple[bool, int, int]:
        """
        处理整个批次数据
        
        Args:
            data: 批次数据
            batch_id: 批次ID
            
        Returns:
            (是否成功, 成功处理的数据量, 失败的数据量)
        """
        pass

    @abstractmethod
    async def calculate_progress(self) -> float:
        """
        计算当前进度
        
        Returns:
            进度百分比
        """
        pass

    async def on_batch_complete(self, batch_id: str, success: bool, processed_count: int, failed_count: int):
        """
        批次处理完成钩子
        
        Args:
            batch_id: 批次ID
            success: 是否成功处理
            processed_count: 成功处理的数据量
            failed_count: 失败的数据量
        """
        pass

    async def should_request_next_batch(self) -> bool:
        """
        是否应该请求下一批数据
        
        Returns:
            是否应该请求下一批数据
        """
        return True

    # 原有抽象方法

    @abstractmethod
    async def on_initialize(self):
        """
        初始化回调
        
        子类需要实现此方法，进行特定的初始化工作
        """
        pass

    @abstractmethod
    async def on_stop(self):
        """
        停止回调
        
        子类需要实现此方法，进行特定的停止工作
        """
        pass

    @abstractmethod
    async def on_complete(self):
        """
        完成回调
        
        子类需要实现此方法，进行特定的完成工作
        """
        pass

    @abstractmethod
    async def on_error(self, error_code: str, error_message: str):
        """
        错误回调
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
        """
        pass
