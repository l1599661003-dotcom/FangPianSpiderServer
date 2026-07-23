from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.services.SpiderConfigService import SpiderConfigService
from server.app.utils.common import generate_id


class SpiderTaskService(MySQLBaseDAO):
    """爬虫任务服务，负责管理爬虫任务信息"""
    
    def __init__(self):
        super().__init__("fp_spider_task")
    
    async def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        通过ID获取爬虫任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            爬虫任务信息
        """
        try:
            query = "SELECT * FROM fp_spider_task WHERE id = :task_id"
            return await self.fetch_one(query, { "task_id": task_id })
        except Exception as e:
            logger.error(f"获取爬虫任务失败: {e}, 任务ID: {task_id}")
            return None
    
    async def get_task_by_name(self, task_name: str) -> Optional[Dict[str, Any]]:
        """
        通过名称获取爬虫任务
        
        Args:
            task_name: 任务名称
            
        Returns:
            爬虫任务信息
        """
        try:
            query = "SELECT * FROM fp_spider_task WHERE spider_task_title = :task_name"
            return await self.fetch_one(query, { "task_name": task_name })
        except Exception as e:
            logger.error(f"获取爬虫任务失败: {e}, 任务名称: {task_name}")
            return None
    
    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有爬虫任务
        
        Returns:
            爬虫任务列表
        """
        try:
            query = """
            SELECT t.*, 
                (SELECT COUNT(*) FROM fp_spider_client_task WHERE task_id = t.id) as client_count 
            FROM fp_spider_task t
            WHERE t.control_action IS NULL
            ORDER BY t.create_time DESC
            """
            return await self.fetch_all(query)
        except Exception as e:
            logger.error(f"获取所有爬虫任务失败: {e}")
            return []
    
    async def get_tasks_by_type(self, task_type: int) -> List[Dict[str, Any]]:
        """
        通过类型获取爬虫任务
        
        Args:
            task_type: 任务类型
            
        Returns:
            爬虫任务列表
        """
        try:
            query = """
            SELECT t.*, 
                (SELECT COUNT(*) FROM fp_spider_client_task WHERE task_id = t.id) as client_count 
            FROM fp_spider_task t
            WHERE t.task_type = :task_type AND t.control_action IS NULL
            ORDER BY t.create_time DESC
            """
            return await self.fetch_all(query, { "task_type": task_type})
        except Exception as e:
            logger.error(f"获取爬虫任务失败: {e}, 任务类型: {task_type}")
            return []
    
    async def get_tasks_by_status(self, status: int) -> List[Dict[str, Any]]:
        """
        通过状态获取爬虫任务
        
        Args:
            status: 任务状态
            
        Returns:
            爬虫任务列表
        """
        try:
            query = """
                SELECT t.*, 
                    (SELECT COUNT(*) FROM fp_spider_client_task WHERE task_id = t.id) as client_count 
                FROM fp_spider_task t
                WHERE t.status = :status AND t.control_action IS NULL AND start_time <= :start_time
                ORDER BY t.create_time DESC
            """
            return await self.fetch_all(query, { "status": status, "start_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S') })
        except Exception as e:
            logger.error(f"获取爬虫任务失败: {e}, 任务状态: {status}")
            return []
    
    async def create_task(self, task_data: Dict[str, Any]) -> Optional[int]:
        """
        创建爬虫任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            任务ID (整数)
        """
        try:
            # 检查是否已存在相同名称的任务
            task_name = task_data.get("spider_task_title")
            if task_name:
                existing_task = await self.get_task_by_name(task_name)
                if existing_task:
                    # 如果任务已存在，返回现有任务ID
                    return existing_task.get("id")
            
            # 生成任务ID (现在返回整数) 和当前时间
            task_id = generate_id()
            now = datetime.now()
            
            # 准备插入数据
            insert_data = {
                "id": task_id,
                "spider_task_title": task_data.get("spider_task_title", ""),
                "task_desc": task_data.get("task_desc", ""),
                "task_type": task_data.get("task_type", 0),
                "status": task_data.get("status", 0),
                "target_site": task_data.get("target_site", ""),
                "schedule_config": task_data.get("schedule_config", "{}"),
                "create_time": now,
                "update_time": now
            }
            
            # 插入任务记录
            await self.insert(insert_data)
            
            # 如果有配置数据，创建配置
            if "config" in task_data:
                config_data = task_data.get("config", {})
                config_data["task_id"] = task_id
                config_data["target_site"] = insert_data["target_site"]
                config_data["config_name"] = insert_data["spider_task_title"]
                await SpiderConfigService.create_config(config_data)
            
            return task_id
        except Exception as e:
            logger.error(f"创建爬虫任务失败: {e}, 任务数据: {task_data}")
            return None
    
    async def update_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        更新爬虫任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            是否更新成功
        """
        try:
            if not task_data:
                return True
            
            # 分离配置数据
            config_data = None
            if "config" in task_data:
                config_data = task_data.pop("config")
            
            # 添加更新时间
            task_data["update_time"] = datetime.now()
            
            # 更新任务记录
            await self.update(task_data, {"id": task_id})
            
            # 如果有配置数据，更新配置
            if config_data:
                # 获取现有配置
                existing_config = await SpiderConfigService.get_config_by_task_id(task_id)
                
                if existing_config:
                    # 更新现有配置
                    await SpiderConfigService.update_config(existing_config.get("id"), config_data)
                else:
                    # 创建新配置
                    config_data["task_id"] = task_id
                    if "target_site" in task_data:
                        config_data["target_site"] = task_data["target_site"]
                    if "spider_task_title" in task_data:
                        config_data["config_name"] = task_data["spider_task_title"]
                    await SpiderConfigService.create_config(config_data)
            
            return True
        except Exception as e:
            logger.error(f"更新爬虫任务失败: {e}, 任务ID: {task_id}")
            return False
    
    async def delete_task(self, task_id: str) -> bool:
        """
        删除爬虫任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        try:
            # 获取任务配置
            config = await SpiderConfigService.get_config_by_task_id(task_id)
            
            # 如果存在配置，删除配置
            if config:
                await SpiderConfigService.delete_config(config.get("id"))
            
            # 删除爬虫任务记录
            await self.delete({"id": task_id})
            
            return True
        except Exception as e:
            logger.error(f"删除爬虫任务失败: {e}, 任务ID: {task_id}")
            return False
    
    async def update_task_status(self, task_id: str, status: int) -> bool:
        """
        更新爬虫任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            
        Returns:
            是否更新成功
        """
        try:
            update_data = {
                "status": status,
                "update_time": datetime.now()
            }
            await self.update(update_data, {"id": task_id})
            return True
        except Exception as e:
            logger.error(f"更新爬虫任务状态失败: {e}, 任务ID: {task_id}, 状态: {status}")
            return False
    
    async def update_client_online_status(self, client_id: str, is_online: bool) -> None:
        """
        更新客户端在线状态
        
        Args:
            client_id: 客户端ID
            is_online: 是否在线
        """
        try:
            query = "UPDATE spider_client SET is_online = :is_online, last_heartbeat = NOW() WHERE client_id = :client_id"
            await self.execute(query, { "is_online": is_online, "client_id": client_id })
        except Exception as e:
            logger.error(f"更新客户端在线状态失败: {str(e)}")
            raise

# 创建全局服务实例
spider_task_service = SpiderTaskService()
