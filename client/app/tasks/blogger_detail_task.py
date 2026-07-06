import asyncio
import concurrent.futures
import functools
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from loguru import logger

from client.app.core.task_base import BaseTask
from client.app.utils import TimeUtil
from client.app.utils.RequestTool import RequestsTool


class BloggerDetailTask(BaseTask):
    """博主详情采集任务处理器"""

    async def on_initialize(self):
        """初始化任务"""
        logger.info(f"初始化博主详情采集任务, 任务ID: {self.task_id}")
        self.platform_id = self.task_data.get("platform_id", 0)  # 平台ID，默认为小红书
        self.token_id = None  # 令牌ID，会在处理过程中请求分配
        self.token_content = None  # 令牌内容
        # 初始化线程池执行器
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        # 保存主事件循环
        self.main_loop = asyncio.get_running_loop()
        # 请求令牌
        await self.request_token()

    async def preprocess_data(self, data: Any) -> Any:
        """预处理数据"""
        return data

    async def clear_current_batch(self):
        """清空当前批次数据"""
        self.current_batch_data = None

    async def has_pending_data(self) -> bool:
        """检查是否有待处理数据"""
        return self.current_batch_data is not None

    async def calculate_progress(self) -> float:
        """计算处理进度"""
        if self.total_count == 0:
            return 0.0
        return (self.success_count + self.fail_count) / self.total_count * 100

    async def calculate_data_count(self, data: Any) -> int:
        """计算数据条数"""
        return len(data) if isinstance(data, list) else 1

    async def process_batch(self, data: Any, batch_id: str) -> Tuple[bool, int, int]:
        """
        处理整批数据
        
        Args:
            data: 数据列表
            batch_id: 批次ID
            
        Returns:
            (成功标志, 成功处理数, 失败处理数)
        """
        if not self.token_content:
            logger.warning(f"令牌无效，请求分配令牌")
            await self.request_token()
            return False, 0, 0
        
        success_count = 0
        fail_count = 0
        
        for item in data:
            if not self.running:
                break
            logger.info(f"process_batch_item: {item}")
            try:
                # 使用线程池执行HTTP请求，避免阻塞事件循环
                result = await self.process_item(item, batch_id)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"处理数据项失败: {e}")
                fail_count += 1
        
        return success_count > 0, success_count, fail_count

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
            # 使用线程池执行耗时的HTTP请求操作
            return await asyncio.get_event_loop().run_in_executor(
                self.executor, 
                functools.partial(self._process_item_sync, item, batch_id)
            )
        except Exception as e:
            logger.error(f"处理博主详情失败: {e}, 博主ID: {locals().get('pgy_url', item)}")
            # 判断是否令牌问题
            if "token" in str(e).lower() or "unauthorized" in str(e).lower() or "401" in str(e):
                # 异步请求新令牌
                asyncio.run_coroutine_threadsafe(
                    self.on_error("TOKEN_INVALID", str(e)),
                    self.main_loop
                )
            TimeUtil.random_sleep(3, 3)
            return False
            
    def _process_item_sync(self, item: Dict[str, Any], batch_id: str) -> bool:
        """同步方式处理单个数据项，在线程池中执行"""
        try:
            # fields = item.get('fields', {})
            pgy_url = item.get('pgy_url')
            record_id = item.get('id')
            #
            # logger.info(f"处理博主信息, 博主ID: {pgy_url}")
            blogger_id = pgy_url.split('/')[-1]
            logger.info(f"处理博主信息, 博主ID: {blogger_id}")

            if not blogger_id:
                logger.error(f"无法获取博主ID, 请检查数据项: {item}")
                return False

            # 检查令牌状态
            if not self.token_content:
                logger.error("令牌无效，无法发送请求")
                # 异步请求新令牌
                asyncio.run_coroutine_threadsafe(self.request_token(), self.main_loop)
                return False

            request_util = RequestsTool("https://pgy.xiaohongshu.com/api", {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Cookie': self.token_content
            }, timeout=30)  # 缩短超时时间，减少长时间阻塞
            
            result = {}
            
            # 使用函数来处理单个API请求，改进错误处理
            def make_api_request(endpoint, params=""):
                try:
                    # 验证任务是否还在运行
                    if not self.running:
                        return None
                        
                    url = f"{endpoint}{params}"
                    response = request_util.get(url)
                    TimeUtil.random_sleep(5, 7)  # 减少等待时间
                    return self._get_request_data(response)
                except Exception as e:
                    logger.error(f"API请求失败 ({url}): {e}")
                    TimeUtil.random_sleep(6, 6)
                    return None
            
            # 博主信息
            blogger_info = make_api_request(f"/solar/cooperator/user/blogger/{blogger_id}")
            if blogger_info is None:
                logger.error(f"获取博主基本信息失败: {blogger_id}")
                return False
                
            result["blogger_info"] = [blogger_info]
            
            # 近期传播表现
            business = 0  # 普通
            note_type = 3
            date_type = 1
            advertise_switch = 1

            # 30天日常笔记全流量
            note_rate_normal_30_all = make_api_request(
                f"/solar/kol/data_v3/notes_rate",
                f"?userId={blogger_id}&business={business}&noteType={note_type}&dateType={date_type}&advertiseSwitch={advertise_switch}")

            date_type = 2  # 90天全流量
            note_rate_normal_90_all = make_api_request(
                f"/solar/kol/data_v3/notes_rate",
                f"?userId={blogger_id}&business={business}&noteType={note_type}&dateType={date_type}&advertiseSwitch={advertise_switch}")

            business = 1  # 合作 90天全流量
            note_rate_coop_90_all = make_api_request(
                f"/solar/kol/data_v3/notes_rate",
                f"?userId={blogger_id}&business={business}&noteType={note_type}&dateType={date_type}&advertiseSwitch={advertise_switch}")

            date_type = 1  # 合作30天全流量
            note_rate_coop_30_all = make_api_request(
                f"/solar/kol/data_v3/notes_rate",
                f"?userId={blogger_id}&business={business}&noteType={note_type}&dateType={date_type}&advertiseSwitch={advertise_switch}")

            advertise_switch = 0  # 30天自然流量
            note_rate_coop_30_only = make_api_request(
                f"/solar/kol/data_v3/notes_rate",
                f"?userId={blogger_id}&business={business}&noteType={note_type}&dateType={date_type}&advertiseSwitch={advertise_switch}")

            result["blogger_note_rate"] = [
                { **note_rate_normal_30_all, "user_id": blogger_id, "dateType": 1, "noteType": 3, "advertiseSwitch": 1, "business": 0 } or {},
                { **note_rate_normal_90_all, "user_id": blogger_id, "dateType": 2, "noteType": 3, "advertiseSwitch": 1, "business": 0 } or {},
                { **note_rate_coop_90_all, "user_id": blogger_id, "dateType": 2, "noteType": 3, "advertiseSwitch": 1, "business": 1 } or {},
                { **note_rate_coop_30_all, "user_id": blogger_id, "dateType": 1, "noteType": 3, "advertiseSwitch": 1, "business": 1 } or {},
                { **note_rate_coop_30_only, "user_id": blogger_id, "dateType": 1, "noteType": 3, "advertiseSwitch": 0, "business": 1 } or {}
            ]

            # 粉丝画像
            fans_profile = make_api_request(f"/solar/kol/data/{blogger_id}/fans_profile")
            result["blogger_fans_profile"] = [{ **fans_profile, "user_id": blogger_id } or {}]

            # 粉丝趋势 30 天
            fans_history = make_api_request(
                f"/solar/kol/data/{blogger_id}/fans_overall_new_history",
                "?dateType=1&increaseType=1")
            result["blogger_fans_history"] = [{**item, "user_id": blogger_id, "dateType": 1, "increaseType": 1} for item in (fans_history or {}).get('list', [])]

            # 粉丝增量趋势 30天
            fans_increase_history = make_api_request(
                f"/solar/kol/data/{blogger_id}/fans_overall_new_history",
                "?dateType=1&increaseType=2")
            result["blogger_fans_increase_history"] = [{**item, "user_id": blogger_id, "dateType": 1, "increaseType": 2} for item in (fans_increase_history or {}).get('list', [])]

            # 核心数据
            fans_summary = make_api_request(f"/solar/kol/data_v3/fans_summary", f"?userId={blogger_id}")
            result["blogger_fans_summary"] = [{ **fans_summary, "user_id" :blogger_id }]

            # 笔记案例
            notes_detail = make_api_request(
                f"/solar/kol/data_v2/notes_detail",
                f"?advertiseSwitch=1&orderType=1&pageNumber=1&pageSize=999&userId={blogger_id}&noteType=4&withComponent=false")

            result["blogger_note_detail"] =  [{**item, "user_id": blogger_id, "advertiseSwitch": "1", "orderType": 1, "noteType": 4} for item in (notes_detail or {}).get('list', [])]

            # 使用异步方式上报结果
            if self.running:
                asyncio.run_coroutine_threadsafe(
                    self.report_result(record_id, result),
                    self.main_loop
                )

            return True

        except Exception as e:
            logger.error(f"处理博主详情失败: {e}, 博主ID: {locals().get('pgy_url', item)}")
            # 判断是否令牌问题
            if "token" in str(e).lower() or "unauthorized" in str(e).lower() or "401" in str(e):
                # 异步请求新令牌
                asyncio.run_coroutine_threadsafe(
                    self.on_error("TOKEN_INVALID", str(e)),
                    self.main_loop
                )
            TimeUtil.random_sleep(6, 6)
            return False

    async def on_stop(self):
        """停止任务时的清理工作"""
        logger.info(f"停止博主详情采集任务, 任务ID: {self.task_id}")

        # 释放令牌
        if self.token_id:
            await self.release_token()
            
        # 关闭线程池
        self.executor.shutdown(wait=False)

    async def on_complete(self):
        """任务完成时的处理"""
        logger.info(f"完成博主详情采集任务, 任务ID: {self.task_id}")

        # 释放令牌
        if self.token_id:
            await self.release_token()
            
        # 关闭线程池
        self.executor.shutdown(wait=False)

    async def on_error(self, error_code: str, error_message: str):
        """
        处理任务错误
        
        Args:
            error_code: 错误代码
            error_message: 错误消息
        """
        logger.error(f"博主详情采集任务出错: [{error_code}] {error_message}")

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
            result_message = {
                "cmd": "result_report",
                "task_id": self.task_id,
                "data": {
                    "blogger_id": blogger_id,
                    "result": result,
                    "timestamp": datetime.now().timestamp()
                }
            }

            # 发送请求
            await self.command_handler.websocket_client.send(result_message, require_confirmation=False)

            logger.info(f"已上报结果, 任务ID: {self.task_id}, 博主ID: {blogger_id}")

        except Exception as e:
            logger.error(f"上报结果失败: {e}")
    
    def _get_request_data(self, request_data: Dict[str, Any]):
        """同步方法：从请求响应获取数据"""
        if not request_data:
            return {}
            
        if isinstance(request_data, dict):
            data = request_data.get('data', {})
            if data:
                return data
                
        return request_data
