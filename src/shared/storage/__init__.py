"""
共享存储模块
提供统一的文件存储接口和实现
"""

from .storage_interface import StorageInterface
from .local_storage import LocalStorage
from .s3_storage import S3Storage
from .storage_factory import get_storage

__all__ = [
    'StorageInterface',
    'LocalStorage',
    'S3Storage',
    'get_storage'
] 