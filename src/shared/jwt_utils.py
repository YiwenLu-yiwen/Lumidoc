#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
JWT工具函数
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv
import time
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException

# 加载环境变量
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# 配置日志
logger = logging.getLogger(__name__)

# 从环境变量获取JWT算法设置
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "RS256")
JWT_SECRET_KEY = os.environ.get("SECRET_KEY", "your-local-secret-key-here")  # 与.env保持一致的默认值
TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 默认24小时

# 令牌刷新阈值（剩余有效期小于此值时刷新令牌，单位：分钟）
TOKEN_REFRESH_THRESHOLD_MINUTES = int(os.environ.get("TOKEN_REFRESH_THRESHOLD_MINUTES", "10"))

# 项目根目录路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 当使用RS256算法时需要的公钥和私钥文件路径
# 优先使用环境变量中的绝对路径，否则使用相对于项目根目录的路径
PUBLIC_KEY_PATH = os.environ.get("JWT_PUBLIC_KEY_PATH", str(ROOT_DIR / "src/modules/auth/key/jwt_public_key.pem"))
PRIVATE_KEY_PATH = os.environ.get("JWT_PRIVATE_KEY_PATH", str(ROOT_DIR / "src/modules/auth/key/jwt_private_key.pem"))

# 缓存密钥
_public_key = None
_private_key = None

logger.info(f"JWT配置: 算法={JWT_ALGORITHM}, 过期时间={TOKEN_EXPIRE_MINUTES}分钟")
logger.info(f"JWT公钥路径: {PUBLIC_KEY_PATH}")
logger.info(f"JWT私钥路径: {PRIVATE_KEY_PATH}")

def get_public_key(force_reload=False):
    """
    获取公钥内容，用于验证JWT
    
    Args:
        force_reload: 是否强制重新加载密钥，忽略缓存
    """
    global _public_key
    
    # 如果已加载且不强制重新加载，直接返回缓存
    if _public_key is not None and not force_reload:
        return _public_key
        
    # 如果使用对称算法，直接返回密钥
    if JWT_ALGORITHM.startswith("HS"):
        return JWT_SECRET_KEY
    
    # 使用非对称算法，加载公钥文件
    try:
        # 严格使用环境变量中指定的路径
        key_path = Path(PUBLIC_KEY_PATH)
        
        if key_path.exists():
            with open(key_path, 'r') as f:
                key_content = f.read().strip()  # 移除空白字符
                
            # 验证公钥格式
            if not key_content.startswith("-----BEGIN PUBLIC KEY-----"):
                logger.error("公钥格式不正确，缺少BEGIN PUBLIC KEY标识")
                return None
                
            if not key_content.endswith("-----END PUBLIC KEY-----"):
                logger.error("公钥格式不正确，缺少END PUBLIC KEY标识")
                return None
                
            # 验证PEM格式
            try:
                from cryptography.hazmat.primitives.asymmetric import rsa
                from cryptography.hazmat.primitives import serialization
                
                # 尝试加载公钥
                public_key = serialization.load_pem_public_key(key_content.encode())
                if not isinstance(public_key, rsa.RSAPublicKey):
                    logger.error("公钥不是有效的RSA公钥")
                    return None
                    
                logger.info("公钥格式验证成功")
            except ImportError:
                # 如果cryptography库不可用，跳过此验证
                logger.warning("缺少cryptography库，跳过公钥格式验证")
            except Exception as e:
                logger.error(f"公钥格式验证失败: {str(e)}")
                # 即使验证失败也继续，可能PyJWT库仍能处理
            
            _public_key = key_content
            logger.info(f"已加载JWT公钥，路径: {key_path}")
            return _public_key
        
        # 如果指定路径不存在
        logger.error(f"找不到JWT公钥文件: {key_path}")
        return None
    except Exception as e:
        logger.error(f"加载JWT公钥失败: {str(e)}")
        return None

def get_private_key(force_reload=False):
    """
    获取私钥内容，用于编码JWT
    
    Args:
        force_reload: 是否强制重新加载密钥，忽略缓存
    """
    global _private_key
    
    # 如果已加载且不强制重新加载，直接返回缓存
    if _private_key is not None and not force_reload:
        return _private_key
        
    # 如果使用对称算法，直接返回密钥
    if JWT_ALGORITHM.startswith("HS"):
        return JWT_SECRET_KEY
    
    # 使用非对称算法，加载私钥文件
    try:
        # 严格使用环境变量中指定的路径
        key_path = Path(PRIVATE_KEY_PATH)
        
        if key_path.exists():
            with open(key_path, 'r') as f:
                key_content = f.read().strip()  # 移除空白字符
                
            # 验证私钥格式
            if not key_content.startswith("-----BEGIN PRIVATE KEY-----"):
                logger.error("私钥格式不正确，缺少BEGIN PRIVATE KEY标识")
                return None
                
            if not key_content.endswith("-----END PRIVATE KEY-----"):
                logger.error("私钥格式不正确，缺少END PRIVATE KEY标识")
                return None
                
            # 验证PEM格式
            try:
                from cryptography.hazmat.primitives.asymmetric import rsa
                from cryptography.hazmat.primitives import serialization
                
                # 尝试加载私钥
                private_key = serialization.load_pem_private_key(
                    key_content.encode(),
                    password=None
                )
                if not isinstance(private_key, rsa.RSAPrivateKey):
                    logger.error("私钥不是有效的RSA私钥")
                    return None
                    
                logger.info("私钥格式验证成功")
            except ImportError:
                # 如果cryptography库不可用，跳过此验证
                logger.warning("缺少cryptography库，跳过私钥格式验证")
            except Exception as e:
                logger.error(f"私钥格式验证失败: {str(e)}")
                # 即使验证失败也继续，可能PyJWT库仍能处理
            
            _private_key = key_content
            logger.info(f"已加载JWT私钥，路径: {key_path}")
            return _private_key
        
        # 如果指定路径不存在
        logger.error(f"找不到JWT私钥文件: {key_path}")
        return None
    except Exception as e:
        logger.error(f"加载JWT私钥失败: {str(e)}")
        return None

def create_jwt_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> Optional[str]:
    """
    创建JWT令牌
    
    Args:
        data: 要编码到令牌的数据
        expires_delta: 过期时间间隔，不提供则使用默认值
        
    Returns:
        str: JWT令牌字符串，失败则返回None
    """
    to_encode = data.copy()
    
    # 设置过期时间
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
        
    to_encode["exp"] = expire
    
    # 确保sub字段为字符串类型
    if "sub" in to_encode and to_encode["sub"] is not None:
        to_encode["sub"] = str(to_encode["sub"])
    
    # 获取签名密钥（强制重新加载确保最新）
    key = get_private_key(force_reload=True)
    if not key:
        logger.error("无法获取JWT签名密钥")
        return None
    
    try:
        # 记录更多调试信息
        logger.info(f"使用 {JWT_ALGORITHM} 算法创建令牌")
        logger.debug(f"令牌数据: {to_encode}")
        
        # 执行JWT编码
        encoded = jwt.encode(to_encode, key, algorithm=JWT_ALGORITHM)
        if isinstance(encoded, bytes):
            encoded_str = encoded.decode('utf-8')
        else:
            encoded_str = encoded
            
        # 验证生成的令牌格式
        parts = encoded_str.split('.')
        if len(parts) != 3:
            logger.error(f"生成的令牌格式不正确，期望3部分但得到{len(parts)}部分")
            return None
            
        logger.info(f"成功生成令牌: {encoded_str[:20]}... (已截断)")
        return encoded_str
    except Exception as e:
        logger.error(f"JWT编码失败: {str(e)}")
        return None

def decode_token(token: str, verify: bool = True) -> dict:
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌
        verify: 是否验证签名
        
    Returns:
        dict: 解码后的令牌内容
    """
    try:
        # 获取公钥
        public_key = get_public_key()
        
        # 解码令牌
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[JWT_ALGORITHM],
            options={"verify_signature": verify}
        )
        
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("令牌已过期")
        raise HTTPException(status_code=401, detail="令牌已过期")
    except jwt.InvalidTokenError as e:
        logger.warning(f"无效的令牌: {str(e)}")
        raise HTTPException(status_code=401, detail="无效的令牌")

# 添加别名，保持兼容性
decode_jwt_token = decode_token

def is_token_expiring_soon(token: str, threshold_minutes: Optional[int] = None) -> bool:
    """
    检查令牌是否即将过期
    
    Args:
        token: JWT令牌
        threshold_minutes: 过期阈值（分钟），小于此时间时返回True，默认为TOKEN_REFRESH_THRESHOLD_MINUTES
        
    Returns:
        bool: 如果令牌即将过期返回True，否则返回False
    """
    if threshold_minutes is None:
        threshold_minutes = TOKEN_REFRESH_THRESHOLD_MINUTES
        
    try:
        # 解码令牌但不验证签名，只读取过期时间
        payload = jwt.decode(token, options={"verify_signature": False})
        
        # 获取过期时间
        expiry = datetime.fromtimestamp(payload["exp"])
        
        # 计算剩余时间
        remaining = expiry - datetime.utcnow()
        
        # 如果剩余时间小于阈值，返回True
        return remaining.total_seconds() < threshold_minutes * 60
    except Exception as e:
        logger.warning(f"检查令牌过期时出错: {str(e)}")
        # 解码失败，可能令牌已过期，返回True以便刷新
        return True

def verify_key_pair():
    """验证公钥和私钥是否匹配"""
    if not JWT_ALGORITHM.startswith("RS"):
        # 非RSA算法不需要验证密钥对
        logger.info(f"当前算法 {JWT_ALGORITHM} 不需要验证密钥对")
        return True
        
    try:
        # 加载密钥
        private_key = get_private_key(force_reload=True)
        public_key = get_public_key(force_reload=True)
        
        if not private_key or not public_key:
            logger.error("无法加载公钥或私钥")
            return False
            
        # 创建测试数据并签名
        test_data = {"test": "data", "time": datetime.utcnow().isoformat()}
        
        # 使用私钥签名
        try:
            token = jwt.encode(test_data, private_key, algorithm=JWT_ALGORITHM)
            if isinstance(token, bytes):
                token = token.decode('utf-8')
                
            # 使用公钥验证
            decoded = jwt.decode(token, public_key, algorithms=[JWT_ALGORITHM])
            
            if decoded and "test" in decoded and decoded["test"] == "data":
                logger.info("公钥和私钥匹配验证成功")
                return True
            else:
                logger.error("公钥和私钥不匹配，令牌解码失败")
                return False
        except Exception as e:
            logger.error(f"密钥对验证失败: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"验证密钥对时出错: {str(e)}")
        return False

# 在模块加载时验证密钥对
try:
    # 记录JWT配置信息
    logger.info(f"JWT配置: 算法={JWT_ALGORITHM}, 过期时间={TOKEN_EXPIRE_MINUTES}分钟")
    logger.info(f"JWT公钥路径: {PUBLIC_KEY_PATH}")
    logger.info(f"JWT私钥路径: {PRIVATE_KEY_PATH}")
    
    # 只在使用RS256等非对称算法时执行验证
    if JWT_ALGORITHM.startswith("RS"):
        key_pair_valid = verify_key_pair()
        if not key_pair_valid:
            logger.error("公钥和私钥不匹配，JWT验证可能会失败")
            # 不终止程序，但发出警告
except Exception as e:
    logger.error(f"初始化JWT工具时出错: {str(e)}")

def refresh_token(user_id: str) -> str:
    """
    刷新用户的JWT令牌
    
    参数:
        user_id: 用户ID
        
    返回:
        新的JWT令牌
    """
    # 创建新的令牌负载
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + 3600 * 24  # 24小时后过期
    }
    
    # 使用私钥签名
    token = jwt.encode(payload, PRIVATE_KEY, algorithm=JWT_ALGORITHM)
    logger.info(f"已为用户 {user_id} 刷新令牌")
    
    return token 