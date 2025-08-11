import logging
from typing import Dict, Any, Optional, Tuple
from fastapi import APIRouter, HTTPException, Depends, Body, FastAPI, Header, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import httpx
from pydantic import BaseModel
from src.modules.config import settings
from src.shared.types.response import ApiResponse
from src.shared.types.user import UserResponse as User, UserCreate, UserUpdate

# 创建FastAPI应用
app = FastAPI()

# 创建路由
router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# 获取认证服务客户端
async def get_auth_service():
    """获取认证服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

async def handle_service_response(response: httpx.Response, operation: str) -> Dict[str, Any]:
    """统一处理服务响应"""
    try:
        logger.info(f"处理{operation}响应: 状态码={response.status_code}, Content-Type={response.headers.get('content-type')}")
        response.raise_for_status()
        
        # 尝试解析JSON
        try:
            data = response.json()
            logger.info(f"{operation}成功: {data}")
            return data
        except ValueError:
            # 如果响应不是JSON格式
            content = response.text[:200] + "..." if len(response.text) > 200 else response.text
            logger.error(f"{operation}响应不是JSON格式: {content}")
            raise HTTPException(
                status_code=500,
                detail=f"无法解析响应数据: {content}"
            )
            
    except httpx.HTTPStatusError as e:
        error_content = e.response.text[:200] + "..." if len(e.response.text) > 200 else e.response.text
        logger.error(f"{operation}失败: 状态码={e.response.status_code}, 内容={error_content}")
        
        # 尝试解析错误响应
        try:
            error_data = e.response.json()
            error_detail = error_data.get('detail', error_content)
        except ValueError:
            error_detail = error_content
            
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Auth service error: {error_detail}"
        )
    except Exception as e:
        logger.error(f"{operation}失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def get_current_user(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    client: httpx.AsyncClient = Depends(get_auth_service)
) -> User:
    """获取当前用户"""
    try:
        # 调用认证服务验证token
        service_response = await client.get(
            f"{settings.auth_service_url}/api/users/me/",
            headers={"Authorization": f"Bearer {token}"}
        )
        user_data = await handle_service_response(service_response, "Get current user")
        
        # 直接返回user对象
        return User(**user_data)
    except Exception as e:
        logger.error(f"获取当前用户失败: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="无法验证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register", response_model=User)
async def register(
    user: UserCreate = Body(...),
    client: httpx.AsyncClient = Depends(get_auth_service)
):
    """注册用户"""
    logger.info(f"Registering new user: {user.email}")
    try:
        response = await client.post(
            f"{settings.auth_service_url}/api/register",
            json=user.dict()
        )
        return await handle_service_response(response, "Register user")
    except Exception as e:
        logger.error(f"Failed to register user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    client: httpx.AsyncClient = Depends(get_auth_service)
):
    """用户登录"""
    logger.info(f"Logging in user: {form_data.username}")
    try:
        # 记录详细请求信息
        auth_url = f"{settings.auth_service_url}/api/token"
        logger.info(f"发送认证请求到: {auth_url}")
        
        # 发送登录请求到认证服务
        response = await client.post(
            auth_url,
            data={
                "username": form_data.username,
                "password": form_data.password
            }
        )
        
        # 记录响应状态
        logger.info(f"认证服务响应状态码: {response.status_code}")
        
        # 处理响应
        return await handle_service_response(response, "Login user")
    except Exception as e:
        logger.error(f"Failed to login user: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=User)
async def get_me(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return user

@router.put("/me", response_model=User)
async def update_me(
    request: Request,
    response: Response,
    user_update: UserUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_auth_service)
):
    """更新当前用户信息"""
    logger.info(f"Updating user: {current_user.email}")
    try:
        update_response = await client.put(
            f"{settings.auth_service_url}/me",
            json=user_update.dict(),
            headers={"Authorization": f"Bearer {current_user.token}"}
        )
        return await handle_service_response(update_response, "Update user")
    except Exception as e:
        logger.error(f"Failed to update user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout", response_model=ApiResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    client: httpx.AsyncClient = Depends(get_auth_service)
):
    """用户登出"""
    logger.info(f"Logging out user: {current_user.email}")
    try:
        logout_response = await client.post(
            f"{settings.auth_service_url}/logout",
            headers={"Authorization": f"Bearer {current_user.token}"}
        )
        return await handle_service_response(logout_response, "Logout user")
    except Exception as e:
        logger.error(f"Failed to logout user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset_password", response_model=ApiResponse)
async def reset_password(
    reset_data: dict = Body(...),
    client: httpx.AsyncClient = Depends(get_auth_service)
):
    """重置用户密码"""
    logger.info(f"Resetting password for user: {reset_data.get('username')}")
    try:
        # 记录详细请求信息
        auth_url = f"{settings.auth_service_url}/reset_password"
        logger.info(f"发送密码重置请求到: {auth_url}")
        
        # 发送重置密码请求到认证服务
        response = await client.post(
            auth_url,
            json=reset_data
        )
        
        # 记录响应状态
        logger.info(f"密码重置服务响应状态码: {response.status_code}")
        
        # 处理响应
        return await handle_service_response(response, "Reset password")
    except Exception as e:
        logger.error(f"Failed to reset password: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Password reset failed: {str(e)}"
        )

# 注册路由
app.include_router(router) 