from fastapi import Request, APIRouter, Depends

from server.app.services.TokenService import token_service
from server.app.core.sign_util import SignUtil
from loguru import logger
router = APIRouter()

# 获取爬虫token列表，接收JSON参数
@router.post("/spider/token", summary="获取爬虫token列表")
async def get_spider_token(request: Request):
    form_data = await request.json()
    result = SignUtil.verify_sign(form_data)
    logger.info(f"签名验证结果: {result}")
    if not result:
        return {"code": 401, "message": "签名验证失败"}
    # 登录逻辑处理并生成token
    token_list = await token_service.list_token_by_platform_id(11, 2)
    return {"code": 200, "data": token_list, "message": "成功"}
