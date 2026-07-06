import datetime
import hashlib
import os
from datetime import timedelta

from fastapi import HTTPException, WebSocket
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from starlette import status

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Security configuration 安全配置 密钥、算法、令牌过期时间
SECRET_KEY = os.getenv("SECRET_KEY", "123456")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 60 # 60天有效期


# Authentication functions 认证函数
def verify_password(plain_password: str, hashed_password, salt):
    md5_pass = hashlib.md5(plain_password.encode("utf-8"))
    md5_pass = hashlib.md5((md5_pass.hexdigest() + salt).encode("utf-8"))
    return hashed_password == md5_pass.hexdigest()


# 获取密码哈希值
def get_password_hash(password):
    return pwd_context.hash(password)


# 创建访问令牌
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_token_from_websocket(websocket: WebSocket):
    # 尝试从Header中获取token
    token = websocket.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        return token[7:]  # 去除 "Bearer " 前缀
    
    # 如果Header中没有token，尝试从URL查询参数中获取
    query_params = dict(websocket.query_params)
    if "token" in query_params:
        return query_params["token"]
    return None

# 命令行客户端获取客户端ID
async def get_cli_client_id(websocket: WebSocket):
    # 如果Header中没有token，尝试从URL查询参数中获取
    query_params = dict(websocket.query_params)
    if "cli_client_id" in query_params:
        return query_params["cli_client_id"]
    return None

# 获取当前用户
def get_current_user(token):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        client_id: int = payload.get("client_id")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return { "username": username, "client_id": client_id }
