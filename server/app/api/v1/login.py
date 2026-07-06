from fastapi import HTTPException, Request, Depends, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from loguru import logger
from starlette import status

from server.app.schemas.schemas import Token, TokenData, UserBase
from server.app.services.LoginService import user_service
from server.app.utils.SessionUtil import oauth2_scheme, SECRET_KEY, ALGORITHM

router = APIRouter()

# 登录
@router.post("/user/login", response_model=Token, summary="客户端登录")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # 登录逻辑处理并生成token
    access_token = await user_service.login(form_data, request)
    return {"access_token": access_token, "token_type": "bearer"}


# 获取当前用户
@router.get("/user/current", response_model=UserBase, summary="获取当前用户")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    logger.info(f"登录Token内容：{token}")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    with UserService() as user_service:
        user = user_service.find_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception
    user_base = UserBase(**{"username": user.username})
    return user_base
