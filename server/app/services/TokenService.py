from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from server.app.db.base import MySQLBaseDAO


class TokenService(MySQLBaseDAO):
    """令牌服务，负责管理爬虫令牌"""
    
    def __init__(self):
        super().__init__("fp_spider_token")
        self.token_log_dao = MySQLBaseDAO("fp_spider_token_log")
    
    async def list_token_by_platform_id(self, platform_id: int, account_type : int = None) -> List[Dict[str, Any]]:
        """
        通过平台ID获取可用令牌
        """
        query = "SELECT * FROM fp_spider_token WHERE platform_id = :platform_id AND status = 1"
        if account_type:
            query += " AND account_type = :account_type"
        return await self.fetch_all(query, {"platform_id": platform_id, "account_type": account_type})

    async def get_token_by_id(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        通过ID获取令牌信息
        
        Args:
            token_id: 令牌ID
            
        Returns:
            令牌信息
        """
        try:
            query = "SELECT * FROM fp_spider_token WHERE id = :token_id"
            return await self.fetch_one(query, {"token_id": token_id})
        except Exception as e:
            logger.error(f"获取令牌信息失败: {e}, 令牌ID: {token_id}")
            return None
    
    async def get_available_token(self, platform_id: int) -> Optional[Dict[str, Any]]:
        """
        获取指定平台可用的令牌
        
        Args:
            platform_id: 平台ID
            
        Returns:
            可用的令牌信息
        """
        try:
            # 获取指定平台的所有可用令牌
            query = """
            SELECT * FROM fp_spider_token 
            WHERE platform_id = :platform_id AND status = 1
            """
            tokens = await self.fetch_all(query, {"platform_id": platform_id})
            
            if not tokens:
                logger.warning(f"平台 {platform_id} 没有可用的令牌")
                return None
            
            # 对每个令牌，检查当前使用数量
            for token in tokens:
                token_id = token["id"]
                client_limit = token["client_limit_num"]
                
                # 获取当前正在使用该令牌且未释放的记录数
                usage_query = """
                SELECT COUNT(*) as count FROM fp_spider_token_log
                WHERE token_id = :token_id AND status = 0
                """
                usage_result = await self.token_log_dao.fetch_one(usage_query, {"token_id": token_id})
                
                current_usage = usage_result.get("count", 0) if usage_result else 0
                
                # 如果使用量未达到限制，则可以使用该令牌
                if current_usage < client_limit:
                    logger.info(f"令牌 {token_id} 当前使用量: {current_usage}/{client_limit}")
                    return token
            
            logger.warning(f"平台 {platform_id} 的所有令牌都已达到使用限制")
            return None
            
        except Exception as e:
            logger.error(f"获取可用令牌失败: {e}, 平台ID: {platform_id}")
            return None
    
    async def allocate_token(self, task_id: str, client_id: str, task_log_id: str, platform_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        分配令牌给客户端任务
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            task_log_id: 任务执行日志ID
            platform_id: 平台ID
            
        Returns:
            (是否成功, 令牌信息)
        """
        try:
            # 获取可用令牌
            token = await self.get_available_token(platform_id)
            
            if not token:
                logger.warning(f"无法为任务 {task_id} 分配令牌，没有可用的令牌")
                return False, None
            
            token_id = token["id"]
            token_content = token["token_content"]
            
            # 创建令牌使用记录
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_data = {
                "task_client_log_id": task_log_id,
                "client_id": client_id,
                "task_id": task_id,
                "token_id": token_id,
                "token_content": token_content,
                "status": 0,  # 0表示未释放
                "create_time": now,
                "update_time": now
            }
            
            # 插入令牌使用记录
            await self.token_log_dao.insert(log_data)
            
            logger.info(f"为任务 {task_id} 分配令牌 {token_id} 成功")
            
            # 返回令牌信息
            return True, {
                "token_id": token_id,
                "token_content": token_content
            }
            
        except Exception as e:
            logger.error(f"分配令牌失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return False, None
    
    async def release_token(self, token_id: int) -> bool:
        """
        释放令牌
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            token_id: 令牌ID
            
        Returns:
            是否释放成功
        """
        try:
            # 更新令牌使用记录状态为已释放
            update_query = """
                UPDATE fp_spider_token_log 
                SET status = 1, update_time = :update_time
                WHERE id = :token_id
            """
            
            params = {
                "token_id": token_id,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            result = await self.token_log_dao.execute(update_query, params)
            if result.rowcount > 0:
                logger.info(f"释放令牌成功: 令牌ID: {token_id}")
                return True
            else:
                logger.warning(f"没有找到匹配的令牌使用记录: 令牌ID: {token_id}")
                return False
            
        except Exception as e:
            logger.error(f"释放令牌失败: {e}, 令牌ID: {token_id}")
            return False
    
    async def get_token_usage(self, token_id: str) -> Dict[str, Any]:
        """
        获取令牌使用情况
        
        Args:
            token_id: 令牌ID
            
        Returns:
            令牌使用情况
        """
        try:
            # 获取令牌信息
            token = await self.get_token_by_id(token_id)
            
            if not token:
                return {
                    "token_id": token_id,
                    "limit": 0,
                    "used": 0,
                    "available": 0
                }
            
            # 获取当前使用量
            usage_query = """
            SELECT COUNT(*) as count FROM fp_spider_token_log
            WHERE token_id = :token_id AND status = 0
            """
            usage_result = await self.token_log_dao.fetch_one(usage_query, {"token_id": token_id})
            
            current_usage = usage_result.get("count", 0) if usage_result else 0
            client_limit = token["client_limit_num"]
            
            return {
                "token_id": token_id,
                "limit": client_limit,
                "used": current_usage,
                "available": max(0, client_limit - current_usage)
            }
            
        except Exception as e:
            logger.error(f"获取令牌使用情况失败: {e}, 令牌ID: {token_id}")
            return {
                "token_id": token_id,
                "limit": 0,
                "used": 0,
                "available": 0,
                "error": str(e)
            }
    
    async def get_client_token(self, task_id: str, client_id: str) -> Optional[Dict[str, Any]]:
        """
        获取客户端已分配的令牌信息
        
        Args:
            task_id: 任务ID
            client_id: 客户端ID
            
        Returns:
            令牌信息，如果未分配则返回None
        """
        try:
            # 查询客户端当前使用的令牌
            query = """
            SELECT id, token_id, token_content FROM fp_spider_token_log
            WHERE task_id = :task_id AND client_id = :client_id AND status = 0
            ORDER BY create_time DESC
            LIMIT 1
            """
            
            token_record = await self.token_log_dao.fetch_one(query, {
                "task_id": task_id,
                "client_id": client_id
            })
            
            if not token_record:
                logger.info(f"客户端未分配令牌: 任务ID: {task_id}, 客户端ID: {client_id}")
                return None
            
            logger.info(f"客户端已分配令牌: 任务ID: {task_id}, 客户端ID: {client_id}, 令牌ID: {token_record['token_id']}")
            
            # 返回令牌信息
            return {
                "id": token_record["id"],
                "token_id": token_record["token_id"],
                "token_content": token_record["token_content"]
            }
            
        except Exception as e:
            logger.error(f"获取客户端令牌信息失败: {e}, 任务ID: {task_id}, 客户端ID: {client_id}")
            return None

    async def update_token_status(self, token_log_id: int, status: int):
        token_log = await self.token_log_dao.fetch_one("SELECT * FROM fp_spider_token_log WHERE id = :id", {"id": token_log_id})
        if token_log:
            await self.token_log_dao.execute("UPDATE fp_spider_token SET status = :status WHERE id = :id", {"status": status, "id": token_log.get('token_id')})
# 创建全局服务实例
token_service = TokenService() 