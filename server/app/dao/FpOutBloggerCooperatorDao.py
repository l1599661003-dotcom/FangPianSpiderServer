from typing import List, Dict, Any

from loguru import logger
import asyncio

from server.app.db.base import MySQLBaseDAO


class FpOutBloggerCooperatorDao(MySQLBaseDAO):

    def __init__(self):
        super().__init__("tibao_2.fp_out_blogger_cooperator_v2")
        self._lock = asyncio.Lock()

    async def list_fp_blogger(self, batch_size: int, task_id, client_id, status) -> List[Dict[str, Any]]:
        sql = f"""
            SELECT id, status, userId
            FROM {self.table_name} 
            WHERE status = {status}
        """
        if status:
            sql += f" AND task_id = {task_id} AND client_id = {client_id}"
        sql += " LIMIT :batch_size"
        logger.info(f"查询博主详情数据, 条数: {sql}")
        params = {"batch_size": 2}

        async with self._lock:
            bloggers = await self.fetch_all(sql, params)
            # logger.info(f"查询到博主详情数据, 条数: {bloggers}")
            if not bloggers:
                return {}
            blogger_ids = [f'{blogger["id"]}' for blogger in bloggers]
            await self.execute(f"UPDATE {self.table_name} SET status = 1, task_id = {task_id}, client_id = {client_id} WHERE id IN ({','.join(blogger_ids)})")
        return {"items": bloggers}

    # 更新博主同步状态
    async def update_fp_blogger_status(self, id, task_id, client_id) -> None:
        sql = f"""
            UPDATE {self.table_name} SET status = 2, task_id = {task_id}, client_id = {client_id} WHERE id = {id}
        """
        logger.info(f"更新博主同步状态, 条数: {sql}")
        if id:
            await self.execute(sql)


fp_out_blogger_cooperator_dao = FpOutBloggerCooperatorDao()
