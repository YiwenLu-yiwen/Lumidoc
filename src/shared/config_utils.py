"""
统一的配置工具模块
处理服务URL和端口配置，确保所有微服务一致使用环境变量
"""

import os
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv
import logging
from typing import Optional, Tuple

# 配置日志
logger = logging.getLogger(__name__)

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

# 确保加载项目根目录的.env文件
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
    logger.debug(f"已从 {ENV_FILE} 加载环境变量")
else:
    logger.warning(f"未找到.env文件在 {ENV_FILE}")

# 服务默认端口映射
DEFAULT_PORTS = {
    "PROJECT": 8020,
    "CHAT": 8001,
    "QUESTION": 8002,
    "GRAPH": 8003, 
    "FILE": 8004,
    "FILEPROC": 8005,
    "RAG": 8006,
    "AUTH": 8007,
    "MONITORING": 8008,
    "LLM_SUMMARY": 8009,
    "LLM": 8080,
    "FRONTEND": 3000
}

def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

def get_port_from_url(url: Optional[str], default_port: int) -> int:
    """从URL中提取端口，如果提取失败则使用默认端口"""
    if not url:
        return default_port
    try:
        parsed = urlparse(ensure_url_protocol(url))
        return parsed.port or default_port
    except Exception as e:
        logger.warning(f"从URL提取端口失败({url}): {str(e)}，使用默认端口{default_port}")
        return default_port

def get_service_url_and_port(service_name: str) -> Tuple[str, int]:
    """
    获取服务URL和端口
    
    Args:
        service_name: 服务名称，如RAG、AUTH等
        
    Returns:
        Tuple[str, int]: 服务URL和端口
    """
    env_name = service_name.upper()
    url_env = f"{env_name}_SERVICE_URL"
    port_env = f"{env_name}_SERVICE_PORT"
    
    # 获取默认端口
    default_port = DEFAULT_PORTS.get(env_name, 8000)
    
    # 首先检查是否直接定义了端口
    port = int(os.getenv(port_env, "0"))
    
    # 获取服务URL
    service_host = os.getenv('SERVICE_HOST', 'localhost')
    url = os.getenv(url_env)
    
    # 如果URL未定义，使用SERVICE_HOST和端口构建
    if not url:
        # 如果端口未定义，使用默认端口
        if port <= 0:
            port = default_port
        url = f"http://{service_host}:{port}"
    else:
        # 从URL中提取端口（如果端口未直接定义）
        if port <= 0:
            port = get_port_from_url(url, default_port)
        
        # 确保URL有协议前缀
        url = ensure_url_protocol(url)
    
    logger.debug(f"服务{service_name}配置: URL={url}, PORT={port}")
    return url, port

def get_service_url(service_name: str) -> str:
    """获取服务URL"""
    url, _ = get_service_url_and_port(service_name)
    return url

def get_service_port(service_name: str) -> int:
    """获取服务端口"""
    _, port = get_service_url_and_port(service_name)
    return port

# 导出常用服务配置
RAG_SERVICE_URL, RAG_SERVICE_PORT = get_service_url_and_port("RAG") 
AUTH_SERVICE_URL, AUTH_SERVICE_PORT = get_service_url_and_port("AUTH")
FILE_SERVICE_URL, FILE_SERVICE_PORT = get_service_url_and_port("FILE")
PROJECT_SERVICE_URL, PROJECT_SERVICE_PORT = get_service_url_and_port("PROJECT")
CHAT_SERVICE_URL, CHAT_SERVICE_PORT = get_service_url_and_port("CHAT")
GRAPH_SERVICE_URL, GRAPH_SERVICE_PORT = get_service_url_and_port("GRAPH") 