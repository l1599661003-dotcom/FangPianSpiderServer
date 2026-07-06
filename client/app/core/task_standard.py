from typing import Dict, Any, List, Optional, Tuple
from abc import abstractmethod
from loguru import logger

from client.app.core.task_base import BaseTask


class StandardTask(BaseTask):
    """
    标准任务基类，提供通用实现
    
    适用于处理列表类型数据的任务，与原BaseTask行为一致，
    但使用新的处理接口，可以让现有子类平滑迁移
    """
    
    async def preprocess_data(self, data: Any) -> List[Dict[str, Any]]:
        """
        预处理数据，将任意数据格式转换为标准的列表格式
        
        Args:
            data: 原始数据
            
        Returns:
            处理后的数据列表
        """
        if not data:
            return []
        
        # 如果数据不是列表类型，尝试将其转换为列表
        if not isinstance(data, list):
            if isinstance(data, dict):
                return [data]
            else:
                try:
                    return list(data)
                except:
                    return [data]
        
        return data
    
    async def calculate_data_count(self, data: List[Dict[str, Any]]) -> int:
        """
        计算数据总量
        
        Args:
            data: 预处理后的数据
            
        Returns:
            数据总量
        """
        return len(data)
    
    async def has_pending_data(self) -> bool:
        """
        检查是否有待处理的数据
        
        Returns:
            是否有待处理的数据
        """
        return bool(self.current_batch_data)
    
    async def clear_current_batch(self):
        """
        清除当前批次数据
        """
        self.current_batch_data = None
    
    async def process_batch(self, data: List[Dict[str, Any]], batch_id: str) -> Tuple[bool, int, int]:
        """
        处理整个批次数据
        
        Args:
            data: 批次数据
            batch_id: 批次ID
            
        Returns:
            (是否成功, 成功处理的数据量, 失败的数据量)
        """
        success_count = 0
        fail_count = 0
        total_items = len(data)
        batch_success = True
        
        for index, item in enumerate(data):
            if not self.running:
                logger.info(f"任务已停止，中断数据处理，任务ID: {self.task_id}")
                break
            
            try:
                # 调用子类的数据处理方法
                result = await self.process_item(item, batch_id)
                
                # 更新计数
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                    batch_success = False
                
                # 更新进度
                progress = (index + 1) / total_items * 100
                if index % 10 == 0 or index == total_items - 1:  # 每10条数据或最后一条数据时上报进度
                    await self.report_progress(progress)
                    
            except Exception as e:
                fail_count += 1
                batch_success = False
                logger.error(f"处理数据项失败: {e}, 任务ID: {self.task_id}, 数据: {item}")
                
                # 上报错误
                await self.report_error("PROCESS_ITEM_ERROR", f"处理数据项失败: {str(e)}", batch_id)
        
        return batch_success, success_count, fail_count
    
    async def calculate_progress(self) -> float:
        """
        计算当前进度
        
        Returns:
            进度百分比
        """
        if self.total_count > 0:
            return (self.success_count + self.fail_count) / self.total_count * 100
        else:
            return 0
    
    @abstractmethod
    async def process_item(self, item: Dict[str, Any], batch_id: str) -> bool:
        """
        处理单个数据项
        
        Args:
            item: 数据项
            batch_id: 批次ID
            
        Returns:
            处理是否成功
        """
        pass 