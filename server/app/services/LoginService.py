import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import HTTPException
from loguru import logger
from starlette import status

from server.app.db.base import MySQLBaseDAO
from server.app.services.FpSpiderClientService import spider_client_service
from server.app.utils import IpUtil
from server.app.utils.SessionUtil import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES


class UserService(MySQLBaseDAO):
    """用户认证和账号管理服务"""

    def __init__(self):
        super().__init__("fp_admin")

    async def find_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        通过用户名查询用户信息

        Args:
            username: 用户名

        Returns:
            User: 用户对象，如果未找到则返回 None
        """
        try:
            # async with self as service:
            #     query = select(User).where(User.username == username)
            #     result = await service.db.execute(query)
            #     user = result.scalar_one_or_none()
            #     return user
            query = """
                        SELECT * 
                        FROM fp_admin ct
                        WHERE ct.username = :username
                        """
            return await self.fetch_one(query, {"username": username})
        except Exception as e:
            logger.error(f"查询用户信息失败: {str(e)}, username: {username}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询用户信息失败"
            )

    async def login(self, form_data, request) -> str:
        """
        用户登录处理

        Args:
            form_data: 登录表单数据
            request: FastAPI 请求对象

        Returns:
            str: 访问令牌

        Raises:
            HTTPException: 登录失败时抛出相应的异常
        """
        try:
            # 验证用户名和密码
            user = await self.find_user_by_username(form_data.username)
            if not user or not verify_password(form_data.password, user.get('password', ''), user.get('salt', '123456')):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            query = """
                                SELECT * 
                                FROM fp_spider_client ct
                                WHERE ct.admin_id = :admin_id and ct.status = 1
                            """
            spider_client = await self.fetch_one(query, {"admin_id": user.get("id", 0)})

            if not spider_client:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="暂无权限登录",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            ws_manager = self.get_websocket_manager()
            is_logined = ws_manager.is_client_connected(spider_client.get('id'))
            logger.info(f"客户端 {spider_client} is_logined: {is_logined}")
            if is_logined:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 更新客户端信息
            if not spider_client.get('device_id', None):
                spider_client['device_id'] = uuid.uuid4().hex
                spider_client['ip_address'] = IpUtil.get_ip_address(request)
                spider_client['update_time'] = datetime.now()
                await spider_client_service.update(spider_client, { "id": spider_client['id', 0] })

                logger.info(f"客户端 {spider_client['ip_address']} 登录成功")

            # 生成访问令牌
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={
                    "sub": user.get('username', ''),
                    "client_id": spider_client.get('id', 0)
                },
                expires_delta=access_token_expires
            )
            return access_token

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"登录处理失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="登录处理失败"
            )

    def get_websocket_manager(self):
        from server.app.main import ws_manager
        return ws_manager

# 创建全局服务实例
user_service = UserService()
