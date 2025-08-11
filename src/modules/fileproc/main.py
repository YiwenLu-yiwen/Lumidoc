#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理服务启动入口
负责文件的异步处理、转换和内容分析
"""

import uvicorn
import sys
import os
import logging
import traceback
import asyncio
import argparse
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
import time
import socket

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 从共享模块导入日志初始化
from src.shared.logger import initialize_logging, get_logger
from src.shared.health_check import register_health_routes, HealthChecker, ServiceStatus
from src.shared.config import get_settings

# 配置日志
log_file = os.getenv("LOG_FILE", "logs/fileproc_service.log")  # 修改为统一的日志文件名
os.environ["LOG_FILE"] = log_file
initialize_logging("fileproc_service")
logger = get_logger(__name__)

logger.info("文件处理服务启动中...")

try:
    # 加载配置
    settings = get_settings()
    logger.info(f"已加载配置: 端口={settings.port}")

    # 导入服务和配置
    from src.modules.fileproc.services.task_service import TaskService
    from src.modules.fileproc.services.file_processor import FileProcessor, file_processor
    from src.modules.fileproc.routes import process_router  # 导入处理路由模块
    from src.modules.fileproc.routes.diagnostic_routes import diagnostics_router  # 导入诊断路由模块
    from src.modules.fileproc.routes.stream_routes import stream_router  # 导入流处理路由模块
    from src.shared.service_discovery import call_service

    # 创建任务服务，使用全局文件处理器实例
    task_service = TaskService()

    # 依赖项函数
    def get_task_service():
        """获取任务服务实例"""
        return task_service
        
    def get_file_processor():
        """获取文件处理器实例"""
        return file_processor

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """服务生命周期管理"""
        # 启动时的初始化
        service_id = None
        
        try:
            # 初始化文件处理器
            logger.info("初始化文件处理器...")
            await file_processor.initialize()
            logger.info("文件处理器已初始化")
            
            # 初始化任务服务
            logger.info("初始化任务服务...")
            await task_service.initialize()
            logger.info("任务服务已初始化")
            
            # 初始化队列服务
            logger.info("初始化队列服务...")
            from .services.queue_service import file_processing_queue
            await file_processing_queue.initialize()
            logger.info("队列服务已初始化")
            
            # 注册服务 - 移除service_registry依赖
            from src.shared.service_discovery import get_service_registry
            sr = await get_service_registry() 
            if sr:
                # 向服务发现注册服务
                import socket
                service_id = f"fileproc-{socket.gethostname()}-{int(time.time())}"
                if os.environ.get("SERVICE_ID"):
                    service_id = os.environ.get("SERVICE_ID")
                    
                # 获取当前端口
                port = int(settings.port)
                
                # 注册服务
                service_id = await sr.register_service(
                    service_name="fileproc",
                    service_id=service_id,
                    host=None,  # 自动检测
                    port=port,
                    health_check_endpoint="/api/health"
                )
                logger.info(f"服务已注册到服务发现，ID: {service_id}")
            else:
                logger.warning("服务发现注册表未初始化，服务将以独立模式运行")
            
            logger.info("文件处理服务启动完成")
        except Exception as e:
            logger.error(f"启动错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
        yield
        
        # 关闭时的清理
        try:
            logger.info("正在关闭文件处理服务")
            
            # 关闭任务服务
            try:
                await task_service.shutdown()
                logger.info("任务服务已关闭")
            except Exception as e:
                logger.error(f"关闭任务服务失败: {str(e)}")
            
            # 关闭文件处理器
            try:
                await file_processor.shutdown()
                logger.info("文件处理器已关闭")
            except Exception as e:
                logger.error(f"关闭文件处理器失败: {str(e)}")
            
            # 从服务注册表注销
            try:
                from src.shared.service_discovery import get_service_registry
                sr = await get_service_registry()
                if sr and service_id:
                    await sr.deregister_service("fileproc", service_id)
                    logger.info(f"服务已从注册表注销，ID: {service_id}")
                else:
                    logger.warning("未找到SERVICE_ID环境变量或服务注册表未初始化，无法注销服务")
            except Exception as e:
                logger.error(f"服务注销失败: {str(e)}")
            
            logger.info("文件处理服务已关闭")
        except Exception as e:
            logger.error(f"服务关闭过程中发生错误: {str(e)}")
            logger.error(traceback.format_exc())

    # 创建FastAPI应用
    app = FastAPI(
        title="文件处理服务",
        description="提供文件异步处理、转换和内容分析功能",
        version="1.0.0",
        lifespan=lifespan
    )

    logger.info("创建FastAPI应用实例完成")

    # 设置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
    )

    # 注册路由
    app.include_router(process_router, prefix="/api")  # 添加/api前缀
    app.include_router(diagnostics_router, prefix="/api")  # 保留诊断路由的/api前缀
    app.include_router(stream_router, prefix="/api")  # 保留流处理路由的/api前缀
    logger.info("所有路由已注册")
    
    # 打印所有注册的路由，便于调试
    for route in app.routes:
        logger.info(f"已注册路由: {route.path} [{', '.join(route.methods)}]")

    # 注册健康检查路由
    health_checker = HealthChecker(service_name="fileproc")
    
    # 添加Redis检查 - 先确保连接
    if not task_service.queue._redis:
        import asyncio
        try:
            # 在主线程中连接队列
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task_service.queue.connect())
            logger.info("启动时建立队列Redis连接")
        except Exception as e:
            logger.error(f"队列Redis连接失败: {e}")
    
    # 添加Redis连接检查
    if task_service.queue._redis:
        health_checker.add_redis_connection("redis_queue", task_service.queue._redis)
        logger.info("队列Redis连接已添加到健康检查")
    else:
        logger.warning("队列Redis连接未建立，跳过健康检查")
    
    # 添加处理器状态检查
    def check_processor_status():
        return file_processor.is_initialized
    
    health_checker.add_check("processor", check_processor_status, critical=True)
    
    # 注册健康检查路由
    register_health_routes(app, health_checker)

    # 命令行参数解析
    parser = argparse.ArgumentParser(description="文件处理服务")
    parser.add_argument("--port", type=int, default=settings.port, help="服务端口")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务主机")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    parser.add_argument("--production", action="store_true", help="是否为生产模式")
    args = parser.parse_args()

    # 启动服务
    if __name__ == "__main__":
        try:
            host = args.host  # 使用命令行参数中的host
            port = settings.port
            
            logger.info(f"启动文件处理服务: {host}:{port}")
            
            if args.production:
                # 生产模式使用Uvicorn服务器
                import uvicorn
                uvicorn.run(
                    "src.modules.fileproc.main:app",
                    host=host,
                    port=port,
                    workers=args.workers,
                    log_level="info"
                )
            else:
                # 开发模式
                import uvicorn
                uvicorn.run(app, host=host, port=port)
        except Exception as e:
            logger.error(f"启动服务失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @app.on_event("startup")
    async def startup_event():
        """FastAPI启动事件处理程序，初始化服务组件"""
        try:
            logger.info("初始化文件处理器...")
            # 使用已导入的file_processor实例而非新建实例
            if not file_processor.is_initialized:
                await file_processor.initialize()
                logger.info("文件处理器已初始化")
            else:
                logger.info("文件处理器已经初始化")
                
            # 确保所有模块使用同一个实例
            import src.modules.fileproc.services.file_processor as fp_module
            fp_module.file_processor = file_processor
            import src.modules.fileproc.routes.process_routes as routes_module
            routes_module.file_processor = file_processor
            
            # 确保任务服务也已初始化
            if not task_service._initialized:
                await task_service.initialize()
                logger.info("任务服务已初始化")
            
            # 确保队列连接已建立
            if not task_service.queue._redis:
                await task_service.queue.connect()
                logger.info("队列Redis连接已建立")
            else:
                logger.info("队列Redis连接已存在")
                
            # 确保摘要客户端已可用
            import src.modules.fileproc.routes.process_routes as routes_module
            if not hasattr(routes_module, 'summary_client') or routes_module.summary_client is None:
                from src.modules.fileproc.services.summary_client import SummaryClient
                routes_module.summary_client = SummaryClient()
                logger.info("摘要客户端已初始化")
        except Exception as e:
            logger.error(f"启动事件处理失败: {str(e)}")
            logger.error(traceback.format_exc())

except Exception as e:
    logger.error(f"服务启动失败: {str(e)}")
    logger.error(traceback.format_exc())
    raise 