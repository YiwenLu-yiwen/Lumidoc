#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理服务的配置模块
"""

import os

# 基础配置
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ENV = os.environ.get("ENV", "development")
SERVICE_NAME = "fileproc"

# 存储配置
CONTENT_DIR = os.environ.get("CONTENT_DIR", "./content")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
STORAGE_TYPE = os.environ.get("STORAGE_TYPE", "local")

# 处理配置
ENABLE_OCR = os.environ.get("ENABLE_OCR", "false").lower() == "true"
MAX_PROCESSING_TIME = int(os.environ.get("MAX_PROCESSING_TIME", "300"))  # 最大处理时间(秒)
PROCESSING_TIMEOUT = int(os.environ.get("PROCESSING_TIMEOUT", "600"))   # 处理超时时间(秒)

# LLM后处理配置
ENABLE_LLM_POST_PROCESSING = os.environ.get("ENABLE_LLM_POST_PROCESSING", "false").lower() == "true"
LLM_PROCESSING_MODE = os.environ.get("LLM_PROCESSING_MODE", "both")  # summary/format/both
MIN_CONTENT_LENGTH_FOR_LLM = int(os.environ.get("MIN_CONTENT_LENGTH_FOR_LLM", "1000"))
MAX_EMPTY_LINES_RATIO = float(os.environ.get("MAX_EMPTY_LINES_RATIO", "0.3"))
LLM_POST_PROCESSING_MODEL = os.environ.get("LLM_POST_PROCESSING_MODEL", "deepseek-chat")

# 服务发现配置
SERVICE_REGISTRY_HOST = os.environ.get("REDIS_HOST", "localhost")
SERVICE_REGISTRY_PORT = int(os.environ.get("REDIS_PORT", "6379"))
SERVICE_REGISTRY_DB = int(os.environ.get("REDIS_DB", "0"))
SERVICE_REGISTRY_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# 缓存配置
CACHE_HOST = os.environ.get("REDIS_HOST", "localhost")
CACHE_PORT = int(os.environ.get("REDIS_PORT", "6379"))
CACHE_DB = int(os.environ.get("REDIS_DB", "0"))
CACHE_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))

# API配置
API_PORT = int(os.environ.get("FILEPROC_PORT", "8005"))
port = API_PORT  # 添加port变量用于服务注册
API_HOST = "0.0.0.0"
API_PREFIX = ""
API_WORKERS = int(os.environ.get("API_WORKERS", "1"))

# RabbitMQ配置
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.environ.get("RABBITMQ_VHOST", "/")

# MinIO配置
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET = os.environ.get("S3_BUCKET", "data")  # 统一使用S3_BUCKET配置

# 文件处理队列配置
QUEUE_NAME = "file_processing"
PROCESSING_CONCURRENCY = int(os.environ.get("FILE_PROCESSING_WORKERS", "2"))

# 日志配置
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("LOG_FILE", "fileproc_service.log")

def get_redis_url() -> str:
    """
    获取Redis连接URL
    
    Returns:
        str: Redis连接URL
    """
    # 从环境变量获取Redis配置
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_password = os.getenv("REDIS_PASSWORD", "123456789")
    redis_db = os.getenv("REDIS_DB", "0")
    
    # 构建Redis URL
    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}" 