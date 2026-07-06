from datetime import datetime
from typing import Dict, Any, List

from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.db.pool import MongoDBPool


class MongoDBService:
    """MongoDB数据服务类，用于处理任务数据的存储和查询"""

    def __init__(self):
        """初始化MongoDB连接"""
        self.mongodb_pool = MongoDBPool()
        self.task_dao = MySQLBaseDAO("fp_spider_task")

    async def save_task_result(self, task_id: str, task_type: str, data: Dict[str, Any]) -> bool:
        """
        保存任务结果到对应的集合
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            data: 结果数据
            
        Returns:
            是否保存成功
        """
        try:
            # 获取对应的集合名称，如果任务类型未定义，使用默认集合
            collection = MongoDBPool().get_collection(task_type)
            client_task_log_id = data.get("client_task_log_id", "")
            client_id = data.get("client_id", "")
            list = data.get("list", [])
            if not list:
                logger.warning(f"任务结果为空，不保存到集合 {task_type}, 任务ID: {task_id}")
                return False

            # task_info = self.task_dao.fetch_one("select * from fp_spider_task where id = :task_id", {"task_id": task_id})

            for item in list:
                # 添加元数据
                document = {
                    **item,  # 包含原始数据
                    "task_id": task_id,
                    "client_task_log_id": client_task_log_id,
                    "client_id": client_id,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "sync_status": 0,
                }
                # 插入文档
                await collection.insert_one(document)

            logger.info(f"已保存任务结果到集合 {task_type}, 任务ID: {task_id}")
            return True

        except Exception as e:
            logger.error(f"保存任务结果失败: {e}, 任务ID: {task_id}, 任务类型: {task_type}")
            return False

    async def batch_save_data(self, data: List[Dict[str, Any]], collection_name: str, creator_info: Dict[str, Any]):
        """
        批量保存数据到MongoDB
        """
        try:
            if not data:
                return True
            collection = self.mongodb_pool.get_collection(collection_name)
            # 通过creator_id和platform_user_id查询是否存在,如果存在，则删除原数据，重新插入
            filter = {
                "creator_id": creator_info.get('id'),
                "platform_user_id": creator_info.get('platform_user_id')
            }
            existing_data = await collection.find(filter).to_list(length=None)
            if existing_data:
                await collection.delete_many(filter)
            
            # 插入新数据
            await collection.insert_many(data)
            return True
        except Exception as e:
            logger.error(f"批量保存数据失败: {e}")
            return False

    async def get_task_results(self, task_id: str, task_type: str = None) -> List[Dict[str, Any]]:
        """
        获取任务结果数据
        
        Args:
            task_id: 任务ID
            task_type: 任务类型，可选
            
        Returns:
            任务结果列表
        """
        try:
            # 如果指定了任务类型，从特定集合查询
            if task_type and task_type in self.task_type_collections:
                collection_name = self.task_type_collections[task_type]
                collection = self.db[collection_name]
                cursor = collection.find({"task_id": task_id})
                return await cursor.to_list(length=100)

            # 否则，从所有相关集合中查询
            results = []
            for collection_name in self.task_type_collections.values():
                collection = self.db[collection_name]
                cursor = collection.find({"task_id": task_id})
                results.extend(await cursor.to_list(length=100))

            return results

        except Exception as e:
            logger.error(f"获取任务结果失败: {e}, 任务ID: {task_id}")
            return []

    async def update_task_result(self, task_id: str, task_type: str,
                                 doc_id: str, update_data: Dict[str, Any]) -> bool:
        """
        更新任务结果
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            doc_id: 文档ID
            update_data: 更新数据
            
        Returns:
            是否更新成功
        """
        try:
            # 获取对应的集合
            collection_name = self.task_type_collections.get(task_type, "task_results")
            collection = self.mongodb[collection_name]

            # 添加更新时间
            update_data["updated_at"] = datetime.now()

            # 更新文档
            result = await collection.update_one(
                {"_id": doc_id, "task_id": task_id},
                {"$set": update_data}
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"已更新任务结果: 任务ID: {task_id}, 文档ID: {doc_id}")
            else:
                logger.warning(f"未找到要更新的文档: 任务ID: {task_id}, 文档ID: {doc_id}")

            return success

        except Exception as e:
            logger.error(f"更新任务结果失败: {e}, 任务ID: {task_id}, 文档ID: {doc_id}")
            return False

    async def delete_task_results(self, task_id: str, task_type: str = None) -> bool:
        """
        删除任务结果
        
        Args:
            task_id: 任务ID
            task_type: 任务类型，可选
            
        Returns:
            是否删除成功
        """
        try:
            # 如果指定了任务类型，从特定集合删除
            if task_type and task_type in self.task_type_collections:
                collection_name = self.task_type_collections[task_type]
                collection = self.db[collection_name]
                result = await collection.delete_many({"task_id": task_id})

                logger.info(f"已从集合 {collection_name} 删除 {result.deleted_count} 条任务结果, 任务ID: {task_id}")
                return result.deleted_count > 0

            # 否则，从所有相关集合中删除
            deleted_count = 0
            for collection_name in self.task_type_collections.values():
                collection = self.db[collection_name]
                result = await collection.delete_many({"task_id": task_id})
                deleted_count += result.deleted_count

            logger.info(f"已从所有集合中删除 {deleted_count} 条任务结果, 任务ID: {task_id}")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"删除任务结果失败: {e}, 任务ID: {task_id}")
            return False

    async def find_blogger_info(self, user_id: str):
        try:
            collection = self.mongodb_pool.get_collection('blogger_info')
            return await collection.find_one({"userId": user_id}, {"_id": 0})
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")

    #  查询博主笔记列表
    async def find_blogger_note_rate(self, user_id: str):
        try:
            collection = self.mongodb_pool.get_collection('blogger_note_rate')
            filter = {}
            if user_id:
                filter['user_id'] = user_id
            return await collection.find_one(filter, {"_id": 0})
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")

    async def find_blogger_note_detail(self, user_id: str):
        try:
            collection = self.mongodb_pool.get_collection('blogger_note_detail')
            filter = { "task_id": "8" }

            # pipeline = [
            #     {"$group": {"_id": None, "client_task_log_id": {"$max": "$client_task_log_id"}}}
            # ]
            # client_task_log_id = await collection.aggregate(pipeline).to_list(length=1)

            if user_id:
                filter['user_id'] = user_id
                # pipeline.append({"$match": {"user_id": user_id}})

            # if client_task_log_id:
            #     filter['client_task_log_id'] = client_task_log_id[0]['client_task_log_id']

            cursor = collection.find(filter, {"_id": 0})
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")

    # 博主粉化画像
    async def find_blogger_fans_profile(self, user_id: str, task_id: int):
        try:
            collection = self.mongodb_pool.get_collection('blogger_fans_profile')
            filter = {}
            if user_id:
                filter['user_id'] = user_id
            if task_id:
                filter['task_id'] = task_id
            return await collection.find_one(filter, {"_id": 0})
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")

    # 博主粉化画像
    async def find_blogger_fans_overall_new_history(self, user_id: str, date_type: int, increaseType: int):

        try:
            collection_name = 'blogger_fans_history'
            if increaseType == 2:
                collection_name = 'blogger_fans_increase_history'
            collection = self.mongodb_pool.get_collection(collection_name)
            filter = {}
            if user_id:
                filter['user_id'] = user_id
            if date_type:
                filter['dateType'] = date_type

            return await collection.find_one(filter, {"_id": 0})
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")


    async def find_blogger_fans_summary(self, user_id: str, task_id: int):
        try:
            collection_name = 'blogger_fans_summary'
            collection = self.mongodb_pool.get_collection(collection_name)
            filter = {}
            if user_id:
                filter['user_id'] = user_id
            if task_id:
                filter['taskId'] = task_id

            return await collection.find_one(filter, {"_id": 0})
        except Exception as e:
            logger.info(f"查询博主信息失败: {e}, 博主ID: {user_id}")


# 创建单例实例
mongodb_service = MongoDBService()
