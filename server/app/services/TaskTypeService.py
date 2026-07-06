from typing import Dict, Any, Optional
from loguru import logger

from server.app.services.SpiderTaskService import spider_task_service


class TaskTypeService:
    """任务类型服务，用于获取任务的类型信息"""
    
    async def get_task_type(self, task_id: str) -> Optional[str]:
        """
        获取任务类型
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务类型，如果未找到返回None
        """
        try:
            # 获取任务信息
            task_info = await spider_task_service.get_task(task_id)
            if not task_info:
                logger.warning(f"未找到任务: {task_id}")
                return None
                
            # 获取任务类型
            task_type = task_info.get("task_type")
            if not task_type:
                logger.warning(f"任务未设置类型: {task_id}")
                return None
                
            return task_type
            
        except Exception as e:
            logger.error(f"获取任务类型失败: {e}, 任务ID: {task_id}")
            return None
    
    def normalize_task_type(self, task_type: str) -> str:
        """
        规范化任务类型
        
        Args:
            task_type: 原始任务类型
            
        Returns:
            规范化后的任务类型
        """
        # 将任务类型转为小写并去掉空格
        normalized = task_type.lower().strip()
        
        # 常见的任务类型映射
        type_mapping = {
            "bloggerinfo": "blogger_info",
            "blogger-info": "blogger_info",
            "bloggerdetail": "blogger_detail",
            "blogger-detail": "blogger_detail",
            "bloggerworks": "blogger_works",
            "blogger-works": "blogger_works",
            "commentinfo": "comment_info",
            "comment-info": "comment_info"
        }
        
        # 如果在映射表中，返回映射结果
        if normalized in type_mapping:
            return type_mapping[normalized]
            
        # 否则返回原始类型
        return normalized


# 创建单例实例
task_type_service = TaskTypeService() 