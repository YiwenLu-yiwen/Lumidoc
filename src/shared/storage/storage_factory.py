"""
存储工厂，根据配置选择存储实现
"""

import os
import logging
from typing import Optional

from .storage_interface import StorageInterface
from .local_storage import LocalStorage
from .s3_storage import S3Storage

logger = logging.getLogger(__name__)

# 存储实例缓存，避免重复创建相同配置的存储实例
_storage_cache = {}


def get_storage_base_path(storage_type: str, directory_type: str) -> str:
    """Return a backend-specific path without leaking local container paths to S3."""
    if storage_type == "s3":
        default_prefixes = {
            "upload": "uploads",
            "content": "content",
            "rag": "rag",
            "models": "models",
        }
        default_prefix = default_prefixes.get(directory_type, "uploads")
        return os.getenv(
            f"S3_{directory_type.upper()}_PREFIX", default_prefix
        ).strip("/")

    default_path = f"./{directory_type if directory_type != 'upload' else 'uploads'}"
    return os.getenv(f"{directory_type.upper()}_DIR", default_path)

async def get_storage(storage_type: Optional[str] = None, directory_type: str = "upload") -> StorageInterface:
    """
    根据配置选择并创建存储实现
    
    Args:
        storage_type: 存储类型，可选值: 'local', 's3'。如果为None，则从环境变量获取
        directory_type: 目录类型，用于确定存储路径前缀: upload, content, rag, models
        
    Returns:
        StorageInterface: 存储实现实例
    """
    if storage_type is None:
        storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
    else:
        storage_type = storage_type.lower()
    
    # 本地目录和对象存储前缀是两种不同的命名空间。容器绝对路径
    # （例如 /app/uploads）绝不能成为 S3 对象键的一部分。
    base_path = get_storage_base_path(storage_type, directory_type)
    
    # 创建缓存键
    cache_key = f"{storage_type}:{directory_type}:{base_path}"
    
    # 检查缓存中是否已有相同配置的存储实例
    if cache_key in _storage_cache:
        logger.debug(f"使用缓存的存储实例: 类型={storage_type}, 目录类型={directory_type}, 路径={base_path}")
        return _storage_cache[cache_key]
    
    logger.info(f"初始化存储: 类型={storage_type}, 目录类型={directory_type}, 路径={base_path}")
    
    if storage_type == 'local':
        # 本地存储
        full_path = base_path
        logger.info(f"使用本地存储，路径: {full_path}")
        storage = LocalStorage(base_dir=full_path)
        _storage_cache[cache_key] = storage  # 缓存实例
        return storage
    
    elif storage_type == 's3':
        # S3/MinIO存储
        endpoint_url = os.getenv('S3_ENDPOINT', 'http://localhost:9000')
        access_key = os.getenv('S3_ACCESS_KEY', '')
        secret_key = os.getenv('S3_SECRET_KEY', '')
        if not access_key or not secret_key:
            raise ValueError("S3_ACCESS_KEY and S3_SECRET_KEY are required")
        bucket_name = os.getenv('S3_BUCKET', 'data')
        region_name = os.getenv('S3_REGION', 'us-east-1')
        
        logger.info(f"使用S3存储，端点: {endpoint_url}, 存储桶: {bucket_name}, 前缀: {base_path}")
        
        storage = S3Storage(
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket_name,
            region_name=region_name,
            base_prefix=base_path
        )
        _storage_cache[cache_key] = storage  # 缓存实例
        return storage
    
    else:
        # 不支持的存储类型，使用本地存储作为默认值
        logger.warning(f"不支持的存储类型: {storage_type}，将使用本地存储作为替代")
        full_path = get_storage_base_path("local", directory_type)
        storage = LocalStorage(base_dir=full_path)
        _storage_cache[cache_key] = storage  # 缓存实例
        return storage


def clear_storage_cache():
    """
    清理存储实例缓存
    主要用于测试或需要强制重新初始化存储的场景
    """
    global _storage_cache
    _storage_cache.clear()
    logger.info("存储实例缓存已清理")
