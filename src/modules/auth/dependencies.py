from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import jwt
from datetime import timedelta
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from src.database import get_db
from .models.user import User
from .config.config import settings
from pathlib import Path
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from src.shared.time_utils import utc_now
# 导入统一JWT工具
from src.shared.jwt_utils import (
    JWT_ALGORITHM,
    create_jwt_token,
    decode_token as decode_jwt_token,
    get_public_key as get_jwt_public_key,
    is_token_expiring_soon,
)

# 配置日志
logger = logging.getLogger(__name__)

logger.info(f"JWT算法设置为: {JWT_ALGORITHM}")

def verify_and_fix_pem_key(key_content):
    """验证PEM格式公钥并尝试修复常见问题"""
    if not key_content:
        return None
        
    # 检查PEM头部和尾部
    if not key_content.strip().startswith('-----BEGIN'):
        logger.error("公钥缺少PEM头部")
        return None
        
    if not key_content.strip().endswith('-----'):
        logger.error("公钥缺少PEM尾部")
        return None
    
    # 尝试解析公钥
    try:
        public_key_obj = serialization.load_pem_public_key(
            key_content.encode('utf-8'),
            backend=default_backend()
        )
        
        # 重新序列化公钥为PEM格式，确保格式正确
        pem_key = public_key_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        logger.info("成功验证并格式化公钥")
        return pem_key
    except Exception as e:
        logger.error(f"验证公钥时出错: {str(e)}")
        return key_content  # 返回原始内容，让后续代码尝试处理

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent
# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent.parent

try:
    PUBLIC_KEY = get_jwt_public_key(force_reload=True)
    if JWT_ALGORITHM.startswith("RS"):
        public_key_path = Path(settings.jwt_public_key_path)
        if not PUBLIC_KEY and public_key_path.exists():
            PUBLIC_KEY = public_key_path.read_text(encoding="utf-8").strip()
        PUBLIC_KEY = verify_and_fix_pem_key(PUBLIC_KEY)
    if not PUBLIC_KEY:
        raise RuntimeError("JWT验证密钥未配置")
except Exception as e:
    logger.error(f"Error loading JWT public key: {str(e)}")
    PUBLIC_KEY = None

# 注意：tokenUrl应该与API路径匹配
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# 令牌过期时间常量（分钟）
TOKEN_EXPIRE_MINUTES = 30
# 令牌刷新阈值（剩余有效期小于此值时刷新令牌，单位：分钟）
TOKEN_REFRESH_THRESHOLD_MINUTES = 5

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    token = create_jwt_token(data, expires_delta)
    if token:
        return token
        
    # 如果使用统一工具创建失败，使用旧的方式作为备份
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        # 设置令牌有效期为30分钟
        expire = utc_now() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # 注意：这里只用于兼容老代码，实际应由认证服务签发
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """解码JWT令牌
    
    确保与认证服务的JWT解码方式兼容，包括正确处理sub字段
    """
    # 使用统一JWT工具解码，仅使用环境变量中配置的算法
    payload = decode_jwt_token(token)
    if payload:
        return payload
    
    # 如果解码失败，抛出异常
    raise ValueError("JWT令牌验证失败")

def should_refresh_token(token: str) -> bool:
    """检查令牌是否需要刷新
    
    当令牌剩余有效期小于阈值时返回True
    """
    return is_token_expiring_soon(token, TOKEN_REFRESH_THRESHOLD_MINUTES)

def refresh_token(user_id: str) -> str:
    """刷新用户令牌"""
    new_token = create_access_token({"sub": user_id})
    logger.info(f"已为用户 {user_id} 刷新令牌")
    return new_token

async def get_current_user(
    request: Request = None,
    response: Response = None,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    验证并返回当前登录用户
    """
    # 如果未提供token，返回401错误
    if not token:
        logger.warning("未提供令牌")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # 验证token
        payload = decode_token(token)
        
        # 确保sub字段为字符串类型
        if "sub" not in payload or not payload.get("sub"):
            logger.error("令牌缺少用户ID(sub)字段")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌: 缺少用户ID信息",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 确保sub是字符串
        user_id = str(payload["sub"])
        logger.debug(f"从token中获取到用户ID: {user_id}")
        
        # 检查是否需要刷新令牌
        if request and response and should_refresh_token(token):
            new_token = refresh_token(user_id)
            if new_token:
                # 设置新令牌到Cookie
                response.set_cookie(
                    key="access_token",
                    value=f"Bearer {new_token}",
                    httponly=True,
                    max_age=TOKEN_EXPIRE_MINUTES * 60,
                    path="/",
                    samesite="lax",
                    secure=True  # 总是使用安全Cookie
                )
                logger.info(f"已为用户 {user_id} 设置新令牌到Cookie")
    except ValueError as e:
        logger.error(f"验证token时发生错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的认证令牌: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ExpiredSignatureError:
        logger.error("令牌已过期")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        logger.error(f"验证JWT时出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"无效的JWT令牌: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"验证token时发生错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
