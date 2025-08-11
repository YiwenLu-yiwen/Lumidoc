"""
服务配置工具
提供统一的服务URL、主机和端口管理
"""

import os
import logging
from typing import Dict, Optional
from urllib.parse import urlparse
from .config_loader import get_env

# 定义日志记录器
logger = logging.getLogger(__name__)

# 服务名称到环境变量名称的映射
SERVICE_ENV_MAPPING: Dict[str, Dict[str, str]] = {
    # LLM工具服务
    "llm": {
        "host": "LLM_HOST",
        "port": "LLM_PORT",
        "url": "LLM_URL"
    },
    # 文件服务
    "file": {
        "host": "FILE_SERVICE_HOST",
        "port": "FILE_SERVICE_PORT",
        "url": "FILE_SERVICE_URL"
    },
    # 聊天服务
    "chat": {
        "host": "CHAT_SERVICE_HOST",
        "port": "CHAT_SERVICE_PORT",
        "url": "CHAT_SERVICE_URL"
    },
    # RAG服务
    "rag": {
        "host": "RAG_SERVICE_HOST",
        "port": "RAG_SERVICE_PORT",
        "url": "RAG_SERVICE_URL"
    },
    # LightRAG服务
    "lightrag": {
        "host": "LIGHTRAG_HOST",
        "port": "LIGHTRAG_PORT",
        "url": "LIGHTRAG_URL"
    },
    # 图谱服务
    "graph": {
        "host": "GRAPH_SERVICE_HOST",
        "port": "GRAPH_SERVICE_PORT",
        "url": "GRAPH_SERVICE_URL"
    },
    # 摘要服务
    "summary": {
        "host": "SUMMARY_SERVICE_HOST",
        "port": "SUMMARY_SERVICE_PORT",
        "url": "SUMMARY_SERVICE_URL"
    },
    # 项目服务
    "project": {
        "host": "PROJECT_SERVICE_HOST",
        "port": "PROJECT_SERVICE_PORT",
        "url": "PROJECT_SERVICE_URL"
    },
    # 问题服务
    "question": {
        "host": "QUESTION_SERVICE_HOST",
        "port": "QUESTION_SERVICE_PORT",
        "url": "QUESTION_SERVICE_URL"
    },
    # 认证服务
    "auth": {
        "host": "AUTH_SERVICE_HOST",
        "port": "AUTH_SERVICE_PORT",
        "url": "AUTH_SERVICE_URL"
    },
    # 监控服务
    "monitoring": {
        "host": "MONITORING_SERVICE_HOST",
        "port": "MONITORING_SERVICE_PORT",
        "url": "MONITORING_SERVICE_URL"
    },
    # 文件处理服务
    "fileproc": {
        "host": "FILEPROC_SERVICE_HOST",
        "port": "FILEPROC_SERVICE_PORT",
        "url": "FILEPROC_SERVICE_URL"
    }
}

# 默认主机和端口
DEFAULT_HOST = "localhost"
DEFAULT_PORTS = {
    "llm": 8080,
    "file": 8004,
    "fileproc": 8005,
    "chat": 8001,
    "rag": 8006,
    "lightrag": 8006,
    "graph": 8003,
    "summary": 8009,
    "llm_summary": 8009,
    "question": 8002,
    "auth": 8007,
    "monitoring": 8008,
    "project": 8020
}


def get_service_url(service_name: str) -> str:
    """
    获取服务的完整URL
    
    Args:
        service_name: 服务名称
        
    Returns:
        服务URL字符串
    """
    service_name = service_name.lower()
    
    # 检查服务名称是否有效
    if service_name not in SERVICE_ENV_MAPPING:
        logger.warning(f"未知的服务名称: {service_name}，使用原始名称")
    
    env_names = SERVICE_ENV_MAPPING.get(service_name, {
        "url": f"{service_name.upper()}_URL",
        "host": f"{service_name.upper()}_HOST",
        "port": f"{service_name.upper()}_PORT"
    })
    
    # 首先尝试直接获取URL
    url = get_env(env_names.get("url", ""))
    if url:
        # 确保URL包含协议
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        return url
    
    # 否则从主机和端口构建
    host = get_service_host(service_name)
    port = get_service_port(service_name)
    
    return f"http://{host}:{port}"


def get_service_host(service_name: str) -> str:
    """
    获取服务主机地址
    
    Args:
        service_name: 服务名称
        
    Returns:
        服务主机地址
    """
    service_name = service_name.lower()
    
    # 获取环境变量名
    env_names = SERVICE_ENV_MAPPING.get(service_name, {
        "host": f"{service_name.upper()}_HOST"
    })
    
    # 尝试从环境变量获取
    host_env_name = env_names.get("host", "")
    host = get_env(host_env_name, DEFAULT_HOST)
    
    # 如果有URL，尝试从URL解析主机
    url_env_name = env_names.get("url", "")
    url = get_env(url_env_name)
    if url and not host:
        try:
            parsed_url = urlparse(url)
            if parsed_url.netloc:
                host_part = parsed_url.netloc.split(':')[0]
                if host_part:
                    return host_part
        except Exception:
            pass
    
    return host


def get_service_port(service_name: str) -> int:
    """
    获取服务端口
    
    Args:
        service_name: 服务名称
        
    Returns:
        服务端口号
    """
    service_name = service_name.lower()
    
    # 获取默认端口
    default_port = DEFAULT_PORTS.get(service_name, 8000)
    
    # 获取环境变量名
    env_names = SERVICE_ENV_MAPPING.get(service_name, {
        "port": f"{service_name.upper()}_PORT"
    })
    
    # 尝试从环境变量获取
    port_env_name = env_names.get("port", "")
    port = get_env(port_env_name, default_port, env_type=int)
    
    # 如果有URL，尝试从URL解析端口
    url_env_name = env_names.get("url", "")
    url = get_env(url_env_name)
    if url and not port:
        try:
            parsed_url = urlparse(url)
            if parsed_url.port:
                return parsed_url.port
        except Exception:
            pass
    
    return port 

# 创建服务配置对象，包含所有服务配置函数
service_config = {
    "get_service_url": get_service_url,
    "get_service_host": get_service_host,
    "get_service_port": get_service_port,
    "SERVICE_ENV_MAPPING": SERVICE_ENV_MAPPING,
    "DEFAULT_HOST": DEFAULT_HOST,
    "DEFAULT_PORTS": DEFAULT_PORTS
} 