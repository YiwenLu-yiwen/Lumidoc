from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import timedelta, datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.modules.auth.user_model import User, UserCreate
from src.modules.auth.auth_service import AuthService
from src.modules.auth.config.config import settings
import jwt
import logging
import os
import httpx
from src.shared.logger import initialize_logging, get_logger

# 配置日志
initialize_logging("auth_api")
logger = get_logger(__name__)

# 定义密码重置请求模型
class PasswordReset(BaseModel):
    username: str
    new_password: str

# 定义登录请求模型
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")

app = FastAPI(title="Auth Service")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化认证服务
auth_service = AuthService()

# OAuth2 密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

@app.on_event("startup")
async def startup_event():
    """服务启动时初始化数据库"""
    try:
        await auth_service._init_db_pool()
        logger.info("认证服务启动成功")
    except Exception as e:
        logger.error(f"认证服务启动失败: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时清理资源"""
    try:
        await auth_service.close()
        logger.info("认证服务已关闭")
    except Exception as e:
        logger.error(f"认证服务关闭时出错: {str(e)}")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """获取当前用户"""
    try:
        payload = jwt.decode(token, auth_service.public_key, algorithms=[settings.JWT_ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await auth_service.get_user(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except (jwt.exceptions.InvalidTokenError, jwt.exceptions.InvalidSubjectError, jwt.exceptions.PyJWTError) as e:
        # 记录具体的JWT错误类型
        logger.warning(f"JWT验证失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.post("/api/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录（OAuth2表单格式）"""
    logger.info(f"OAuth2 login attempt for user: {form_data.username}")
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Authentication failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 使用配置的过期时间（30分钟）
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info(f"为用户 {user.username} 创建令牌，有效期: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}分钟")
    access_token = auth_service.create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    # 返回完整用户信息
    logger.info(f"User {user.username} (ID: {user.id}) logged in successfully")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@app.post("/api/login")
async def login_json(login_data: LoginRequest):
    """用户登录（JSON格式）"""
    logger.info(f"JSON login attempt for user: {login_data.username}")
    user = await auth_service.authenticate_user(login_data.username, login_data.password)
    if not user:
        logger.warning(f"Authentication failed for user: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    # 使用配置的过期时间（30分钟）
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    logger.info(f"为用户 {user.username} 创建令牌，有效期: {settings.ACCESS_TOKEN_EXPIRE_MINUTES}分钟")
    access_token = auth_service.create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    # 返回完整用户信息
    logger.info(f"User {user.username} (ID: {user.id}) logged in successfully")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "nickname": user.nickname,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }

@app.post("/api/register", response_model=User)
async def create_user(user: UserCreate):
    """创建用户"""
    try:
        logger.info(f"注册请求: username={user.username}, email={user.email}, nickname={user.nickname or 'None'}")
        new_user = await auth_service.create_user(user)
        logger.info(f"用户注册成功: id={new_user.id}, username={new_user.username}")
        return new_user
    except ValueError as e:
        logger.warning(f"用户注册失败 (输入值错误): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        error_msg = f"创建用户失败: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户失败"
        )

@app.post("/api/reset_password")
async def reset_password(password_reset: PasswordReset):
    """重置用户密码"""
    try:
        if not password_reset.username or not password_reset.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名和新密码不能为空"
            )
            
        if password_reset.username == password_reset.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名和密码不能相同"
            )
            
        # 确保数据库连接池已初始化
        if auth_service.db_pool is None:
            await auth_service._init_db_pool()
            
        # 检查用户是否存在
        async with auth_service.db_pool.acquire() as conn:
            user = await conn.fetchrow('SELECT * FROM users WHERE username = $1', password_reset.username)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户不存在"
                )
                
            # 生成新的密码哈希
            hashed_password = auth_service.get_password_hash(password_reset.new_password)
            
            # 更新密码
            await conn.execute(
                'UPDATE users SET hashed_password = $1, updated_at = CURRENT_TIMESTAMP WHERE username = $2',
                hashed_password, password_reset.username
            )
            
        logger.info(f"用户 {password_reset.username} 的密码已重置")
        return {"message": "密码重置成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置密码失败: {str(e)}"
        )

@app.get("/api/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user

@app.get("/api/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """验证令牌有效性"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "username": current_user.username
    }

@app.post("/api/refresh")
async def refresh_token(current_user = Depends(get_current_user)):
    """刷新用户令牌"""
    logger.info(f"刷新用户令牌: {current_user.username} (ID: {current_user.id})")
    
    # 创建新令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": current_user.id}, 
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# 健康检查已在main.py中通过共享HealthChecker配置

async def ping_frontend():
    """检查前端服务是否可达"""
    try:
        async with httpx.AsyncClient() as client:
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
            response = await client.get(frontend_url, timeout=2.0)
            if response.status_code == 200:
                return True
    except Exception as e:
        logger.warning(f"无法连接到前端服务: {str(e)}")
    return False

async def ping_backend():
    """通过Gateway检查主后端服务是否可达"""
    try:
        async with httpx.AsyncClient() as client:
            # 严格遵循项目原则：所有服务间调用必须通过Gateway
            gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8888")
            response = await client.get(f"{gateway_url}/health", timeout=2.0)
            if response.status_code == 200:
                return True
    except Exception as e:
        logger.warning(f"无法连接到Gateway: {str(e)}")
    return False

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.auth_service_port) 