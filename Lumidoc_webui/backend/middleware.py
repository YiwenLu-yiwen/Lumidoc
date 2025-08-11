from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from typing import Callable, List
import json
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware.base import BaseHTTPMiddleware
import traceback

logger = logging.getLogger("Lumidoc_webui.backend.middleware")

def setup_cors(app: FastAPI):
    """设置跨域请求"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

class RequestLoggingMiddleware:
    """请求日志记录中间件"""
    
    def __init__(self, app: ASGIApp):
        self.app = app
        
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        # 记录请求开始时间
        start_time = time.time()
        
        # 创建自定义的receive函数来捕获请求体
        async def custom_receive():
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                try:
                    body_json = json.loads(body) if body else {}
                    logger.info(f"Request Body: {body_json}")
                except:
                    pass
            return message
        
        # 创建自定义的send函数来捕获响应
        async def custom_send(message):
            if message["type"] == "http.response.start":
                # 记录响应时间
                process_time = time.time() - start_time
                logger.info(
                    f"Response Time: {process_time:.2f}s"
                )
            await send(message)
        
        try:
            await self.app(scope, custom_receive, custom_send)
        except Exception as e:
            # 记录错误信息
            logger.error(f"Error: {str(e)}")
            
            # 返回错误响应
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
            await response(scope, receive, send)

class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            # 记录详细错误信息
            tb = traceback.format_exc()
            logger.error(f"Error: {str(e)}")
            logger.debug(f"Traceback: {tb}")
            
            # 返回500错误
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

class AuthMiddleware(BaseHTTPMiddleware):
    """API认证中间件 - 确保请求具有有效的身份验证"""
    
    def __init__(
        self, 
        app: ASGIApp, 
        exclude_paths: List[str] = None,
        auth_header: str = "Authorization",
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/api/auth/login", 
            "/api/auth/register",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
            "/system-info",
            "/db-status",
            "/static"
        ]
        self.auth_header = auth_header
        logger.info(f"已加载认证中间件，排除路径: {self.exclude_paths}")
        
    async def dispatch(self, request: Request, call_next):
        # 获取请求路径
        path = request.url.path
        
        # 检查路径是否在排除列表中
        for excluded_path in self.exclude_paths:
            if path.startswith(excluded_path):
                return await call_next(request)
        
        # 检查Authorization头
        auth_header = request.headers.get(self.auth_header)
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(f"未授权访问: {path}, 缺少有效身份验证令牌")
            return JSONResponse(
                status_code=401,
                content={"detail": "缺少有效身份验证令牌"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # 继续处理请求
        return await call_next(request)

def setup_middleware(app: FastAPI):
    """设置中间件"""
    setup_cors(app)
    
    # 添加身份验证中间件 - 最先处理，确保请求有效授权
    app.add_middleware(
        AuthMiddleware,
        exclude_paths=[
            "/api/auth/login", 
            "/api/auth/register",
            "/api/auth/reset_password",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
            "/system-info",
            "/db-status",
            "/static",
            # 允许静态资源和公共API访问
            "/favicon.ico",
            "/api/public"
        ]
    )
    
    # 添加请求日志中间件
    app.add_middleware(RequestLoggingMiddleware)
    
    # 添加异常处理中间件
    app.add_middleware(ExceptionHandlerMiddleware) 