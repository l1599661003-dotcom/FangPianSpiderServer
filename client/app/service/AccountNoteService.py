from typing import Dict, List, Any

from loguru import logger

from client.app.core.database.mysql_database_manager import MysqlDatabaseManager


class AccountNoteService:
    def __init__(self):
        self.db = MysqlDatabaseManager()

    # 获取媒体账号
    def get_kol_media_accounts(self, ids: List[int]) -> List[Dict[str, Any]]:
        try:
            sql = f'''
                SELECT * 
                FROM kol_media_accounts kma 
                where kma.sign_type = "自孵化" and kma.is_enable = 1 and xhs_url is not null
            ''';
            if len(ids) > 0:
                sql = f"""
                    {sql}and kma.dandelion_platform_id in ('{"','".join(ids)}')
                """
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取媒体账号失败: {str(e)}")
            return []

    # 获取账号分组
    def list_media_account_group_names(self) -> List[Dict[str, Any]]:
        try:
            sql = f'''
                SELECT distinct group_name, sleep_time
                FROM kol_media_account_note_group
            ''';
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取账号分组失败: {str(e)}")
            return []


    # 获取账号分组
    def list_media_account_group_accounts(self, group_name) -> List[Dict[str, Any]]:
        try:
            sql = f'''
                SELECT *
                FROM kol_media_account_note_group where group_name = '{group_name}'
            ''';
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取账号分组失败: {str(e)}")
            return []

    def save_note(self, note_data: Dict[str, Any]) -> bool:
        """
        保存或更新笔记数据
        :param note_data: 笔记数据字典
        :return: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 检查笔记是否存在
                cursor.execute('SELECT note_id FROM kol_media_account_note WHERE note_id = %s', (note_data['note_id'],))
                exists = cursor.fetchone()

                if exists:
                    # 更新现有记录
                    update_sql = '''
                            UPDATE kol_media_account_note SET 
                                user_id = %s,
                                nickname = %s,
                                title = %s,
                                `desc` = %s,
                                liked_count = %s,
                                collected_count = %s,
                                comment_count = %s,
                                share_count = %s,
                                last_update_time = %s,
                                last_sync_time = %s
                            WHERE note_id = %s
                        '''
                    cursor.execute(update_sql, (
                        note_data['user_id'],
                        note_data['nickname'],
                        note_data['title'],
                        note_data['desc'],
                        note_data['liked_count'],
                        note_data['collected_count'],
                        note_data['comment_count'],
                        note_data['share_count'],
                        note_data['last_update_time'],
                        note_data['last_sync_time'],
                        note_data['note_id']
                    ))
                    logger.info(f"更新笔记数据: {note_data['note_id']}")
                else:
                    # 插入新记录
                    insert_sql = '''
                            INSERT INTO kol_media_account_note (
                                note_id, user_id, nickname, title, `desc`, liked_count, collected_count, comment_count, share_count, last_update_time, last_sync_time
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        '''
                    cursor.execute(insert_sql, (
                        note_data['note_id'],
                        note_data['user_id'],
                        note_data['nickname'],
                        note_data['title'],
                        note_data['desc'],
                        note_data['liked_count'],
                        note_data['collected_count'],
                        note_data['comment_count'],
                        note_data['share_count'],
                        note_data['last_update_time'],
                        note_data['last_sync_time']
                    ))
                    logger.info(f"新增笔记数据: {note_data['note_id']}")
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"保存笔记数据失败: {str(e)}")
            return False

    def save_comment(self, note_data: Dict[str, Any]) -> bool:
        """
        保存或更新评论数据
        :param note_data: 评论数据字典
        :return: 是否成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 检查评论是否存在 - 修复查询条件与参数不匹配的问题
                cursor.execute('SELECT cid FROM kol_media_account_comment WHERE cid = %s', (note_data['cid'],))
                exists = cursor.fetchone()

                if exists:
                    # 更新现有记录 - 修复SQL语法错误，添加缺少的逗号
                    update_sql = '''
                            UPDATE kol_media_account_comment SET 
                                comment_text = %s,
                                reply_id = %s,
                                `reply_to_reply_id` = %s,
                                root_comment_id = %s,
                                status = %s,
                                level = %s,
                                comment_reply_total = %s,
                                comment_create_time = %s,
                                aweme_id = %s,
                                note_id = %s,
                                note_url = %s,
                                sync_last_time = %s
                            WHERE cid = %s
                        '''
                    cursor.execute(update_sql, (
                        note_data['comment_text'],
                        note_data['reply_id'],
                        note_data['reply_to_reply_id'],
                        note_data['root_comment_id'],
                        note_data['status'],
                        note_data['level'],
                        note_data['comment_reply_total'],
                        note_data['comment_create_time'],
                        note_data['aweme_id'],
                        note_data['note_id'],
                        note_data['note_url'],
                        note_data['sync_last_time'],
                        note_data['cid']
                    ))
                    logger.info(f"更新评论数据: {note_data['cid']}")
                else:
                    # 插入新记录
                    insert_sql = '''
                            INSERT INTO kol_media_account_comment (
                                cid, comment_text, reply_id,reply_to_reply_id,root_comment_id,status,level,comment_reply_total,content_type,comment_create_time,aweme_id,note_id,note_url,sync_last_time
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        '''
                    cursor.execute(insert_sql, (
                        note_data['cid'],
                        note_data['comment_text'],
                        note_data['reply_id'],
                        note_data['reply_to_reply_id'],
                        note_data['root_comment_id'],
                        note_data['status'],
                        note_data['level'],
                        note_data['comment_reply_total'],
                        note_data['content_type'],
                        note_data['comment_create_time'],
                        note_data['aweme_id'],
                        note_data['note_id'],
                        note_data['note_url'],
                        note_data['sync_last_time']
                    ))
                    logger.info(f"新增评论数据: {note_data['cid']}")
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"保存评论数据失败: {str(e)}")
            return False
