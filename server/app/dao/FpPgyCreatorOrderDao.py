from typing import List, Dict, Any

from loguru import logger
import asyncio

from server.app.db.base import MySQLBaseDAO


class FpPgyCreatorOrderDao(MySQLBaseDAO):
    """
    创作者订单数据库操作类，用于操作创作者订单数据
    """
    def __init__(self):
        super().__init__("fp_pgy_creator_order")
        self._lock = asyncio.Lock()

    async def list_pgy_creator_order(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        查询创作者订单数据
        """
        page_num = params.get("page_num", 1)
        page_size = params.get("page_size", 100)
        offset = (page_num - 1) * page_size
        limit = page_size
        
        sql = f"""
            SELECT *
            FROM {self.table_name} 
        """
        
        order_ids = params.get("order_ids", [])

        if order_ids:
            sql += f"""
                WHERE platform_order_id IN ('{"','".join(order_ids)}')
            """
        logger.info(f"查询创作者订单数据, 条数: {sql}")
        return await self.fetch_all(sql)
    
    # 批量添加创作者订单数据
    async def batch_add_pgy_creator_order(self, orders: List[Dict[str, Any]]) -> None:
        # sql = f"""
        #     INSERT INTO {self.table_name} ()
        #     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        # """
        fields = [
            "platform_order_id",
            "platform_create_time",
            "creator_nickname",
            "creator_id",
            "platform_user_id",
            "content_type",
            "content_price",
            "total_price",
            "brand_name",
            "brand_id",
            "report_brand_name",
            "report_brand_user_id", 
            "order_status", "title", "state", "sign_type", "mcn_name", 
            "mcn_id", "publish_time", "expected_publish_time", "complete_time", 
            "creator_contact_name", "creator_contact_phone", "creator_contact_name_cipher", 
            "creator_contact_phone_cipher", "contact_name", "contact_name_cipher", "contact_phone", 
            "contact_phone_cipher", "note_id", "note_image", "note_type", "create_time", "update_time"
        ]
        await self.batch_insert(fields, orders)
    
    # 通过主键批量删除创作者订单数据
    async def batch_delete_pgy_creator_order(self, ids: List[int]) -> None:
        sql = f"""
            DELETE FROM {self.table_name} WHERE id IN ({','.join(ids)})
        """
        await self.execute(sql)
        
    # 添加单条创作者订单数据
    async def add_pgy_creator_order(self, order: Dict[str, Any]) -> None:
        """
        添加单条创作者订单数据
        
        Args:
            order: 订单数据
        """
        try:
            # 直接使用insert方法插入单条数据
            await self.insert(order)
            logger.info(f"添加单条订单数据成功: {order.get('platform_order_id')}")
        except Exception as e:
            logger.exception(f"添加单条订单数据失败: {e}")
            raise

fp_pgy_creator_order_dao = FpPgyCreatorOrderDao()