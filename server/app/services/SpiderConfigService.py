from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.utils.common import generate_id


class SpiderConfigService(MySQLBaseDAO):
    """爬虫配置服务，负责管理爬虫配置信息"""

    def __init__(self):
        super().__init__("fp_spider_config")

    async def get_config_by_id(self, config_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取爬虫配置"""
        try:
            query = "SELECT * FROM fp_spider_config WHERE id = :config_id"
            return await self.fetch_one(query, {"config_id": config_id})
        except Exception as e:
            logger.error(f"获取爬虫配置失败: {e}, 配置ID: {config_id}")
            return None

    async def get_config_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """通过任务ID获取爬虫配置"""
        try:
            query = "SELECT * FROM fp_spider_config WHERE task_id = :task_id"
            return await self.fetch_one(query, {"task_id": task_id})
        except Exception as e:
            logger.error(f"获取爬虫配置失败: {e}, 任务ID: {task_id}")
            return None

    async def get_all_configs(self) -> List[Dict[str, Any]]:
        """获取所有爬虫配置"""
        try:
            query = "SELECT * FROM fp_spider_config ORDER BY create_time DESC"
            return await self.fetch_all(query)
        except Exception as e:
            logger.error(f"获取所有爬虫配置失败: {e}")
            return []

    async def create_config(self, config_data: Dict[str, Any]) -> Optional[int]:
        """
        创建爬虫配置
        
        Args:
            config_data: 配置数据
            
        Returns:
            配置ID (整数)
        """
        try:
            # 生成配置ID (整数) 和当前时间
            config_id = generate_id()
            now = datetime.now()

            # 准备插入数据
            insert_data = {
                "id": config_id,
                "task_id": config_data.get("task_id"),
                "config_name": config_data.get("config_name", ""),
                "target_site": config_data.get("target_site", ""),
                "config_content": config_data.get("config_content", "{}"),
                "create_time": now,
                "update_time": now
            }

            # 插入配置记录
            await self.insert(insert_data)

            return config_id
        except Exception as e:
            logger.error(f"创建爬虫配置失败: {e}, 配置数据: {config_data}")
            return None

    async def update_config(self, config_id: str, config_data: Dict[str, Any]) -> bool:
        """更新爬虫配置"""
        try:
            if not config_data:
                return True

            # 添加更新时间
            config_data["update_time"] = datetime.now()

            # 更新配置记录
            await self.update(config_data, {"id": config_id})

            return True
        except Exception as e:
            logger.error(f"更新爬虫配置失败: {e}, 配置ID: {config_id}")
            return False

    async def delete_config(self, config_id: str) -> bool:
        """删除爬虫配置"""
        try:
            await self.delete({"id": config_id})
            return True
        except Exception as e:
            logger.error(f"删除爬虫配置失败: {e}, 配置ID: {config_id}")
            return False

    async def get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """
        获取代理配置
        
        Returns:
            代理配置信息
        """
        try:
            query = """
                SELECT * FROM fp_proxy_config WHERE is_active = 1 LIMIT 1
            """
            result = await self.fetch_one(query)
            if result:
                return dict(result)
            return None


        except Exception as e:
            logger.error(f"获取代理配置失败: {e}")
            return None

    async def get_user_agents(self) -> List[str]:
        """
        获取用户代理列表
        
        Returns:
            用户代理列表
        """
        try:
            query = """
                SELECT user_agent FROM fp_user_agent WHERE is_active = 1
            """

            result = await self.fetch_all(query)

            if result:
                return [row["user_agent"] for row in result]

            return []
        except Exception as e:
            logger.error(f"获取用户代理列表失败: {e}")
            return []


# 创建全局服务实例
spider_config_service = SpiderConfigService()
