#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
STP系统统一API网关
负责统一管理所有微服务的请求转发、负载均衡、认证、限流等功能
"""

import sys
import os
import asyncio
import logging
import uvicorn
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

# 添加项目根目录到Python路径
current_dir = Path(__file__).resolve().parent.parent.parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

# 导入Gateway组件
from src.modules.gateway.config.config import settings
from src.modules.gateway.services.service_discovery import get_service_discovery
from src.modules.gateway.services.proxy import get_request_proxy
from src.modules.gateway.middleware.auth import AuthMiddleware
from src.modules.gateway.middleware.rate_limit import RateLimitMiddleware
from src.modules.gateway.routes.proxy import router as proxy_router

# 导入共享组件
from src.shared.logger import initialize_logging, get_logger

# 初始化日志
initialize_logging("gateway")
logger = get_logger(__name__)

def create_app() -> FastAPI:
    """创建FastAPI应用"""
    
    # 全局变量存储实际运行的端口
    actual_port = settings.port
    
    # 定义lifespan事件管理器
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """应用生命周期管理"""
        nonlocal actual_port
        
        # 启动事件
        # 动态获取实际运行的端口
        import argparse
        
        # 从命令行参数中获取端口
        try:
            parser = argparse.ArgumentParser(description="STP Gateway API")
            parser.add_argument("--port", type=int, default=settings.port, help="监听端口")
            args, _ = parser.parse_known_args()
            actual_port = args.port
        except:
            # 如果无法解析命令行参数，使用默认端口
            actual_port = settings.port
        
        logger.info(f"启动STP Gateway API v{settings.service_version}，实际端口: {actual_port}")
        
        try:
            # 创建服务代理路由
            from src.modules.gateway.routes.proxy import create_service_routes
            create_service_routes()
            logger.info("服务代理路由创建完成")
            
            # 初始化服务发现
            service_discovery = await get_service_discovery()
            await service_discovery.initialize()
            logger.info("服务发现初始化完成")
            
            # 初始化请求代理
            request_proxy = await get_request_proxy()
            logger.info("请求代理初始化完成")
            
            # 注册到服务发现（如果启用Redis）- 使用实际端口
            if settings.redis_enabled:
                try:
                    from src.shared.service_discovery import register_service
                    logger.info(f"正在注册Gateway到服务发现: 端口={actual_port}")
                    await register_service(
                        service_name="gateway", 
                        port=actual_port,
                        health_check_endpoint="/healthz"  # 使用Kubernetes标准健康检查端点
                    )
                    logger.info("已注册到服务发现")
                except Exception as e:
                    logger.warning(f"注册到服务发现失败: {e}")
            
            # 显示配置信息
            logger.info(f"Gateway配置:")
            logger.info(f"  - 监听地址: {settings.host}:{actual_port}")
            logger.info(f"  - 调试模式: {settings.debug}")
            logger.info(f"  - 认证: {'启用' if settings.auth_enabled else '禁用'}")
            logger.info(f"  - 限流: {'启用' if settings.rate_limit_enabled else '禁用'}")
            logger.info(f"  - 健康检查: {'启用' if settings.health_check_enabled else '禁用'}")
            logger.info(f"  - 负载均衡: {'启用' if settings.load_balancer_enabled else '禁用'}")
            logger.info(f"  - 支持的服务: {', '.join(settings.get_all_services())}")
            
            logger.info("Gateway启动完成")
            
        except Exception as e:
            logger.error(f"Gateway启动失败: {e}")
            raise
            
        yield
        
        # 关闭事件
        logger.info("正在关闭Gateway...")
        
        try:
            # 关闭服务发现
            service_discovery = await get_service_discovery()
            await service_discovery.close()
            logger.info("服务发现已关闭")
            
            # 关闭请求代理
            request_proxy = await get_request_proxy()
            await request_proxy.close()
            logger.info("请求代理已关闭")
            
            # 注销服务注册
            if settings.redis_enabled:
                try:
                    from src.shared.service_discovery import unregister_service
                    await unregister_service("gateway")
                    logger.info("已注销服务注册")
                except Exception as e:
                    logger.warning(f"注销服务注册失败: {e}")
            
            logger.info("Gateway已关闭")
            
        except Exception as e:
            logger.error(f"Gateway关闭失败: {e}")
    
    # 创建FastAPI实例
    app = FastAPI(
        title="STP Gateway API",
        description="STP系统统一API网关",
        version=settings.service_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None
    )
    
    # 设置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        max_age=3600,  # 预检请求缓存时间（秒）
    )
    
    # 添加限流中间件
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)
        logger.info("已启用限流中间件")
    
    # 添加认证中间件
    if settings.auth_enabled:
        app.add_middleware(AuthMiddleware)
        logger.info("已启用认证中间件")
    
    # 注册路由
    app.include_router(proxy_router)
    
    # Kubernetes标准健康检查端点
    @app.get("/healthz")
    async def kubernetes_health_check():
        """Gateway健康检查端点"""
        try:
            # 检查服务发现是否正常
            service_discovery = await get_service_discovery()
            services = await service_discovery.get_all_services()
            
            healthy_services = 0
            total_services = 0
            
            for service_name, instances in services.items():
                for instance in instances:
                    total_services += 1
                    if instance.get("health_status") == "healthy":
                        healthy_services += 1
            
            health_percentage = (healthy_services / total_services * 100) if total_services > 0 else 0
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "gateway_version": settings.service_version,
                "service_discovery": "connected",
                "services": {
                    "total": total_services,
                    "healthy": healthy_services,
                    "health_percentage": f"{health_percentage:.1f}%"
                }
            }
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "gateway_version": settings.service_version,
                "error": str(e)
            }
    
    # 显式注册项目服务路由，确保POST /api/projects/能够正确处理
    from src.modules.gateway.services.proxy import get_request_proxy
    
    @app.api_route("/api/projects/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def project_proxy_with_path(request: Request, path: str):
        """项目服务代理 - 带路径"""
        proxy = await get_request_proxy()
        return await proxy.proxy_request(request=request, service_name="project")
    
    @app.api_route("/api/projects", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def project_proxy_root(request: Request):
        """项目服务代理 - 根路径"""
        proxy = await get_request_proxy()
        return await proxy.proxy_request(request=request, service_name="project")
    
    @app.api_route("/api/projects/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def project_proxy_root_slash(request: Request):
        """项目服务代理 - 根路径带斜杠"""
        proxy = await get_request_proxy()
        return await proxy.proxy_request(request=request, service_name="project")
    
    # 自定义OpenAPI文档
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title="STP Gateway API",
            version=settings.service_version,
            description="STP系统统一API网关，负责路由转发、负载均衡、认证、限流等功能",
            routes=app.routes,
        )
        
        # 添加自定义信息
        openapi_schema["info"]["x-logo"] = {
            "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    return app

# 创建应用实例
app = create_app()

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """404错误处理器"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"路径 {request.url.path} 未找到",
            "gateway": "STP-Gateway",
            "available_services": settings.get_all_services()
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """500错误处理器"""
    logger.error(f"内部错误: {request.url.path} - {exc.detail}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "网关内部错误",
            "gateway": "STP-Gateway"
        }
    )

@app.exception_handler(502)
async def bad_gateway_handler(request: Request, exc: HTTPException):
    """502错误处理器"""
    logger.error(f"网关错误: {request.url.path} - {exc.detail}")
    return JSONResponse(
        status_code=502,
        content={
            "error": "Bad Gateway",
            "message": "目标服务不可用",
            "gateway": "STP-Gateway"
        }
    )

@app.exception_handler(503)
async def service_unavailable_handler(request: Request, exc: HTTPException):
    """503错误处理器"""
    logger.error(f"服务不可用: {request.url.path} - {exc.detail}")
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service Unavailable",
            "message": "服务暂时不可用",
            "gateway": "STP-Gateway"
        }
    )

@app.exception_handler(504)
async def gateway_timeout_handler(request: Request, exc: HTTPException):
    """504错误处理器"""
    logger.error(f"网关超时: {request.url.path} - {exc.detail}")
    return JSONResponse(
        status_code=504,
        content={
            "error": "Gateway Timeout",
            "message": "请求超时",
            "gateway": "STP-Gateway"
        }
    )

def main():
    """主函数"""
    # 解析命令行参数
    import argparse
    
    parser = argparse.ArgumentParser(description="STP Gateway API")
    parser.add_argument("--host", default=settings.host, help="监听主机")
    parser.add_argument("--port", type=int, default=settings.port, help="监听端口")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    parser.add_argument("--reload", action="store_true", help="开发模式自动重载")
    
    args = parser.parse_args()
    
    # 设置实际运行端口
    global actual_port
    actual_port = args.port
    
    # 启动服务
    logger.info(f"启动Gateway API服务 - {args.host}:{args.port}")
    
    uvicorn.run(
        "src.modules.gateway.main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload,
        log_level=settings.log_level.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main() 