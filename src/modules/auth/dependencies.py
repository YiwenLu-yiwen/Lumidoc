from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import jwt
from datetime import datetime, timedelta
from typing import Optional, Any, Dict, Tuple
from sqlalchemy.orm import Session
from src.database import get_db
from .models.user import User
from .config.config import settings
from pathlib import Path
import os
import logging
import json
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pydantic import ValidationError
# 导入统一JWT工具
from src.shared.jwt_utils import decode_token, get_public_key, is_token_expiring_soon, create_jwt_token, JWT_ALGORITHM, refresh_token

# 配置日志
logger = logging.getLogger(__name__)

# 判断是否为开发环境
IS_DEVELOPMENT = False
# 是否跳过令牌验证
SKIP_TOKEN_VERIFICATION = os.getenv("SKIP_TOKEN_VERIFICATION", "false").lower() in ("true", "1", "t")
# 开发用户ID
DEVELOPMENT_USER_ID = None

logger.info(f"SKIP_TOKEN_VERIFICATION设置为: {SKIP_TOKEN_VERIFICATION}")
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

# 从jwt_utils直接导入公钥获取函数，确保使用相同的密钥
from src.shared.jwt_utils import get_public_key as get_jwt_public_key

# 读取公钥内容 - 使用与jwt_utils.py完全相同的路径
PUBLIC_KEY_PATH = ROOT_DIR / 'src' / 'modules' / 'auth' / 'key' / 'jwt_public_key.pem'
if not PUBLIC_KEY_PATH.exists():
    raise FileNotFoundError(f"JWT public key file not found at: {PUBLIC_KEY_PATH}")

try:
    # 使用jwt_utils中的函数获取公钥，确保一致性
    PUBLIC_KEY = get_jwt_public_key(force_reload=True)
    if not PUBLIC_KEY:
        # 如果获取失败，尝试直接读取
        with open(PUBLIC_KEY_PATH, 'r') as f:
            PUBLIC_KEY = f.read().strip()
        logger.info(f"直接从文件加载JWT公钥: {PUBLIC_KEY_PATH}")
    else:
        logger.info(f"使用jwt_utils加载JWT公钥: {PUBLIC_KEY_PATH}")
    
    # 验证并修复PEM格式公钥
    PUBLIC_KEY = verify_and_fix_pem_key(PUBLIC_KEY)
    if PUBLIC_KEY:
        logger.info("JWT公钥已验证并格式化")
    else:
        logger.error("JWT公钥格式无效，无法修复")
        # 尝试备用解决方案
        with open(PUBLIC_KEY_PATH, 'r') as f:
            PUBLIC_KEY = f.read().strip()
        logger.warning("已尝试使用原始公钥内容作为备用")
    
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
        expire = datetime.utcnow() + expires_delta
    else:
        # 设置令牌有效期为30分钟
        expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # 注意：这里只用于兼容老代码，实际应由认证服务签发
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """解码JWT令牌
    
    确保与认证服务的JWT解码方式兼容，包括正确处理sub字段
    """
    logger.debug("尝试解码token")
    
    # 使用统一JWT工具解码，仅使用环境变量中配置的算法
    payload = decode_token(token)
    if payload:
        logger.debug(f"成功解码令牌，payload: {payload}")
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
    # 开发环境下允许使用简化令牌机制
    if os.environ.get("ENVIRONMENT", "development").lower() in ("development", "local"):
        # 允许使用有效的Bearer令牌，无需严格验证
        if token and len(token) > 10:
            try:
                # 尝试简单解码,不验证签名
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub", "1")  # 默认使用ID=1
                
                # 查询或创建开发用户
                dev_user = db.query(User).filter(User.id == int(user_id)).first()
                if not dev_user:
                    dev_user = User(
                        id=1,
                        username="dev_user",
                        email="dev@example.com",
                        is_active=True,
                        is_superuser=True
                    )
                
                dev_user.token = token
                logger.info(f"开发环境简化验证成功: 用户ID={user_id}")
                return dev_user
            except Exception as e:
                logger.warning(f"开发环境令牌解析失败: {str(e)}")
        
    # 如果配置了跳过令牌验证，使用默认用户
    if SKIP_TOKEN_VERIFICATION:
        logger.warning("已启用跳过令牌验证，使用默认用户")
        # 使用ID=1的用户作为默认用户
        default_user = db.query(User).filter(User.id == 1).first()
        if default_user:
            return default_user
        else:
            logger.warning("找不到默认用户，尝试创建一个")
            try:
                # 创建一个默认用户
                from .models.user import User as UserModel
                default_user = UserModel(
                    id=1,
                    username="admin",
                    email="admin@example.com",
                    hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 'password'
                    nickname="Admin",
                    is_active=True,
                    is_superuser=True
                )
                db.add(default_user)
                db.commit()
                db.refresh(default_user)
                logger.info("已创建默认管理员用户")
                return default_user
            except Exception as e:
                logger.error(f"创建默认用户失败: {str(e)}")
                # 创建失败，继续常规验证流程
    
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