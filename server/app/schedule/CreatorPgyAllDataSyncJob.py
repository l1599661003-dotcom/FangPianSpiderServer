import asyncio
import uuid
import time
import json
from loguru import logger

from common.RequestTool import RequestsTool
from server.app.core.constant import PLATFORM_TYPE_PGY
from server.app.dao.SignCreatorBusinessDao import fp_sign_creator_business_dao
from server.app.dao.FpCreatorDao import fp_creator_dao
from server.app.db.context import DatabaseManager
from server.app.services.MongoDBService import mongodb_service
from server.app.services.TokenService import token_service
from server.app.services.sync.sync_service import MongoToMySQLSyncService


class CreatorPgyAllDataSyncJob:
    """创作者蒲公英所有数据同步任务"""
    
    def __init__(self):
        self.token_service = token_service
        self.creator_business_dao = fp_sign_creator_business_dao
        self.creator_dao = fp_creator_dao
        self.token = None
        self.xs = None
        self.headers = None
        self.request_tool = None
        self.mongodb_service = mongodb_service
        self.sync_service = MongoToMySQLSyncService()

    async def handle(self) -> int:
        """主处理函数"""
        try:
            logger.info("开始执行创作者蒲公英所有数据同步任务")
            accounts = await self.token_service.list_token_by_platform_id(platform_id=PLATFORM_TYPE_PGY)
            if not accounts:
                logger.info("没有创作者账号")
                return 0
            
            self.token = accounts[0].get('token_content')
            
            # 获取待获取信息的博主列表
            creator_list = await self.creator_business_dao.list_sign_creator(batch_size=100)
            for creator in creator_list:
                creator_info = await self.creator_dao.find_creator_by_user_id(creator.get('creator_id'))
                if not creator_info:
                    logger.error(f"创作者 {creator.get('user_id')} 不存在")
                    continue
                
                self.headers = self._generate_headers(self.token, creator_info.get('platform_user_id'))
                self.request_tool = RequestsTool(headers=self.headers)
                logger.info(f"开始处理创作者: {creator_info.get('user_id')}")
                result = await self.get_creator_data(creator_info)
                if result:
                    self.request_tool.post('http://localhost:8000/admin/creatorSign/recordCreatorData', json={ "creator_data": result })
                    await self.creator_business_dao.update_sign_creator_status(creator.get('id', 0))
                    await self.save_data_to_mongodb(creator_info, result)
                    for key in result.keys():
                        await self.sync_service.sync_table_by_data(key, result.get(key))
                await asyncio.sleep(1)  # 避免请求过快
                
            logger.info("创作者蒲公英所有数据同步任务执行完成")
            return 1
            
        except Exception as e:
            logger.error(f"创作者蒲公英所有数据同步任务执行失败: {str(e)}")
            raise
    
    # 获取创作者数据
    async def get_creator_data(self, creator_info):

        user_id = creator_info.get('platform_user_id')
        
        urls = [
            { "url": f"https://pgy.xiaohongshu.com/api/solar/cooperator/user/blogger/{user_id}", "key": "blogger_info", "method": "GET", "params": "", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/notes_rate", "key": "blogger_note_rate", "method": "GET", "params": f"?userId={user_id}&business=0&noteType=3&dateType=1&advertiseSwitch=1", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/core_data", "key": "blogger_core_data", "method": "POST", "params": "", "json": {
                "userId": user_id,
                "business": 0,
                "noteType": 3,
                "dateType": 1,
                "advertiseSwitch": 1} 
            },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/notes_rate", "key": "blogger_note_rate", "method": "GET", "params": f"?userId={user_id}&business=0&noteType=3&dateType=2&advertiseSwitch=1", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/core_data", "key": "blogger_core_data", "method": "POST", "params": "", "json": {
                "userId": user_id,
                "business": 0,
                "noteType": 3,
                "dateType": 2,
                "advertiseSwitch": 1} 
            },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/notes_rate", "key": "blogger_note_rate", "method": "GET", "params": f"?userId={user_id}&business=1&noteType=3&dateType=2&advertiseSwitch=1", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/core_data", "key": "blogger_core_data", "method": "POST", "params": "", "json": {
                "userId": user_id,
                "business": 1,
                "noteType": 3,
                "dateType": 2,
                "advertiseSwitch": 1} 
            },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/notes_rate", "key": "blogger_note_rate", "method": "GET", "params": f"?userId={user_id}&business=1&noteType=3&dateType=1&advertiseSwitch=1", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/core_data", "key": "blogger_core_data", "method": "POST", "params": "", "json": {
                "userId": user_id,
                "business": 1,
                "noteType": 3,
                "dateType": 1,
                "advertiseSwitch": 1} 
            },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/notes_rate", "key": "blogger_note_rate", "method": "GET", "params": f"?userId={user_id}&business=1&noteType=3&dateType=1&advertiseSwitch=0", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/core_data", "key": "blogger_core_data", "method": "POST", "params": "", "json": {
                "userId": user_id,
                "business": 1,
                "noteType": 3,
                "dateType": 1,
                "advertiseSwitch": 0} 
            },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data/{user_id}/fans_profile", "key": "blogger_fans_profile", "method": "GET", "params": "", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data/{user_id}/fans_overall_new_history", "key": "blogger_fans_history", "method": "GET", "params": "?dateType=1&increaseType=1", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v3/fans_summary?userId={user_id}", "key": "blogger_fans_summary", "method": "GET", "params": "", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/solar/kol/data_v2/notes_detail", "key": "blogger_note_detail", "method": "GET", "params": f"?advertiseSwitch=1&orderType=1&pageNumber=1&pageSize=999&userId={user_id}&noteType=4&withComponent=false", "json": {} },
            { "url": f"https://pgy.xiaohongshu.com/api/pgy/kol/data/data_summary?userId={user_id}&business=1", "key": "blogger_data_summary", "method": "GET", "params": "", "json": {} },
        ]
        result = {}
        for url_info in urls:
            response = self.request_tool.make_api_request(url_info.get('url'), method=url_info.get('method'), params=url_info.get('params'), json=url_info.get('json'))
            if response:
                # 将params解析成对象，格式：?dateType=1&increaseType=1
                params = url_info.get('params').replace('?', '')
                param_data = {}
                if params:
                    param_data = {k: v for k, v in [item.split('=') for item in params.split('&')]}
                response_data = {}

                if response.get('list', []):
                    list_data = response.get('list', [])
                    response_data = [{  **url_info.get('json', {}), **param_data, **item,"creator_id": creator_info.get('id'), "platform_user_id": user_id, "create_time": time.time(), "sync_status": 0 } for item in list_data]
                    result[url_info.get('key')] = response_data
                    continue

                if response.get('dailyData', []):
                    list_data = response.get('dailyData', [])
                    response_data = [{  **url_info.get('json', {}), **param_data, **item,"creator_id": creator_info.get('id'), "platform_user_id": user_id, "create_time": time.time(), "sync_status": 0 } for item in list_data]
                    result[url_info.get('key')] = response_data
                    continue
                
                response_data = { **url_info.get('json', {}), **param_data, **response, "creator_id": creator_info.get('id'), "platform_user_id": user_id, "create_time": time.time(), "sync_status": 0 }
                if result.get(url_info.get('key')):
                    result[url_info.get('key')].append(response_data)
                else:
                    result[url_info.get('key')] = [response_data]
            else:
                logger.error(f"创作者 {creator_info.get('user_id')} 数据获取失败: {url_info.get('key')}")
            # 避免请求过快
            await asyncio.sleep(6)
        
        logger.info(f"创作者 {creator_info.get('user_id')}, data: {json.dumps(result, ensure_ascii= False)}")
        return result

    # 保存数据到MongoDB
    async def save_data_to_mongodb(self, creator_info, result):
        if not result:
            return
        for key in result.keys():
            await self.mongodb_service.batch_save_data(result.get(key), key, creator_info)
                

    # 生成请求头
    def _generate_headers(self, token, creator_id):
        trace_id = str(uuid.uuid4())
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Authorization': '',
            'Cookie': token,
            'Referer': f'https://pgy.xiaohongshu.com/solar/pre-trade/blogger-detail/{creator_id}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0',
            'X-B3-Traceid': trace_id[:16],
        }
        return headers
    

# 创建任务实例的工厂函数
async def create_creator_pgy_all_data_sync_job() -> CreatorPgyAllDataSyncJob:
    """创建创作者蒲公英所有数据同步任务实例"""
    return CreatorPgyAllDataSyncJob()


# 直接执行任务的函数
async def run_creator_pgy_all_data_sync_task() -> int:
    """运行创作者蒲公英所有数据同步任务"""
    await DatabaseManager.initialize()
    job = await create_creator_pgy_all_data_sync_job()
    return await job.handle()


if __name__ == "__main__":
    logger.add("data/logs/server_{time}.log", rotation="1 day", retention="7 days", level="INFO")
    # 初始化数据库连接池
    # 测试执行
    asyncio.run(run_creator_pgy_all_data_sync_task())