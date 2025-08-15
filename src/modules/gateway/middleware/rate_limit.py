"""
Gateway限流中间件
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from src.modules.gateway.config.config import settings

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        # 检查是否启用限流
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # OPTIONS请求无需限流，直接放行
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 健康检查请求白名单，避免Gateway自己的健康检查被限流
        user_agent = request.headers.get("User-Agent", "")
        x_health_check = request.headers.get("X-Health-Check", "")
        
        # 多重检测确保健康检查被正确识别
        is_health_check = (
            "HealthCheck" in user_agent or 
            "gateway" in x_health_check or
            request.url.path.endswith(("/health", "/healthz", "/api/health")) or
            request.url.path in ["/health", "/healthz", "/api/health"]
        )
        
        if is_health_check:
            return await call_next(request)
        
        # 获取客户端标识
        client_id = self._get_client_id(request)
        
        # 对于项目相关的API请求，使用更宽松的限制
        is_project_api = request.url.path.startswith("/api/projects")
        effective_limit = settings.rate_limit_requests * 2 if is_project_api else settings.rate_limit_requests
        
        # 检查限流
        is_allowed, remaining_requests = await self._check_rate_limit(client_id, effective_limit)
        
        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁",
                    "message": "已达到请求频率限制，请稍后再试"
                },
                headers={
                    "X-RateLimit-Limit": str(effective_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + settings.rate_limit_window),
                    "Access-Control-Allow-Origin": "*",  # 确保CORS头正确设置
                    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # 继续处理请求
        response = await call_next(request)
        
        # 添加限流信息到响应头
        response.headers["X-RateLimit-Limit"] = str(effective_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + settings.rate_limit_window)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """获取客户端标识"""
        # 优先使用用户ID（如果已认证）
        if hasattr(request.state, 'user') and request.state.user:
            return f"user:{request.state.user.get('id', 'unknown')}"
        
        # 使用IP地址
        client_ip = request.client.host
        
        # 检查是否有X-Forwarded-For头（处理代理情况）
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"
    
    async def _check_rate_limit(self, client_id: str, effective_limit: int) -> tuple[bool, int]:
        """检查限流状态"""
        # 尝试使用Redis
        if await self._ensure_redis_connection():
            return await self._check_rate_limit_redis(client_id, effective_limit)
        else:
            # 回退到本地缓存
            return await self._check_rate_limit_local(client_id, effective_limit)
    
    async def _ensure_redis_connection(self) -> bool:
        """确保Redis连接"""
        if not settings.redis_enabled:
            return False
        
        if self.redis_client is None:
            try:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password or None,
                    decode_responses=True
                )
                await self.redis_client.ping()
                return True
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                self.redis_client = None
                return False
        
        return True
    
    async def _check_rate_limit_redis(self, client_id: str, effective_limit: int) -> tuple[bool, int]:
        """使用Redis检查限流"""
        try:
            key = f"rate_limit:{client_id}"
            current_time = int(time.time())
            window_start = current_time - settings.rate_limit_window
            
            # 使用Redis的sorted set来实现滑动窗口
            pipe = self.redis_client.pipeline()
            
            # 移除过期的请求记录
            pipe.zremrangebyscore(key, 0, window_start)
            
            # 获取当前窗口内的请求数量
            pipe.zcard(key)
            
            # 添加当前请求
            pipe.zadd(key, {str(current_time): current_time})
            
            # 设置过期时间
            pipe.expire(key, settings.rate_limit_window)
            
            results = await pipe.execute()
            
            current_requests = results[1]  # zcard的结果
            
            if current_requests >= effective_limit:
                return False, 0
            else:
                remaining = effective_limit - current_requests - 1
                return True, remaining
                
        except Exception as e:
            logger.error(f"Redis限流检查失败: {e}")
            # 回退到本地缓存
            return await self._check_rate_limit_local(client_id, effective_limit)
    
    async def _check_rate_limit_local(self, client_id: str, effective_limit: int) -> tuple[bool, int]:
        """使用本地缓存检查限流"""
        current_time = time.time()
        
        if client_id not in self.local_cache:
            self.local_cache[client_id] = {
                "requests": [],
                "last_cleanup": current_time
            }
        
        client_data = self.local_cache[client_id]
        
        # 清理过期记录
        window_start = current_time - settings.rate_limit_window
        client_data["requests"] = [
            req_time for req_time in client_data["requests"]
            if req_time > window_start
        ]
        
        # 检查是否超过限制
        if len(client_data["requests"]) >= effective_limit:
            return False, 0
        
        # 添加当前请求
        client_data["requests"].append(current_time)
        
        # 计算剩余请求数
        remaining = effective_limit - len(client_data["requests"])
        
        # 定期清理本地缓存
        if current_time - client_data["last_cleanup"] > 300:  # 5分钟清理一次
            self._cleanup_local_cache(current_time)
            client_data["last_cleanup"] = current_time
        
        return True, remaining
    
    def _cleanup_local_cache(self, current_time: float):
        """清理本地缓存"""
        window_start = current_time - settings.rate_limit_window
        
        # 删除过期的客户端记录
        expired_clients = []
        for client_id, client_data in self.local_cache.items():
            client_data["requests"] = [
                req_time for req_time in client_data["requests"]
                if req_time > window_start
            ]
            
            # 如果客户端没有活跃请求，标记为过期
            if not client_data["requests"]:
                expired_clients.append(client_id)
        
        # 删除过期的客户端
        for client_id in expired_clients:
            del self.local_cache[client_id]
    
    async def close(self):
        """关闭中间件"""
        if self.redis_client:
            await self.redis_client.close() 