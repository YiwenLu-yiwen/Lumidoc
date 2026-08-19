#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库模块
"""
import os
import redis
import logging
import asyncpg
from typing import AsyncGenerator

# 设置日志
logger = logging.getLogger(__name__)

# 全局数据库连接池
_db_pool = None

async def get_db_pool() -> asyncpg.Pool:
    """
    获取或创建数据库连接池
    
    Returns:
        asyncpg.Pool: 数据库连接池
    """
    global _db_pool
    
    if _db_pool is not None:
        return _db_pool
        
    try:
        # 获取数据库URL
        try:
            from src.modules.config import settings
            database_url = settings.database_url
        except (ImportError, AttributeError):
            # 如果无法从settings获取，则使用环境变量或默认值
            pg_user = os.environ.get("POSTGRES_USER", "postgres")
            pg_password = os.environ.get("POSTGRES_PASSWORD", "")
            pg_host = os.environ.get("POSTGRES_HOST", "localhost")
            pg_port = os.environ.get("POSTGRES_PORT", "5432") 
            pg_db = os.environ.get("POSTGRES_DB", "lumidoc")
            
            database_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        
        # 检查环境变量是否有更高优先级的设置
        if os.environ.get("POSTGRES_URL"):
            database_url = os.environ.get("POSTGRES_URL")
            logger.info(f"使用环境变量POSTGRES_URL: {database_url}")
            
        # 创建连接池
        logger.info("创建数据库连接池...")
        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            timeout=30
        )
        logger.info("数据库连接池创建成功")
        return _db_pool
    except Exception as e:
        logger.error(f"创建数据库连接池失败: {str(e)}")
        raise

async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    获取数据库连接
    
    Yields:
        asyncpg.Connection: 数据库连接
    """
    try:
        # 获取数据库URL
        try:
            from src.modules.config import settings
            database_url = settings.database_url
        except (ImportError, AttributeError):
            # 如果无法从settings获取，则使用环境变量或默认值
            pg_user = os.environ.get("POSTGRES_USER", "postgres")
            pg_password = os.environ.get("POSTGRES_PASSWORD", "")
            pg_host = os.environ.get("POSTGRES_HOST", "localhost")
            pg_port = os.environ.get("POSTGRES_PORT", "5432") 
            pg_db = os.environ.get("POSTGRES_DB", "lumidoc")
            
            database_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        
        # 检查环境变量是否有更高优先级的设置
        if os.environ.get("POSTGRES_URL"):
            database_url = os.environ.get("POSTGRES_URL")
            logger.info(f"使用环境变量POSTGRES_URL: {database_url}")
        
        # 创建连接
        conn = await asyncpg.connect(database_url)
        try:
            yield conn
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"数据库连接错误: {str(e)}")
        raise

def get_redis_client() -> redis.Redis:
    """
    获取Redis客户端连接
    
    Returns:
        redis.Redis: Redis客户端实例
    """
    try:
        # 尝试从配置模块获取设置
        try:
            from src.modules.config import settings
            redis_host = settings.redis_host
            redis_port = settings.redis_port
            redis_db = settings.redis_db
            redis_password = getattr(settings, 'redis_password', None)
        except (ImportError, AttributeError):
            # 如果无法从settings获取，则使用环境变量或默认值
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", "6379"))
            redis_db = int(os.environ.get("REDIS_DB", "0"))
            redis_password = os.environ.get("REDIS_PASSWORD")
        
        # 创建Redis客户端实例
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,  # 自动解码响应为字符串
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # 测试连接
        client.ping()
        logger.info(f"成功连接到Redis服务器: {redis_host}:{redis_port}")
        return client
    
    except redis.ConnectionError as e:
        logger.error(f"无法连接到Redis: {str(e)}")
        # 返回一个空的客户端，调用时会引发异常，但不会在导入时崩溃
        return redis.Redis(host="localhost", port=6379)
    
    except Exception as e:
        logger.error(f"初始化Redis客户端时出错: {str(e)}")
        return redis.Redis(host="localhost", port=6379)

def get_database_url() -> str:
    """获取数据库连接URL，优先从环境变量获取"""
    # 优先使用环境变量
    if os.environ.get("POSTGRES_URL"):
        database_url = os.environ.get("POSTGRES_URL")
        logger.info(f"使用环境变量POSTGRES_URL: {database_url}")
        return database_url

# 关闭数据库连接池
async def close_db_pool():
    """
    关闭数据库连接池
    """
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("数据库连接池已关闭")
