#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一LLM服务主入口文件
负责启动FastAPI服务，注册路由
"""

import os
import logging
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import traceback
import socket

from .config.config import settings
from .api.endpoints import router as api_router
from src.shared.health_check import register_health_routes, create_health_checker
from src.shared.config import llm_settings
from .services.llm_service import LLMService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceAuthMiddleware(BaseHTTPMiddleware):
    """服务间认证中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.expected_token = os.environ.get("SERVICE_AUTH_TOKEN", "service-token-for-internal-use")
    
    async def dispatch(self, request: Request, call_next):
        """处理请求认证"""
        # 健康检查和根路径不需要认证
        if request.url.path in ["/", "/health", "/healthz", "/ready", "/api/health"]:
            return await call_next(request)
        
        # 检查是否为本地服务间调用（来自localhost或内部服务）
        client_host = request.client.host if request.client else "unknown"
        if client_host in ["127.0.0.1", "localhost", "::1"]:
            logger.debug(f"本地服务间调用，跳过认证: {request.url.path} from {client_host}")
            return await call_next(request)
        
        # 检查认证头
        auth_header = request.headers.get("authorization")
        if not auth_header:
            logger.warning(f"请求缺少认证头: {request.url.path} from {client_host}")
            raise HTTPException(status_code=401, detail="缺少认证令牌")
        
        # 验证Service token
        if auth_header.startswith("Service "):
            service_token = auth_header.replace("Service ", "")
            if service_token == self.expected_token:
                logger.debug(f"服务间认证成功: {request.url.path}")
                return await call_next(request)
            else:
                logger.warning(f"无效的服务令牌: {request.url.path}")
                raise HTTPException(status_code=401, detail="无效的服务令牌")
        
        # 检查Bearer token（用户认证）
        elif auth_header.startswith("Bearer "):
            # 对于用户认证，我们简化处理（在实际部署中应该验证JWT）
            logger.debug(f"用户认证请求: {request.url.path}")
            return await call_next(request)
        
        else:
            logger.warning(f"不支持的认证类型: {auth_header[:20]}...")
            raise HTTPException(status_code=401, detail="不支持的认证类型")

# 创建FastAPI应用
app = FastAPI(
    title=settings.service_name,
    description="统一LLM服务，提供文本生成、聊天、摘要、问答等能力",
    version=settings.service_version,
)

# 🔧 修复：添加服务间认证中间件
app.add_middleware(ServiceAuthMiddleware)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)

# 创建LLM服务实例
llm_service = LLMService()

# 添加根路由
@app.get("/")
async def root():
    """根路由，返回服务信息"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "统一LLM服务，提供文本生成、聊天、摘要、问答等能力",
        "llm_model_type": llm_settings.model_type,
        "llm_model_name": llm_settings.model_name,
    }

# 创建健康检查器
health_checker = create_health_checker("llm", "llm_service_1")

# 添加LLM特定的健康检查
async def check_llm_availability():
    """检查LLM模型可用性"""
    try:
        # 使用全局LLM服务实例，避免重复初始化
        return llm_service.adapter is not None
    except Exception as e:
        logger.error(f"LLM可用性检查失败: {str(e)}")
        return False

# 添加API连接检查
async def check_api_connection():
    """检查API连接状态"""
    try:
        # 检查配置是否正确
        if llm_settings.model_type and llm_settings.model_name:
            return True
        return False
    except Exception as e:
        logger.error(f"API连接检查失败: {str(e)}")
        return False

# 配置健康检查项
health_checker.add_check("llm_model", check_llm_availability, critical=True)
health_checker.add_check("api_connection", check_api_connection, critical=True)

# 注册统一健康检查路由
register_health_routes(app, health_checker)

@app.on_event("startup")
async def startup_event():
    """
    服务启动时执行的操作
    """
    try:
        # 启动健康检查器
        await health_checker.start()
        logger.info("健康检查器已启动")
        
        # 初始化LLM服务
        logger.info("初始化LLM服务...")
        
        # 注册服务到服务发现
        try:
            from src.shared.service_discovery import register_service
            await register_service("llm", port=settings.port, health_check_endpoint="/api/health")
            logger.info("LLM服务已注册到服务发现")
        except Exception as e:
            logger.error(f"LLM服务注册失败: {str(e)}")
            logger.error(traceback.format_exc())
            logger.warning("LLM服务将以独立模式运行")
        
        logger.info("LLM服务启动成功")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        logger.error(traceback.format_exc())

@app.on_event("shutdown")  
async def shutdown_event():
    """
    服务关闭时执行的操作
    """
    try:
        # 停止健康检查器
        await health_checker.stop()
        logger.info("健康检查器已停止")
        
        # 注销服务
        try:
            from src.shared.service_discovery import unregister_service
            await unregister_service("llm")
            logger.info("LLM服务已从服务发现注销")
        except Exception as e:
            logger.error(f"服务注销失败: {str(e)}")
            
        logger.info("LLM服务已安全关闭")
    except Exception as e:
        logger.error(f"服务关闭失败: {str(e)}")

# 启动服务
if __name__ == "__main__":
    import uvicorn
    
    # 获取端口
    port = int(os.environ.get("PORT", 8080))
    
    # 启动服务
    uvicorn.run(
        "src.modules.llm.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENV") == "development"
    ) 