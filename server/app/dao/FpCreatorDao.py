from typing import List, Dict, Any

from loguru import logger
import asyncio
import time

from server.app.db.base import MySQLBaseDAO


class FpCreatorDao(MySQLBaseDAO):

    def __init__(self):
        super().__init__("fp_creator")
        self._lock = asyncio.Lock()

    # 查询创作者数据
    async def list_sign_creator(self, batch_size: int, platform_user_ids: List[str]) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT *
            FROM {self.table_name} 
            WHERE 1 = 1
        """
        if platform_user_ids:
            sql += f"""
                AND platform_user_id IN ('{"','".join(platform_user_ids)}')
            """
            
        params = {"batch_size": batch_size}
        if batch_size:
            sql += " LIMIT :batch_size"
        logger.info(f"查询创作者数据, 条数: {sql}")

        async with self._lock:
            bloggers = await self.fetch_all(sql, params)
            if not bloggers:
                return {}
        return {"items": bloggers}

    async def find_creator_by_user_id(self, creator_id: str) -> Dict[str, Any]:
        sql = f"""
            SELECT *
            FROM {self.table_name} 
            WHERE id = {creator_id}
        """
        return await self.fetch_one(sql)

fp_creator_dao = FpCreatorDao()
