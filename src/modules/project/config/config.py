"""
项目服务配置
使用统一配置系统
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from src.shared.config import ProjectServiceSettings, get_env

# 创建全局设置实例
settings_base = ProjectServiceSettings()

class ExtendedProjectSettings:
    """项目服务扩展配置，保持向后兼容性"""
    
    # 添加版本信息
    version: str = get_env('PROJECT_SERVICE_VERSION', '1.0.0')
    
    # 数据库配置
    POSTGRES_HOST: str = get_env('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT: int = get_env('POSTGRES_PORT', 5432, env_type=int)
    POSTGRES_USER: str = get_env('POSTGRES_USER', 'stpuser')
    POSTGRES_PASSWORD: str = get_env('POSTGRES_PASSWORD', 'stppassword')
    POSTGRES_DB: str = get_env('POSTGRES_DB', 'stpdb')
    
    # 项目配置
    PROJECT_STORAGE_PATH: str = get_env('PROJECT_STORAGE_PATH', 'storage/projects')
    MAX_PROJECT_SIZE: int = get_env('MAX_PROJECT_SIZE', 1000000000, env_type=int)  # 1GB
    ALLOWED_FILE_TYPES: list = get_env('ALLOWED_FILE_TYPES', '.txt,.md,.py,.js,.html,.css,.json').split(',')
    
    # 缓存配置
    CACHE_TTL: int = get_env('CACHE_TTL', 3600, env_type=int)  # 1小时
    
    # 服务URL配置
    graph_service_url: str = get_env('GRAPH_SERVICE_URL', 'http://localhost:8003')
    chat_service_url: str = get_env('CHAT_SERVICE_URL', 'http://localhost:8001')
    file_service_url: str = get_env('FILE_SERVICE_URL', 'http://localhost:8004')
    question_service_url: str = get_env('QUESTION_SERVICE_URL', 'http://localhost:8002')
    rag_service_url: str = get_env('RAG_SERVICE_URL', 'http://localhost:8006')
    
    # 服务主机和端口
    service_host: str = get_env('SERVICE_HOST', '0.0.0.0')
    service_port: int = settings_base.port

# 创建配置实例
settings = ExtendedProjectSettings() 