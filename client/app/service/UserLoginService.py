import os

from loguru import logger

from client.app.utils.RequestTool import RequestsTool


class UserLoginService:
    def __init__(self):
        self.request = RequestsTool(base_url=os.getenv("BASE_URL", "http://127.0.0.1:8000/api/v1"))

    def login(self, username, password):
        """
        用户登录
        :param username: 用户名
        :param password: 密码
        :return:
        """
        token = self.request.post('/user/login', data={"username": username, "password": password})
        logger.info(f"token: {token}")
        if not token:
            return False, "用户名或密码错误"
        return True, token.get('access_token', '')
