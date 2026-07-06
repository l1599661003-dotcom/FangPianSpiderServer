from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from loguru import logger

from server.app.dao.FpOutBloggerCooperatorDao import fp_out_blogger_cooperator_dao
from server.app.dao.FpSpiderBloggerDao import fp_spider_blogger_dao
from server.app.dao.NoteDetailBloggerDao import note_detail_blogger_dao
from server.app.dao.TrainingBloggerDetailsDao import training_blogger_details_dao
from server.app.db.base import MySQLBaseDAO
from server.app.services.ClientTaskService import client_task_service
from server.app.services.SpiderClientService import spider_client_service
from server.app.services.SpiderTaskService import spider_task_service
from server.app.services.feishu.BlogerOutService import blogger_out_service
from server.app.utils.common import generate_id


class TaskService(MySQLBaseDAO):
    """任务服务，负责管理爬虫任务和客户端任务的关联"""
    
    def __init__(self):
        super().__init__("fp_spider_task")
        self.blogger_service = blogger_out_service;
        self.training_blogger_details_dao = training_blogger_details_dao;
        self.fp_spider_blogger_dao = fp_spider_blogger_dao;
        self.fp_out_blogger_cooperator_dao = fp_out_blogger_cooperator_dao;
        self.note_detail_blogger_dao = note_detail_blogger_dao;

    async def get_available_tasks(self) -> List[Dict[str, Any]]:
        """获取可分配的任务列表"""
        try:
            # 获取状态为运行中的爬虫任务
            active_tasks = await spider_task_service.get_tasks_by_status(1)  # 1表示运行中
            
            # 过滤掉不需要继续分配的任务
            available_tasks = []
            for task in active_tasks:
                # 获取当前已分配的客户端数量
                client_tasks = await client_task_service.get_tasks_by_task_id(task["id"])
                running_count = sum(1 for ct in client_tasks if ct.get("status") in [0, 1])  # 0未开始，1运行中
                
                # 检查是否需要分配更多客户端
                client_limit = task.get("client_limit", 1)
                if running_count < client_limit:
                    task["client_count"] = running_count
                    available_tasks.append(task)
            
            return available_tasks
            
        except Exception as e:
            logger.error(f"获取可用任务失败: {e}")
            return []
    
    async def assign_task(self, client_id: str, task_id: str) -> Optional[int]:
        """
        分配任务给客户端
        
        Args:
            client_id: 客户端ID
            task_id: 任务ID
            
        Returns:
            客户端任务ID (整数), 失败时返回None
        """
        try:
            # 检查客户端是否存在且在线
            client = await spider_client_service.get_client_by_id(client_id)
            if not client or not client.get("is_online"):
                logger.error(f"客户端不存在或不在线, 客户端ID: {client_id}")
                return None
            
            # 检查任务是否存在且可分配
            task = await spider_task_service.get_task_by_id(task_id)
            if not task or task.get("status") != 1:  # 1表示运行中
                logger.error(f"任务不存在或不可分配, 任务ID: {task_id}")
                return None
            
            # 检查是否已分配给该客户端
            existing_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
            if existing_task:
                logger.warning(f"任务已分配给该客户端, 任务ID: {task_id}, 客户端ID: {client_id}")
                return existing_task.get("id")
            
            # 创建客户端任务
            task_data = {
                "task_id": task_id,
                "client_id": client_id,
                "status": 0,  # 未开始
                "progress": 0,
                "result": "",
                "error_msg": ""
            }
            
            return await client_task_service.create_task(task_data)
            
        except Exception as e:
            logger.error(f"分配任务失败: {e}, 客户端ID: {client_id}, 任务ID: {task_id}")
            return None
    
    async def start_task(self, task_id: str, client_id: str) -> bool:
        """开始任务"""
        try:
            # 获取客户端任务
            client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
            
            if not client_task:
                logger.error(f"客户端任务不存在, 任务ID: {task_id}, 客户端ID: {client_id}")
                return False
            
            # 准备更新数据
            update_data = {
                "status": 1,  # 1表示运行中
                "start_time": datetime.now()
            }
            
            # 更新客户端任务
            return await client_task_service.update_task(client_task["id"], update_data)
            
        except Exception as e:
            logger.error(f"开始任务失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False
    
    async def complete_task(self, task_id: str, client_id: str, complete_data: Dict[str, Any]) -> bool:
        """完成任务"""
        try:
            # 获取客户端任务
            client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
            
            if not client_task:
                logger.error(f"客户端任务不存在, 任务ID: {task_id}, 客户端ID: {client_id}")
                return False
            
            # 当前时间
            now = datetime.now()
            
            # 准备更新数据
            update_data = {
                "status": 2,  # 2表示完成
                "progress": 100,
                "result": complete_data.get("result", ""),
                "end_time": now
            }
            
            # 更新客户端任务
            success = await client_task_service.update_task(client_task["id"], update_data)
            
            # 更新任务执行日志
            task_log_id = client_task.get("task_log_id")
            if task_log_id:
                execution_data = {
                    "status": 2,  # 2表示已完成
                    "completed_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "progress": 100,
                    "update_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "result": complete_data.get("result", "任务已完成")
                }
                await client_task_service.update_execution_record(task_log_id, execution_data)
                logger.info(f"更新任务执行日志成功, 日志ID: {task_log_id}")
            
            # 检查是否所有客户端都已完成
            all_client_tasks = await client_task_service.get_tasks_by_task_id(task_id)
            all_completed = all(ct.get("status") == 2 for ct in all_client_tasks)
            
            # 如果所有客户端都已完成，更新爬虫任务状态
            if all_completed:
                await spider_task_service.update_task_status(task_id, 2)  # 2表示完成
            
            return success
            
        except Exception as e:
            logger.error(f"完成任务失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False
    
    # 为兼容性添加complete_client_task方法作为complete_task的别名
    async def complete_client_task(self, task_id: str, client_id: str, complete_data: Dict[str, Any]) -> bool:
        """完成客户端任务（complete_task的别名）"""
        return await self.complete_task(task_id, client_id, complete_data)
    
    async def record_task_error(self, task_id: str, client_id: str, error_code: str, error_message: str) -> bool:
        """记录任务错误"""
        try:
            # 获取客户端任务
            client_task = await client_task_service.get_task_by_client_and_task(client_id, task_id)
            
            if not client_task:
                logger.error(f"客户端任务不存在, 任务ID: {task_id}, 客户端ID: {client_id}")
                return False
            
            # 准备更新数据
            update_data = {
                "status": 3,  # 3表示错误
                "error_msg": error_message,
                "end_time": datetime.now()
            }
            
            # 更新客户端任务
            success = await client_task_service.update_task(client_task["id"], update_data)
            
            # 检查是否需要停止整个任务
            should_stop = await self.should_stop_task(task_id, error_code)
            if should_stop:
                await spider_task_service.update_task_status(task_id, 3)  # 3表示错误
            
            return success
            
        except Exception as e:
            logger.error(f"记录任务错误失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False
    
    async def should_stop_task(self, task_id: str, error_code: str) -> bool:
        """判断是否需要停止整个任务"""
        # 严重错误代码列表，出现这些错误时整个任务都需要停止
        critical_errors = ["AUTH_FAILED", "IP_BANNED", "API_LIMIT_EXCEEDED"]
        
        return error_code in critical_errors
    
    async def update_task_status(self, task_id: str, status: int) -> bool:
        """更新爬虫任务状态"""
        try:
            return await spider_task_service.update_task_status(task_id, status)
        except Exception as e:
            logger.error(f"更新爬虫任务状态失败: {e}, 任务ID: {task_id}")
            return False
    
    async def get_task_data(self, task_id: str, client_id: str, batch_size: int = 100) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取任务数据
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            batch_size: 批次大小
            
        Returns:
            (数据列表, 批次ID(整数))
        """
        try:
            # 获取爬虫任务
            task = await spider_task_service.get_task_by_id(task_id)
            
            if not task:
                logger.error(f"爬虫任务不存在, 任务ID: {task_id}")
                return [], 0
            
            # 生成批次ID (整数)
            batch_id = generate_id()
            
            # 根据任务类型获取数据
            task_type = task.get("task_type", 0)
            platform_id = task.get("platform_id", 0)
            logger.info(f"获取任务数据, 任务ID: {task_id}, 平台ID: {platform_id}, 任务类型: {task_type}")
            if task_type == 0 or task_type == 4:  # 培训博主列表
                data = await self.get_training_blogger_data(platform_id, batch_size)
            elif task_type == 1 or task_type == 2 or task_type == 3 or task_type == 5:  # 博主详情任务
                data = await self.get_blogger_info_data(task_id, batch_size, client_id)
            elif task_type == 6:  # 博主详情任务
                data = await self.get_out_blogger_cooperator_data(task_id, batch_size, client_id)
            elif task_type == 7:  # 博主详情任务
                data = await self.get_note_detail_blogger_data(task_id, batch_size, client_id)
            else:
                data = []
            
            # 记录批次信息
            if data:
                # 记录批次信息的逻辑可以在这里实现
                pass
            
            return data, batch_id
            
        except Exception as e:
            logger.error(f"获取任务数据失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return [], 0

    # 飞书博主列表
    async def get_blogger_info_data(self, task_id: int, batch_size: int, client_id) -> List[Dict[str, Any]]:
        """获取博主信息数据"""
        try:
            if task_id and client_id:
                pre_list = await self.fp_spider_blogger_dao.list_fp_blogger(batch_size, task_id, client_id, 1)
            if pre_list and len(pre_list) > 0:
                return pre_list

            result = await self.fp_spider_blogger_dao.list_fp_blogger(batch_size, task_id, client_id, 0)
            return result
        except Exception as e:
            logger.error(f"获取博主信息数据失败: {e}")
            return {}

    # 飞书博主列表
    async def get_out_blogger_cooperator_data(self, task_id: int, batch_size: int, client_id) -> List[Dict[str, Any]]:
        """获取博主信息数据"""
        try:
            if task_id and client_id:
                pre_list = await self.fp_out_blogger_cooperator_dao.list_fp_blogger(batch_size, task_id, client_id, 1)
            if pre_list and len(pre_list) > 0:
                return pre_list

            result = await self.fp_out_blogger_cooperator_dao.list_fp_blogger(batch_size, task_id, client_id, 0)
            return result
        except Exception as e:
            logger.error(f"获取博主信息数据失败: {e}")
            return {}

    # 20万博主笔记任务-博主信息列表
    async def get_note_detail_blogger_data(self, task_id: int, batch_size: int, client_id) -> List[Dict[str, Any]]:
        try:
            result = await self.note_detail_blogger_dao.list_note_detail_blogger(batch_size, task_id, client_id, 1)
            if result and len(result) > 0:
                return result
            result = await self.note_detail_blogger_dao.list_note_detail_blogger(batch_size, task_id, client_id, 0)
            return result
        except Exception as e:
            logger.error(f"获取博主信息数据失败: {e}")
            return {}

    async def get_training_blogger_data(self, platform_id: int, batch_size: int) -> List[Dict[str, Any]]:
        try:
            result = await self.training_blogger_details_dao.list_training_blogger_details(batch_size);
            return result
        except Exception as e:
            logger.error(f"获取培训博主数据失败: {e}")
            return {}

    # 培训博主列表
    async def get_blogger_note_detail_data(self, platform_id: int, batch_size: int) -> List[Dict[str, Any]]:
        """获取博主笔记详情数据"""
        try:
            query = """
                SELECT * FROM fp_blogger_note_detail 
                WHERE platform_id = :platform_id AND status = 0 
                LIMIT :batch_size
            """
            return await self.fetch_all(query, {"platform_id": platform_id, "batch_size": batch_size})
        except Exception as e:
            logger.error(f"获取博主笔记详情数据失败: {e}")
            return []

    async def get_blogger_detail_data(self, platform_id: int, batch_size: int) -> List[Dict[str, Any]]:
        """获取博主详情数据"""
        try:
            query = """
            SELECT * FROM fp_blogger_detail 
            WHERE platform_id = :platform_id AND status = 0 
            LIMIT :batch_size
            """
            return await self.fetch_all(query, {"platform_id": platform_id, "batch_size": batch_size})
        except Exception as e:
            logger.error(f"获取博主详情数据失败: {e}")
            return []


# 创建全局服务实例
task_service = TaskService() 