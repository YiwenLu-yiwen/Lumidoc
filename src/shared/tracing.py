"""
统一的请求追踪工具
为前后端和微服务间通信提供请求追踪功能
"""

import uuid
import time
import logging
import functools
import asyncio
from typing import Optional, Callable, Any, Dict
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import contextmanager

# 配置日志
logger = logging.getLogger(__name__)

# 请求追踪ID的请求头名称
REQUEST_ID_HEADER = "X-Request-ID"

# 线程/协程本地存储，用于传递请求ID
class RequestContext:
    """请求上下文，用于存储当前请求的追踪信息"""
    _storage = {}
    
    @classmethod
    def get_request_id(cls) -> Optional[str]:
        """获取当前请求ID"""
        task = asyncio.current_task()
        return cls._storage.get(task, {}).get("request_id")
    
    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        """设置当前请求ID"""
        task = asyncio.current_task()
        if task not in cls._storage:
            cls._storage[task] = {}
        cls._storage[task]["request_id"] = request_id
    
    @classmethod
    def clear(cls) -> None:
        """清除当前请求的上下文信息"""
        task = asyncio.current_task()
        if task in cls._storage:
            del cls._storage[task]

# 生成请求ID
def generate_request_id() -> str:
    """生成唯一的请求ID"""
    return str(uuid.uuid4()).replace("-", "")[:16]

# 请求追踪中间件
class RequestTracingMiddleware(BaseHTTPMiddleware):
    """FastAPI请求追踪中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 获取或生成请求ID
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = generate_request_id()
        
        # 记录请求ID
        RequestContext.set_request_id(request_id)
        
        # 记录请求开始
        start_time = time.time()
        path = request.url.path
        method = request.method
        logger.info(f"[{request_id}] 开始处理请求: {method} {path}")
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 记录请求结束
            duration = time.time() - start_time
            status_code = response.status_code
            logger.info(f"[{request_id}] 完成请求: {method} {path} - 状态码: {status_code}, 耗时: {duration:.3f}秒")
            
            # 添加请求ID到响应头
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception as e:
            # 记录异常
            duration = time.time() - start_time
            logger.error(f"[{request_id}] 请求出错: {method} {path} - 错误: {str(e)}, 耗时: {duration:.3f}秒")
            raise
        finally:
            # 清除请求上下文
            RequestContext.clear()

# 装饰器：为函数添加请求追踪
def trace_request(func):
    """装饰器：为函数添加请求追踪"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 获取请求ID，如果没有则生成
        request_id = RequestContext.get_request_id()
        if not request_id:
            request_id = generate_request_id()
            RequestContext.set_request_id(request_id)
        
        # 记录函数调用开始
        start_time = time.time()
        func_name = func.__qualname__
        logger.debug(f"[{request_id}] 开始执行: {func_name}")
        
        try:
            # 执行原函数
            result = await func(*args, **kwargs)
            
            # 记录函数调用结束
            duration = time.time() - start_time
            logger.debug(f"[{request_id}] 完成执行: {func_name}, 耗时: {duration:.3f}秒")
            return result
        except Exception as e:
            # 记录异常
            duration = time.time() - start_time
            logger.error(f"[{request_id}] 执行出错: {func_name}, 错误: {str(e)}, 耗时: {duration:.3f}秒")
            raise
        
    return wrapper

# 上下文管理器：创建追踪上下文
@contextmanager
def tracing_context(request_id: Optional[str] = None, operation: Optional[str] = None):
    """创建追踪上下文"""
    # 获取或生成请求ID
    if not request_id:
        request_id = generate_request_id()
    
    # 保存旧的请求ID
    old_request_id = RequestContext.get_request_id()
    
    try:
        # 设置新请求ID
        RequestContext.set_request_id(request_id)
        
        # 记录操作开始
        if operation:
            logger.debug(f"[{request_id}] 开始操作: {operation}")
        
        start_time = time.time()
        yield request_id
        
        # 记录操作结束
        duration = time.time() - start_time
        if operation:
            logger.debug(f"[{request_id}] 完成操作: {operation}, 耗时: {duration:.3f}秒")
            
    finally:
        # 恢复原请求ID或清除
        if old_request_id:
            RequestContext.set_request_id(old_request_id)
        else:
            RequestContext.clear()

# 获取当前请求的追踪ID
def get_current_request_id() -> str:
    """获取当前请求的追踪ID，如果不存在则生成新的"""
    request_id = RequestContext.get_request_id()
    if not request_id:
        request_id = generate_request_id()
        RequestContext.set_request_id(request_id)
    return request_id

# 创建带有请求追踪信息的HTTP头
def create_trace_headers() -> Dict[str, str]:
    """创建带有请求追踪信息的HTTP头"""
    return {REQUEST_ID_HEADER: get_current_request_id()} 