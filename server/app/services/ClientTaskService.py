from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.services.MongoDBService import mongodb_service


class ClientTaskService(MySQLBaseDAO):
    """客户端任务服务，负责管理客户端爬虫任务信息"""

    def __init__(self):
        super().__init__("fp_spider_client_task")

    async def get_task_by_id(self, client_task_id: str) -> Optional[Dict[str, Any]]:
        """
        通过ID获取客户端任务
        
        Args:
            client_task_id: 客户端任务ID
            
        Returns:
            客户端任务信息
        """
        try:
            query = """
            SELECT ct.*, st.spider_task_title 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_task st ON ct.task_id = st.id
            WHERE ct.id = :client_task_id
            """
            return await self.fetch_one(query, {"client_task_id": client_task_id})
        except Exception as e:
            logger.error(f"获取客户端任务失败: {e}, 客户端任务ID: {client_task_id}")
            return None

    async def get_tasks_by_client_id(self, client_id: str) -> List[Dict[str, Any]]:
        """
        通过客户端ID获取客户端任务列表
        
        Args:
            client_id: 客户端ID
            
        Returns:
            客户端任务列表
        """
        try:
            query = """
            SELECT ct.*, st.spider_task_title 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_task st ON ct.task_id = st.id
            WHERE ct.client_id = :client_id
            ORDER BY ct.create_time DESC
            """
            return await self.fetch_all(query, {"client_id": client_id})
        except Exception as e:
            logger.error(f"获取客户端任务列表失败: {e}, 客户端ID: {client_id}")
            return []

    async def get_tasks_by_task_id(self, task_id: str) -> List[Dict[str, Any]]:
        """
        通过爬虫任务ID获取客户端任务列表
        
        Args:
            task_id: 爬虫任务ID
            
        Returns:
            客户端任务列表
        """
        try:
            query = """
            SELECT ct.*, c.client_name 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_client c ON ct.client_id = c.id
            WHERE ct.task_id = :task_id
            ORDER BY ct.create_time DESC
            """
            return await self.fetch_all(query, {"task_id": task_id})
        except Exception as e:
            logger.error(f"获取客户端任务列表失败: {e}, 任务ID: {task_id}")
            return []

    async def get_task_by_client_and_task(self, client_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        通过客户端ID和任务ID获取客户端任务
        
        Args:
            client_id: 客户端ID
            task_id: 爬虫任务ID
            
        Returns:
            客户端任务信息
        """
        try:
            query = """
            SELECT ct.*, st.spider_task_title 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_task st ON ct.task_id = st.id
            WHERE ct.client_id = :client_id AND ct.task_id = :task_id
            """
            return await self.fetch_one(query, {"client_id": client_id, "task_id": task_id})
        except Exception as e:
            logger.error(f"获取客户端任务失败: {e}, 客户端ID: {client_id}, 任务ID: {task_id}")
            return None

    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有客户端任务
        
        Returns:
            客户端任务列表
        """
        try:
            query = """
            SELECT ct.*, st.spider_task_title, c.client_name 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_task st ON ct.task_id = st.id
            LEFT JOIN fp_spider_client c ON ct.client_id = c.id
            ORDER BY ct.create_time DESC
            """
            return await self.fetch_all(query)
        except Exception as e:
            logger.error(f"获取所有客户端任务失败: {e}")
            return []

    async def get_tasks_by_status(self, status: int) -> List[Dict[str, Any]]:
        """
        通过状态获取客户端任务列表
        
        Args:
            status: 任务状态
            
        Returns:
            客户端任务列表
        """
        try:
            query = """
            SELECT ct.*, st.spider_task_title, c.client_name 
            FROM fp_spider_client_task ct
            LEFT JOIN fp_spider_task st ON ct.task_id = st.id
            LEFT JOIN fp_spider_client c ON ct.client_id = c.id
            WHERE ct.status = :status
            ORDER BY ct.create_time DESC
            """
            return await self.fetch_all(query, {"status": status})
        except Exception as e:
            logger.error(f"获取客户端任务列表失败: {e}, 状态: {status}")
            return []

    async def create_task(self, task_data: Dict[str, Any]) -> Optional[int]:
        """
        创建客户端任务
        
        Args:
            task_data: 任务数据
            
        Returns:
            任务ID (整数)
        """
        try:
            # 获取当前时间
            now = datetime.now()

            # 准备插入数据，不再手动指定ID，让MySQL使用自增ID
            insert_data = {
                "task_id": task_data.get("task_id"),
                "client_id": task_data.get("client_id"),
                "status": task_data.get("status", 0),
                "progress": task_data.get("progress", 0),
                "result": task_data.get("result", ""),
                "error_msg": task_data.get("error_msg", ""),
                "create_time": now,
                "update_time": now,
                "start_time": task_data.get("start_time"),
                "end_time": task_data.get("end_time")
            }

            # 插入任务记录并获取自增ID
            task_id = await self.insert(insert_data)
            logger.info(f"创建客户端任务成功, ID: {task_id}")

            return task_id
        except Exception as e:
            logger.error(f"创建客户端任务失败: {e}, 任务数据: {task_data}")
            return None

    async def update_task(self, client_task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        更新客户端任务
        
        Args:
            client_task_id: 客户端任务ID
            task_data: 任务数据
            
        Returns:
            是否更新成功
        """
        try:
            if not task_data:
                return True

            # 添加更新时间
            task_data["update_time"] = datetime.now()

            # 更新任务记录
            await self.update(task_data, {"id": client_task_id})

            return True
        except Exception as e:
            logger.error(f"更新客户端任务失败: {e}, 客户端任务ID: {client_task_id}")
            return False

    async def delete_task(self, client_task_id: str) -> bool:
        """
        删除客户端任务
        
        Args:
            client_task_id: 客户端任务ID
            
        Returns:
            是否删除成功
        """
        try:
            await self.delete({"id": client_task_id})
            return True
        except Exception as e:
            logger.error(f"删除客户端任务失败: {e}, 客户端任务ID: {client_task_id}")
            return False

    async def delete_tasks_by_client_id(self, client_id: str) -> bool:
        """
        通过客户端ID删除所有客户端任务
        
        Args:
            client_id: 客户端ID
            
        Returns:
            是否删除成功
        """
        try:
            await self.delete({"client_id": client_id})
            return True
        except Exception as e:
            logger.error(f"删除客户端任务失败: {e}, 客户端ID: {client_id}")
            return False

    async def delete_tasks_by_task_id(self, task_id: str) -> bool:
        """
        通过爬虫任务ID删除所有客户端任务
        
        Args:
            task_id: 爬虫任务ID
            
        Returns:
            是否删除成功
        """
        try:
            await self.delete({"task_id": task_id})
            return True
        except Exception as e:
            logger.error(f"删除客户端任务失败: {e}, 任务ID: {task_id}")
            return False

    async def update_task_status(self, client_task_id: str, status: int) -> bool:
        """
        更新客户端任务状态
        
        Args:
            client_task_id: 客户端任务ID
            status: 任务状态
            
        Returns:
            是否更新成功
        """
        try:
            # 确保client_task_id是整数类型
            client_task_id_int = int(client_task_id) if isinstance(client_task_id,
                                                                   str) and client_task_id.isdigit() else client_task_id

            # 使用字符串格式的当前时间
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            update_data = {
                "status": status,
                "update_time": now
            }
            await self.update(update_data, {"id": client_task_id_int})
            return True
        except Exception as e:
            logger.error(f"更新客户端任务状态失败: {e}, 客户端任务ID: {client_task_id}, 状态: {status}")
            return False

    async def update_task_result(self, task_id: str, client_id: str, result: Dict[str, Any]) -> bool:
        """
        更新任务结果
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            result: 任务结果
            
        Returns:
            是否更新成功
        """
        try:
            # 保存结果到 MongoDB
            doc_id = await mongodb_service.save_task_result(task_id, client_id, result)

            if not doc_id:
                logger.error(f"保存任务结果到 MongoDB 失败, 任务ID: {task_id}, 客户端ID: {client_id}")
                return False

            # 更新 MySQL 中的任务状态
            update_data = {
                "result_id": doc_id,
                "status": 2,  # 已完成
                "update_time": datetime.now()
            }

            success = await self.update(update_data, {"task_id": task_id, "client_id": client_id})

            if not success:
                logger.error(f"更新任务状态失败, 任务ID: {task_id}, 客户端ID: {client_id}")
                return False

            return True

        except Exception as e:
            logger.error(f"更新任务结果失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False

    async def get_task_result(self, task_id: str, client_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            
        Returns:
            任务结果
        """
        try:
            # 从 MySQL 获取任务信息
            task = await self.fetch_one({"task_id": task_id, "client_id": client_id})

            if not task or not task.get("result_id"):
                return None

            # 从 MongoDB 获取结果详情
            result = await mongodb_service.get_task_result(task_id, client_id)

            return result

        except Exception as e:
            logger.error(f"获取任务结果失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return None

    async def create_execution_log(self, log_data: Dict[str, Any]) -> Optional[int]:
        """
        创建任务执行日志
        
        Args:
            log_data: 日志数据
            
        Returns:
            日志ID (整数)
        """
        try:
            # 确保所有ID字段都是整数类型
            client_task_id = log_data.get("client_task_id")
            client_id = log_data.get("client_id")
            task_id = log_data.get("task_id")

            # 处理字符串类型的ID
            if isinstance(client_task_id, str) and client_task_id.isdigit():
                client_task_id = int(client_task_id)
            if isinstance(client_id, str) and client_id.isdigit():
                client_id = int(client_id)
            if isinstance(task_id, str) and task_id.isdigit():
                task_id = int(task_id)

            # 获取当前时间
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 准备插入数据
            insert_data = {
                "client_task_id": client_task_id,
                "client_id": client_id,
                "task_id": task_id,
                "start_time": now,
                "total_num": log_data.get("total_num", 0),
                "fail_num": log_data.get("fail_num", 0),
                "succ_num": log_data.get("succ_num", 0),
                "status": log_data.get("status", 0),
                "create_time": now,
                "update_time": now
            }

            # 创建DAO对象
            task_log_dao = MySQLBaseDAO("fp_spider_client_task_log")

            # 构建INSERT SQL
            columns = ', '.join(insert_data.keys())
            placeholders = ', '.join(f':{k}' for k in insert_data.keys())
            sql = f"INSERT INTO fp_spider_client_task_log ({columns}) VALUES ({placeholders})"

            # 执行SQL并获取最后插入的ID
            result = await task_log_dao.execute(sql, insert_data)
            last_id = result.lastrowid

            logger.info(f"创建任务执行日志成功, ID: {last_id}")
            return last_id

        except Exception as e:
            logger.error(f"创建任务执行日志失败: {e}, 日志数据: {log_data}")
            return None

    async def update_execution_record(self, execution_id: str, update_data: Dict[str, Any]) -> bool:
        """
        更新任务执行记录
        
        Args:
            execution_id: 执行记录ID
            update_data: 更新数据
            
        Returns:
            是否更新成功
        """
        try:
            # 创建DAO对象来访问fp_spider_client_task_log表
            task_log_dao = MySQLBaseDAO("fp_spider_client_task_log")
            await task_log_dao.update(update_data, {"id": execution_id})
            return True
        except Exception as e:
            logger.error(f"更新任务执行记录失败: {e}, 执行记录ID: {execution_id}")
            return False

    async def get_execution_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """获取任务执行记录详情"""
        try:
            # 创建DAO对象来访问fp_spider_client_task_log表
            task_log_dao = MySQLBaseDAO("fp_spider_client_task_log")
            query = """
            SELECT l.*, c.client_name, t.spider_task_title
            FROM fp_spider_client_task_log l
            LEFT JOIN fp_spider_client c ON l.client_id = c.id
            LEFT JOIN fp_spider_task t ON l.task_id = t.id
            WHERE l.id = :record_id
            """
            return await task_log_dao.fetch_one(query, {"record_id": record_id})
        except Exception as e:
            logger.error(f"获取任务执行记录详情失败: {e}")
            return None


# 创建全局服务实例
client_task_service = ClientTaskService()
