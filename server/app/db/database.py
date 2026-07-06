from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

from server.app.core.config import DatabaseConfig

# MySQL异步引擎
engine = create_async_engine(
    **DatabaseConfig.get_database_config(),
    future=True
)

# 创建异步会话工厂
async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# MongoDB客户端
mongodb_client = None
mongodb_db = None


async def init_db():
    """初始化数据库连接"""
    global mongodb_client, mongodb_db
    
    try:
        # 测试MySQL连接
        async with engine.begin() as conn:
            logger.info("MySQL connection initialized successfully")
        
        # 初始化MongoDB连接
        mongodb_config = DatabaseConfig.get_mongodb_config()
        mongodb_client = AsyncIOMotorClient(
            mongodb_config['uri'],
            maxPoolSize=mongodb_config['maxPoolSize']
        )
        mongodb_db = mongodb_client[mongodb_config['database']]
        
        # 测试MongoDB连接
        await mongodb_db.command('ping')
        logger.info("MongoDB connection initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database connections: {str(e)}")
        raise


async def close_db():
    """关闭数据库连接"""
    try:
        # 关闭MySQL连接
        await engine.dispose()
        logger.info("MySQL connection closed successfully")
        
        # 关闭MongoDB连接
        if mongodb_client:
            mongodb_client.close()
            logger.info("MongoDB connection closed successfully")
            
    except Exception as e:
        logger.error(f"Failed to close database connections: {str(e)}")
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取MySQL数据库会话"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            await session.close()


def get_mongodb_database():
    """获取MongoDB数据库实例"""
    if not mongodb_db:
        raise RuntimeError("MongoDB not initialized")
    return mongodb_db


async def get_mongodb_collection(collection_name: str):
    """获取MongoDB集合"""
    if not mongodb_db:
        raise RuntimeError("MongoDB not initialized")
    try:
        collection = mongodb_db[collection_name]
        yield collection
    except Exception as e:
        logger.error(f"Failed to get MongoDB collection {collection_name}: {str(e)}")
        raise 