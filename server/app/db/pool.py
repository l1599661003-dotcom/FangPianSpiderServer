from typing import Optional, Dict, Any
import aiomysql
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

from server.app.core.config import DatabaseConfig


class MySQLPool:
    """MySQL连接池管理类"""
    _instance: Optional['MySQLPool'] = None
    _pool: Optional[aiomysql.Pool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls) -> 'MySQLPool':
        """获取MySQL连接池单例"""
        if cls._instance is None:
            cls._instance = cls()
        if cls._pool is None:
            await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        """初始化连接池"""
        try:
            self._pool = await aiomysql.create_pool(**DatabaseConfig.get_mysql_pool_config())
            logger.info("MySQL连接池初始化成功")
        except Exception as e:
            logger.error(f"MySQL连接池初始化失败: {e}")
            raise

    async def get_conn(self) -> aiomysql.Connection:
        """获取数据库连接"""
        if self._pool is None:
            await self.initialize()
        return await self._pool.acquire()

    async def release_conn(self, conn: aiomysql.Connection):
        """释放数据库连接"""
        if self._pool is not None:
            self._pool.release(conn)

    async def close(self):
        """关闭连接池"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            logger.info("MySQL连接池已关闭")


class MongoDBPool:
    """MongoDB连接池管理类"""
    _instance: Optional['MongoDBPool'] = None
    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[Any] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def get_instance(cls) -> 'MongoDBPool':
        """获取MongoDB连接池单例"""
        if cls._instance is None:
            cls._instance = cls()
        if cls._client is None:
            await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        """初始化连接池"""
        try:
            config = DatabaseConfig.get_mongodb_config()
            self._client = AsyncIOMotorClient(config['uri'], maxPoolSize=config['maxPoolSize'])
            self._db = self._client[config['database']]
            logger.info("MongoDB连接池初始化成功")
        except Exception as e:
            logger.error(f"MongoDB连接池初始化失败: {e}")
            raise

    def get_collection(self, collection_name: str):
        """获取集合"""
        if self._db is None:
            raise RuntimeError("MongoDB连接池未初始化")
        return self._db[collection_name]

    async def close(self):
        """关闭连接池"""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB连接池已关闭") 