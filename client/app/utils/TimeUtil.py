import time
import asyncio
from numpy import random


@staticmethod
def random_sleep(self, min_seconds=1, max_seconds=5):
    """随机等待一段时间，避免被反爬"""
    time.sleep(random.uniform(min_seconds, max_seconds))


@staticmethod
async def async_random_sleep(self, min_seconds=1, max_seconds=5):
    """异步版本的随机等待一段时间，避免被反爬"""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))