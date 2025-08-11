"""
统一的日志记录模块，为所有微服务提供统一的日志配置
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Union
import datetime

# 日志目录
LOG_DIR = Path("logs")

# 日志级别映射
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# 格式化器
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SERVICE_LOG_FORMAT = "%(asctime)s - %(name)s - [%(service)s] - %(levelname)s - %(message)s"
DETAILED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"


def initialize_logging(service_name: str) -> None:
    """初始化根日志配置"""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    level = LOG_LEVELS.get(log_level, logging.INFO)

    # 确保日志目录存在
    LOG_DIR.mkdir(exist_ok=True)
    
    # 处理日志文件路径
    log_file = os.environ.get("LOG_FILE")
    if log_file:
        # 如果环境变量中的路径已经包含logs，则直接使用
        if log_file.startswith("logs/"):
            file_path = Path(log_file)
        # 否则检查是否为绝对路径
        elif Path(log_file).is_absolute():
            file_path = Path(log_file)
        else:
            # 相对路径，添加到日志目录
            file_path = LOG_DIR / log_file
    else:
        # 默认日志文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        file_path = LOG_DIR / f"{service_name}_{timestamp}.log"

    # 创建服务专用的日志文件
    service_file_path = LOG_DIR / f"{service_name}.log"

    # 定义服务上下文过滤器
    class ServiceContextFilter(logging.Filter):
        def __init__(self, service_name):
            super().__init__()
            self.service_name = service_name
            
        def filter(self, record):
            record.service = self.service_name
            return True

    # 添加服务上下文
    service_filter = ServiceContextFilter(service_name)
    
    # 配置根日志
    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(file_path, encoding="utf-8"),
        ],
    )
    
    # 创建服务专用日志处理器
    service_handler = logging.FileHandler(service_file_path, encoding="utf-8")
    service_handler.setFormatter(logging.Formatter(SERVICE_LOG_FORMAT))
    service_handler.addFilter(service_filter)
    
    # 将服务处理器添加到根日志
    root_logger.addHandler(service_handler)
    
    # 设置标准库日志级别，减少噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

def setup_logger(
    name: str,
    service_name: str = None,
    log_level: str = "info",
    log_to_console: bool = True,
    log_to_file: bool = True,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_file: Optional[str] = None,
    overwrite: bool = False
) -> logging.Logger:
    """
    配置并返回一个命名日志记录器
    
    Args:
        name: 日志记录器名称
        service_name: 服务名称，默认使用日志记录器名称
        log_level: 日志级别 (debug, info, warning, error, critical)
        log_to_console: 是否输出到控制台
        log_to_file: 是否输出到文件
        log_format: 日志格式
        log_file: 日志文件名，如果为None则自动生成
        overwrite: 是否覆盖已存在的日志记录器配置
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    # 确保服务名称存在
    if not service_name:
        service_name = name.split('.')[-1] if '.' in name else name

    # 先确保根日志配置已初始化
    initialize_logging(service_name)

    # 获取日志级别
    level = LOG_LEVELS.get(log_level.lower(), logging.INFO)

    # 获取或创建日志记录器
    logger = logging.getLogger(name)

    # 如果日志记录器已配置且不需要覆盖，直接返回
    if logger.handlers and not overwrite:
        return logger
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 设置日志级别
    logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(log_format)
    
    # 创建服务上下文过滤器
    class ServiceContextFilter(logging.Filter):
        def __init__(self, service_name):
            super().__init__()
            self.service_name = service_name
            
        def filter(self, record):
            record.service = service_name
            return True
    
    # 添加服务上下文过滤器
    service_filter = ServiceContextFilter(service_name)
    logger.addFilter(service_filter)
    
    # 添加控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 添加文件处理器
    if log_to_file:
        # 确保日志目录存在
        LOG_DIR.mkdir(exist_ok=True)
        
        # 生成日志文件名
        if log_file is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d")
            log_file = f"{service_name}_{timestamp}.log"
        
        # 确保路径不会重复logs
        log_path = LOG_DIR / log_file if not log_file.startswith("logs/") else Path(log_file)
        
        # 创建两个文件处理器: 一个是通用日志，一个是服务专用日志
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 服务专用日志
        service_log_file = f"{service_name}.log"
        service_log_path = LOG_DIR / service_log_file
        service_handler = logging.FileHandler(service_log_path, encoding='utf-8')
        service_handler.setFormatter(logging.Formatter(SERVICE_LOG_FORMAT))
        logger.addHandler(service_handler)
    
    # 设置为非传播，避免日志重复
    logger.propagate = False
    
    return logger

def get_logger(name: str, service_name: str = None) -> logging.Logger:
    """
    获取一个已配置的日志记录器，如果不存在则创建一个新的
    
    Args:
        name: 日志记录器名称
        service_name: 服务名称，默认从name中提取
        
    Returns:
        logging.Logger: 日志记录器
    """
    # 尝试从名称中提取服务名
    if not service_name and '.' in name:
        parts = name.split('.')
        if len(parts) >= 3 and parts[0] == 'src' and parts[1] == 'modules':
            service_name = parts[2]
        else:
            service_name = parts[-1]
    elif not service_name:
        service_name = name
        
    logger = logging.getLogger(name)

    # 如果日志记录器尚未配置，使用setup_logger配置
    if not logger.handlers:
        logger = setup_logger(name, service_name=service_name)

    return logger
