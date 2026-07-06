import asyncio
from datetime import datetime
import traceback
from typing import Dict, List, Any

from loguru import logger

from server.app.db.base import MySQLBaseDAO, MongoDBBaseDAO
from server.app.services.sync.field_mapper import FIELD_TRANSFORMERS, FIELD_TYPES, FieldMapper
from server.app.services.sync.table_mapper import TABLE_MAPPING


class MongoToMySQLSyncService:
    """MongoDB到MySQL的数据同步服务"""
    
    def __init__(self):
        self.table_mapper = TABLE_MAPPING
    
    async def initialize(self):
        """初始化服务，预加载缓存数据"""
        logger.info("正在初始化同步服务...")
        # 预加载MCN缓存
        await FieldMapper.load_mcn_cache()
        logger.info("同步服务初始化完成")
        
    async def sync_table(self, collection_name: str):
        """同步单个表的数据"""
        try:
            # 1. 获取表映射配置
            table_config = self.table_mapper[collection_name]
            mongo_dao = MongoDBBaseDAO(collection_name)
            mysql_dao = MySQLBaseDAO(table_config['mysql_table'])
            
            # 2. 分页查询并处理未同步的数据
            batch_size = table_config.get('batch_size', 1000)  # 默认每页1000条
            total_synced = 0
            
            while True:
                # 查询当前页的未同步数据
                unsynced_data = await mongo_dao.find_many(
                    {table_config['sync_key']: 0},
                    batch_size=batch_size
                )
                
                if not unsynced_data:
                    if total_synced == 0:
                        logger.info(f"集合 {collection_name} 没有需要同步的数据")
                    else:
                        logger.info(f"集合 {collection_name} 同步完成，共同步 {total_synced} 条数据")
                    break
                
                # 3. 转换数据格式
                transformed_data = await self._transform_data(
                    unsynced_data, 
                    table_config['fields']
                )
                
                # 4. 批量插入或更新MySQL
                if transformed_data:
                    try:
                        # 构建批量插入数据
                        fields = list(table_config['fields'].values())
                        values = [
                            [doc.get(field, None) for field in fields]
                            for doc in transformed_data
                        ]
                        
                        if table_config.get('is_update', True):
                            # 执行更新操作
                            await self._update_mysql_data(mysql_dao, transformed_data, table_config)
                        else:
                            # 通过主键删除历史数据
                            primary_key = table_config['primary_key']
                            mysql_primary_key = table_config['fields'][primary_key]
                            
                            # 构建业务键值列表
                            key_values = [doc[mysql_primary_key] for doc in transformed_data if mysql_primary_key in doc]
                            
                            if key_values:
                                # 批量删除历史数据
                                deleted_count = await mysql_dao.batch_delete_by_keys(mysql_primary_key, key_values)
                                logger.info(f"批量删除历史数据成功，表: {table_config['mysql_table']}, 删除记录数: {deleted_count}")
                            else:
                                logger.warning(f"没有找到有效的业务键值，表: {table_config['mysql_table']}")

                            # 执行插入操作
                            await mysql_dao.batch_insert(fields, values)
                        
                        # 更新MongoDB同步状态
                        ids = [doc.get(table_config['primary_key']) for doc in unsynced_data if table_config['primary_key'] in doc]
                        await mongo_dao.update_many(
                            {table_config['primary_key']: {'$in': ids}},
                            {table_config['sync_key']: 1}
                        )
                        
                        total_synced += len(transformed_data)
                        logger.info(f"成功同步当前批次 {len(transformed_data)} 条数据从 {collection_name} 到 {table_config['mysql_table']}")
                        
                    except Exception as e:
                        logger.error(f"MySQL数据操作失败: {str(e)}")
                        raise
                
                await asyncio.sleep(1)
                
        except Exception as e:
            traceback.print_exc()
            logger.exception(f"同步表 {collection_name} 失败")
            logger.error(f"同步表 {collection_name} 失败: {str(e)}")

            raise

    async def sync_table_by_data(self, collection_name: str, data: List[Dict[str, Any]]):
        """同步单个表的数据"""
        try:
            # 1. 获取表映射配置
            table_config = self.table_mapper[collection_name]
            mysql_dao = MySQLBaseDAO(table_config['mysql_table'])
            
            if not data:
                logger.info(f"集合 {collection_name} 没有需要同步的数据")
                return
            
            # 3. 转换数据格式
            transformed_data = await self._transform_data(
                data, 
                table_config['fields']
            )
            
            # 4. 批量插入或更新MySQL
            if transformed_data:
                try:
                    # 构建批量插入数据
                    fields = list(table_config['fields'].values())
                    values = [
                        [doc.get(field, None) for field in fields]
                        for doc in transformed_data
                    ]
                    
                    if table_config.get('is_update', True):
                        # 执行更新操作
                        await self._update_mysql_data(mysql_dao, transformed_data, table_config)
                    else:
                        # 通过主键删除历史数据
                        primary_key = table_config['primary_key']
                        mysql_primary_key = table_config['fields'][primary_key]
                        
                        # 构建业务键值列表
                        key_values = [doc[mysql_primary_key] for doc in transformed_data if mysql_primary_key in doc]
                        
                        if key_values:
                            # 批量删除历史数据
                            deleted_count = await mysql_dao.batch_delete_by_keys(mysql_primary_key, key_values)
                            logger.info(f"批量删除历史数据成功，表: {table_config['mysql_table']}, 删除记录数: {deleted_count}")
                        else:
                            logger.warning(f"没有找到有效的业务键值，表: {table_config['mysql_table']}")

                        # 执行插入操作
                        await mysql_dao.batch_insert(fields, values)
                    
                    logger.info(f"成功同步当前批次 {len(transformed_data)} 条数据从 {collection_name} 到 {table_config['mysql_table']}")
                    
                except Exception as e:
                    logger.error(f"MySQL数据操作失败: {str(e)}")
                    raise
            
            await asyncio.sleep(1)
                
        except Exception as e:
            traceback.print_exc()
            logger.exception(f"同步表 {collection_name} 失败")
            logger.error(f"同步表 {collection_name} 失败: {str(e)}")
            raise

    async def _update_mysql_data(self, mysql_dao: MySQLBaseDAO, data: List[Dict[str, Any]], table_config: Dict[str, Any]):
        """
        更新MySQL数据，如果数据不存在则插入
        
        Args:
            mysql_dao: MySQL数据访问对象
            data: 转换后的数据列表
            table_config: 表配置信息
        """
        try:
            # 获取主键字段
            primary_key = table_config['primary_key']
            mysql_primary_key = table_config['fields'][primary_key]
            
            # 获取所有主键值
            primary_keys = [doc.get(mysql_primary_key) for doc in data if mysql_primary_key in doc]
            primary_keys.append('0')
            # 批量查询已存在的数据
            existing_data = await mysql_dao.fetch_all(
                f"SELECT {mysql_primary_key} FROM {table_config['mysql_table']} WHERE {mysql_primary_key} IN :primary_keys",
                {"primary_keys": tuple(primary_keys)}  # 将列表转换为元组
            )
            existing_keys = {row[mysql_primary_key] for row in existing_data}
            
            # 分离需要插入和更新的数据
            to_insert = []
            to_update = []
            
            for doc in data:
                if mysql_primary_key in doc and doc[mysql_primary_key] in existing_keys:
                    to_update.append(doc)
                else:
                    to_insert.append(doc)
            
            # 批量插入新数据
            if to_insert:
                fields = list(table_config['fields'].values())
                # 将列表转换为元组列表
                values = [tuple(doc.get(field, None) for field in fields) for doc in to_insert]
                await mysql_dao.batch_insert(fields, values)
                logger.info(f"批量插入 {len(to_insert)} 条数据")
            
            # 批量更新已存在的数据
            if to_update:
                update_fields = [field for field in table_config['fields'].values() if field != mysql_primary_key]
                for doc in to_update:
                    where = {mysql_primary_key: doc.get(mysql_primary_key)}
                    update_data = {field: doc.get(field, None) for field in update_fields}
                    # 使用当前时间戳（秒数）
                    current_timestamp = int(datetime.now().timestamp())
                    # update_data['update_time'] = current_timestamp

                    await mysql_dao.update(update_data, where)
                logger.info(f"批量更新 {len(to_update)} 条数据")
                
        except Exception as e:
            logger.error(f"更新MySQL数据失败: {str(e)}")
            raise
            
    async def _transform_data(self, mongo_data: List[Dict[str, Any]], field_mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        转换数据格式，支持异步转换器
        
        Args:
            mongo_data: MongoDB文档列表
            field_mapping: 字段映射配置
            
        Returns:
            转换后的数据列表
        """
        transformed = []
        for doc in mongo_data:
            transformed_doc = {}
            
            # 先处理所有非异步转换字段
            for mongo_field, mysql_field in field_mapping.items():
                # 获取字段值，如果不存在则为None
                value = doc.get(mongo_field)
                
                # 仅处理非异步转换器
                if mysql_field in FIELD_TYPES:
                    transformer = FIELD_TRANSFORMERS.get(FIELD_TYPES[mysql_field])
                    # 跳过异步转换器，稍后处理
                    if transformer and not asyncio.iscoroutinefunction(transformer) and value is not None:
                        value = transformer(value)
                transformed_doc[mysql_field] = value
            
            # 再处理异步转换字段
            for mongo_field, mysql_field in field_mapping.items():
                if mysql_field in FIELD_TYPES:
                    field_type = FIELD_TYPES[mysql_field]
                    transformer = FIELD_TRANSFORMERS.get(field_type)
                    if transformer and asyncio.iscoroutinefunction(transformer):
                        # 执行异步转换
                        value = doc.get(mongo_field)
                        if value is not None:
                            transformed_doc[mysql_field] = await transformer(value)
            
            transformed.append(transformed_doc)
        
        return transformed 