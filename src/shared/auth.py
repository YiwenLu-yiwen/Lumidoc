"""
统一的认证工具模块，为所有微服务提供身份认证功能
"""

from fastapi import Depends, HTTPException, status, Request, Response, Header
from typing import Optional
import os
import requests
import logging
from datetime import datetime
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer
from src.shared.jwt_utils import decode_jwt_token, is_token_expiring_soon, TOKEN_EXPIRE_MINUTES

# 初始化日志
logger = logging.getLogger(__name__)

# 设置认证服务URL
AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8007")

# 令牌刷新阈值（剩余有效期小于此值时刷新令牌，单位：分钟）
TOKEN_REFRESH_THRESHOLD_MINUTES = 5

# 配置OAuth2认证
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# 用户模型
class User(BaseModel):
    """用户模型"""
    id: int
    username: str
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    updated_at: datetime

async def get_current_user_from_auth_service(token: str) -> Optional[User]:
    """
    从认证服务验证用户身份 - 严格遵循项目原则：通过Gateway调用
    
    Args:
        token: JWT令牌
        
    Returns:
        User: 用户对象，如果验证失败则返回None
    """
    try:
        # 严格遵循项目原则：所有服务间调用必须通过Gateway
        from .service_discovery import call_service
        
        logger.debug("通过Gateway验证用户令牌")
        
        # 通过Gateway调用认证服务验证端点
        response = await call_service(
            service_name="auth",
            endpoint="api/verify",
            method="GET",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0
        )
        
        if not response:
            logger.warning("认证服务未返回验证结果")
            return None

        if response.get("success") is False or response.get("valid") is False:
            logger.warning("认证服务拒绝了令牌")
            return None

        user_data = dict(response.get("data") or response)
        if user_data.get("valid") is False:
            logger.warning("认证服务拒绝了令牌")
            return None
        if "id" not in user_data and "user_id" in user_data:
            user_data["id"] = user_data["user_id"]

        logger.debug("认证服务已验证用户 %s", user_data.get("id"))
        return User(**user_data)
    except Exception as e:
        logger.error(f"验证请求发生错误: {str(e)}")
        return None

async def get_current_user_from_token(
    authorization: str = Header(None),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    获取当前用户
    
    Args:
        authorization: 认证头
        token: JWT令牌
        
    Returns:
        User: 用户信息
        
    Raises:
        HTTPException: 认证失败
    """
    # 检查是否是服务间调用
    if authorization and authorization.startswith("Service "):
        service_token = authorization.replace("Service ", "")
        expected_token = os.environ.get("SERVICE_AUTH_TOKEN")
        
        if expected_token and service_token == expected_token:
            # 服务间认证成功，返回系统用户
            return User(
                id=0,
                username="system",
                email="system@example.com",
                is_active=True,
                is_superuser=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        else:
            logger.warning("服务间认证失败: 无效的服务令牌")
            raise HTTPException(status_code=401, detail="无效的服务令牌")
    
    # 常规用户认证
    if not token:
        logger.warning("未提供认证令牌")
        raise HTTPException(status_code=401, detail="未提供认证令牌")
        
    try:
        payload = decode_jwt_token(token)
        user_id = payload.get("user_id") or payload.get("sub")
        
        if not user_id:
            logger.warning("令牌中未找到用户ID")
            raise HTTPException(status_code=401, detail="令牌中未找到用户ID")
            
        # 在开发环境中，可以直接返回模拟用户
        if os.environ.get("ENV", "development") == "development" and user_id:
            return User(
                id=int(user_id),
                username=f"user{user_id}",
                email=f"user{user_id}@example.com",
                is_active=True,
                is_superuser=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
        # TODO: 在生产环境中，从数据库获取用户信息
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证令牌失败: {str(e)}")
        raise HTTPException(status_code=401, detail="无效的认证令牌")

async def get_current_user(request: Request = None, response: Response = None) -> User:
    """
    识别当前用户，并支持令牌刷新
    
    Args:
        request: FastAPI请求对象
        response: FastAPI响应对象
        
    Returns:
        User: 当前用户对象
    """
    # 如果没有请求对象，直接尝试使用导入的函数
    if not request:
        try:
            # 尝试导入auth模块的函数
            from src.modules.auth.dependencies import get_current_user as auth_get_current_user
            from fastapi import Request, Response
            # 构造空请求和响应
            empty_request = Request(scope={"type": "http"})
            empty_response = Response()
            return await auth_get_current_user(
                request=empty_request, response=empty_response
            )
        except ImportError:
            logger.error("无法导入auth模块的get_current_user函数")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="认证系统配置错误"
            )
    
    # 从请求头获取令牌
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization.replace("Bearer ", "")
    
    # 从认证服务验证令牌
    user = await get_current_user_from_auth_service(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证失败",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 检查令牌是否需要刷新
    try:
        if is_token_expiring_soon(token, TOKEN_REFRESH_THRESHOLD_MINUTES) and response:
            logger.info(f"用户{user.id}的令牌剩余有效期不足，正在刷新")
            # 调用认证服务刷新令牌
            refresh_url = f"{AUTH_SERVICE_URL}/api/auth/refresh"
            headers = {"Authorization": f"Bearer {token}"}
            
            try:
                refresh_response = requests.post(refresh_url, headers=headers, timeout=5.0)
                if refresh_response.status_code == 200:
                    new_token = refresh_response.json().get("access_token")
                    if new_token:
                        # 设置新令牌到响应的Cookie
                        response.set_cookie(
                            key="access_token",
                            value=f"Bearer {new_token}",
                            httponly=True,
                            max_age=TOKEN_EXPIRE_MINUTES * 60,
                            path="/",
                            samesite="lax",
                            secure=True
                        )
                        logger.info(f"已为用户{user.id}设置新令牌")
            except Exception as e:
                logger.warning(f"刷新令牌失败: {str(e)}")
                # 即使刷新失败，仍继续使用原令牌
    except Exception as e:
        logger.warning(f"检查令牌有效期时出错: {str(e)}")
        # 忽略错误，继续使用原令牌
        
    return user
