import os
from contextvars import ContextVar
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from starlette.requests import Request

# 创建一个上下文变量来存储数据库连接
mongodb_connection_context = ContextVar("mongodb_connection", default=None)


class MongoDB:
    """MongoDB连接管理器"""
    
    def __init__(self):
        """初始化MongoDB连接管理器"""
        self.client = None
        self.db = None
    
    async def connect(self):
        """连接到MongoDB"""
        try:
            # 从环境变量获取MongoDB配置
            mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            mongodb_db = os.getenv("MONGODB_DB", "fangpian")
            
            # 创建连接
            self.client = AsyncIOMotorClient(mongodb_uri)
            self.db = self.client[mongodb_db]
            
            logger.info(f"MongoDB连接成功: {mongodb_uri}/{mongodb_db}")
            
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
    
    async def disconnect(self):
        """断开MongoDB连接"""
        if self.client:
            self.client.close()
            logger.info("MongoDB连接已关闭")
    
    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """
        获取MongoDB集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            MongoDB集合对象
        """
        if self.db is None:
            raise ValueError("MongoDB连接未初始化")
        
        return self.db[collection_name]
    
    async def find_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        查询单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            查询结果文档
        """
        collection = self.get_collection(collection_name)
        return await collection.find_one(filter_dict)
    
    async def find_many(self, collection_name: str, filter_dict: Dict[str, Any], limit: int = 0, skip: int = 0) -> List[Dict[str, Any]]:
        """
        查询多个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            limit: 限制数量，0表示不限制
            skip: 跳过数量
            
        Returns:
            查询结果文档列表
        """
        collection = self.get_collection(collection_name)
        cursor = collection.find(filter_dict)
        
        if skip > 0:
            cursor = cursor.skip(skip)
        
        if limit > 0:
            cursor = cursor.limit(limit)
        
        return await cursor.to_list(length=None)
    
    async def insert_one(self, collection_name: str, document: Dict[str, Any]) -> str:
        """
        插入单个文档
        
        Args:
            collection_name: 集合名称
            document: 要插入的文档
            
        Returns:
            插入文档的ID
        """
        collection = self.get_collection(collection_name)
        result = await collection.insert_one(document)
        return str(result.inserted_id)
    
    async def insert_many(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[str]:
        """
        批量插入文档
        
        Args:
            collection_name: 集合名称
            documents: 要插入的文档列表
            
        Returns:
            插入文档的ID列表
        """
        collection = self.get_collection(collection_name)
        result = await collection.insert_many(documents)
        return [str(id) for id in result.inserted_ids]
    
    async def update_one(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """
        更新单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            update_dict: 更新内容
            
        Returns:
            匹配的文档数量
        """
        collection = self.get_collection(collection_name)
        result = await collection.update_one(filter_dict, {"$set": update_dict})
        return result.matched_count
    
    async def update_many(self, collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
        """
        批量更新文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            update_dict: 更新内容
            
        Returns:
            匹配的文档数量
        """
        collection = self.get_collection(collection_name)
        result = await collection.update_many(filter_dict, {"$set": update_dict})
        return result.matched_count
    
    async def delete_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """
        删除单个文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            删除的文档数量
        """
        collection = self.get_collection(collection_name)
        result = await collection.delete_one(filter_dict)
        return result.deleted_count
    
    async def delete_many(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """
        批量删除文档
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            删除的文档数量
        """
        collection = self.get_collection(collection_name)
        result = await collection.delete_many(filter_dict)
        return result.deleted_count
    
    async def count_documents(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """
        统计文档数量
        
        Args:
            collection_name: 集合名称
            filter_dict: 过滤条件
            
        Returns:
            文档数量
        """
        collection = self.get_collection(collection_name)
        return await collection.count_documents(filter_dict)
    
    async def create_collection(self, collection_name: str) -> bool:
        """
        创建集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            是否创建成功
        """
        try:
            await self.db.create_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"创建集合失败: {e}, 集合名称: {collection_name}")
            return False
    
    async def list_collections(self) -> List[str]:
        """
        获取所有集合名称
        
        Returns:
            集合名称列表
        """
        collections = await self.db.list_collection_names()
        return collections


async def get_mongodb() -> AsyncGenerator[MongoDB, None]:
    """
    获取MongoDB连接上下文管理器
    
    使用示例:
    ```
    async with get_mongodb() as mongo:
        result = await mongo.find_one("users", {"username": "test"})
    ```
    
    Returns:
        MongoDB连接上下文管理器
    """
    mongo = MongoDB()
    
    # 如果还未连接，先连接
    if mongo.client is None:
        await mongo.connect()
    
    token = mongodb_connection_context.set(mongo)
    
    try:
        yield mongo
    finally:
        mongodb_connection_context.reset(token)


# 中间件：将MongoDB连接添加到请求对象
async def mongodb_middleware(request: Request, call_next: Any):
    """MongoDB中间件"""
    mongo = MongoDB()
    await mongo.connect()
    request.state.mongodb = mongo
    
    try:
        response = await call_next(request)
    finally:
        if hasattr(request.state, "mongodb"):
            await mongo.disconnect()
    
    return response


# 初始化MongoDB
mongodb = MongoDB()


# 启动时连接MongoDB
async def connect_mongodb():
    """启动时连接MongoDB"""
    await mongodb.connect()


# 关闭时断开MongoDB连接
async def disconnect_mongodb():
    """关闭时断开MongoDB连接"""
    await mongodb.disconnect() 