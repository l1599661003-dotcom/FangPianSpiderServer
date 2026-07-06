from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
import aiomysql
from loguru import logger

from server.app.db.pool import MySQLPool, MongoDBPool


@asynccontextmanager
async def get_mysql_conn() -> AsyncGenerator[aiomysql.Connection, None]:
    """
    获取MySQL连接的上下文管理器
    
    使用示例:
    ```python
    async with get_mysql_conn() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users")
            result = await cursor.fetchall()
    ```
    """
    pool = await MySQLPool.get_instance()
    conn = await pool.get_conn()
    try:
        yield conn
    finally:
        await pool.release_conn(conn)


@asynccontextmanager
async def get_mongodb_collection(collection_name: str):
    """
    获取MongoDB集合的上下文管理器
    
    使用示例:
    ```python
    async with get_mongodb_collection("users") as collection:
        result = await collection.find_one({"username": "test"})
    ```
    """
    pool = await MongoDBPool.get_instance()
    try:
        collection = pool.get_collection(collection_name)
        yield collection
    except Exception as e:
        logger.error(f"获取MongoDB集合失败: {e}")
        raise
    finally:
        # MongoDB的连接由连接池自动管理，这里不需要手动释放
        pass


class DatabaseManager:
    """数据库管理器，用于管理数据库连接池的生命周期"""
    
    _mysql_pool: Optional[MySQLPool] = None
    _mongodb_pool: Optional[MongoDBPool] = None
    
    @classmethod
    async def initialize(cls):
        """初始化所有数据库连接池"""
        try:
            # 初始化MySQL连接池
            cls._mysql_pool = await MySQLPool.get_instance()
            
            # 初始化MongoDB连接池
            cls._mongodb_pool = await MongoDBPool.get_instance()
            
            logger.info("数据库连接池初始化成功")
            
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            raise
    
    @classmethod
    async def close(cls):
        """关闭所有数据库连接池"""
        try:
            # 关闭MySQL连接池
            if cls._mysql_pool:
                await cls._mysql_pool.close()
            
            # 关闭MongoDB连接池
            if cls._mongodb_pool:
                await cls._mongodb_pool.close()
            
            logger.info("数据库连接池已关闭")
            
        except Exception as e:
            logger.error(f"关闭数据库连接池失败: {e}")
            raise 