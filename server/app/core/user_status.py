from typing import Dict, Set, Optional
from datetime import datetime
import asyncio
from config import settings

class UserStatus:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.is_online = False
        self.last_seen = None
        self.current_room = None
        self.status = "offline"  # offline, online, busy, away 离线、在线、忙碌、离开
        self.devices = set()  # 存储设备ID
        self.last_activity = datetime.utcnow()
        self.custom_status = None  # 自定义状态消息

# 用户状态管理器
class UserStatusManager:
    def __init__(self):
        self.user_statuses: Dict[int, UserStatus] = {}
        self._cleanup_task = None

    # 启动清理任务
    def start_cleanup_task(self):
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_inactive_users())

    # 异步 清理不活跃用户
    async def _cleanup_inactive_users(self):
        while True:
            await asyncio.sleep(settings.USER_STATUS_CLEANUP_INTERVAL)
            self.cleanup_inactive_users()

    # 清理不活跃用户
    def cleanup_inactive_users(self):
        current_time = datetime.utcnow()
        inactive_threshold = settings.USER_INACTIVE_THRESHOLD
        
        for user_id, status in list(self.user_statuses.items()):
            if (current_time - status.last_activity).total_seconds() > inactive_threshold:
                self.set_user_offline(user_id)

    # 添加用户
    def add_user(self, user_id: int, username: str, device_id: str) -> UserStatus:
        if user_id not in self.user_statuses:
            self.user_statuses[user_id] = UserStatus(user_id, username)
        
        status = self.user_statuses[user_id]
        status.devices.add(device_id)
        status.is_online = True
        status.status = "online"
        status.last_seen = datetime.utcnow()
        status.last_activity = datetime.utcnow()
        
        return status

    # 移除用户设备
    def remove_user_device(self, user_id: int, device_id: str):
        if user_id in self.user_statuses:
            status = self.user_statuses[user_id]
            status.devices.discard(device_id)
            
            if not status.devices:
                self.set_user_offline(user_id)

    # 设置用户离线
    def set_user_offline(self, user_id: int):
        if user_id in self.user_statuses:
            status = self.user_statuses[user_id]
            status.is_online = False
            status.status = "offline"
            status.devices.clear()
            status.current_room = None

    # 更新用户活动
    def update_user_activity(self, user_id: int):
        if user_id in self.user_statuses:
            self.user_statuses[user_id].last_activity = datetime.utcnow()

    # 设置用户状态
    def set_user_status(self, user_id: int, status: str, custom_status: Optional[str] = None):
        if user_id in self.user_statuses:
            self.user_statuses[user_id].status = status
            if custom_status is not None:
                self.user_statuses[user_id].custom_status = custom_status

    # 设置用户房间
    def set_user_room(self, user_id: int, room_id: Optional[str]):
        if user_id in self.user_statuses:
            self.user_statuses[user_id].current_room = room_id

    # 获取用户状态
    def get_user_status(self, user_id: int) -> Optional[UserStatus]:
        return self.user_statuses.get(user_id)

    # 获取在线用户
    def get_online_users(self) -> Dict[int, UserStatus]:
        return {uid: status for uid, status in self.user_statuses.items() 
                if status.is_online}

    # 获取房间用户
    def get_room_users(self, room_id: str) -> Dict[int, UserStatus]:
        return {uid: status for uid, status in self.user_statuses.items() 
                if status.current_room == room_id and status.is_online}

    # 获取用户数量
    def get_user_count(self) -> int:
        return len(self.user_statuses)

    # 获取在线用户数量
    def get_online_user_count(self) -> int:
        return len(self.get_online_users())

# 用户状态管理器实例
user_status_manager = UserStatusManager() 