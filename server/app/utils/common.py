import uuid
import time
import random
import string
from datetime import datetime
import threading


# 雪花算法实现
class SnowflakeGenerator:
    """
    雪花算法ID生成器
    64位ID (42(毫秒)+5(机器ID)+5(业务ID)+12(重复累加))
    """

    def __init__(self, worker_id=0, datacenter_id=0):
        """
        初始化
        :param worker_id: 机器ID
        :param datacenter_id: 数据中心ID
        """
        # 初始时间戳 (2022-01-01)
        self.twepoch = 1640995200000
        # 机器ID所占位数
        self.worker_id_bits = 5
        # 数据中心ID所占位数
        self.datacenter_id_bits = 5
        # 序列号所占位数
        self.sequence_bits = 12
        # 机器ID上限
        self.max_worker_id = -1 ^ (-1 << self.worker_id_bits)
        # 数据中心ID上限
        self.max_datacenter_id = -1 ^ (-1 << self.datacenter_id_bits)
        # 序列号上限
        self.max_sequence = -1 ^ (-1 << self.sequence_bits)
        # 机器ID偏移量
        self.worker_id_shift = self.sequence_bits
        # 数据中心ID偏移量
        self.datacenter_id_shift = self.sequence_bits + self.worker_id_bits
        # 时间戳偏移量
        self.timestamp_shift = self.sequence_bits + self.worker_id_bits + self.datacenter_id_bits

        # 参数校验
        if worker_id > self.max_worker_id or worker_id < 0:
            raise ValueError(f"worker_id 不能大于 {self.max_worker_id} 或小于 0")
        if datacenter_id > self.max_datacenter_id or datacenter_id < 0:
            raise ValueError(f"datacenter_id 不能大于 {self.max_datacenter_id} 或小于 0")

        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def next_id(self):
        """
        生成下一个ID
        :return: ID
        """
        with self.lock:
            timestamp = self._get_timestamp()
            if timestamp < self.last_timestamp:
                # 时钟回拨，抛出异常
                raise Exception(f"时钟回拨，拒绝生成ID，上次时间：{self.last_timestamp}，当前时间：{timestamp}")

            if timestamp == self.last_timestamp:
                # 同一毫秒内，序列号递增
                self.sequence = (self.sequence + 1) & self.max_sequence
                if self.sequence == 0:
                    # 序列号溢出，等待下一毫秒
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                # 不同毫秒内，序列号重置
                self.sequence = 0

            self.last_timestamp = timestamp

            # 生成ID
            return ((timestamp - self.twepoch) << self.timestamp_shift) | \
                   (self.datacenter_id << self.datacenter_id_shift) | \
                   (self.worker_id << self.worker_id_shift) | \
                   self.sequence

    def _get_timestamp(self):
        """
        获取当前时间戳（毫秒）
        :return: 时间戳
        """
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp):
        """
        等待下一毫秒
        :param last_timestamp: 上次时间戳
        :return: 新的时间戳
        """
        timestamp = self._get_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_timestamp()
        return timestamp


# 创建雪花算法ID生成器单例
_snowflake_generator = SnowflakeGenerator(worker_id=1, datacenter_id=1)


def generate_id() -> str:
    """
    生成唯一ID (雪花算法)
    
    Returns:
        唯一ID (bigint兼容的整数)
    """
    return f'{_snowflake_generator.next_id()}'


def generate_short_id(length: int = 8) -> str:
    """
    生成短ID
    
    Args:
        length: ID长度
        
    Returns:
        短ID字符串
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def get_timestamp() -> int:
    """
    获取当前时间戳（秒）
    
    Returns:
        当前时间戳
    """
    return int(time.time())


def get_timestamp_ms() -> int:
    """
    获取当前时间戳（毫秒）
    
    Returns:
        当前时间戳
    """
    return int(time.time() * 1000)


def datetime_to_str(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    将datetime对象转换为字符串
    
    Args:
        dt: datetime对象
        format_str: 格式化字符串
        
    Returns:
        格式化后的时间字符串
    """
    return dt.strftime(format_str)


def str_to_datetime(date_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    将字符串转换为datetime对象
    
    Args:
        date_str: 时间字符串
        format_str: 格式化字符串
        
    Returns:
        datetime对象
    """
    return datetime.strptime(date_str, format_str)
