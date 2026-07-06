import json
import re
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup
from loguru import logger
from requests.exceptions import RequestException


class RequestsTool:

    def __init__(self, base_url=None, headers=None, timeout=60):
        """
        初始化请求工具类

        :param base_url: 可选的基础 URL
        :param headers: 可选的默认请求头
        :param timeout: 请求超时时间，默认为 60 秒
        """
        self.base_url = base_url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'}
        self.timeout = timeout

    def _get_full_url(self, endpoint):
        """
        拼接完整的 URL（基础 URL + endpoint）

        :param endpoint: 请求的路径或 API
        :return: 完整的 URL
        """
        return f"{self.base_url}{endpoint}" if self.base_url else endpoint

    def _send_request(self, method, url, **kwargs):
        """
        发送 HTTP 请求，并处理异常

        :param method: HTTP 方法（如 GET, POST 等）
        :param url: 请求的 URL
        :param kwargs: 其他请求参数（如 params, data, json 等）
        :return: 响应数据
        """
        try:
            logger.info(f"发送请求: {method} {url}")

            response = requests.request(method, url, headers=self.headers, timeout=self.timeout, **kwargs)
            # response.raise_for_status()  # 如果响应状态码不是 2xx，会抛出异常
            response_text = response.text
            # logger.info(f"响应数据: {response_text}")

            return json.loads(response_text)
        except RequestException as e:
            logger.error(f"请求失败: {e}")
            return None

    def get(self, endpoint, **kwargs):
        """
        发送 GET 请求

        :param endpoint: 请求的 API 路径
        :param kwargs: 其他 GET 请求的参数（如 params 等）
        :return: 响应数据
        """
        url = self._get_full_url(endpoint)
        return self._send_request('GET', url, **kwargs)

    def post(self, endpoint, data=None, json=None, **kwargs):
        """
        发送 POST 请求

        :param endpoint: 请求的 API 路径
        :param data: 要发送的表单数据
        :param json: 要发送的 JSON 数据
        :param kwargs: 其他 POST 请求的参数
        :return: 响应数据
        """
        url = self._get_full_url(endpoint)
        return self._send_request('POST', url, data=data, json=json, **kwargs)

    def put(self, endpoint, data=None, **kwargs):
        """
        发送 PUT 请求

        :param endpoint: 请求的 API 路径
        :param data: 要发送的数据
        :param kwargs: 其他 PUT 请求的参数
        :return: 响应数据
        """
        url = self._get_full_url(endpoint)
        return self._send_request('PUT', url, data=data, **kwargs)

    def delete(self, endpoint, **kwargs):
        """
        发送 DELETE 请求

        :param endpoint: 请求的 API 路径
        :param kwargs: 其他 DELETE 请求的参数
        :return: 响应数据
        """
        url = self._get_full_url(endpoint)
        return self._send_request('DELETE', url, **kwargs)

    def download_file(self, url, save_path):
        """
        下载文件

        :param url: 文件的 URL
        :param save_path: 保存文件的路径
        :return: 响应数据
        """
        response = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return save_path

    # 使用函数来处理单个API请求，改进错误处理
    def make_api_request(self, endpoint, params="", method='GET', json=None):
        try:
            url = f"{endpoint}{params}"
            if method == 'GET':
                response = self.get(url)
            else:
                response = self.post(endpoint=url,  json=json)
            return response
        except Exception as e:
            logger.error(f"API请求失败 ({url}): {e}")
            return None

    def get_blogger_xhs_desc(self, blogger_id):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        url = f"https://www.xiaohongshu.com/user/profile/{blogger_id}"
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        response_body = response.text
        soup = BeautifulSoup(response_body, "html.parser")
        user_desc_tag = soup.find("div", class_="user-desc")
        if user_desc_tag:
            user_desc = user_desc_tag.get_text(strip=True)
            print(user_desc)
        # 备用方案：使用正则匹配
        match = re.search(r'<div class="user-desc"[^>]*>(.*?)</div>', response_body, re.S)
        if match:
            user_desc = match.group(1).strip()
            return user_desc

        return None
    # 从请求响应获取数据
    def _get_request_data(self, request_data: Dict[str, Any]):
        """同步方法：从请求响应获取数据"""
        if not request_data:
            return {}
            
        if isinstance(request_data, dict):
            code = request_data.get('code')
            if code == 300013 or code == 903 or code == 902 or code == 906:
                logger.error(f"获取请求响应数据失败: {request_data}")
                return request_data
            data = request_data.get('data', {})
            if data:
                return data
        return None