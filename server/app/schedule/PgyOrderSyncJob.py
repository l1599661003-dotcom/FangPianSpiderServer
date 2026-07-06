import asyncio
from typing import List
from datetime import datetime
import uuid

from server.app.core.constant import PLATFORM_TYPE_PGY, ACCOUNT_TYPE_SENSITIVE 
from server.app.services.TokenService import token_service
from server.app.dao.FpPgyCreatorOrderDao import fp_pgy_creator_order_dao
from server.app.dao.FpCreatorDao import fp_creator_dao
from common.RequestTool import RequestsTool
from loguru import logger


class PgyOrderSyncJob:
    def __init__(self):
        self.token_service = token_service
        self.fp_pgy_creator_order_dao = fp_pgy_creator_order_dao
        self.page_size = 50
        self.fp_creator_dao = fp_creator_dao
    

    async def handle(self):
        """处理蒲公英订单同步任务"""
        # 获取所有可用token
        tokens = await self.token_service.list_token_by_platform_id(platform_id=PLATFORM_TYPE_PGY, account_type=ACCOUNT_TYPE_SENSITIVE)
        if not tokens:
            print("No valid tokens found")
            return
            
        # 使用asyncio.gather同时处理多个token，而不是创建多线程
        tasks = [self._sync_orders_for_token(token) for token in tokens]
        await asyncio.gather(*tasks)
        
    async def _sync_orders_for_token(self, token: str):
        """为单个token同步订单数据
        
        Args:
            token: 蒲公英平台的访问token
        """
        page = 1
        while True:
            try:
                # 获取订单数据
                orders = await self._fetch_orders_page(token, page)

                if not orders:
                    break
                
                order_ids = [v["orderId"] for order in orders for v in order["orderVos"]]
                
                # 删除数据库已存在订单
                origin_orders = await self.fp_pgy_creator_order_dao.list_pgy_creator_order(params={"order_ids": order_ids})
                if origin_orders:
                    ids = [str(v["id"]) for v in origin_orders]
                    await self.fp_pgy_creator_order_dao.batch_delete_pgy_creator_order(ids)
                    logger.info(f"删除数据库已存在订单, 条数: {len(ids)}")
                
                origin_order_map = {v["platform_order_id"]: v for v in origin_orders or []}

                # 获取博主基本信息
                creator_ids = [v["kolId"] for order in orders for v in order["orderVos"]]   
                creators = await self.fp_creator_dao.list_sign_creator(batch_size=len(creator_ids), platform_user_ids=creator_ids)
                creator_map = {v["platform_user_id"]: v for v in creators.get("items", [])}

                creator_orders = []
                for order in orders:
                    for v in order["orderVos"]:
                        creator_order = {
                            "create_time": int(datetime.now().timestamp()),
                            "update_time": int(datetime.now().timestamp()),
                        }
                        creator_order_detail = None
                        if v["orderId"] in origin_order_map:
                            creator_order = origin_order_map[v["orderId"]]
                            creator_order['id'] = None
                        else:
                            creator_order_detail = await self._fetch_order_detail(token, v["orderId"])
                        creator = creator_map.get(v["kolId"], {})

                        creator_order['platform_order_id'] = v["orderId"]
                        creator_order['platform_create_time'] = v["createTime"]
                        creator_order['creator_nickname'] = v["kolName"]
                        creator_order['creator_id'] = creator.get("id", 0)
                        creator_order['platform_user_id'] = v["kolId"]
                        creator_order['content_type'] = v["contentType"]
                        creator_order['content_price'] = v["contentPrice"]
                        creator_order['total_price'] = v["totalPrice"]
                        creator_order['brand_name'] = v["brandName"]
                        creator_order['brand_id'] = v["brandId"]
                        creator_order['order_status'] = v["orderStatus"]
                        creator_order['state'] = v["state"]
                        creator_order['sign_type'] = '2'
                        creator_order['publish_time'] = v["notePublishTime"]
                        creator_order['scenes_id'] = v["scenesId"]
                        creator_order['complete_time'] = v["brandConfirmTime"]

                        creator_order['title'] = order["title"]
                        creator_order['expected_publish_time'] = order["expectPublishTime"]
                        if creator_order_detail:
                            creator_order['note_id'] = creator_order_detail["noteId"]
                            creator_order['note_image'] = creator_order_detail["noteImage"]
                            creator_order['note_type'] = creator_order_detail["noteType"]
                            kolContactInfo = creator_order_detail.get('kolContactInfo', {})
                            if kolContactInfo:
                                creator_order['creator_contact_name'] = kolContactInfo.get("contactName", "")  
                                creator_order['creator_contact_phone'] = kolContactInfo.get("contactPhone", "")
                                creator_order['creator_contact_name_cipher'] = kolContactInfo.get("contactNameCiphertext", "")
                                creator_order['creator_contact_phone_cipher'] = kolContactInfo.get("contactPhoneCiphertext", "")

                                sensitive_info_view = await self._fetch_sensitive_info_view(token, creator_order['creator_contact_name_cipher'], v["orderId"])
                                creator_order['creator_contact_name'] = sensitive_info_view.get("text", "")
                                sensitive_info_view = await self._fetch_sensitive_info_view(token, creator_order['creator_contact_phone_cipher'], v["orderId"])
                                creator_order['creator_contact_phone'] = sensitive_info_view.get("text", "")
                            
                            creator_order['contact_name'] = creator_order_detail.get('contactName', "")
                            creator_order['contact_phone'] = creator_order_detail.get('contactPhone', "")
                            creator_order['contact_name_cipher'] = creator_order_detail.get('contactNameCiphertext', "")
                            creator_order['contact_phone_cipher'] = creator_order_detail.get('contactPhoneCiphertext', "")
                            creator_order['mcn_name'] = creator_order_detail.get('mcnName', "")
                            creator_order['mcn_id'] = creator_order_detail.get('mcnId', "")
                            creator_order['report_brand_name'] = creator_order_detail.get('reportBrandName', "")
                            creator_order['report_brand_user_id'] = creator_order_detail.get('reportBrandUserId', "")

                            # 解密敏感信息
                            sensitive_info_view = await self._fetch_sensitive_info_view(token, creator_order['contact_name_cipher'], v["orderId"])
                            creator_order['contact_name'] = sensitive_info_view.get("text", "")
                            sensitive_info_view = await self._fetch_sensitive_info_view(token, creator_order['contact_phone_cipher'], v["orderId"])
                            creator_order['contact_phone'] = sensitive_info_view.get("text", "")
                        
                        await self.fp_pgy_creator_order_dao.add_pgy_creator_order(creator_order)
                logger.info(f"获取订单详情数据, 条数: {len(creator_orders)}")
                
                # 继续下一页
                page += 1
                
            except Exception as e:
                # 打印出异常堆栈
                logger.exception(f"Error syncing orders for token {token.get('platform_account')}, page {page}: {e}")
                break
                
    async def _fetch_orders_page(self, token: dict, page: int) -> List[dict]:
        """获取单页订单数据
        
        Args:
            token: 蒲公英平台的访问token
            page: 页码
            
        Returns:
            订单数据列表
        """
        url = f"https://pgy.xiaohongshu.com/api/solar/order/order/query"
        params = {
            'commitTime': [],
            'completeTime': [],
            'cooperationType': '',
            'isWindmill': False,
            'kolType': 0,
            'kolUserId': '',
            'mcnAuthorized': '',
            'negotiationStatus': '',
            'orderId': '',
            'orderSource': '',
            'pageNum': page,
            'pageSize': self.page_size,
            'publishTime': [],
            'scenesId': 0,
            'settlementRule': '',
            'state': '',
            'title': '',
            'windmillFilter': 0,
        }

        headers = await self._get_headers(token)
        request_tool = RequestsTool(headers=headers)
        response = request_tool.post(url, json=params)
        logger.info(f"获取订单数据, 条数: {response}")
        await asyncio.sleep(6)
        if response and response.get("code") == 0:
            return response.get("data", {}).get("list", [])
        if response and response.get("code") in [902, 903]:
            logger.error(f"token: {token.get('platform_account')} 登录过期, 请重新登录。")
            return []
        if response and response.get("code") in [300013]:
            logger.error(f"token: {token.get('platform_account')} 访问频次过高, 请稍后再试。")
            return []
        return []
    
    async def _fetch_order_detail(self, token: str, order_id: str) -> dict:
        """获取订单详情数据
        
        Args:
            token: 蒲公英平台的访问token
            order_id: 订单ID
        """
        url = f"https://pgy.xiaohongshu.com/api/solar/order/detail/{order_id}"
        headers = await self._get_headers(token)
        # headers['Referer'] = f"https://pgy.xiaohongshu.com/solar/transaction/order/detail/mcn/{order_id}"
        request_tool = RequestsTool(headers=headers)
        response = request_tool.get(url)
        await asyncio.sleep(6)

        if response and response.get("code") == 0: 
            return response.get("data", {})
        if response and response.get("code") in [902, 903]:
            logger.error(f"token: {token.get('platform_account')} 登录过期, 请重新登录。")
            return {}
        if response and response.get("code") in [300013]:
            logger.error(f"token: {token.get('platform_account')} 访问频次过高, 请稍后再试。")
            return {}
        return {}

    async def _fetch_sensitive_info_view(self, token: str, content: str, order_id: str) -> dict:
        if not content:
            return {}
        """获取敏感信息视图
        
        Args:
            token: 蒲公英平台的访问token
            content: 敏感信息
        """
        url = f"https://pgy.xiaohongshu.com/api/solar/common/sensitive_info_view"
        headers = await self._get_headers(token)
        headers['Referer'] = f"https://pgy.xiaohongshu.com/solar/transaction/order/detail/mcn/{order_id}"
        headers['Content-Type'] = 'application/json'
        data = {
            "ciphertext": content
        }
        request_tool = RequestsTool(headers=headers)
        response = request_tool.post(url, json=data)
        await asyncio.sleep(6)
        return response.get("data", {})

    async def _get_headers(self, token: dict) -> dict:
        """获取请求头
        Args:
            token: 蒲公英平台的访问token
        """
        # 生成一个随机的trace_id
        trace_id = str(uuid.uuid4())

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-encoding': 'gzip, deflate, br, zstd',
            'Accept-language': 'zh-CN,zh;q=0.9',
            'Content-Type': 'application/json;charset=UTF-8',
            'Cookie': token.get("token_content"),  # 蒲公英token
            # 'Origin': 'https://pgy.xiaohongshu.com',
            'Priority': 'u=1, i',
            # 'Referer': 'https://pgy.xiaohongshu.com/solar/transaction_v2/mcn/order-list',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Host': 'pgy.xiaohongshu.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            # 'X-B3-Traceid': trace_id[:16], # 确保填写完整的cookie字符串
        }

        return headers
            
if __name__ == "__main__":
    job = PgyOrderSyncJob()
    asyncio.run(job.handle())