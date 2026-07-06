from loguru import logger

from server.app.db.database import get_db, get_mongodb_database


# 基础服务类，提供数据库会话管理
class BaseService:
    """基础服务类，提供数据库会话管理"""

    async def __aenter__(self):
        """
        异步进入上下文管理器，创建数据库会话
        """
        try:
            # 获取数据库会话生成器
            self.db_gen = get_db()
            # 获取数据库会话
            self.db = await self.db_gen.__anext__()
            # 获取 MongoDB 数据库实例
            self.mongodb = get_mongodb_database()
            return self
        except Exception as e:
            logger.error(f"创建数据库会话失败: {str(e)}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步退出上下文管理器，关闭数据库会话
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪信息
        """
        try:
            if exc_type is not None:
                # 如果发生异常，记录错误日志
                logger.error(f"服务执行出错: {str(exc_val)}")
                # 回滚事务
                await self.db.rollback()
            else:
                # 提交事务
                await self.db.commit()
        except Exception as e:
            logger.error(f"关闭数据库会话时发生错误: {str(e)}")
            raise
        finally:
            # 确保关闭数据库会话
            await self.db.close()
