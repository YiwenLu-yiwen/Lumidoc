#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
项目服务入口
"""

import uvicorn
import sys
import os
import logging
from src.shared.logger import initialize_logging, get_logger
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socket
from contextlib import asynccontextmanager
from typing import List
from sqlalchemy.orm import Session
import traceback
from datetime import datetime

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 更新配置导入
from src.shared.config import ProjectServiceSettings
settings_base = ProjectServiceSettings()
from .config.config import settings
from src.modules.auth.dependencies import get_current_user
from src.database import get_db
from .models.project import Project as DBProject
from .project_service import ProjectPermissionResponse

# 导入服务发现和健康检查模块
from src.shared.service_discovery import service_registry
from src.shared.health_check import create_health_checker, register_health_routes
from src.shared.task_manager import task_manager

# 配置日志
initialize_logging("project_service")
logger = get_logger(__name__)

# 定义应用生命周期上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用启动和关闭时的生命周期钩子
    """
    service_id = None

    try:
        # 启动时执行
        logger.info("项目服务正在启动...")
        
        # 连接到Redis任务管理器
        await task_manager.connect()
        logger.info("任务管理器已连接")

        # 注册服务到服务发现
        service_id = await service_registry.register_service(
            service_name="project",
            host="localhost",
            port=settings.service_port,
            health_check_endpoint="/healthz",
            metadata={
                "version": settings.version,
                "environment": os.environ.get("ENVIRONMENT", "development")
            },
            endpoints={
                "api": "/api",
                "docs": "/docs"
            }
        )
        logger.info(f"服务已注册: ID={service_id}")

        yield
        
        # 关闭时执行
        logger.info("项目服务正在关闭...")

    except Exception as e:
        logger.error(f"启动时出错: {str(e)}")
        yield
    finally:
        # 清理资源
        if service_id:
            try:
                await service_registry.deregister_service("project", service_id)
                logger.info("服务已注销")
            except Exception as e:
                logger.error(f"注销服务失败: {str(e)}")
        
        # 关闭连接
        await service_registry.close()
        await task_manager.close()
        logger.info("项目服务已关闭")

# 导入服务
from .project_service import router as project_router
from .project_service import permissions_router
from .project_service import health_router

# 创建健康检查器
health_checker = create_health_checker("project_service")

# 创建应用
app = FastAPI(
    title="STP项目服务",
    description="STP平台项目管理微服务",
    version=settings.version,
    lifespan=lifespan
)

# 添加Project特定的健康检查
async def check_database_connection():
    """检查数据库连接"""
    try:
        from src.database import get_db
        from sqlalchemy import text
        db_generator = get_db()
        db = next(db_generator)
        try:
            # 使用text()包装SQL语句
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False

async def check_task_manager():
    """检查任务管理器状态"""
    try:
        return task_manager.is_connected()
    except Exception as e:
        logger.error(f"任务管理器检查失败: {str(e)}")
        return False

# 配置健康检查项
health_checker.add_check("database", check_database_connection, critical=True)
health_checker.add_check("task_manager", check_task_manager, critical=True)

# 注册健康检查路由
register_health_routes(app, health_checker)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含项目API路由
app.include_router(project_router)
# 包含权限API路由
app.include_router(permissions_router)
# 包含健康检查路由
app.include_router(health_router, prefix="/api/projects")

# 添加用户权限路由处理
@permissions_router.get("/projects", response_model=List[ProjectPermissionResponse])
async def get_user_project_permissions(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的项目权限列表"""
    logger.info(f"获取用户 {user.id} 的项目权限列表")
    try:
        # 查询用户有权限访问的项目
        projects = []
        try:
            projects = db.query(DBProject).filter(DBProject.user_id == user.id).all()
        except Exception as db_error:
            logger.error(f"数据库查询失败: {str(db_error)}")
            logger.error(traceback.format_exc())
            # 数据库查询失败，返回空列表
            return []
        
        # 创建权限响应列表
        permissions = []
        for project in projects:
            try:
                permissions.append(ProjectPermissionResponse(
                    project_id=str(project.id),
                    access_level="owner"  # 用户自己创建的项目都是owner权限
                ))
            except Exception as item_error:
                logger.error(f"处理项目 {project.id} 权限时出错: {str(item_error)}")
                # 继续处理其他项目
                continue
        
        logger.info(f"找到用户 {user.id} 的项目权限: {len(permissions)} 条记录")
        return permissions
    except Exception as e:
        logger.error(f"获取用户项目权限失败: {str(e)}")
        logger.error(traceback.format_exc())
        # 返回空列表，而不是500错误
        return []

@app.get("/")
async def root():
    """根路由"""
    return {
        "service": "STP项目微服务",
        "version": settings.version,
        "status": "running"
    }

if __name__ == "__main__":
    print(f"启动项目管理服务 - 监听: 0.0.0.0:{settings.service_port}")
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)