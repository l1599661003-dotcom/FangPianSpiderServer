from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.utils.common import generate_id


class SpiderClientService(MySQLBaseDAO):
    """爬虫客户端服务，负责管理客户端信息"""

    def __init__(self):
        super().__init__("fp_spider_client")

    async def get_client_by_id(self, client_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取客户端信息"""
        try:
            query = "SELECT * FROM fp_spider_client WHERE id = :client_id"
            return await self.fetch_one(query, {"client_id": client_id})
        except Exception as e:
            logger.error(f"获取客户端信息失败: {e}, 客户端ID: {client_id}")
            return None

    async def get_client_by_device_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """通过设备ID获取客户端信息"""
        try:
            query = "SELECT * FROM fp_spider_client WHERE device_id = :device_id"
            return await self.fetch_one(query, {"device_id": device_id})
        except Exception as e:
            logger.error(f"获取客户端信息失败: {e}, 设备ID: {device_id}")
            return None

    async def get_all_clients(self) -> List[Dict[str, Any]]:
        """获取所有客户端"""
        try:
            query = "SELECT * FROM fp_spider_client ORDER BY create_time DESC"
            return await self.fetch_all(query)
        except Exception as e:
            logger.error(f"获取所有客户端失败: {e}")
            return []

    async def create_client(self, client_data: Dict[str, Any]) -> Optional[int]:
        """
        创建客户端
        
        Args:
            client_data: 客户端数据
            
        Returns:
            客户端ID (整数)
        """
        try:
            # 生成客户端ID (整数) 和当前时间
            client_id = generate_id()
            now = datetime.now()
            
            # 准备插入数据
            insert_data = {
                "id": client_id,
                "client_name": client_data.get("client_name", ""),
                "device_id": client_data.get("device_id", ""),
                "ip_address": client_data.get("ip_address", ""),
                "status": client_data.get("status", 0),
                "is_online": client_data.get("is_online", False),
                "last_heartbeat": now,
                "create_time": now,
                "update_time": now
            }
            
            # 插入客户端记录
            await self.insert(insert_data)
            
            return client_id
        except Exception as e:
            logger.error(f"创建客户端失败: {e}, 客户端数据: {client_data}")
            return None

    async def update_client(self, client_id: str, client_data: Dict[str, Any]) -> bool:
        """更新客户端信息"""
        try:
            if not client_data:
                return True
            
            # 添加更新时间
            client_data["update_time"] = datetime.now()
            
            # 更新客户端记录
            await self.update(client_data, {"id": client_id})
            
            return True
        except Exception as e:
            logger.error(f"更新客户端失败: {e}, 客户端ID: {client_id}")
            return False

    async def delete_client(self, client_id: str) -> bool:
        """删除客户端"""
        try:
            await self.delete({"id": client_id})
            return True
        except Exception as e:
            logger.error(f"删除客户端失败: {e}, 客户端ID: {client_id}")
            return False

    async def update_client_status(self, client_id: str, status: int) -> bool:
        """更新客户端状态"""
        try:
            update_data = {
                "status": status,
                "update_time": datetime.now()
            }
            await self.update(update_data, {"id": client_id})
            return True
        except Exception as e:
            logger.error(f"更新客户端状态失败: {e}, 客户端ID: {client_id}, 状态: {status}")
            return False

    async def update_client_online_status(self, client_id: str, is_online: bool) -> bool:
        """更新客户端在线状态"""
        try:
            update_data = {
                "is_online": is_online,
                "last_heartbeat": datetime.now(),
                "update_time": datetime.now()
            }
            await self.update(update_data, {"id": client_id})
            return True
        except Exception as e:
            logger.error(f"更新客户端在线状态失败: {e}, 客户端ID: {client_id}")
            return False


# 创建全局服务实例
spider_client_service = SpiderClientService()
