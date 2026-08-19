#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理服务诊断API路由
提供文件处理相关诊断功能的REST API
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional, List
import logging
import asyncio
from pydantic import BaseModel
import time

# 导入诊断服务
from ..services.diagnostics import FileServiceDiagnostics

# 创建日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
diagnostics_router = APIRouter(
    prefix="/diagnostics",
    tags=["diagnostics"],
    responses={404: {"description": "Not found"}},
)

# 定义请求模型
class DiagnosticRequest(BaseModel):
    """诊断请求模型"""
    project_id: Optional[str] = None
    components: Optional[List[str]] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "project_id": "project_123",
                "components": ["redis", "postgres", "storage", "system"]
            }
        }
    }

# 定义路由
@diagnostics_router.post("/run", response_model=Dict[str, Any])
async def run_diagnostics(request: DiagnosticRequest = Body(...)):
    """
    运行指定的诊断组件
    可以指定要诊断的组件，不指定则运行全部诊断
    """
    try:
        # 创建诊断工具实例
        diagnostics = FileServiceDiagnostics()
        
        # 确定要运行的诊断组件
        components = request.components or ["all"]
        results = {}
        
        if "all" in components or len(components) == 0:
            # 运行完整诊断
            results = await diagnostics.run_full_diagnostics(request.project_id)
        else:
            # 运行特定组件诊断
            if "redis" in components:
                results["redis_connection"] = await diagnostics.check_redis_connection()
            
            if "postgres" in components:
                results["postgres_connection"] = await diagnostics.check_postgres_connection()
                
            if "health" in components:
                # 使用服务发现获取服务URL
                file_service_url = await diagnostics.get_service_url("file")
                fileproc_service_url = await diagnostics.get_service_url("fileproc")
                
                results["file_service_health"] = await diagnostics.check_service_health(file_service_url)
                results["fileproc_service_health"] = await diagnostics.check_service_health(fileproc_service_url)
                
            if "storage" in components:
                results["directories"] = diagnostics.check_directories()
                
            if "system" in components:
                results["system_info"] = diagnostics.check_system_info()
                
            if "logs" in components:
                results["logs"] = await diagnostics.read_logs(50)
                
            if "upload" in components and request.project_id:
                results["file_upload_test"] = await diagnostics.test_file_upload(request.project_id)
                
            if "service_discovery" in components:
                results["service_discovery"] = await diagnostics.check_service_discovery()
        
        # 返回结果
        return {
            "success": True,
            "diagnostics": results,
            "timestamp": time.time()
        }
    
    except Exception as e:
        logger.error(f"运行诊断失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"诊断过程中发生错误: {str(e)}")

@diagnostics_router.get("/components", response_model=Dict[str, Any])
async def list_components():
    """列出可用的诊断组件"""
    components = {
        "redis": "检查Redis连接和服务注册状态",
        "postgres": "检查PostgreSQL连接和文件表状态",
        "health": "检查文件服务和处理服务的健康状态",
        "storage": "检查存储目录状态和权限",
        "system": "获取系统信息、GPU状态和Docling可用性",
        "logs": "读取服务日志",
        "upload": "测试文件上传功能(需要project_id)",
        "service_discovery": "检查服务发现功能",
        "all": "运行所有诊断"
    }
    
    return {
        "success": True,
        "components": components
    }

@diagnostics_router.get("/health", response_model=Dict[str, Any])
async def check_diagnostics_health():
    """诊断服务健康检查"""
    return {
        "success": True,
        "status": "ok",
        "service": "file_diagnostics"
    }

@diagnostics_router.get("/status", response_model=Dict[str, Any])
async def get_service_status():
    """获取服务状态概览"""
    try:
        diagnostics = FileServiceDiagnostics()
        
        # 使用服务发现获取服务URL
        file_service_url = await diagnostics.get_service_url("file")
        fileproc_service_url = await diagnostics.get_service_url("fileproc")
        
        # 并行运行基本检查
        file_health_task = asyncio.create_task(diagnostics.check_service_health(file_service_url))
        fileproc_health_task = asyncio.create_task(diagnostics.check_service_health(fileproc_service_url))
        redis_task = asyncio.create_task(diagnostics.check_redis_connection())
        postgres_task = asyncio.create_task(diagnostics.check_postgres_connection())
        
        # 同步运行目录检查
        dir_result = diagnostics.check_directories()
        sys_result = diagnostics.check_system_info()
        
        # 等待异步任务完成
        file_health = await file_health_task
        fileproc_health = await fileproc_health_task
        redis_result = await redis_task
        postgres_result = await postgres_task
        
        # 构建状态摘要
        status_summary = {
            "file_service": file_health["success"],
            "fileproc_service": fileproc_health["success"],
            "redis": redis_result["success"],
            "postgres": postgres_result["success"],
            "storage": dir_result["success"] if dir_result["success"] else False,
            "gpu_available": sys_result["system_info"]["gpu"]["available"] if sys_result["success"] else False,
            "docling_available": sys_result["system_info"]["docling"]["available"] if sys_result["success"] else False
        }
        
        # 计算整体健康度
        health_score = sum(1 for status in status_summary.values() if status) / len(status_summary) * 100
        
        return {
            "success": True,
            "status_summary": status_summary,
            "health_score": round(health_score, 2),
            "timestamp": time.time()
        }
    
    except Exception as e:
        logger.error(f"获取服务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")

@diagnostics_router.get("/services")
async def check_services():
    """检查相关服务的健康状态"""
    try:
        # 创建诊断实例
        diagnostics = FileServiceDiagnostics()
        
        # 使用服务发现获取服务URL
        file_service_url = await diagnostics.get_service_url("file")
        fileproc_service_url = await diagnostics.get_service_url("fileproc")
        
        # 检查服务健康状态
        results = {}
        results["file_service_health"] = await diagnostics.check_service_health(file_service_url)
        results["fileproc_service_health"] = await diagnostics.check_service_health(fileproc_service_url)
        
        return {
            "success": True,
            "timestamp": time.time(),
            "results": results
        }
    except Exception as e:
        logger.error(f"检查服务健康状态失败: {str(e)}")
        return {
            "success": False,
            "error": f"检查服务健康状态失败: {str(e)}"
        }

@diagnostics_router.get("/all")
async def run_full_diagnostics(project_id: Optional[str] = None):
    """运行完整诊断"""
    try:
        diagnostics = FileServiceDiagnostics()
        
        # 并行运行所有诊断任务
        system_task = asyncio.create_task(asyncio.to_thread(diagnostics.check_system_info))
        dirs_task = asyncio.create_task(asyncio.to_thread(diagnostics.check_directories))
        redis_task = asyncio.create_task(diagnostics.check_redis_connection())
        postgres_task = asyncio.create_task(diagnostics.check_postgres_connection())
        discovery_task = asyncio.create_task(diagnostics.check_service_discovery())
        
        # 使用服务发现获取服务URL
        file_service_url = await diagnostics.get_service_url("file")
        fileproc_service_url = await diagnostics.get_service_url("fileproc")
        
        file_health_task = asyncio.create_task(diagnostics.check_service_health(file_service_url))
        fileproc_health_task = asyncio.create_task(diagnostics.check_service_health(fileproc_service_url))
        
        logs_task = asyncio.create_task(diagnostics.read_logs())
        
        # 等待所有任务完成
        results = {}
        results["system_info"] = await system_task
        results["directories"] = await dirs_task
        results["redis_connection"] = await redis_task
        results["postgres_connection"] = await postgres_task
        results["service_discovery"] = await discovery_task
        results["file_service_health"] = await file_health_task
        results["fileproc_service_health"] = await fileproc_health_task
        results["logs"] = await logs_task
        
        # 如果提供了项目ID，测试文件上传
        if project_id:
            results["file_upload_test"] = await diagnostics.test_file_upload(project_id)
        
        return {
            "success": True,
            "timestamp": time.time(),
            "diagnostics": results
        }
    except Exception as e:
        logger.error(f"运行完整诊断失败: {str(e)}")
        return {
            "success": False,
            "error": f"运行诊断失败: {str(e)}"
        } 