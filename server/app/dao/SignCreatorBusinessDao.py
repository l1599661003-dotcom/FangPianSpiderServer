from typing import List, Dict, Any

from loguru import logger
import asyncio
import time

from server.app.db.base import MySQLBaseDAO


class SignCreatorBusinessDao(MySQLBaseDAO):

    def __init__(self):
        super().__init__("fp_creator_business")
        self._lock = asyncio.Lock()

    # 查询创作者数据
    async def list_sign_creator(self, batch_size: int) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT *
            FROM {self.table_name} 
            WHERE sync_status = 0
        """
        sql += " LIMIT :batch_size"
        logger.info(f"查询创作者数据, 条数: {sql}")
        params = {"batch_size": batch_size}

        async with self._lock:
            bloggers = await self.fetch_all(sql, params)
            if not bloggers:
                return {}
        return bloggers

    # 更新创作者同步状态，及最后更新时间，时间戳
    async def update_sign_creator_status(self, id) -> None:
        sql = f"""
            UPDATE {self.table_name} SET sync_status = 1, last_sync_time = {int(time.time())} WHERE id = {id}
        """
        logger.info(f"更新创作者同步状态, 条数: {sql}")
        if id:
            await self.execute(sql)

fp_sign_creator_business_dao = SignCreatorBusinessDao()
