#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
监控服务启动入口
"""

# ruff: noqa: E402 -- direct execution adjusts sys.path before package imports.

import uvicorn
import sys
import os
import asyncio
import psutil
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
    metrics_task = None
    sr = None
    
    try:
        await health_checker.start()

        # 启动时注册服务
        from src.shared.service_discovery import get_service_registry
        try:
            from config import settings
            port = settings.monitoring_service_port
        except (ImportError, AttributeError):
            from src.shared.config import get_settings
            settings = get_settings()
            port = getattr(settings, 'monitoring_service_port', 8008)
        
        sr = await get_service_registry()
        
        if sr:
            # 定义WebSocket端点
            websocket_endpoints = {
                "monitoring": "/api/ws/monitoring/admin",
                "project": "/api/ws/monitoring/project/{project_id}"
            }
            
            service_id = await sr.register_service(
                service_name="monitoring",
                host=None,  # 自动检测
                port=port,
                websocket_endpoints=websocket_endpoints,
                health_check_endpoint="/healthz"
            )
            print(f"Monitoring服务已注册到服务发现，ID: {service_id}")
        
        # 启动系统指标推送任务
        metrics_task = asyncio.create_task(start_system_metrics_task())
        print("系统指标推送任务已启动")
        
    except Exception as e:
        print(f"Monitoring服务注册失败: {str(e)}")
    
    yield
    
    # 服务关闭时清理
    try:
        # 停止指标推送任务
        if metrics_task and not metrics_task.done():
            metrics_task.cancel()
            try:
                await metrics_task
            except asyncio.CancelledError:
                pass
            print("系统指标推送任务已停止")
        
        # 注销服务
        if service_id and sr:
            await sr.deregister_service("monitoring", service_id)
            print(f"Monitoring服务已注销，ID: {service_id}")
        await health_checker.stop()
    except Exception as e:
        print(f"Monitoring服务关闭失败: {str(e)}")

# 创建健康检查器
from src.shared.health_check import create_health_checker, register_health_routes
health_checker = create_health_checker("monitoring", "monitoring_service_1")


def check_monitoring_service() -> bool:
    """确认监控服务能够读取基本系统信息。"""
    psutil.virtual_memory()
    return True


def check_system_resources() -> bool:
    """在关键资源达到 90% 前保持健康状态。"""
    memory_ok = psutil.virtual_memory().percent <= 90
    cpu_ok = psutil.cpu_percent(interval=None) <= 90
    disk_ok = psutil.disk_usage("/").percent <= 90
    return memory_ok and cpu_ok and disk_ok


health_checker.add_check(
    "monitoring_service", check_monitoring_service, critical=True
)
health_checker.add_check("system_resources", check_system_resources, critical=False)

# 创建FastAPI应用
app = FastAPI(
    title="监控服务",
    description="提供系统监控和告警功能",
    version="1.0.0",
    lifespan=lifespan
)

# 导入WebSocket路由
from src.modules.monitoring.routes.websocket_routes import monitoring_websocket_router

# 注册WebSocket路由
app.include_router(monitoring_websocket_router, prefix="/api")

# 注册健康检查路由
register_health_routes(app, health_checker)

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
)

# 导入配置
try:
    from config import settings
    port = settings.monitoring_service_port
except (ImportError, AttributeError):
    from src.shared.config import get_settings
    settings = get_settings()
    port = getattr(settings, 'monitoring_service_port', 8008)

# 系统指标定时推送任务
async def start_system_metrics_task():
    """启动系统指标定时推送任务"""
    from src.modules.monitoring.routes.websocket_routes import monitoring_connection_manager, get_current_system_metrics
    
    while True:
        try:
            # 如果有管理员连接，获取并推送系统指标
            if monitoring_connection_manager.admin_connections:
                metrics = await get_current_system_metrics()
                if metrics:
                    await monitoring_connection_manager.send_system_metrics(metrics)
            
            # 每30秒推送一次
            await asyncio.sleep(30)
        except Exception as e:
            print(f"系统指标推送任务错误: {str(e)}")
            await asyncio.sleep(60)  # 出错时等待更长时间


from src.modules.monitoring.routes.admin_routes import router as admin_router
app.include_router(admin_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
