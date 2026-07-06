from typing import List, Dict, Any

from loguru import logger
import asyncio

from server.app.db.base import MySQLBaseDAO


class TrainingBloggerDetailsDao(MySQLBaseDAO):

    def __init__(self):
        super().__init__("tibao_2.training_blogger_details_month_5")
        self._lock = asyncio.Lock()

    async def list_training_blogger_details(self, batch_size: int) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT id, nickname, blogger_dandelion_id, status
            FROM {self.table_name} 
            WHERE status = 0 and `month` = '2025-04' and (video_price >=500 or graphic_price>=500 )
            LIMIT :batch_size
        """
        logger.info(f"查询博主详情数据, 条数: {sql}")
        params = {"batch_size": 2}

        async with self._lock:
            bloggers = await self.fetch_all(sql, params)
            # logger.info(f"查询到博主详情数据, 条数: {bloggers}")
            if not bloggers:
                return {}
            blogger_ids = [f'{blogger["id"]}' for blogger in bloggers]
            await self.execute(f"UPDATE {self.table_name} SET status = 1 WHERE id IN ({','.join(blogger_ids)})")
        return {"items": bloggers}

    # 更新博主同步状态
    async def update_training_blogger_status(self, id) -> None:
        sql = f"""
            UPDATE {self.table_name} SET status = 2 WHERE id = {id}
        """
        logger.info(f"更新博主同步状态, 条数: {sql}")
        if id:
            await self.execute(sql)


training_blogger_details_dao = TrainingBloggerDetailsDao()
