from threading import Lock
from typing import List, Dict, Any

from loguru import logger

from server.app.core.feishu.feishu_service import search_feishu_record_page_list


class BlogerOutService:
    def __init__(self):
        self.app_token = "O5uNbHYLdaWQV1sPn8FcdsbSnmb"
        self.table_id = "tbl1NdootwK1xnMz"
        self.view_id = "vew5rRPpZE"
        self._lock = Lock()
        self.page_token = ""
        self.has_more = True

    def list_records(self) -> List[Dict[str, Any]]:
        """
        外采博主列表查询
        """
        if not self.has_more:
            return []

        with self._lock:
            result = search_feishu_record_page_list(self.app_token, self.table_id, self.view_id, self.page_token)
            self.page_token = result.get("page_token", "")
            self.has_more = result.get("has_more", False)
            logger.info(f"查询飞书表格信息成功，page_token: {self.page_token}, has_more: {self.has_more}")
        return result


blogger_out_service = BlogerOutService()
