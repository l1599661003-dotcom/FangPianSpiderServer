import asyncio
import os
import time
import urllib.parse
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from loguru import logger

from common import TimeUtil
from server.app.core.constant import PLATFORM_TYPE_CREATOR
from server.app.db.context import get_mysql_conn
from server.app.services.TokenService import token_service
from common.RequestTool import RequestsTool


class CreatorBillReportJob:
    """创作者账单报告任务"""
    
    def __init__(self):
        self.token_service = token_service
        self.request_tool = RequestsTool()
        
    async def handle(self) -> int:
        """主处理函数"""
        try:
            logger.info("开始执行创作者账单报告任务")
            accounts = await self.token_service.list_token_by_platform_id(platform_id=PLATFORM_TYPE_CREATOR, account_type=2)
            synced_billing_dates = set()
            # 获取每个账号的账单数据
            for account in accounts:
                logger.info(f"开始处理账号: {account.get('platform_account')}")
                account_billing_dates = await self.get_zhangdan(account)
                synced_billing_dates.update(
                    billing_date
                    for billing_date in account_billing_dates or []
                    if billing_date
                )
                await asyncio.sleep(2)  # 避免请求过快

            await self.process_synced_bill_data(sorted(synced_billing_dates))
            logger.info("创作者账单报告任务执行完成")
            return 1
            
        except Exception as e:
            logger.error(f"创作者账单报告任务执行失败: {str(e)}")
            raise
    
    async def get_zhangdan(self, account: Dict[str, Any]) -> set:
        """获取指定账号的账单数据"""
        # 使用单个数据库连接处理整个账号的数据
        async with get_mysql_conn() as conn:
            try:
                logger.info(f"开始处理账号: {account}")
                # 获取访问token和签名
                token, xs = await self.get_token(account)
                if not token or not xs:
                    logger.error(f"获取账号 {account.get('platform_account')} 的token失败")
                    return
                logger.info(f"开始处理账号, token: {token}, xs: {xs}")
                 # 生成请求头
                headers = self._generate_headers(token, xs)
                self.request_tool = RequestsTool(headers=headers)

                # 预先获取已存在的账单编号，减少数据库查询
                existing_bills = await self._get_existing_bills(conn)
                logger.info(f"已存在 {len(existing_bills)} 个账单记录")

                total_pages = 1
                page = 1
                all_bills_to_process = []  # 收集需要处理的账单
                synced_billing_dates = set()

                while True:
                    url = f'https://creator.xiaohongshu.com/api/galaxy/settlement/list?pageNo={page}&pageSize=10&statementNo=&status=&sourceTypeStr=AD_CONTENT'
                    res_data = self.request_tool.get(url)
                    if not res_data:
                        logger.error(f"请求失败: {res_data}")
                        continue
                    logger.error(f"请求失败: {res_data}")
                    total = res_data.get('data', {}).get('count', 0)
                    items = res_data.get('data', {}).get('data', [])
                    
                    for item in items:
                        download_url = item.get('downloadUrl')
                        bill_number = item.get('statementNo')
                        billing_date = item.get('chargeOffDay')
                        start_time = item.get('startTime')
                        end_time = item.get('endTime')
                        settlement_period = f"{start_time} - {end_time}"
                        amount = item.get('amount')
                        
                        # 检查账单是否已存在（使用预获取的数据）
                        if bill_number in existing_bills:
                            logger.info(f"账单 {bill_number} 已存在，跳过")
                            page = total_pages
                            break;
                            
                        all_bills_to_process.append({
                            'download_url': download_url,
                            'bill_number': bill_number,
                            'billing_date': billing_date,
                            'settlement_period': settlement_period,
                            'amount': amount,
                            'account': account
                        })
                    
                    # 计算总页数
                    if page == 1:
                        total_pages = (total + 9) // 10  # 向上取整
                    page += 1
                    if page > total_pages:
                        break
                    logger.info(f"等待1-3秒, page: {page}")
                    await TimeUtil.async_random_sleep(1, 3)
                
                # 批量处理收集到的账单
                logger.info(f"开始批量处理 {len(all_bills_to_process)} 个新账单")
                for bill_info in all_bills_to_process:
                    await asyncio.sleep(3)  # 下载间隔
                    await self.download_and_parse_excel_with_conn(
                        conn, 
                        bill_info['download_url'],
                        bill_info['bill_number'],
                        bill_info['billing_date'],
                        bill_info['settlement_period'],
                        bill_info['amount'],
                        bill_info['account']
                    )
                    if bill_info.get('billing_date'):
                        synced_billing_dates.add(bill_info['billing_date'])

                return synced_billing_dates
                    
            except Exception as e:
                logger.error(f"获取账号 {account} 账单数据失败: {str(e)}")
                raise

    # 获取账号的token
    async def get_token(self, account: Dict[str, Any] ) -> Tuple[str, str]:
        """从飞书获取指定账号的访问token"""
        try:
            token = account.get('token_content')
            xs = account.get('xs')
            return token, xs
                    
        except Exception as e:
            logger.error(f"获取账号 {account} token失败: {str(e)}")
            return "", ""
    
    async def download_and_parse_excel_with_conn(self, conn, url: str, bill_number: str, 
                                              billing_date: str, settlement_period: str, 
                                              amount: str, account: Dict[str, Any]):
        """下载并解析Excel文件（使用已有连接）"""
        file_path = None
        try:
            # 从URL中提取文件名
            filename = self._extract_filename_from_url(url)
            if not filename:
                filename = f"bill_{bill_number}_{int(time.time())}.xlsx"
            
            # 确保数据目录存在
            data_dir = f"data/bills/{billing_date}"
            os.makedirs(data_dir, exist_ok=True)
            
            # 创建完整的文件路径
            file_path = os.path.join(data_dir, filename)
            
            logger.info(f"开始下载文件: {url}, 保存到: {file_path}")
            # 下载文件
            self.request_tool.download_file(url, file_path)
            
            # 解析Excel文件
            df = pd.read_excel(file_path, engine='openpyxl')
            
            # 跳过前8行（表头），从第9行开始读取数据
            if len(df) <= 7:
                logger.warning(f"Excel文件 {bill_number} 数据行数不足")
                return
            data_rows = df.iloc[7:].values  # 从第9行开始
            
            # 准备插入数据
            insert_data = []
            t = 0;
            for row in data_rows:
                if len(row) < 10:  # 确保有足够的列
                    continue
                if len(row) == 10:
                    t = 1;
                # 跳过空行
                if pd.isna(row[1]) and pd.isna(row[2]):
                    continue
                    
                insert_data.append({
                    'bill_number': bill_number,
                    'download_url': url,
                    'billing_date': billing_date,
                    'settlement_period': settlement_period,
                    'amount': amount,
                    'cooperator_id': str(row[0]),
                    'order_completed_at': self._parse_datetime(row[1 - t]),
                    'order_number': str(row[2 - t]) if not pd.isna(row[2 - t]) else None,
                    'order_created_at': self._parse_datetime(row[3 - t]),
                    'cooperation_name': str(row[4 - t]) if not pd.isna(row[4 - t]) else None,
                    'cooperator_name': str(row[5 - t]) if not pd.isna(row[5 - t]) else None,
                    'organization_name': str(row[6 - t]) if not pd.isna(row[6 - t]) else None,
                    'brand_name': str(row[7 - t]) if not pd.isna(row[7 - t]) else None,
                    'cooperation_amount': float(row[8 - t]) if not pd.isna(row[8 - t]) else 0.0,
                    'remain_money': float(row[8 - t]) if not pd.isna(row[8 - t]) else 0.0,
                    'platform_fee': float(row[9 - t]) if not pd.isna(row[9 - t]) else 0.0,
                    'income_amount': float(row[10 - t]) if not pd.isna(row[10 - t]) else 0.0,
                    'notesign': account.get('platform_account', ''),
                    'created_at': int(time.time()),
                    'updated_at': int(time.time()),
                    'order_status': 200,
                    'diff_value': -1,
                    'system_type': '签约'
                })
            logger.info(f"开始插入数据: {insert_data}")
            # 批量插入数据库（使用已有连接）
            if insert_data:
                await self._batch_insert_bills_with_conn(conn, insert_data)
                logger.info(f"成功插入 {len(insert_data)} 条账单记录")
            else:
                logger.info("没有需要插入的数据")
                
        except Exception as e:
            logger.error(f"下载解析Excel文件失败: {str(e)}")
            raise
        finally:
            # 文件已保存，不需要清理
            logger.info(f"文件已保存到: {file_path}")
            pass

    async def download_and_parse_excel(self, url: str, bill_number: str, 
                                     billing_date: str, settlement_period: str, 
                                     amount: str, account: Dict[str, Any]):
        """下载并解析Excel文件（兼容接口）"""
        async with get_mysql_conn() as conn:
            await self.download_and_parse_excel_with_conn(
                conn, url, bill_number, billing_date, settlement_period, amount, account
            )
    
    def _extract_filename_from_url(self, url: str) -> Optional[str]:
        """从URL中提取文件名"""
        try:
            filename = urllib.parse.unquote(url)
            # 截取?之前的所有内容
            filename = filename.split('?')[0]
            logger.info(f"开始执行创作者账单报告任务: {filename}")
            filename = filename.replace('一口价/招募/分成', '一口价_招募_分成').split('/')[-1]
            
            # 确保文件名有效且是xlsx文件
            if filename and filename.endswith('.xlsx'):
                return filename
            return None
        except Exception as e:
            logger.error(f"从URL提取文件名失败: {str(e)}")
            return None
    
    def _parse_datetime(self, value) -> Optional[str]:
        """解析日期时间"""
        if pd.isna(value):
            return None
        try:
            if isinstance(value, str):
                # 尝试解析字符串格式的日期
                dt = pd.to_datetime(value)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, (pd.Timestamp, datetime)):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                return None
        except:
            return None
    
    def _generate_headers(self, token: str, xs: str) -> Dict[str, str]:
        """生成请求头"""
        trace_id = str(uuid.uuid4())
        timestamp = int(time.time() * 1000)
        
        return  {
            'Accept': 'application/json, text/plain, */*',
            'Accept-encoding': 'gzip, deflate, br, zstd',
            'Accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Authorization': '',
            'Cookie': token,
            'Priority': 'u=1, i',
            'Referer': 'https://creator.xiaohongshu.com/mcn/management',
            'Sec-Ch-Ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?1',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 Edg/130.0.0.0',
            'X-B3-Traceid': trace_id[:16],
            'X-S': xs,
            'X-T': str(timestamp),
        }
    
    async def _get_existing_bills(self, conn) -> set:
        """获取已存在的账单编号集合"""
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT bill_number FROM fp_pgy_creator_order_statements")
                results = await cursor.fetchall()
                return {row[0] for row in results}
        except Exception as e:
            logger.error(f"获取已存在账单失败: {str(e)}")
            return set()

    async def _bill_exists(self, bill_number: str) -> bool:
        """检查账单是否已存在（兼容接口）"""
        try:
            async with get_mysql_conn() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT COUNT(*) FROM fp_pgy_creator_order_statements WHERE bill_number = %s",
                        (bill_number,)
                    )
                    result = await cursor.fetchone()
                    return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"检查账单是否存在失败: {str(e)}")
            return False
    
    async def _batch_insert_bills_with_conn(self, conn, data: List[Dict]):
        """批量插入账单数据（使用已有连接）"""
        if not data:
            return
            
        try:
            async with conn.cursor() as cursor:
                # 构建插入SQL   
                sql = """
                INSERT INTO fp_pgy_creator_order_statements (
                    bill_number, download_url, billing_date, settlement_period, amount,
                    order_complete_time, order_number, order_create_time, cooperation_name,
                    cooperator_name, organization_name, brand_name, cooperation_amount,
                    platform_fee, income_amount, notesign, create_time, update_time,cooperator_id,system_type, remain_money,order_status,diff_value
                ) VALUES (
                    %(bill_number)s, %(download_url)s, %(billing_date)s, %(settlement_period)s,
                    %(amount)s, %(order_completed_at)s, %(order_number)s, %(order_created_at)s,
                    %(cooperation_name)s, %(cooperator_name)s, %(organization_name)s,
                    %(brand_name)s, %(cooperation_amount)s, %(platform_fee)s, %(income_amount)s,
                    %(notesign)s, %(created_at)s, %(updated_at)s, %(cooperator_id)s, %(system_type)s, %(remain_money)s, %(order_status)s, %(diff_value)s
                )
                """
                
                # 批量插入
                await cursor.executemany(sql, data)
                await conn.commit()
                
        except Exception as e:
            logger.error(f"批量插入账单数据失败: {str(e)}")
            # 不要抛出异常，以免影响其他数据处理
            await conn.rollback()

    async def _batch_insert_bills(self, data: List[Dict]):
        """批量插入账单数据（兼容接口）"""
        async with get_mysql_conn() as conn:
            await self._batch_insert_bills_with_conn(conn, data)

    async def process_synced_bill_data(self, billing_dates: Iterable[str]):
        """所有账号账单同步完成后，按本次同步到的出账日处理账单数据。"""
        normalized_dates = self._normalize_billing_dates(billing_dates)
        if not normalized_dates:
            logger.info("本次没有新的出账日需要处理")
            return

        async with get_mysql_conn() as conn:
            await self._process_bill_data_by_billing_dates_with_conn(
                conn, normalized_dates
            )

    async def _process_bill_data_by_billing_dates_with_conn(
        self, conn, billing_dates: Iterable[str]
    ):
        """执行 docs/1.txt 中的账单后处理 SQL，支持多个出账日。"""
        normalized_dates = self._normalize_billing_dates(billing_dates)
        if not normalized_dates:
            logger.info("没有可处理的出账日")
            return

        sql_templates = self._get_bill_processing_sql_templates()
        try:
            async with conn.cursor() as cursor:
                for billing_date in normalized_dates:
                    logger.info(f"开始处理出账日 {billing_date} 的账单数据")
                    for sql in sql_templates:
                        await cursor.execute(sql, (billing_date,))
                await conn.commit()
                logger.info(
                    f"账单数据处理完成，出账日: {', '.join(normalized_dates)}"
                )
        except Exception as e:
            logger.error(f"处理账单数据失败: {str(e)}")
            await conn.rollback()
            raise

    def _normalize_billing_dates(self, billing_dates: Iterable[str]) -> List[str]:
        """过滤空出账日并排序去重，保证处理顺序稳定。"""
        return sorted({billing_date for billing_date in billing_dates if billing_date})

    def _get_bill_processing_sql_templates(self) -> List[str]:
        """docs/1.txt 中的账单处理 SQL，billing_date 使用参数绑定。"""
        return [
            """
            update fp_pgy_creator_order_statements t1
            join fp_creator t2 on t2.platform_user_id = t1.cooperator_id
            set t1.creator_id = t2.id
            where t1.creator_id is null
              and t1.billing_date = %s
              and t1.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            join fp_order t2 on t1.order_number = t2.platform_order_code
            set t1.order_id = t2.id,
                t1.order_status = t2.order_status,
                t1.diff_value = 1
            where t1.billing_date = %s
              and t2.order_status >= 0
              and t2.order_type < 3
              and t1.platform_id = 1
            """,
            """
            update fp_order_difference t1
            join fp_pgy_creator_order_statements t2 on t2.order_id = t1.order_id
            set t1.pgy_order_id = t2.id
            where t2.billing_date = %s
              and t1.pgy_order_id is null
              and t1.order_id > 0
              and t2.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            set t1.system_type = '签约',
                t1.order_status = 200,
                t1.diff_value = 1
            where t1.billing_date = %s
              and t1.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            join fp_creator_business t3
              on t1.creator_id = t3.creator_id and t3.cooperate_type = 1
            set t1.system_type = '自孵'
            where t1.billing_date = %s
              and t1.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            join fp_creator_employee_mappings t3 on t1.creator_id = t3.creator_id
            join fp_department_employee_mappings t4 on t3.employee_id = t4.employee_id
            set t1.system_type = '自孵联营'
            where t4.department_level_code like '008013%%'
              and t1.billing_date = %s
              and t1.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            join fp_creator_employee_mappings t3 on t1.creator_id = t3.creator_id
            join fp_department_employee_mappings t4 on t3.employee_id = t4.employee_id
            set t1.system_type = '签约联营'
            where t4.department_level_code like '008012%%'
              and t1.billing_date = %s
              and t1.platform_id = 1
            """,
            """
            update fp_pgy_creator_order_statements t1
            join fp_creator_employee_mappings t3 on t1.creator_id = t3.creator_id
            join fp_department_employee_mappings t4 on t3.employee_id = t4.employee_id
            set t1.system_type = '灿灿'
            where t4.department_level_code like '008013086%%'
              and t1.billing_date = %s
              and t1.platform_id = 1
            """,
        ]


# 创建任务实例的工厂函数
async def create_creator_bill_report_job() -> CreatorBillReportJob:
    """创建创作者账单报告任务实例"""
    return CreatorBillReportJob()


# 直接执行任务的函数
async def run_creator_bill_report_task() -> int:
    """运行创作者账单报告任务"""
    job = await create_creator_bill_report_job()
    # await job.download_and_parse_excel("https://finance-private.xiaohongshu.com/%E7%83%9F%E5%8F%B0%E6%96%B9%E7%89%87%E4%BA%94%E6%96%B0%E5%AA%92%E4%BD%93%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8%E5%93%81%E7%89%8C%E5%90%88%E4%BD%9C%E4%B8%80%E5%8F%A3%E4%BB%B7%E6%8B%9B%E5%8B%9F%E5%88%86%E6%88%90%E8%B4%A6%E5%8D%951748765771860.xlsx?e=1749205530&token=edMBpdzSWI2pH13onoAIcpYw7pSU2tplRrPTySQO:H2YbGATUmmPHODfwUWm41TzhQ3E=", "1234567890", "2021-01-01", "2021-01-01", "100", "1234567890")
    return await job.handle()


if __name__ == "__main__":
    logger.add("data/logs/server_{time}.log", rotation="1 day", retention="7 days", level="INFO")
    # 测试执行
    asyncio.run(run_creator_bill_report_task())