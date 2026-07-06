from loguru import logger

from client.app.core.feishu.feishu_service import search_feishu_record, insert_records, delete_records, insert_record, \
    update_record


# 飞书笔记服务
class FeishuNoteService:

    # 初始化
    def __init__(self, table_id, view_id, app_token):
        self.table_id = table_id # 'tblGRbQ67CraBXKW'  # 飞书表id
        self.view_id = view_id # 'vewq34emtR'  # 飞书视图id
        self.app_token = app_token #"GvoobItcNaf47jsqyiHcg4GNnWd"  # 飞书应用id

    # 查询飞书笔记列表
    def query_notes(self, node):
        filters = {
            "conjunction": "and",
            "conditions": [
                {
                    "field_name": '笔记id',
                    "operator": "is",
                    "value": [node.get('笔记id', '0')]
                }
            ]
        }
        logger.info(f"查询飞书笔记列表参数：{filters}")
        return search_feishu_record(app_token=self.app_token, table_id=self.table_id, view_id=self.view_id,
                                    filters=filters)

    # 批量插入飞书笔记
    def update_note(self, record_id, notes):
        update_record(app_token=self.app_token, table_id=self.table_id, record_id=record_id, fields=notes)
        return

    # 批量删除飞书笔记
    def insert_note(self, notes):
        return insert_record(app_token=self.app_token, table_id=self.table_id, fields=notes)

    def save_note(self, node):
        origin_note = self.query_notes(node)
        # logger.info(f"查询飞书笔记列表{node} orign: {origin_note}")
        if origin_note:
            # 更新
            return self.update_note(origin_note[0].get('record_id'), node)
        else:
            # 新增
            return self.insert_note(node)