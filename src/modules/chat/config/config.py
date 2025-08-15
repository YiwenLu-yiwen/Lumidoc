"""
聊天服务配置模块
使用统一配置系统
"""

import os
from typing import Optional, Dict, Any, List
from src.shared.config import ChatServiceSettings, get_env

# 创建全局设置实例
settings_base = ChatServiceSettings()

class ExtendedChatSettings:
    """扩展聊天服务配置，保持向后兼容性"""
    
    # 服务配置
    service_host: str = "0.0.0.0"
    service_port: int = settings_base.port
    
    # Redis配置
    redis_host: str = get_env("REDIS_HOST", "localhost")
    redis_port: int = get_env("REDIS_PORT", 6379, env_type=int)
    redis_db: int = get_env("REDIS_DB", 0, env_type=int)
    redis_password: str = get_env("REDIS_PASSWORD", "")
    
    # PostgreSQL配置
    postgres_host: str = get_env("POSTGRES_HOST", "localhost")
    postgres_port: int = get_env("POSTGRES_PORT", 5432, env_type=int)
    postgres_user: str = get_env("POSTGRES_USER", "postgres")
    postgres_password: str = get_env("POSTGRES_PASSWORD", "postgres")
    postgres_db: str = get_env("POSTGRES_DB", "stpdb")
    
    # 构建PostgreSQL连接URL
    @property
    def postgres_url(self) -> str:
        """获取PostgreSQL连接URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    # 消息缓存配置
    message_ttl: int = 60 * 60 * 24 * 30  # 默认30天过期时间（秒）
    
    # 自动迁移配置
    auto_migrate_days: int = 30  # 默认30天前的消息自动迁移
    migrate_interval_hours: int = 24  # 默认每24小时执行一次迁移
    
    # 从统一配置获取的聊天特定配置
    max_history_messages: int = settings_base.max_history_messages
    session_timeout: int = settings_base.session_timeout
    storage_mode: str = settings_base.storage_mode

# 创建配置实例
settings = ExtendedChatSettings() 