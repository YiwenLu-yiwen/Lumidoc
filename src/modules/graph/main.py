#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图服务启动入口
"""

import uvicorn
import sys
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 服务注册生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期管理"""
    service_id = None
    
    try:
        # 启动时注册服务
        from src.shared.service_discovery import get_service_registry
        from src.shared.config import GraphServiceSettings
        
        settings = GraphServiceSettings()
        sr = await get_service_registry()
        
        if sr:
            # 定义WebSocket端点
            websocket_endpoints = {
                "graph": "/api/ws/graph/{project_id}",
                "updates": "/api/ws/updates/{project_id}"
            }
            
            service_id = await sr.register_service(
                service_name="graph",
                host=None,  # 自动检测
                port=settings.port,
                websocket_endpoints=websocket_endpoints,
                health_check_endpoint="/healthz"
            )
            print(f"Graph服务已注册到服务发现，ID: {service_id}")
        
    except Exception as e:
        print(f"Graph服务注册失败: {str(e)}")
    
    yield
    
    # 服务关闭时注销
    try:
        if service_id and sr:
            await sr.deregister_service("graph", service_id)
            print(f"Graph服务已注销，ID: {service_id}")
    except Exception as e:
        print(f"Graph服务注销失败: {str(e)}")

try:
    # 导入原有路由模块
    from src.modules.graph.routes.graph_routes import app
    # 添加WebSocket路由
    from src.modules.graph.routes.websocket_routes import graph_websocket_router
    
    # 注册WebSocket路由
    app.include_router(graph_websocket_router, prefix="/api")
    
    # 注册健康检查路由
    from src.shared.health_check import HealthChecker, register_health_routes
    health_checker = HealthChecker(service_name="graph")
    register_health_routes(app, health_checker)
    
    # 更新配置导入
    from src.shared.config import GraphServiceSettings
    settings = GraphServiceSettings()
    
    # 设置CORS（如果原有app没有设置的话）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
    )
    
    # 更新应用的生命周期
    app.router.lifespan_context = lifespan

except ImportError:
    # 如果无法导入原有路由，创建新的应用
    app = FastAPI(
        title="知识图谱服务",
        description="提供知识图谱构建和查询功能",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # 导入WebSocket路由
    from src.modules.graph.routes.websocket_routes import graph_websocket_router
    
    # 注册WebSocket路由
    app.include_router(graph_websocket_router, prefix="/api")
    
    # 注册健康检查路由
    from src.shared.health_check import HealthChecker, register_health_routes
    health_checker = HealthChecker(service_name="graph")
    register_health_routes(app, health_checker)
    
    # 设置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
    )
    
    from src.shared.config import GraphServiceSettings
    settings = GraphServiceSettings()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 