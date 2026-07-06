from contextlib import contextmanager

import mysql.connector
from loguru import logger


class MysqlDatabaseManager:
    def __init__(self):
        """
        初始化数据库管理器
        :param db_name: 数据库名称
        """
        self.db_config = {
            'host': '47.104.13.93',
            'user': 'fpdev',
            'password': 'fpdev',
            'database': "tibao_2",
            # 'auth_plugin': 'mysql_native_password'  # 添加这一行以指定认证插件
            'auth_plugin': 'caching_sha2_password'  # 添加这一行以指定认证插件
        }

    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        使用方法:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
        """
        conn = None
        try:
            conn = mysql.connector.connect(**self.db_config)
            yield conn
        except Exception as e:
            logger.error(f"数据库连接错误: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
