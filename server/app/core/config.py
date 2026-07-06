import os
from typing import Dict, Any
from dotenv import load_dotenv
from pathlib import Path

from loguru import logger
from pydantic_settings import BaseSettings


# 加载环境变量
env_path = Path(__file__).parents[3] / 'server/.env'
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    APP_NAME: str = "FangPian Spider Server"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # MySQL配置
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "fpdev")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "fpdev")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "fangpian")
    MYSQL_CHARSET: str = os.getenv("MYSQL_CHARSET", "utf8mb4")
    MYSQL_POOL_SIZE: int = int(os.getenv("MYSQL_POOL_SIZE", "5"))
    MYSQL_POOL_RECYCLE: int = int(os.getenv("MYSQL_POOL_RECYCLE", "3600"))
    
    # SQLAlchemy配置
    SQLALCHEMY_ECHO: bool = os.getenv("SQLALCHEMY_ECHO", "False").lower() == "true"
    SQLALCHEMY_POOL_SIZE: int = int(os.getenv("SQLALCHEMY_POOL_SIZE", "5"))
    SQLALCHEMY_POOL_TIMEOUT: int = int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "30"))
    SQLALCHEMY_POOL_RECYCLE: int = int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "3600"))
    SQLALCHEMY_MAX_OVERFLOW: int = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10"))
    
    # MongoDB配置
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "fangpian")
    MONGODB_POOL_SIZE: int = int(os.getenv("MONGODB_POOL_SIZE", "5"))


# 创建全局配置实例
settings = Settings()
logger.info(f"数据库配置: {settings.dict()}")


class DatabaseConfig:
    """数据库配置管理"""
    
    @staticmethod
    def get_database_url() -> str:
        """获取数据库URL"""
        return (
            f"mysql+asyncmy://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@"
            f"{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
    
    @staticmethod
    def get_database_config() -> Dict[str, Any]:
        """获取数据库配置 (SQLAlchemy)"""
        return {
            'url': DatabaseConfig.get_database_url(),
            'pool_size': settings.SQLALCHEMY_POOL_SIZE,
            'pool_timeout': settings.SQLALCHEMY_POOL_TIMEOUT,
            'pool_recycle': settings.SQLALCHEMY_POOL_RECYCLE,
            'max_overflow': settings.SQLALCHEMY_MAX_OVERFLOW,
            'echo': settings.SQLALCHEMY_ECHO,
            'pool_pre_ping': True
        }
    
    @staticmethod
    def get_mysql_pool_config() -> Dict[str, Any]:
        """获取MySQL连接池配置 (aiomysql)"""
        config = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'db': settings.MYSQL_DATABASE,
            'charset': settings.MYSQL_CHARSET,
            'maxsize': settings.MYSQL_POOL_SIZE,
            'minsize': 1,
            'pool_recycle': settings.MYSQL_POOL_RECYCLE,
            'autocommit': True
        }
        logger.info(f"MySQL连接池配置: {config}")
        return config
    
    @staticmethod
    def get_mongodb_config() -> Dict[str, Any]:
        """获取MongoDB配置"""
        return {
            'uri': settings.MONGODB_URI,
            'database': settings.MONGODB_DATABASE,
            'maxPoolSize': settings.MONGODB_POOL_SIZE
        }
