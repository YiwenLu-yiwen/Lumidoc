#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
服务配置基类
为所有微服务提供统一的配置管理
遵循STP微服务架构原则，支持环境变量和分布式环境
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional, Set, Union
from pathlib import Path
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parents[2] / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    
logger = logging.getLogger(__name__)

class ServiceBaseSettings(BaseSettings):
    """
    服务配置基类
    所有微服务应继承此类，确保配置一致性
    """
    
    # 服务基本信息
    service_name: str = Field(default="unnamed-service")
    service_description: str = Field(default="")
    service_version: str = Field(default="1.0.0")
    
    # 服务网络配置
    host: str = Field(default="0.0.0.0", env="SERVICE_HOST")  # 服务主机
    port: int = Field(default=0, env="SERVICE_PORT")  # 服务端口（默认为0，要求每个服务明确指定端口）
    debug: bool = Field(default=True, env="DEBUG")  # 调试模式
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")  # CORS允许的源
    
    # Redis配置
    redis_enabled: bool = Field(default=True, env="REDIS_ENABLED")  # 是否启用Redis
    redis_host: str = Field(default="localhost", env="REDIS_HOST")  # Redis主机
    redis_port: int = Field(default=6379, env="REDIS_PORT")  # Redis端口
    redis_db: int = Field(default=0, env="REDIS_DB")  # Redis数据库
    redis_password: str = Field(default="", env="REDIS_PASSWORD")  # Redis密码
    
    # 服务发现配置
    service_discovery_enabled: bool = Field(default=True, env="SERVICE_DISCOVERY_ENABLED")  # 是否启用服务发现
    service_registry_ttl: int = Field(default=30, env="SERVICE_REGISTRY_TTL")  # 服务注册TTL秒数
    
    # 通用超时配置
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")  # 请求超时时间（秒）
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")  # 日志级别
    log_dir: str = Field(default="./logs", env="LOG_DIR")  # 日志目录
    log_file_prefix: str = Field(default="", env="LOG_FILE_PREFIX")  # 日志文件前缀
    
    # 共享目录配置
    data_dir: str = Field(default="./data", env="DATA_DIR")
    tmp_dir: str = Field(default="./tmp", env="TMP_DIR")
    
    # 环境配置
    environment: str = Field(default="development", env="ENVIRONMENT")
    testing: bool = Field(default=False, env="TESTING")
    
    @validator("log_file_prefix", pre=True, always=True)
    def set_log_file_prefix(cls, v, values):
        """如果未设置日志文件前缀，则使用服务名称"""
        if not v and "service_name" in values:
            return values["service_name"]
        return v
    
    def get_log_file_path(self) -> str:
        """获取日志文件路径"""
        log_dir = Path(self.log_dir)
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / f"{self.log_file_prefix}.log")
    
    def get_absolute_data_dir(self) -> Path:
        """获取绝对数据目录路径"""
        data_dir = Path(self.data_dir)
        if not data_dir.is_absolute():
            # 转换为绝对路径
            project_root = Path(__file__).parents[2]
            data_dir = project_root / data_dir
        return data_dir
    
    def get_absolute_tmp_dir(self) -> Path:
        """获取绝对临时目录路径"""
        tmp_dir = Path(self.tmp_dir)
        if not tmp_dir.is_absolute():
            # 转换为绝对路径
            project_root = Path(__file__).parents[2]
            tmp_dir = project_root / tmp_dir
        return tmp_dir
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment.lower() == "development"
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment.lower() == "production"
    
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.testing or self.environment.lower() == "testing"
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def get_service_url(self) -> str:
        """获取服务URL"""
        return f"http://{self.host}:{self.port}"
    
    def get_service_info(self) -> Dict[str, Any]:
        """获取服务信息"""
        return {
            "service_name": self.service_name,
            "description": self.service_description,
            "version": self.service_version,
            "debug_mode": self.debug,
            "host": self.host,
            "port": self.port,
        }
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """解析CORS来源"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",")]
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "validate_assignment": True,
        "arbitrary_types_allowed": True
    } 