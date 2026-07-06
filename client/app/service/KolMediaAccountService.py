from typing import List, Dict, Any

from loguru import logger

from client.app.core.database.mysql_database_manager import MysqlDatabaseManager


class KolMediaAccountService:
    def __init__(self):
        self.db = MysqlDatabaseManager()

    # 获取媒体账号
    def get_kol_media_accounts(self, xhsIds: List[int], is_enables: List[int], id: int) -> List[Dict[str, Any]]:
        try:
            sql = f'''
                SELECT * 
                FROM kol_media_accounts kma 
                where 1 = 1
            ''';

            if len(is_enables) > 0:
                sql = f"""
                    {sql} and kma.is_enable in ('{"','".join(is_enables)}')
                """
            if len(xhsIds) > 0:
                sql = f"""
                    {sql} and kma.dandelion_platform_id in ('{"','".join(xhsIds)}')
                """
            if id:
                sql = f"{sql} and kma.id = {id}"
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    # 根据小红书ID查询媒体账号
    def get_kol_media_account_by_xhs_id(self, xhs_id: str) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                SELECT * 
                FROM kol_media_accounts kma 
                where dandelion_platform_id = '{xhs_id}'
            """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchone()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    def get_kol_media_account_by_id(self, id: str) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                SELECT * 
                FROM kol_media_accounts kma 
                where id = '{id}'
            """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchone()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    # 根据小红书ID查询媒体账号
    def get_kol_business_media_account_by_account_id(self, xhs_id: str) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                SELECT * 
                FROM kol_business_media_accounts kma 
                where media_account_id = '{xhs_id}'
            """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchone()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    # 根据小红书ID查询媒体账号
    def get_admin_user_by_id(self, id: str) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                SELECT * 
                FROM admin_users kma 
                where id = '{id}'
            """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchone()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    # 根据小红书ID查询媒体账号
    def get_admin_group_by_id(self, id: str) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                SELECT * 
                FROM admin_user_groups kma 
                where id = '{id}'
            """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchone()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    def get_pendant_account_joins_by_account_id(self, account_id) -> List[Dict[str, Any]]:
        try:
            sql = f"""
                    SELECT GROUP_CONCAT(CONCAT(p2.name, '-->', p.name) SEPARATOR ',') as name
                    FROM tibao_2.pendant_account_joins as j
                    LEFT JOIN tibao_2.pendants as p ON p.id = j.pendant_id
                    LEFT JOIN tibao_2.pendants as p2 ON p2.id = p.p_id
                    WHERE j.account_id = '{account_id}'
                """;
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                data = cursor.fetchall()
                return data
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    def update_kol_media_account(self) -> bool:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                sql = f'''
                    UPDATE kol_media_accounts SET is_update = 1
                '''

                cursor.execute(sql)
                conn.commit()
        except Exception as e:
            logger.error(f"更新媒体账号失败: {str(e)}")
            return False
    

    def insert_kol_media_account_history(self, data: Dict[str, Any]) -> bool:
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                sql = f"""
                        INSERT INTO tibao_2.kol_media_account_history
                        (media_account_id, old_nickname, new_nickname, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """

                cursor.execute(sql, (
                    data.get('media_account_id'),
                    data['old_nickname'],
                    data['new_nickname'],
                    data['created_at'],
                    data['updated_at']
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"更新媒体账号失败: {str(e)}")
            return False

