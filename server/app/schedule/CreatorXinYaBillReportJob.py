import asyncio
import os
import tempfile
import time
import urllib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
from loguru import logger

from common import TimeUtil
from server.app.core.constant import PLATFORM_TYPE_CREATOR
from server.app.db.context import get_mysql_conn
from server.app.services.TokenService import token_service
from common.RequestTool import RequestsTool


class CreatorXinYaBillReportJob:
    """创作者新芽账单报告任务"""
    
    def __init__(self):
        self.token_service = token_service
        self.request_tool = RequestsTool()
        
    async def handle(self) -> int:
        """主处理函数"""
        try:
            logger.info("开始执行创作者新芽账单报告任务")
            accounts = await self.token_service.list_token_by_platform_id(platform_id=PLATFORM_TYPE_CREATOR, account_type=2)
            # 获取每个账号的账单数据
            for account in accounts:
                logger.info(f"开始处理新芽账号: {account.get('platform_account')}")
                await self.get_zhangdan_xinya(account)
                await asyncio.sleep(2)  # 避免请求过快
                
            logger.info("创作者新芽账单报告任务执行完成")
            return 1
            
        except Exception as e:
            logger.error(f"创作者新芽账单报告任务执行失败: {str(e)}")
            raise
    
    async def get_zhangdan_xinya(self, account: Dict[str, Any]):
        """获取指定账号的新芽账单数据"""
        # 使用单个数据库连接处理整个账号的数据
        async with get_mysql_conn() as conn:
            try:
                logger.info(f"开始处理新芽账号: {account}")
                # 获取访问token和签名
                token, xs = await self.get_token(account)
                if not token or not xs:
                    logger.error(f"获取账号 {account.get('platform_account')} 的token失败")
                    return
                 # 生成请求头
                headers = self._generate_headers(token, xs)
                self.request_tool = RequestsTool(headers=headers)

                # 预先获取已存在的账单编号和包号，减少数据库查询
                existing_bills, existing_packages = await self._get_existing_data(conn)
                logger.info(f"已存在 {len(existing_bills)} 个新芽账单记录, {len(existing_packages)} 个包号")

                total_pages = 1
                page = 1
                all_bills_to_process = []  # 收集需要处理的账单

                while True:
                    # 注意这里的sourceTypeStr=DISTRIBUTOR，这是新芽账单的关键区别
                    url = f'https://creator.xiaohongshu.com/api/galaxy/settlement/list?pageNo={page}&pageSize=10&statementNo=&status=&sourceTypeStr=DISTRIBUTOR'
                    res_data = self.request_tool.get(url)
                    if not res_data:
                        logger.error(f"请求失败: {res_data}")
                        continue
                    # logger.info(f"res_data  {res_data}")
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
                            logger.info(f"新芽账单 {bill_number} 已存在，跳过")
                            page = total_pages
                            break;
                            
                        all_bills_to_process.append({
                            'download_url': download_url,
                            'bill_number': bill_number,
                            'billing_date': billing_date,
                            'settlement_period': settlement_period,
                            'amount': amount,
                            'account': account,
                            'existing_packages': existing_packages  # 传递已存在的包号
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
                logger.info(f"开始批量处理 {len(all_bills_to_process)} 个新芽新账单")
                for bill_info in all_bills_to_process:
                    await asyncio.sleep(3)  # 下载间隔
                    await self.download_and_parse_excel_with_conn(
                        conn,
                        bill_info['download_url'],
                        bill_info['bill_number'],
                        bill_info['billing_date'],
                        bill_info['settlement_period'],
                        bill_info['amount'],
                        bill_info['account'],
                        bill_info['existing_packages']
                    )
                    
            except Exception as e:
                logger.error(f"获取账号 {account} 新芽账单数据失败: {str(e)}")
                raise

    async def get_token(self, account: Dict[str, Any]) -> Tuple[str, str]:
        """从账号配置获取访问token"""
        try:
            token = account.get('token_content')
            xs = account.get('xs')
            return token, xs
                    
        except Exception as e:
            logger.error(f"获取账号 {account} token失败: {str(e)}")
            return "", ""

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

    async def download_and_parse_excel_with_conn(self, conn, url: str, bill_number: str, 
                                              billing_date: str, settlement_period: str, 
                                              amount: str, account: Dict[str, Any], existing_packages: set):
        """下载并解析新芽Excel文件（使用已有连接）"""
        temp_file = None
        try:
            filename = self._extract_filename_from_url(url)
            if not filename:
                filename = f"bill_{bill_number}.xlsx"
            # 确保数据目录存在
            data_dir = f"data/bills/xinya/{billing_date}"
            os.makedirs(data_dir, exist_ok=True)

            # 创建完整的文件路径
            file_path = os.path.join(data_dir, filename)
            if os.path.exists(file_path):
                logger.info(f"文件 {file_path} 已存在，跳过下载")
            else:
                logger.info(f"开始下载文件 {file_path}")
                self.request_tool.download_file(url, file_path)
            
            # 解析Excel文件
            df = pd.read_excel(file_path, engine='openpyxl')
            
            # 新芽版本：跳过前6行（表头），从第7行开始读取数据
            if len(df) <= 6:
                logger.warning(f"新芽Excel文件 {bill_number} 数据行数不足")
                return
                
            data_rows = df.iloc[5:].values  # 从第7行开始（索引6）
            logger.info(f"新芽Excel文件 {bill_number} 共 {len(data_rows)} 行数据")
            
            # 准备插入数据
            insert_data = []
            skipped_packages = []
            
            for row in data_rows:
                if len(row) < 15:  # 确保有足够的列（新芽版本有15列）
                    continue
                    
                # 跳过空行（检查package_number字段）
                if pd.isna(row[5]):
                    continue
                
                # # 检查package_number是否已存在（使用预获取的数据）
                # package_number = str(row[5]) if not pd.isna(row[5]) else None
                # if package_number and package_number in existing_packages:
                #     skipped_packages.append(package_number)
                #     continue
                    
                insert_data.append({
                    'bill_number': bill_number,
                    'download_url': url,
                    'billing_date': billing_date,
                    'settlement_period': settlement_period,
                    'amount': amount,
                    'order_completed_at': self._parse_datetime(row[0]),
                    'order_created_at': self._parse_datetime(row[1]),
                    'blogger_id': str(row[2]) if not pd.isna(row[2]) else None,
                    'blogger_name': str(row[3]) if not pd.isna(row[3]) else None,
                    'contract_type': str(row[4]) if not pd.isna(row[4]) else None,
                    'package_number': str(row[5]) if not pd.isna(row[5]) else None,
                    'shop_name': str(row[6]) if not pd.isna(row[6]) else None,
                    'product_name': str(row[7]) if not pd.isna(row[7]) else None,
                    'product_quantity': int(row[8]) if not pd.isna(row[8]) else 0,
                    'effective_sales_amount': float(row[9]) if not pd.isna(row[9]) else 0.0,
                    'merchant_cps_rate': str(row[10]) if not pd.isna(row[10]) else None,
                    'platform_tech_fee': str(row[11]) if not pd.isna(row[11]) else "0.0",
                    'distribution_commission_rate': str(row[12]) if not pd.isna(row[12]) else None,
                    'commission_income': float(row[13]) if not pd.isna(row[13]) else 0.0,
                    'activity_type': str(row[14]) if not pd.isna(row[14]) else None,
                    'notesign': account.get('platform_account', ''),
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })
                
                # 将新包号添加到已存在集合中，避免重复处理
                # if package_number:
                #     existing_packages.add(package_number)
                
            if skipped_packages:
                logger.info(f"跳过 {len(skipped_packages)} 个已存在的包号")
                
            logger.info(f"开始插入新芽数据: {len(insert_data)}")
            # 批量插入数据库（使用已有连接）
            if insert_data:
                await self._batch_insert_bills_with_conn(conn, insert_data)
                logger.info(f"成功插入 {len(insert_data)} 条新芽账单记录")
            else:
                logger.info("没有需要插入的新芽数据")
                
        except Exception as e:
            logger.error(f"下载解析新芽Excel文件失败: {str(e)}")
            raise
        finally:
            # 清理临时文件
            # if temp_file and os.path.exists(temp_file):
            #     os.unlink(temp_file)
            pass

    async def download_and_parse_excel(self, url: str, bill_number: str, 
                                     billing_date: str, settlement_period: str, 
                                     amount: str, account: Dict[str, Any]):
        """下载并解析新芽Excel文件（兼容接口）"""
        async with get_mysql_conn() as conn:
            existing_bills, existing_packages = await self._get_existing_data(conn)
            await self.download_and_parse_excel_with_conn(
                conn, url, bill_number, billing_date, settlement_period, amount, account, existing_packages
            )
    
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
        
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Authorization': '',
            'Cookie': token,
            'Priority': 'u=1, i',
            'Referer': 'https://creator.xiaohongshu.com/mcn/finance',
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
    
    async def _get_existing_data(self, conn) -> tuple[set, set]:
        """获取已存在的账单编号和包号集合"""
        try:
            async with conn.cursor() as cursor:
                # 获取已存在的账单编号
                await cursor.execute("SELECT bill_number FROM fp_pgy_creator_order_xinya_statements")
                bill_results = await cursor.fetchall()
                existing_bills = {row[0] for row in bill_results}
                
                # 获取已存在的包号
                await cursor.execute("SELECT package_number FROM fp_pgy_creator_order_xinya_statements WHERE package_number IS NOT NULL")
                package_results = await cursor.fetchall()
                existing_packages = {row[0] for row in package_results}
                
                return existing_bills, existing_packages
        except Exception as e:
            logger.error(f"获取已存在新芽数据失败: {str(e)}")
            return set(), set()

    async def _bill_exists(self, bill_number: str) -> bool:
        """检查新芽账单是否已存在（兼容接口）"""
        try:
            async with get_mysql_conn() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT COUNT(*) FROM fp_pgy_creator_order_xinya_statements WHERE bill_number = %s",
                        (bill_number,)
                    )
                    result = await cursor.fetchone()
                    return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"检查新芽账单是否存在失败: {str(e)}")
            return False
    
    async def _package_exists(self, package_number: str) -> bool:
        """检查包号是否已存在（兼容接口）"""
        try:
            async with get_mysql_conn() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT COUNT(*) FROM fp_pgy_creator_order_xinya_statements WHERE package_number = %s",
                        (package_number,)
                    )
                    result = await cursor.fetchone()
                    return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"检查包号是否存在失败: {str(e)}")
            return False
    
    async def _batch_insert_bills_with_conn(self, conn, data: List[Dict]):
        """批量插入新芽账单数据（使用已有连接）"""
        if not data:
            return
            
        try:
            async with conn.cursor() as cursor:
                # 构建插入SQL - 新芽版本字段
                sql = """
                INSERT INTO fp_pgy_creator_order_xinya_statements (
                    bill_number, download_url, billing_date, settlement_period, amount,
                    order_completed_at, order_created_at, blogger_id, blogger_name, contract_type,
                    package_number, shop_name, product_name, product_quantity, effective_sales_amount,
                    merchant_cps_rate, platform_tech_fee, distribution_commission_rate, 
                    commission_income, activity_type, notesign, created_at, updated_at
                ) VALUES (
                    %(bill_number)s, %(download_url)s, %(billing_date)s, %(settlement_period)s,
                    %(amount)s, %(order_completed_at)s, %(order_created_at)s, %(blogger_id)s,
                    %(blogger_name)s, %(contract_type)s, %(package_number)s, %(shop_name)s,
                    %(product_name)s, %(product_quantity)s, %(effective_sales_amount)s,
                    %(merchant_cps_rate)s, %(platform_tech_fee)s, %(distribution_commission_rate)s,
                    %(commission_income)s, %(activity_type)s, %(notesign)s, %(created_at)s, %(updated_at)s
                )
                """
                
                # 批量插入
                await cursor.executemany(sql, data)
                await conn.commit()
                
        except Exception as e:
            logger.error(f"批量插入新芽账单数据失败: {str(e)}")
            # 不要抛出异常，以免影响其他数据处理
            await conn.rollback()

    async def _batch_insert_bills(self, data: List[Dict]):
        """批量插入新芽账单数据（兼容接口）"""
        async with get_mysql_conn() as conn:
            await self._batch_insert_bills_with_conn(conn, data)


# 创建任务实例的工厂函数
async def create_creator_xinya_bill_report_job() -> CreatorXinYaBillReportJob:
    """创建创作者新芽账单报告任务实例"""
    return CreatorXinYaBillReportJob()


# 直接执行任务的函数
async def run_creator_xinya_bill_report_task() -> int:
    """运行创作者新芽账单报告任务"""
    job = await create_creator_xinya_bill_report_job()
    return await job.handle()


if __name__ == "__main__":
    logger.add("data/logs/server_{time}.log", rotation="1 day", retention="7 days", level="INFO")
    # 测试执行
    asyncio.run(run_creator_xinya_bill_report_task())
