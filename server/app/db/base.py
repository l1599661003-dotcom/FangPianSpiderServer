from typing import Dict, List, Any, Optional
from datetime import datetime

from loguru import logger
from sqlalchemy import text

from server.app.db.context import get_mongodb_collection
from server.app.db.database import get_db


class MySQLBaseDAO:
    """MySQL数据访问基类"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
    
    def _debug_sql(self, sql: str, params: Optional[Dict[str, Any]] = None):
        """
        调试SQL语句和参数
        """
        if params:
            # 替换SQL中的参数占位符
            debug_sql = sql
            for key, value in params.items():
                placeholder = f":{key}"
                if isinstance(value, str):
                    value = f"'{value}'"
                debug_sql = debug_sql.replace(placeholder, str(value))
            
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理参数中的特殊值
        """
        if not params:
            return {}
            
        cleaned = {}
        for key, value in params.items():
            if isinstance(value, datetime):
                # 将datetime对象转换为字符串
                cleaned[key] = value.strftime("%Y-%m-%d %H:%M:%S")
            else:
                cleaned[key] = value
        return cleaned
    
    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """执行 SQL 语句"""
        async for session in get_db():
            try:
                # 调试SQL
                # self._debug_sql(sql, params)
                
                # 处理参数中的特殊值
                cleaned_params = self._sanitize_params(params) if params else None
                
                result = await session.execute(text(sql), cleaned_params)
                await session.commit()  # 显式提交事务
                return result
            except Exception as e:
                await session.rollback()  # 出错时回滚事务
                # logger.error(f"执行SQL失败: {sql}, 参数: {params}, 错误: {str(e)}")
                raise
    
    async def fetch_one(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """获取单条记录"""
        result = await self.execute(sql, params)
        row = result.fetchone()
        return dict(row._mapping) if row else None
    
    async def fetch_all(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """获取多条记录"""
        result = await self.execute(sql, params)
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]
    
    async def insert(self, data: Dict[str, Any]) -> int:
        """插入记录"""
        # 处理可能的大整数和字符串数字
        sanitized_data = self._sanitize_params(data)
        
        columns = ', '.join(sanitized_data.keys())
        placeholders = ', '.join(f':{k}' for k in sanitized_data.keys())
        sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        
        try:
            result = await self.execute(sql, sanitized_data)
            return result.lastrowid
        except Exception as e:
            # logger.error(f"插入记录失败: {e}, 表: {self.table_name}, 数据: {sanitized_data}")
            raise
    
    async def update(self, data: Dict[str, Any], where: Dict[str, Any]) -> int:
        """更新记录"""
        set_clause = ', '.join(f"{k} = :{k}" for k in data.keys())
        where_clause = ' AND '.join(f"{k} = :where_{k}" for k in where.keys())
        # logger.info(f"更新记录: {self.table_name}, {set_clause}, {where_clause}")
        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"
        
        # 合并参数并处理特殊值
        params = {**data}
        params.update({f"where_{k}": v for k, v in where.items()})
        
        result = await self.execute(sql, params)
        return result.rowcount
    
    async def delete(self, where: Dict[str, Any]) -> int:
        """删除记录"""
        where_clause = ' AND '.join(f"{k} = :{k}" for k in where.keys())
        sql = f"DELETE FROM {self.table_name} WHERE {where_clause}"
        result = await self.execute(sql, where)
        return result.rowcount

    async def batch_insert(self, fields: List[str], values: List[Any]) -> int:
        """
        批量插入数据
        
        Args:
            fields: 字段列表
            values: 值列表，每个元素可以是元组或列表
            
        Returns:
            插入的记录数
        """
        if not fields or not values:
            return 0
            
        try:
            # 构建插入SQL，使用命名参数
            column_names = ', '.join(fields)
            param_names = ', '.join([f":{field}" for field in fields])
            sql = f"""
                INSERT INTO {self.table_name} 
                ({column_names}) 
                VALUES ({param_names})
            """
            
            # 记录SQL查询
            # logger.info(f"批量插入SQL: {sql}")
            
            # 构建参数字典列表
            params_list = []
            for row in values:
                # 将行数据转换为字典
                row_dict = {fields[i]: value for i, value in enumerate(row) if i < len(fields)}
                params_list.append(row_dict)
            
            # 执行批量插入
            count = 0
            async for session in get_db():
                for params in params_list:
                    try:
                        # 使用参数字典执行插入
                        await session.execute(text(sql), params)
                        count += 1
                    except Exception as e:
                        logger.error(f"插入失败: {e}")
                
                # 提交事务
                await session.commit()
                return count
                
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            raise

    async def delete_by_key(self, key_field: str, data: Dict[str, Any]) -> int:
        """
        根据主键删除记录
        
        Args:
            key_field: 主键字段名
            data: 包含主键值的数据字典
            
        Returns:
            删除的记录数
        """
        if key_field not in data:
            logger.error(f"删除失败: 数据中不包含主键 {key_field}")
            return 0
            
        where = {key_field: data[key_field]}
        try:
            return await self.delete(where)
        except Exception as e:
            logger.error(f"通过主键删除记录失败: {str(e)}, 表: {self.table_name}, 主键: {key_field}={data[key_field]}")
            raise

    async def batch_delete_by_keys(self, key_field: str, values: List[Any]) -> int:
        """
        根据业务键批量删除记录
        
        Args:
            key_field: 业务键字段名
            values: 业务键值列表
            
        Returns:
            删除的记录数
        """
        if not values:
            return 0
            
        try:
            # 构建IN条件进行批量删除
            placeholders = ", ".join([":val_" + str(i) for i in range(len(values))])
            # 构建参数字典
            params = {f"val_{i}": val for i, val in enumerate(values)}

            # 通过条件查询是否存在记录
            sql = f"SELECT id FROM {self.table_name} WHERE {key_field} IN ({placeholders})"
            result = await self.fetch_all(sql, params)
            if len(result) == 0:
                logger.info(f"没有找到有效的业务键值，表: {self.table_name}")
                return 0
            placeholders = ", ".join([str(id.get('id')) for id in result])
            sql = f"DELETE FROM {self.table_name} WHERE id IN ({placeholders})"
            # 执行删除操作
            result = await self.execute(sql)

            deleted_count = result.rowcount
            # logger.info(f"批量删除 {deleted_count} 条数据，表: {self.table_name}, 字段: {key_field}")
            return deleted_count
        except Exception as e:
            # logger.error(f"批量删除记录失败: {str(e)}, 表: {self.table_name}, 字段: {key_field}, 值数量: {len(values)}")
            raise

    async def batch_delete_by_composite_keys(self, key_fields: List[str], rows: List[Dict[str, Any]]) -> int:
        """
        根据联合业务键批量删除记录

        Args:
            key_fields: 联合业务键字段名列表
            rows: 包含联合业务键的数据列表

        Returns:
            删除的记录数
        """
        if not key_fields or not rows:
            return 0

        valid_rows = [
            row for row in rows
            if all(field in row and row[field] is not None for field in key_fields)
        ]
        if not valid_rows:
            return 0

        try:
            or_clauses = []
            params: Dict[str, Any] = {}

            for row_index, row in enumerate(valid_rows):
                and_clauses = []
                for field in key_fields:
                    param_name = f"{field}_{row_index}"
                    and_clauses.append(f"{field} = :{param_name}")
                    params[param_name] = row[field]
                or_clauses.append("(" + " AND ".join(and_clauses) + ")")

            sql = f"DELETE FROM {self.table_name} WHERE " + " OR ".join(or_clauses)
            result = await self.execute(sql, params)
            return result.rowcount
        except Exception as e:
            logger.error(f"联合键批量删除失败: {str(e)}, 表: {self.table_name}, 字段: {key_fields}")
            raise


class MongoDBBaseDAO:
    """MongoDB数据访问基类"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    async def get_collection(self):
        """获取集合对象"""
        async for session in get_mongodb_collection(self.collection_name):
            return session

    async def insert_one(self, document: Dict[str, Any]) -> str:
        """插入单个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            # logger.error(f"Failed to insert document: {document}, error: {str(e)}")
            raise

    async def insert_many(self, documents: List[Dict[str, Any]]) -> List[str]:
        """插入多个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.insert_many(documents)
            return [str(id) for id in result.inserted_ids]
        except Exception as e:
            # logger.error(f"Failed to insert documents: {documents}, error: {str(e)}")
            raise

    async def find_one(self, filter: Dict[str, Any], projection: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """查询单个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.find_one(filter, projection)
            return result
        except Exception as e:
            # logger.error(f"Failed to find document: {filter}, error: {str(e)}")
            raise

    async def find_many(self, filter: Dict[str, Any], projection: Optional[Dict[str, Any]] = None, batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        查询多个文档，支持分页
        
        Args:
            filter: 查询条件
            projection: 投影条件
            batch_size: 每页大小，如果为None则返回所有数据
            
        Returns:
            文档列表
        """
        try:
            async with get_mongodb_collection(self.collection_name) as collection:
                if batch_size:
                    # 使用分页查询
                    cursor = collection.find(filter, projection).limit(batch_size)
                else:
                    # 不使用分页
                    cursor = collection.find(filter, projection)
                return await cursor.to_list(length=None)
        except Exception as e:
            # logger.error(f"Failed to find documents: {filter}, error: {str(e)}")
            raise

    async def update_one(self, filter: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> int:
        """更新单个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.update_one(filter, {"$set": update}, upsert=upsert)
            return result.modified_count
        except Exception as e:
            # logger.error(f"Failed to update document: {filter}, {update}, error: {str(e)}")
            raise

    async def update_many(self, filter: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> int:
        """更新多个文档"""
        try:
            async with get_mongodb_collection(self.collection_name) as collection:
                result = await collection.update_many(filter, {"$set": update}, upsert=upsert)
                return result.modified_count
        except Exception as e:
            # logger.error(f"Failed to update documents: {filter}, {update}, error: {str(e)}")
            raise

    async def delete_one(self, filter: Dict[str, Any]) -> int:
        """删除单个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.delete_one(filter)
            return result.deleted_count
        except Exception as e:
            # logger.error(f"Failed to delete document: {filter}, error: {str(e)}")
            raise

    async def delete_many(self, filter: Dict[str, Any]) -> int:
        """删除多个文档"""
        try:
            collection = await self.get_collection()
            result = await collection.delete_many(filter)
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to delete documents: {filter}, error: {str(e)}")
            raise 
