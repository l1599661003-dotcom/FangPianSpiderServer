from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# 用户基础模型
class UserBase(BaseModel):
    username: str


# 用户创建模型
class UserCreate(UserBase):
    password: str


# 用户模型
class User(UserBase):
    id: int
    create_time: datetime
    salt: str
    password: str
    nickname: str

    class Config:
        from_attributes = True


# 令牌模型
class Token(BaseModel):
    access_token: str
    token_type: str


# 令牌数据模型
class TokenData(BaseModel):
    username: Optional[str] = None
