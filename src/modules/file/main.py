#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理服务启动入口 - 负责重量级文件处理
"""

import uvicorn
import sys
import os
import logging
import traceback
import asyncio
from src.shared.logger import initialize_logging, get_logger
from fastapi import FastAPI, Depends, HTTPException, UploadFile, Form, File, Request, Query, Header
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from fastapi.responses import RedirectResponse
from .routes import router
from .database.ensure_tables import init_database
from src.shared.service_discovery import ServiceRegistry
from src.shared.config import get_settings
from datetime import datetime
from .config.database import FileServiceDatabase

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 配置日志
initialize_logging("file_service")
logger = get_logger(__name__)

logger.info("文件服务启动中...")

try:
    # 使用统一配置系统
    settings = get_settings()
    logger.info(f"已加载配置: 端口={settings.port}, 存储目录={settings.storage_dir}")

    # 检查存储目录
    if not os.path.exists(settings.storage_dir):
        try:
            logger.warning(f"存储目录不存在，尝试创建: {settings.storage_dir}")
            os.makedirs(settings.storage_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"创建存储目录失败: {str(e)}")
            raise RuntimeError(f"无法创建存储目录: {str(e)}")

    # 导入处理器
    try:
        from src.shared.file.schemas import FileProcessingStatusResponse
        from src.modules.file.routes import file_routes  # 只导入file_routes
    except ImportError as e:
        logger.error(f"导入模块失败: {str(e)}")
        raise RuntimeError(f"无法导入必要模块: {str(e)}")

    # 创建应用
    app = FastAPI(
        title="文件服务", 
        description="提供文件管理和存储功能，处理逻辑由fileproc服务提供",
        version="0.1.0"
    )

    # 设置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
        expose_headers=["Content-Type", "Authorization", "Content-Disposition"],
        max_age=86400,  # 预检请求缓存时间，单位秒
    )

    # 注册主要的文件路由
    app.include_router(router)
    logger.info("文件路由已注册")
    
    # 添加Gateway转发路径处理（当strip_prefix=False时）
    # 这些路由直接处理Gateway转发的完整路径
    from .routes.file_routes import (
        get_current_user_or_service,
        list_project_files, 
        get_file_content,
        download_file,
        User
    )
    
    @app.get("/file/api/projects/{project_id}/files")
    async def gateway_list_project_files(
        project_id: str,
        authorization: Optional[str] = Header(None)
    ):
        """Gateway转发: 获取项目文件列表"""
        logger.info(f"Gateway转发路径: 获取项目{project_id}的文件列表")
        return await list_project_files(project_id)
    
    @app.get("/file/api/projects/{project_id}/files/content/{file_name:path}")
    async def gateway_get_file_content(
        project_id: str, 
        file_name: str,
        authorization: Optional[str] = Header(None)
    ):
        """Gateway转发: 获取文件内容"""
        logger.info(f"Gateway转发路径: 获取项目{project_id}文件{file_name}的内容")
        current_user = await get_current_user_or_service(authorization)
        return await get_file_content(project_id, file_name, current_user)
    
    @app.get("/file/api/projects/{project_id}/files/download/{file_name:path}")
    @app.head("/file/api/projects/{project_id}/files/download/{file_name:path}")
    async def gateway_download_file(
        project_id: str, 
        file_name: str,
        download: bool = Query(False), 
        preview: bool = Query(False),
        token: Optional[str] = Query(None),
        current_user: User = Depends(get_current_user_or_service)
    ):
        """Gateway转发: 下载文件"""
        logger.info(f"Gateway转发路径: 下载项目{project_id}文件{file_name}, 预览模式={preview}")
        return await download_file(project_id, file_name, download, preview, token, current_user)

    # 添加项目文件API端点 - 重定向到/api前缀的端点
    @app.get("/projects/{project_id}/files")
    async def get_project_files_redirect(project_id: str):
        """重定向到正确的API路径"""
        logger.info(f"重定向旧的文件列表请求到新API路径: 项目ID={project_id}")
        # 返回API数据而不是重定向，以避免浏览器跟随重定向
        return await file_routes.list_project_files(project_id)

    # 添加项目文件上传API端点 - 重定向到/api前缀的端点
    @app.post("/projects/{project_id}/files/upload")
    async def upload_project_file_redirect(
        project_id: str,
        file: UploadFile = File(...),
        process: bool = Form(True)
    ):
        """重定向到正确的API路径"""
        logger.info(f"重定向旧的文件上传请求到新API路径: 项目ID={project_id}, 文件名={file.filename}")
        # 重置文件流位置并调用新的处理函数
        await file.seek(0)
        return await file_routes.upload_file(project_id, file, process)

    # 添加项目文件删除API端点 - 重定向到/api前缀的端点
    @app.delete("/projects/{project_id}/files/{file_path:path}")
    async def delete_project_file_redirect(project_id: str, file_path: str):
        """重定向到正确的API路径"""
        logger.info(f"重定向旧的文件删除请求到新API路径: 项目ID={project_id}, 文件路径={file_path}")
        # 调用新的处理函数
        return await file_routes.delete_project_file_by_path(project_id, file_path)

    # 添加/file/* 到/api/file/* 的路由映射
    # 文件上传
    @app.post("/file/upload/{project_id}")
    async def file_upload_mapping(
        project_id: str,
        file: UploadFile = File(...),
        process: bool = Form(True)
    ):
        """映射/file/upload/到/api/file/upload/"""
        logger.info(f"映射/file/upload/请求到/api/file/upload/: 项目ID={project_id}, 文件名={file.filename}")
        try:
            # 重新定位文件指针到开始位置
            await file.seek(0)
            
            # 导入FileService并初始化
            from src.modules.file.file_processor_service import FileProcessorService
            file_service = FileProcessorService()
            
            # 直接调用服务的upload_file方法
            result = await file_service.upload_file(file, project_id, process)
            logger.info(f"文件上传成功: 文件ID={result.file_id}, 哈希值={result.file_id if result.file_id != 'error' else 'N/A'}")
            return result
            
        except Exception as e:
            logger.error(f"处理文件上传请求失败: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 导入正确的响应模型，确保错误情况下也返回一致的响应结构
            from src.shared.file.schemas import FileUploadResponse, FileProcessingStatusEnum
            return FileUploadResponse(
                file_id="error",
                filename=file.filename if file else "unknown",
                size=0,
                content_type=file.content_type if file else "application/octet-stream",
                upload_time=str(datetime.now()),
                task_id=None,
                status=FileProcessingStatusEnum.FAILED,
                exists=False
            )
    
    # 文件列表
    @app.get("/file/list/{project_id}")
    async def file_list_mapping(project_id: str):
        """映射/file/list/到/api/file/list/"""
        logger.info(f"映射/file/list/请求到/api/file/list/: 项目ID={project_id}")
        return await file_routes.list_project_files(project_id)
    
    # 文件状态
    @app.get("/file/status/{task_id}")
    async def file_status_mapping(task_id: str):
        """映射/file/status/到/api/file/status/"""
        logger.info(f"映射/file/status/请求到/api/file/status/: 任务ID={task_id}")
        return await file_routes.get_processing_status(task_id)
    
    # 文件信息
    @app.get("/file/info/{project_id}/{file_id}")
    async def file_info_mapping(project_id: str, file_id: str):
        """映射/file/info/到/api/file/info/"""
        logger.info(f"映射/file/info/请求到/api/file/info/: 项目ID={project_id}, 文件ID={file_id}")
        return await file_routes.get_file_info(project_id, file_id)
    
    # 文件删除
    @app.delete("/file/{project_id}/{file_hash}")
    async def file_delete_mapping(project_id: str, file_hash: str):
        """映射/file/{project_id}/{file_hash}到/api/file/{project_id}/{file_hash}"""
        logger.info(f"映射/file/删除请求到/api/file/: 项目ID={project_id}, 文件哈希={file_hash}")
        return await file_routes.delete_file(project_id, file_hash)

    # 预览Markdown文件
    @app.get("/file/preview/{project_id}/{file_hash}")
    async def preview_markdown_mapping(project_id: str, file_hash: str):
        """映射/file/preview/到/api/file/preview/"""
        logger.info(f"映射Markdown预览请求: 项目ID={project_id}, 文件哈希={file_hash}")
        return await file_routes.preview_markdown_content(project_id, file_hash)

    # 下载Markdown文件
    @app.get("/file/download/markdown/{project_id}/{file_hash}")
    async def download_markdown_mapping(project_id: str, file_hash: str):
        """映射/file/download/markdown/到/api/file/download/markdown/"""
        logger.info(f"映射Markdown下载请求: 项目ID={project_id}, 文件哈希={file_hash}")
        return await file_routes.download_markdown_content(project_id, file_hash)

    # 添加明确的API端点 - 项目文件列表
    @app.get("/api/projects/{project_id}/files")
    async def get_project_files_api(project_id: str):
        """获取项目文件列表"""
        try:
            logger.info(f"处理项目文件列表请求: 项目ID={project_id}")
            files = await file_routes.list_project_files(project_id)
            
            # 确保返回的是列表格式
            if not isinstance(files, list):
                logger.warning(f"文件列表不是数组格式: {type(files)}")
                files = []
            
            # 确保每个文件都有正确的状态信息
            for file in files:
                if 'status' not in file or not file['status']:
                    file['status'] = 'pending'
            
            logger.info(f"返回文件列表，数量: {len(files)}")
            return files
        except Exception as e:
            logger.error(f"获取项目文件列表失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取项目文件列表失败: {str(e)}")
    
    # 添加明确的API端点 - 项目文件上传
    @app.post("/api/projects/{project_id}/files")
    async def upload_project_file_api(
        project_id: str,
        file: UploadFile = File(...),
        process: bool = Form(True)
    ):
        """上传文件到项目"""
        try:
            logger.info(f"处理项目文件上传请求: 项目ID={project_id}, 文件名={file.filename}")
            
            # 调用上传文件处理函数
            result = await file_routes.upload_file(project_id, file, process)
            return result
        except Exception as e:
            logger.error(f"上传文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")
    
    # 添加明确的API端点 - 项目文件删除
    @app.delete("/api/projects/{project_id}/files/{file_path:path}")
    async def delete_project_file_api(project_id: str, file_path: str):
        """删除项目文件"""
        try:
            logger.info(f"处理项目文件删除请求: 项目ID={project_id}, 文件路径={file_path}")
            
            # 调用删除文件处理函数
            result = await file_routes.delete_project_file_by_path(project_id, file_path)
            return result
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
    
    # 健康检查 - 使用共享HealthChecker实现
    from src.shared.health_check import create_health_checker, register_health_routes
    
    health_checker = create_health_checker("file", "file_service_1")
    
    async def check_database_connection():
        """检查数据库连接"""
        try:
            database = FileServiceDatabase()
            await database.initialize()
            return True
        except Exception as e:
            logger.error(f"数据库连接检查失败: {str(e)}")
            return False
    
    async def check_storage_directory():
        """检查存储目录"""
        try:
            return os.path.exists(settings.storage_dir)
        except Exception as e:
            logger.error(f"存储目录检查失败: {str(e)}")
            return False
    
    # 配置健康检查项
    health_checker.add_check("database", check_database_connection, critical=True)
    health_checker.add_check("storage", check_storage_directory, critical=True)
    
    # 注册统一健康检查路由
    register_health_routes(app, health_checker)

    # 启动时执行的事件
    @app.on_event("startup")
    async def startup_event():
        """服务启动时执行"""
        logger.info("文件服务启动中...")
        
        try:
            # 初始化数据库表
            await init_database()
            logger.info("已初始化数据库表结构")
            
            # 确保存储目录存在
            if not os.path.exists(settings.storage_dir):
                os.makedirs(settings.storage_dir, exist_ok=True)
                logger.info(f"已创建存储目录: {settings.storage_dir}")
            else:
                logger.info(f"已确保存储目录存在: {settings.storage_dir}")
            
            # 注册服务到服务发现
            try:
                service_registry = ServiceRegistry()
                await service_registry.connect()
                
                service_id = await service_registry.register_service(
                    service_name="file",
                    host="localhost",
                    port=settings.port,
                    metadata={"version": "1.0.0"},
                    health_check_endpoint="/api/health"
                )
                logger.info(f"服务已注册到服务发现，ID: {service_id}")
                app.state.service_registry = service_registry
                app.state.service_id = service_id
            except Exception as e:
                logger.error(f"服务注册失败: {str(e)}")
                logger.error(traceback.format_exc())
                logger.warning("服务将以独立模式运行")
        except Exception as e:
            logger.error(f"服务启动失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    # 关闭时执行的事件
    @app.on_event("shutdown")
    async def shutdown_event():
        """服务关闭时执行"""
        logger.info("文件服务正在关闭...")
        
        try:
            # 注销服务
            if hasattr(app.state, "service_registry") and hasattr(app.state, "service_id"):
                service_registry = app.state.service_registry
                service_id = app.state.service_id
                
                if service_registry and service_id:
                    try:
                        await service_registry.deregister_service("file", service_id)
                        logger.info(f"服务已从服务发现注销，ID: {service_id}")
                    except Exception as e:
                        logger.error(f"服务注销失败: {str(e)}")
                        logger.error(traceback.format_exc())
            
            logger.info("文件服务已关闭")
        except Exception as e:
            logger.error(f"服务关闭过程中发生错误: {str(e)}")
            logger.error(traceback.format_exc())

    # 错误处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理器"""
        logger.error(f"全局异常: {str(exc)}")
        logger.error(traceback.format_exc())
        
        # 返回统一的错误响应
        return {
            "error": "服务器内部错误",
            "detail": str(exc),
            "timestamp": str(datetime.now())
        }

    # 创建文件处理服务实例
    from src.modules.file.file_processor_service import FileProcessorService
    file_service = FileProcessorService(settings.storage_dir)

    def get_file_service():
        """获取文件处理服务实例"""
        return file_service

    # 启动服务
    if __name__ == "__main__":
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=settings.port,
            reload=settings.debug,
            log_level="info"
        )

except Exception as e:
    logger.error(f"文件服务启动失败: {str(e)}")
    logger.error(traceback.format_exc())
    sys.exit(1) 