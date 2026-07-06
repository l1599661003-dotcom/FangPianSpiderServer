import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from urllib.parse import parse_qsl, urlparse

from loguru import logger
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from sqlalchemy import text

from client.app.core.database.database import session
from client.app.core.task_base import BaseTask
from client.app.models.models_tibao import KolMediaAccount
from client.app.utils import TimeUtil


class BloggerInfoTask(BaseTask):
    """博主信息采集任务处理器"""

    async def on_initialize(self):
        """初始化任务"""
        logger.info(f"初始化博主信息采集任务, 任务ID: {self.task_id}")
        self.platform_id = self.task_data.get("platform_id", 0)  # 平台ID，默认为小红书
        self.token_id = None  # 令牌ID，会在处理过程中请求分配
        self.token_content = None  # 令牌内容

        self.base_url = "https://pgy.xiaohongshu.com"
        self.is_logged_in = False
        self.api_data = {}  # 存储API数据

        self.notes = []
        self.stopScroll = False

        self.current_user_data = {}  # 添加一个临时存储当前用户数据的字典
        self.notes_rate_processed = False  # 添加到清空数据的地方

        # 请求令牌
        await self.request_token()
        # await self.setup_browser()

    async def setup_browser(self, url):
        """初始化浏览器"""
        self.playwright = await async_playwright().start()
        # 配置浏览器选项
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        # 创建上下文
        self.context = await self.browser.new_context(
            viewport={'width': 1680, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        )

        self.page = await self.context.new_page()
        # 设置页面超时时间
        self.page.set_default_timeout(20000)
        # 设置响应监听
        self.page.on("response", self._handle_api_response)

    async def preprocess_data(self, data: Any) -> Any:
        return data["items"]

    async def clear_current_batch(self):
        self.current_batch_data = None

    async def has_pending_data(self) -> bool:
        return bool(self.current_batch_data)

    async def calculate_progress(self) -> float:
        if self.total_count > 0:
            return (self.success_count + self.fail_count) / self.total_count * 100
        else:
            return 0

    async def calculate_data_count(self, data: Any) -> int:
        return len(data)

    async def process_batch(self, data: Any, batch_id: str) -> Tuple[bool, int, int]:
        """
        处理整个批次数据
        
        Args:
            data: 批次数据
            batch_id: 批次ID
        """
        items = await self.preprocess_data(data)
        if not items or len(items) == 0:
            return False, 0, 0

        for item in items:
            result = await self.process_item(item, batch_id)
            if not result:
                return False, 0, 0
        TimeUtil.async_random_sleep(5, 7)
        return True, len(items), 0

    async def process_item(self, item: Dict[str, Any], batch_id: str) -> bool:
        """
        处理单个数据项
        
        Args:
            item: 数据项
            batch_id: 批次ID
            
        Returns:
            处理是否成功
        """
        try:
            fields = item.get('fields', {})
            logger.info(f"处理博主信息, 博主ID: {fields.get('蒲公英链接', { 'text': '' }).get('text')} 令牌信息：{self.token_content}")

            # 设置令牌
            # 模拟数据处理
            await asyncio.sleep(0.5)  # 模拟网络请求延迟

            # 处理结果
            url = fields.get('蒲公英链接', { text: '' }).get('text', '')
            try:
                # 清空之前的数据
                self.api_data.clear()
                self.current_user_data.clear()  # 清空上一个用户的数据
                nickname = fields.get('达人昵称', [{ text: '' }])[0].get('text', '')
                dandelion_platform_link = fields.get('蒲公英链接', { text: '' }).get('text', '')

                logger.info(f"正在处理博主全数据: { fields }")
                logger.info(f"正在处理博主: {nickname}")
                logger.info(f"访问链接: {dandelion_platform_link}")

                # 访问页面
                await self.page.goto(dandelion_platform_link)

                # 等待页面加载完成
                await self.page.wait_for_load_state('networkidle')
                await TimeUtil.async_random_sleep(1, 1)  # 等待API请求完成

                try:
                    # 默认日常笔记30天全流量 无需处理

                    # 使用trans-data-item类定位容器
                    dropdown_container = self.page.locator('.trans-data-item')

                    # 1. 切换到日常笔记90天全流量
                    option_90d = await dropdown_container.page.wait_for_selector('text=近90日', timeout=10000)
                    await option_90d.click()
                    await self.page.wait_for_load_state('networkidle')
                    await TimeUtil.async_random_sleep(0.2, 0.5)

                    # 2. 切换到合作笔记90天全流量
                    switch_button = dropdown_container.locator('button:has-text("合作笔记")').first
                    await switch_button.click()
                    await self.page.wait_for_load_state('networkidle')
                    await TimeUtil.async_random_sleep(0.2, 0.5)

                    # 3. 切换到合作笔记30天全流量
                    option_30d = await dropdown_container.page.wait_for_selector('text=近30日', timeout=10000)
                    await option_30d.click()
                    await self.page.wait_for_load_state('networkidle')
                    await TimeUtil.async_random_sleep(0.2, 0.5)

                    # 4. 切换到合作笔记30天仅自然流量
                    natural_flow = await dropdown_container.page.wait_for_selector('text=仅自然流量')
                    await natural_flow.click()
                    await self.page.wait_for_load_state('networkidle')
                    await TimeUtil.async_random_sleep(0.2, 0.5)

                except Exception as e:
                    logger.error(f"处理笔记数据时出错: {str(e)}")
                    logger.error(traceback.format_exc())

                # 处理捕获到的API数据
                if self.api_data:
                    # 创建api_data的副本进行遍历
                    api_data_copy = dict(self.api_data)

                    # 1. 首先处理blogger API获取基本信息
                    note_rates = []
                    blogger_data = {}
                    data_summary = {}
                    fans_profile = {}
                    fans_overall = {}
                    fans_summary = {}
                    notes_detail = []
                    cost_effective = {}
                    for api_url, response_data in api_data_copy.items():
                        try:
                            if 'data' not in response_data:
                                continue

                            api_data = response_data['data']
                            # 博主信息数据
                            if 'blogger' in api_url and 'data' in response_data:
                                blogger_data = dict(api_data)

                            # 根据不同的API进行不同的处理

                            # 近期传播表现 需要5次 日常（30，全流量 | 90天全流量）合作（30，全流量 | 90天全流量 | 30天仅自然流量）
                            if 'notes_rate' in api_url and 'data' in response_data:
                                user_id = await self.get_url_params(api_url, "userId")
                                business = await self.get_url_params(api_url, "business")
                                note_type = await self.get_url_params(api_url, "noteType")
                                date_type = await self.get_url_params(api_url, "dateType")
                                advertise_switch = await self.get_url_params(api_url, "advertiseSwitch")
                                api_data.update({
                                    'userId': user_id,
                                    'business': business,
                                    'noteType': note_type,
                                    'dateType': date_type,
                                    'advertiseSwitch': advertise_switch
                                })
                                note_rates.append(api_data)

                            # 数据概览
                            elif 'data_summary' in api_url:
                                data_summary.update(api_data)

                            # 粉丝分析-粉丝画像
                            elif 'fans_profile' in api_url:
                                fans_profile.update(api_data)
                            # 粉丝分析-粉丝趋势
                            elif 'fans_overall_new_history' in api_url:
                                fans_overall.update(api_data)
                            # 粉丝分析-核心数据
                            elif 'fans_summary' in api_url:
                                fans_summary.update(api_data)
                            # 笔记数据-笔记案例 查近90天数据 最多2次
                            elif 'notes_detail' in api_url:
                                data = api_data.get('data', {})
                                for item in data.get('list', []):
                                    try:
                                        notes_detail.append(item)
                                    except (ValueError, KeyError) as e:
                                        logger.warning(f"处理订单日期时出错: {str(e)}")
                                        continue

                            # 数据概览-成本most_cost_effective 性价比表现、阅读成本
                            elif 'cost_effective' in api_url:
                                cost_effective.update(api_data)
                        except Exception as api_error:
                            logger.error(f"处理API {api_url} 数据时出错: {str(api_error)}")
                            continue

                # 在适当的位置增加异步等待
                await TimeUtil.async_random_sleep(2, 3)  # 防止请求过快

            except Exception as e:
                logger.error(f"处理博主 {url} 数据时出错: {str(e)}")
                await TimeUtil.async_random_sleep(3, 4)  # 等待API请求完成

            # 上报结果
            await self.report_result(blogger_data.get('userId', ''), {
                'blogger_data': blogger_data,
                'note_rates': note_rates,
                'data_summary': data_summary,
                'fans_profile': fans_profile,
                'fans_overall': fans_overall,
                'fans_summary': fans_summary,
                'notes_detail': notes_detail,
                'cost_effective': cost_effective
            })
            return True

        except Exception as e:
            logger.error(f"处理博主信息失败: {e}, 博主ID: {item.get('blogger_id', 'unknown')}")
            await TimeUtil.async_random_sleep(3, 4)  # 等待API请求完成
            return False

    # 获取URL参数
    async def get_url_params(self, url: str, param_name: str):
        params = dict(parse_qsl(urlparse(url).query))
        param_value = params.get(param_name, '')
        return param_value

    async def on_stop(self):
        """停止任务时的清理工作"""
        logger.info(f"停止博主信息采集任务, 任务ID: {self.task_id}")

        # 释放令牌
        if self.token_id:
            await self.release_token()
            
        # 关闭浏览器资源
        await self.close()

    async def on_complete(self):
        """任务完成时的处理"""
        logger.info(f"完成博主信息采集任务, 任务ID: {self.task_id}")

        # 释放令牌
        if self.token_id:
            await self.release_token()
            
        # 关闭浏览器资源
        await self.close()

    async def on_error(self, error_code: str, error_message: str):
        """
        处理任务错误
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
        """
        logger.error(f"博主信息采集任务出错: [{error_code}] {error_message}")

        # 特定错误处理
        if error_code == "TOKEN_INVALID":
            # 令牌无效，尝试重新获取
            self.token_content = None
            await self.request_token()

    async def request_token(self):
        """请求分配令牌"""
        try:
            # 构建令牌请求消息
            token_request = {
                "cmd": "token_request",
                "task_id": self.task_id,
                "data": {
                    "platform_id": self.platform_id
                }
            }

            # 发送请求
            await self.command_handler.websocket_client.send(token_request, require_confirmation=False)

            logger.info(f"已发送令牌请求, 任务ID: {self.task_id}, 平台ID: {self.platform_id}")

            # 注意：令牌分配结果会通过单独的消息返回，在CommandHandler中处理

        except Exception as e:
            logger.error(f"请求令牌失败: {e}")

    async def release_token(self):
        """释放令牌"""
        try:
            if not self.token_id:
                return

            # 构建令牌释放消息
            token_release = {
                "cmd": "token_release",
                "task_id": self.task_id,
                "data": {
                    "token_id": self.token_id
                }
            }

            # 发送请求
            await self.command_handler.websocket_client.send(token_release, require_confirmation=False)

            logger.info(f"已发送令牌释放请求, 任务ID: {self.task_id}, 令牌ID: {self.token_id}")

            # 清空令牌信息
            self.token_id = None
            self.token_content = None

        except Exception as e:
            logger.error(f"释放令牌失败: {e}")

    async def report_result(self, blogger_id: str, result: Dict[str, Any]):
        """
        上报处理结果
        
        Args:
            blogger_id: 博主ID
            result: 处理结果
        """
        try:
            # 构建结果上报消息
            result_report = {
                "cmd": "result_report",
                "task_id": self.task_id,
                "data": {
                    "blogger_id": blogger_id,
                    "result": result
                }
            }

            # 发送请求
            await self.command_handler.websocket_client.send(result_report, require_confirmation=False)

            logger.debug(f"已上报处理结果, 任务ID: {self.task_id}, 博主ID: {blogger_id}")

        except Exception as e:
            logger.error(f"上报处理结果失败: {e}, 博主ID: {blogger_id}")

    async def close(self):
        """
        关闭浏览器和playwright
        """
        try:
            if hasattr(self, 'page'):
                await self.page.close()
            if hasattr(self, 'context'):
                await self.context.close()
            if hasattr(self, 'browser'):
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()

            # 确保关闭数据库会话
            session.close()

            logger.info("浏览器和playwright已关闭")
        except Exception as e:
            logger.error(f"关闭资源时出错: {str(e)}")

    async def _handle_api_response(self, response):
        """处理API响应，只捕获指定的API请求"""
        try:
            url = response.url
            # 定义需要捕获的API路径
            target_apis = [
                'api/solar/kol/data_v3/notes_rate',
                'api/solar/kol/data/fans_profile',
                'api/solar/kol/data_v3/data_summary',
                'api/solar/cooperator/user/blogger/',
                'api/solar/kol/data/fans_overall_new_history',
                'api/solar/kol/data_v3/fans_summary',
                'api/solar/kol/data_v2/notes_detail',
                'api/solar/kol/data_v2/cost_effective'
            ]

            # 检查是否是目标API
            is_target_api = any(api in url for api in target_apis)

            if is_target_api and (response.request.resource_type == 'fetch' or response.request.resource_type == 'xhr'):
                try:
                    data = await response.json()

                    # 存储API数据
                    self.api_data[url] = {
                        'url': url,
                        'data': data,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }

                except Exception as e:
                    logger.error(f"处理API数据时出错: {str(e)}")
        except Exception as e:
            logger.error(f"处理API响应时出错: {str(e)}")

    def _calculate_metrics(self, data, video_price, graphic_price, prefix):
        """计算CPE、CPM、CPC、CPR指标"""
        try:
            metrics = {}
            engagement_num = int(data.get('mEngagementNum', 0))
            read_median = int(data.get('readMedian', 0))
            imp_median = int(data.get('impMedian', 0))

            if prefix == 'daily_pic_video':
                # 视频指标
                if engagement_num > 0:
                    metrics['daily_pic_video_video_cpe'] = format(video_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['daily_pic_video_video_cpc'] = format(video_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['daily_pic_video_video_cpm'] = format((video_price / imp_median) * 1000, '.2f')
                        metrics['daily_pic_video_video_cpr'] = format(read_median / imp_median, '.2f')
                # 图文指标
                if engagement_num > 0:
                    metrics['daily_pic_video_text_cpe'] = format(graphic_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['daily_pic_video_text_cpc'] = format(graphic_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['daily_pic_video_text_cpm'] = format((graphic_price / imp_median) * 1000, '.2f')
                        metrics['daily_pic_video_text_cpr'] = format(read_median / imp_median, '.2f')

            elif prefix == 'cooperation_pic_video':
                # 视频指标
                if engagement_num > 0:
                    metrics['cooperation_pic_video_video_cpe'] = format(video_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['cooperation_pic_video_video_cpc'] = format(video_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['cooperation_pic_video_video_cpm'] = format((video_price / imp_median) * 1000, '.2f')
                        metrics['cooperation_pic_video_video_cpr'] = format(read_median / imp_median, '.2f')
                # 图文指标
                if engagement_num > 0:
                    metrics['cooperation_pic_video_text_cpe'] = format(graphic_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['cooperation_pic_video_text_cpc'] = format(graphic_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['cooperation_pic_video_text_cpm'] = format((graphic_price / imp_median) * 1000, '.2f')
                        metrics['cooperation_pic_video_text_cpr'] = format(read_median / imp_median, '.2f')

            elif prefix == 'daily_90':
                # 视频指标
                if engagement_num > 0:
                    metrics['daily_video_cpe'] = format(video_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['daily_video_cpc'] = format(video_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['daily_video_cpm'] = format((video_price / imp_median) * 1000, '.2f')
                        metrics['daily_video_cpr'] = format(read_median / imp_median, '.2f')
                # 图文指标
                if engagement_num > 0:
                    metrics['coop_video_cpe'] = format(graphic_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['coop_video_cpc'] = format(graphic_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['coop_video_cpm'] = format((graphic_price / imp_median) * 1000, '.2f')
                        metrics['coop_video_cpr'] = format(read_median / imp_median, '.2f')

            elif prefix == 'daily_pic_text':
                # 图文指标
                if engagement_num > 0:
                    metrics['daily_pic_text_cpe'] = format(video_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['daily_pic_text_cpc'] = format(video_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['daily_pic_text_cpm'] = format((video_price / imp_median) * 1000, '.2f')
                        metrics['daily_pic_text_cpr'] = format(read_median / imp_median, '.2f')
                # 视频指标
                if engagement_num > 0:
                    metrics['coop_pic_text_cpe'] = format(graphic_price / engagement_num, '.2f')
                if read_median > 0:
                    metrics['coop_pic_text_cpc'] = format(graphic_price / read_median, '.2f')
                    if imp_median > 0:
                        metrics['coop_pic_text_cpm'] = format((graphic_price / imp_median) * 1000, '.2f')
                        metrics['coop_pic_text_cpr'] = format(read_median / imp_median, '.2f')

            # 设置默认值为'0.00'
            for key in metrics:
                if not metrics[key]:
                    metrics[key] = '0.00'

            self.current_user_data.update(metrics)

        except Exception as e:
            logger.error(f"计算{prefix}指标时出错: {str(e)}")
            logger.error(f"错误的数据结构: {data}")

    def _process_notes_detail(self, api_data, blogger):
        """处理笔记详情数据"""
        if api_data['code'] != 0:
            return

        try:
            data = api_data['data']

            # 计算不同时间段的订单数量
            current_date = datetime.now()
            thirty_days_ago = current_date - timedelta(days=30)
            ninety_days_ago = current_date - timedelta(days=90)

            day30 = 0
            day90 = 0
            all_orders = 0

            # 处理品牌名称列表，过滤掉None值
            brand_names = []
            for item in data.get('list', []):
                brand_name = item.get('brandName')
                if brand_name:  # 只添加非空的品牌名称
                    brand_names.append(brand_name)

            # 统计蒲公英平台订单数据
            for item in data.get('list', []):
                try:
                    item_date = datetime.strptime(item['date'], '%Y-%m-%d')

                    if thirty_days_ago <= item_date <= current_date:
                        day30 += 1

                    if ninety_days_ago <= item_date <= current_date:
                        day90 += 1

                    all_orders += 1
                except (ValueError, KeyError) as e:
                    logger.warning(f"处理订单日期时出错: {str(e)}")
                    continue

            try:
                # 获取当前博主信息
                account = session.query(KolMediaAccount).filter(
                    KolMediaAccount.dandelion_platform_id == blogger.dandelion_platform_id
                ).first()

                if account:
                    # 使用原生SQL查询来避免模型字段不匹配的问题
                    zf_order30 = session.execute(text("""
                        SELECT COUNT(*) as count
                        FROM kol_orders
                        WHERE media_account_id = :account_id
                        AND stage NOT IN (11, 12)
                        AND created_at >= :thirty_days_ago
                    """), {
                        'account_id': account.id,
                        'thirty_days_ago': thirty_days_ago
                    }).scalar()

                    zf_order90 = session.execute(text("""
                        SELECT COUNT(*) as count
                        FROM kol_orders
                        WHERE media_account_id = :account_id
                        AND stage NOT IN (11, 12)
                        AND created_at >= :ninety_days_ago
                    """), {
                        'account_id': account.id,
                        'ninety_days_ago': ninety_days_ago
                    }).scalar()

                    zf_all = session.execute(text("""
                        SELECT COUNT(*) as count
                        FROM kol_orders
                        WHERE media_account_id = :account_id
                        AND stage NOT IN (11, 12)
                    """), {
                        'account_id': account.id
                    }).scalar()

                    # 更新用户数据
                    self.current_user_data.update({
                        'brand_name': ','.join(brand_names),  # 使用过滤后的品牌名称列表
                        'pgy_total_orders': all_orders,
                        'pgy_orders_30_days': day30,
                        'pgy_orders_90_days': day90,
                        'system_total_orders': zf_all or 0,
                        'system_orders_30_days': zf_order30 or 0,
                        'system_orders_90_days': zf_order90 or 0,
                    })
                else:
                    logger.error(f"未找到博主信息: {blogger.dandelion_platform_id}")
                    # 至少保存蒲公英平台的数据
                    self.current_user_data.update({
                        'brand_name': ','.join(brand_names),  # 使用过滤后的品牌名称列表
                        'pgy_total_orders': all_orders,
                        'pgy_orders_30_days': day30,
                        'pgy_orders_90_days': day90,
                    })

            except Exception as e:
                logger.error(f"处理系统订单数据时出错: {str(e)}")
                # 至少保存蒲公英平台的数据
                self.current_user_data.update({
                    'brand_name': ','.join(brand_names),  # 使用过滤后的品牌名称列表
                    'pgy_total_orders': all_orders,
                    'pgy_orders_30_days': day30,
                    'pgy_orders_90_days': day90,
                })

        except Exception as e:
            logger.error(f"处理笔记详情数据时出错: {str(e)}")
            # 设置默认值
            self.current_user_data.update({
                'brand_name': '',
                'pgy_total_orders': 0,
                'pgy_orders_30_days': 0,
                'pgy_orders_90_days': 0,
                'system_total_orders': 0,
                'system_orders_30_days': 0,
                'system_orders_90_days': 0,
            })

    def _process_fans_profile(self, api_data):
        """处理粉丝画像数据"""
        if api_data['code'] == 0:
            data = api_data['data']
            try:
                # 处理年龄分布
                self.current_user_data.update({
                    'age_less_than_18': format(data['ages'][0]['percent'], '.2f'),  # 年龄<18
                    'age_18_to_24': format(data['ages'][1]['percent'], '.2f'),  # 年龄18_24
                    'age_25_to_34': format(data['ages'][2]['percent'], '.2f'),  # 年龄25_34
                    'age_35_to_44': format(data['ages'][3]['percent'], '.2f'),  # 年龄35_44
                    'age_greater_than_44': format(data['ages'][4]['percent'], '.2f'),  # 年龄>44
                })

                # 处理性别分布
                self.current_user_data.update({
                    'male_fan_percentage': format(data['gender']['male'], '.2f'),  # 男粉丝占比
                    'female_fan_percentage': format(data['gender']['female'], '.2f'),  # 女粉丝占比
                })

                # 处理用户兴趣 top5
                for i in range(5):
                    interest = data['interests'][i]
                    self.current_user_data[f'interest_top{i + 1}'] = (
                        f"{interest['name']}({format(interest['percent'] * 100, '.2f')}%)"
                    )

                # 处理省份 top3
                for i in range(3):
                    province = data['provinces'][i]
                    self.current_user_data[f'province_top{i + 1}'] = (
                        f"{province['name']}({format(province['percent'] * 100, '.2f')}%)"
                    )

                # 处理城市 top3
                for i in range(3):
                    city = data['cities'][i]
                    self.current_user_data[f'city_top{i + 1}'] = (
                        f"{city['name']}({format(city['percent'] * 100, '.2f')}%)"
                    )

                # 处理设备 top3
                for i in range(3):
                    device = data['devices'][i]
                    self.current_user_data[f'device_top{i + 1}'] = (
                        f"{device['name']}({format(device['percent'] * 100, '.2f')}%)"
                    )

            except Exception as e:
                logger.error(f"处理粉丝画像数据时出错: {str(e)}")

    def _process_data_summary(self, api_data):
        """处理数据摘要"""
        if api_data['code'] == 0:
            data = api_data['data']
            try:
                self.current_user_data.update({
                    'notes_published': data.get('noteNumber', 0),  # 发布笔记数量
                    'content_categories': ','.join([item.get('contentTag', '') for item in data.get('noteType', [])]),
                    # 内容类目及占比
                    'cooperated_industries': ','.join(data.get('tradeNames', [])),  # 合作行业
                })
            except Exception as e:
                logger.error(f"处理数据摘要时出错: {str(e)}")

    def _process_fans_history(self, api_data):
        """处理粉丝历史数据"""
        if api_data['code'] == 0:
            self.current_user_data.update({
                'followers_increase': api_data['data']['fansNumInc'],
                'followers_change_rate': float(f"{float(api_data['data']['fansNumIncRate']):.2f}")
            })

    def _process_fans_summary(self, api_data):
        """处理粉丝概要数据"""
        if api_data['code'] == 0:
            self.current_user_data.update({
                'active_followers_percentage': float(api_data['data']['activeFansRate']) / 100,
                'active_followers_benchmark_exceed': float(api_data['data']['activeFansBeyondRate']),
                'engaged_followers_percentage': float(api_data['data']['engageFansRate']),
                'engaged_followers_benchmark_exceed': float(api_data['data']['engageFansBeyondRate']),
                'reading_followers_percentage': float(api_data['data']['readFansRate']),
                'reading_followers_benchmark_exceed': float(api_data['data']['readFansBeyondRate']),
            })

    def _process_cost_effective(self, api_data):
        """处理成本效益数据"""
        try:
            if not api_data or api_data.get('data') is None:
                self.current_user_data.update({
                    'video_read_cost': 0,
                    'picture_read_cost': 0,
                })
            else:
                data = api_data['data']
                self.current_user_data.update({
                    'video_read_cost': data.get('videoReadCost', 0),
                    'picture_read_cost': data.get('pictureReadCost', 0),
                })
        except Exception as e:
            logger.error(f"处理成本效益数据时出错: {str(e)}")
            self.current_user_data.update({
                'video_read_cost': 0,
                'picture_read_cost': 0,
            })

    def parse_percentage(self, value, default=0.0):
        """
        将字符串或数字形式的百分比转换为小数

        Args:
            value: 要转换的值，可以是字符串(如 "12.34" 或 "12.34%")或数字
            default: 转换失败时返回的默认值

        Returns:
            float: 转换后的小数值
        """
        try:
            if value is None:
                return default

            # 如果是字符串，去除百分号和空白
            if isinstance(value, str):
                value = value.strip().rstrip('%')

            # 转换为float并除以100
            return float(value) / 100

        except (ValueError, TypeError, AttributeError):
            return default

    async def login(self):
        """
        使用账号密码登录蒲公英
        :param username: 登录账号
        :param password: 登录密码
        :return: 是否登录成功
        """
        try:
            logger.info("开始登录流程...")
            try:
                # 访问首页
                await self.page.goto(self.base_url)
                await TimeUtil.async_random_sleep(1, 1)

                # 等待并点击第一个登录按钮
                logger.info("等待第一个登录按钮出现...")
                first_login_button = await self.page.wait_for_selector("text=账号登录", timeout=10000)
                if not first_login_button:
                    logger.error("未找到第一个登录按钮")
                    return False
                await first_login_button.click()
                await TimeUtil.async_random_sleep(1, 2)

                # 等待并点击弹窗中的账号登录按钮
                logger.info("等待弹窗中的账号登录按钮...")
                second_login_button = await self.page.wait_for_selector("text=账号登录 >> nth=1", timeout=10000)
                if not second_login_button:
                    logger.error("未找到弹窗中的账号登录按钮")
                    return False
                await second_login_button.click()
                await TimeUtil.async_random_sleep(1, 2)

                # 等待邮箱输入框出现并输入邮箱
                logger.info("正在输入账号密码...")
                email_input = await self.page.wait_for_selector("input.css-1dbyz17.css-xno39g.dyn", timeout=5000)
                await email_input.fill("W224564785@163.com")
                await TimeUtil.async_random_sleep(1, 2)  # 模拟人工输入间隔

                # 等待密码输入框出现并输入密码
                password_input = await self.page.wait_for_selector("input.css-1dbyz17.css-cct1ew.dyn", timeout=5000)
                await password_input.fill("Aa123456!")
                await TimeUtil.async_random_sleep(1, 2)  # 模拟人工输入间隔

                # 点击登录按钮
                submit_button = await self.page.wait_for_selector("button.css-r7neow.css-wp7z9d.dyn.beer-login-btn",
                                                            timeout=5000)
                await submit_button.click()

                logger.info("等待登录成功...")
                # 等待个人头像出现，表示登录成功
                avatar = await self.page.wait_for_selector(".home_head_user_info", timeout=60000)
                if avatar:
                    logger.info("登录成功！")
                    self.is_logged_in = True

                    # 登录成功后保存Cookie
                    self.token_content = await self.page.context.cookies()
                    logger.info(f"保存Cookie成功: {self.token_content}")

                    return True
                else:
                    logger.error("登录失败，未检测到登录成功状态")
                    return False
            except PlaywrightTimeoutError as e:
                logger.error("登录超时，请重试")
                return False

        except Exception as e:
            logger.error(f"登录过程出现异常: {str(e)}")
            return False