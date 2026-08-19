#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LightRAG服务启动入口
"""

# ruff: noqa: E402 -- environment and sys.path setup must precede package imports.

import uvicorn
import sys
import os
import time
import socket
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from src.shared.logger import initialize_logging, get_logger
from fastapi import Body, Request
from typing import List

# 确保加载环境变量
load_dotenv()

# 配置基本日志
initialize_logging("lightrag_local")
logger = get_logger(__name__)

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 导入本地路由模块
from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from .routes.enterprise_rag_routes import router
from .config.config import config

# 🔧 修复：自定义JSON编码器，确保中文字符正确显示
class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,  # 这是关键：不将非ASCII字符转换为\uXXXX形式
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

# 定义应用生命周期上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭时的生命周期钩子
    """
    service_id = None
    service_registry = None

    try:
        # 启动时执行
        logger.info("LightRAG服务正在启动...")
        
        # 获取配置
        from src.shared.config import RAGServiceSettings
        settings = RAGServiceSettings()
        
        # 初始化企业级服务
        try:
            from .services.enterprise_lightrag_service import get_enterprise_lightrag_service
            await get_enterprise_lightrag_service()
            logger.info("✅ 企业级LightRAG服务初始化完成")
            
            # 项目隔离模式：按需初始化项目
            logger.info("🏢 企业级项目隔离模式：按需初始化项目")
            
        except Exception as e:
            logger.error(f"初始化企业级服务失败: {str(e)}")
            logger.error("服务将继续启动，但功能可能受限")

        # 注册服务到服务发现
        try:
            from src.shared.service_discovery import get_service_registry
            service_registry = await get_service_registry()
            
            if service_registry:
                # 生成服务ID
                service_id = f"lightraglocal-{socket.gethostname()}-{int(time.time())}"
                if os.environ.get("SERVICE_ID"):
                    service_id = os.environ.get("SERVICE_ID")
                
                # 注册服务（使用lightraglocal作为服务名称，与文件服务查找的名称一致）
                service_id = await service_registry.register_service(
                    service_name="lightraglocal",
                    service_id=service_id,
                    host=None,  # 自动检测
                    port=settings.port,
                    health_check_endpoint="/healthz",
                    metadata={
                        "version": "0.1.0",
                        "description": "轻量级RAG检索服务",
                        "environment": os.environ.get("ENVIRONMENT", "development")
                    },
                    endpoints={
                        "api": "/api",
                        "rag": "/rag",
                        "health": "/healthz",
                        "search": "/search"
                    }
                )
                logger.info(f"服务已注册到服务发现，ID: {service_id}")
            else:
                logger.warning("服务发现注册表未初始化，服务将以独立模式运行")
        except Exception as e:
            logger.error(f"服务注册失败: {str(e)}")
            logger.warning("服务将以独立模式运行")

        yield
        
        # 关闭时执行
        logger.info("LightRAG服务正在关闭...")

    except Exception as e:
        logger.error(f"启动时出错: {str(e)}")
        yield
    finally:
        # 清理资源
        if service_id and service_registry:
            try:
                await service_registry.deregister_service("lightraglocal", service_id)
                logger.info("服务已注销")
            except Exception as e:
                logger.error(f"注销服务失败: {str(e)}")
        
        # 关闭服务发现连接
        if service_registry:
            try:
                await service_registry.close()
            except Exception as e:
                logger.error(f"关闭服务发现连接失败: {str(e)}")
        
        logger.info("LightRAG服务已关闭")

# 创建FastAPI应用，使用生命周期管理器
app = FastAPI(
    title="LightRAG API",
    description="轻量级RAG检索服务",
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=CustomJSONResponse  # 使用自定义JSON响应类
)

# 添加CORS中间件，解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有头部
)

# 创建一个带API前缀的路由
api_router = APIRouter(prefix="/api")

# 注册标准路由
app.include_router(router)

# 将标准路由复制到API前缀路由下
# 首先创建一个和router功能一样的路由器，但设置前缀为/api/rag
api_rag_router = APIRouter(prefix="/rag", tags=["rag"])

# 从原始路由复制所有路由处理函数和API定义到带前缀的路由器
for route in router.routes:
    # 注意使用相同的路径、HTTP方法和回调函数
    api_rag_router.add_api_route(
        path=route.path,
        endpoint=route.endpoint,
        methods=route.methods,
        name=f"api_{route.name}" if route.name else None,
        description=route.description
    )

# 添加带API前缀的路由到应用
api_router.include_router(api_rag_router)

# 最后注册API前缀路由
app.include_router(api_router)

# 🔧 添加特殊路由处理，支持前端请求（企业级）
@app.post("/lightrag/rag/build/{project_id}")
async def lightrag_build_endpoint(
    request: Request,
    project_id: str,
    selected_files: List[str] = Body(..., embed=True)
):
    """特殊路由处理，支持前端请求格式（企业级）"""
    from .routes.enterprise_rag_routes import build_rag
    return await build_rag(project_id=project_id, selected_files=selected_files, http_request=request)

# 🔧 添加对/api/lightrag/rag/build/{project_id}的支持
@app.post("/api/lightrag/rag/build/{project_id}")
async def api_lightrag_build_endpoint(
    request: Request,
    project_id: str,
    selected_files: List[str] = Body(..., embed=True)
):
    """特殊路由处理，支持前端请求格式（带API前缀）"""
    from .routes.enterprise_rag_routes import build_rag
    return await build_rag(project_id=project_id, selected_files=selected_files, http_request=request)

# 🔧 添加对/api/lightrag/lightrag/build/{project_id}的支持（双重前缀）
@app.post("/api/lightrag/lightrag/build/{project_id}")
async def double_prefix_build_endpoint(
    request: Request,
    project_id: str,
    selected_files: List[str] = Body(..., embed=True)
):
    """特殊路由处理，支持前端请求格式（双重前缀）"""
    from .routes.enterprise_rag_routes import build_rag
    return await build_rag(project_id=project_id, selected_files=selected_files, http_request=request)

# 🔧 添加获取RAG文件列表的特殊路由
@app.get("/lightrag/rag/files/{project_id}")
async def lightrag_get_files_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件列表请求"""
    from .routes.enterprise_rag_routes import get_rag_files
    return await get_rag_files(project_id=project_id, http_request=request)

# 🔧 添加获取RAG文件列表的API前缀特殊路由
@app.get("/api/lightrag/rag/files/{project_id}")
async def api_lightrag_get_files_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件列表请求（带API前缀）"""
    from .routes.enterprise_rag_routes import get_rag_files
    return await get_rag_files(project_id=project_id, http_request=request)
    
# 🔧 添加获取RAG文件列表的双重前缀特殊路由
@app.get("/api/lightrag/lightrag/files/{project_id}")
async def double_prefix_files_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件列表请求（双重前缀）"""
    from .routes.enterprise_rag_routes import get_rag_files
    return await get_rag_files(project_id=project_id, http_request=request)

# 🔧 添加获取RAG文件状态的特殊路由
@app.get("/lightrag/rag/status/{project_id}")
async def lightrag_get_status_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件状态请求"""
    from .routes.enterprise_rag_routes import get_file_status
    return await get_file_status(project_id=project_id, http_request=request)

# 🔧 添加获取RAG文件状态的API前缀特殊路由
@app.get("/api/lightrag/rag/status/{project_id}")
async def api_lightrag_get_status_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件状态请求（带API前缀）"""
    from .routes.enterprise_rag_routes import get_file_status
    return await get_file_status(project_id=project_id, http_request=request)
    
# 🔧 添加获取RAG文件状态的双重前缀特殊路由
@app.get("/api/lightrag/lightrag/status/{project_id}")
async def double_prefix_status_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取文件状态请求（双重前缀）"""
    from .routes.enterprise_rag_routes import get_file_status
    return await get_file_status(project_id=project_id, http_request=request)

# 🔧 添加获取知识图谱的特殊路由
@app.get("/lightrag/projects/{project_id}/knowledge-graph")
async def lightrag_knowledge_graph_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取知识图谱请求"""
    from .routes.enterprise_rag_routes import get_knowledge_graph
    return await get_knowledge_graph(project_id=project_id, http_request=request)

# 🔧 添加获取知识图谱的API前缀特殊路由
@app.get("/api/lightrag/projects/{project_id}/knowledge-graph")
async def api_lightrag_knowledge_graph_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取知识图谱请求（带API前缀）"""
    from .routes.enterprise_rag_routes import get_knowledge_graph
    return await get_knowledge_graph(project_id=project_id, http_request=request)

# 🔧 添加获取知识图谱的双重前缀特殊路由
@app.get("/api/lightrag/lightrag/projects/{project_id}/knowledge-graph")
async def double_prefix_knowledge_graph_endpoint(request: Request, project_id: str):
    """特殊路由处理，支持前端获取知识图谱请求（双重前缀）"""
    from .routes.enterprise_rag_routes import get_knowledge_graph
    return await get_knowledge_graph(project_id=project_id, http_request=request)

# 添加根级搜索接口 - 方便直接访问，提高兼容性
@app.post("/search")
async def root_search(
    request: Request,
    query: str = Body(...),
    project_id: str = Body(None),
    top_k: int = Body(5),
    mode: str = Body(None),
    rerank: bool = Body(False)
):
    """直接在根路径提供搜索接口，以增加兼容性"""
    from .routes.enterprise_rag_routes import search_rag
    # 使用配置中的默认查询模式
    if mode is None:
        mode = config.default_query_mode
    return await search_rag(
        http_request=request,
        query=query,
        project_id=project_id,
        top_k=top_k,
        mode=mode,
        rerank=rerank
    )

@app.get("/healthz")
async def root_health_check():
    """
    根路径健康检查接口 - 企业级服务
    """
    try:
        from .services.enterprise_lightrag_service import get_enterprise_lightrag_service
        
        # 简单健康检查
        await get_enterprise_lightrag_service()
        return {
            "success": True,
            "status": "healthy",
            "service": "enterprise-lightrag",
            "timestamp": time.time(),
            "version": "enterprise-2.0"
        }
    except Exception as e:
        return {
            "success": False,
            "status": "unhealthy",
            "service": "enterprise-lightrag",
            "error": str(e),
            "timestamp": time.time()
        }

# 导入配置 - 更新配置路径
from src.shared.config import RAGServiceSettings
settings = RAGServiceSettings()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
