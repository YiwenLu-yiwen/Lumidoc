#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理路由 - 负责文件处理相关API
遵循STP微服务架构原则，确保路由正确映射到处理服务
"""

import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..services.task_service import TaskService, task_service
from ..services.file_processor import FileProcessor, file_processor
from src.shared.service_discovery import call_service
from src.shared.models.api_models import ApiResponse
from src.shared.models.health_models import HealthResponse, ServiceHealthCheck

# 创建路由器，统一API前缀
router = APIRouter(tags=["文件处理"])

# 导入摘要客户端
from src.modules.fileproc.services.summary_client import SummaryClient
summary_client = SummaryClient()

logger = logging.getLogger(__name__)

# 依赖项函数
def get_task_service():
    """获取任务服务实例"""
    return task_service
    
def get_file_processor():
    """获取文件处理器实例"""
    return file_processor

@router.get("/health")
async def health_check():
    """
    健康检查接口，检查服务及其依赖的健康状态
    
    Returns:
        Dict: 健康检查结果
    """
    from datetime import datetime
    
    dependencies_status = {}
    
    try:
        # 检查Redis队列健康状态（核心功能）
        redis_health = await get_task_service().check_redis_health()
        dependencies_status["redis"] = {
            "status": "ok" if redis_health else "error",
            "critical": True,  # 核心依赖
            "message": None if redis_health else "Redis连接失败"
        }
        
        # 检查文件处理器健康状态（核心功能）
        processor_health = await get_file_processor().check_storage_health()
        dependencies_status["storage"] = {
            "status": "ok" if processor_health else "error",
            "critical": True,  # 核心依赖
            "message": None if processor_health else "存储服务连接失败"
        }
        
        # 检查是否有任何核心服务不可用
        overall_status = ServiceHealthCheck.determine_status(dependencies_status)
        
        # 生成健康响应
        return HealthResponse(
            status=overall_status,
            service="fileproc", 
            version="1.0.0",
            checks=dependencies_status,
            detail="文件处理服务健康检查",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"健康检查错误: {str(e)}")
        return HealthResponse(
            status="error",
            service="fileproc",
            version="1.0.0",
            checks={"error": {"status": "error", "message": str(e), "critical": True}},
            detail=f"健康检查异常: {str(e)}",
            timestamp=datetime.now().isoformat()
        )

@router.post("/process")
async def process_file_task(task_data: Dict[str, Any] = Body(...)):
    """
    提交文件处理任务
    
    Args:
        task_data: 任务数据，包含任务ID、文件ID、文件路径等
        
    Returns:
        Dict: 处理任务信息
    """
    logger.info(f"接收到文件处理任务请求: task_id={task_data.get('task_id')}, file_id={task_data.get('file_id')}")
    
    # 确保任务服务已初始化
    if not get_task_service()._initialized:
        await get_task_service().initialize()
    
    return await get_task_service().submit_task_data(task_data)

@router.post("/process/{file_id}")
async def process_file(file_id: str, project_id: str = None):
    """
    提交文件处理请求
    
    Args:
        file_id: 文件ID
        project_id: 项目ID
        
    Returns:
        Dict: 处理任务信息
    """
    logger.info(f"接收到文件处理请求: file_id={file_id}, project_id={project_id}")
    return await get_task_service().submit_task(file_id, project_id)

@router.post("/process/{file_id}/ocr")
async def process_file_with_ocr(file_id: str, project_id: str = None):
    """
    提交文件OCR处理请求
    
    Args:
        file_id: 文件ID
        project_id: 项目ID
        
    Returns:
        Dict: 处理任务信息
    """
    logger.info(f"接收到文件OCR处理请求: file_id={file_id}, project_id={project_id}")
    return await get_task_service().submit_task(file_id, project_id)

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 任务状态
    """
    logger.info(f"获取任务状态: {task_id}")
    try:
        status_result = await get_task_service().get_task_status(task_id)
        
        # 记录任务状态日志，便于调试
        logger.info(f"任务状态结果: {task_id} -> {status_result}")
        
        # 如果没有获取到状态，返回明确的失败状态
        if not status_result:
            return {
                "status": "failed",
                "progress": 100,
                "message": "任务处理失败，请检查文件格式或重新上传",
                "task_id": task_id
            }
        
        return status_result
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        # 返回明确的失败状态，而不是抛出异常
        return {
            "status": "failed",
            "progress": 100,
            "message": f"获取任务状态失败: {str(e)}",
            "task_id": task_id
        }

@router.get("/result/{task_id}")
async def get_task_result(task_id: str):
    """
    获取任务结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 任务结果
    """
    return await get_task_service().get_task_result(task_id)

@router.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """
    取消处理任务
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict: 取消结果
    """
    return await get_task_service().cancel_task(task_id)

@router.post("/summary/generate")
async def generate_summary(content: str = Body(...), project_id: Optional[str] = None, file_hash: Optional[str] = None):
    """
    生成文档摘要
    
    Args:
        content: 文档内容
        project_id: 项目ID（可选）
        file_hash: 文件哈希（可选）
        
    Returns:
        Dict: 摘要结果
    """
    try:
        logger.info(f"接收到摘要生成请求: 内容长度={len(content)}, 项目ID={project_id}")
        
        # 检查摘要服务是否可用
        summary_health = await summary_client.check_health()
        if not summary_health:
            logger.warning("摘要服务不可用，返回降级响应")
            return {
                "success": False,
                "error": "摘要服务当前不可用",
                "message": "摘要服务暂时不可用，请稍后再试",
                "is_degraded": True,
                "summary": "摘要服务不可用，无法生成摘要"
            }
        
        # 摘要服务可用，调用生成摘要API
        result = await summary_client.generate_summary(content, project_id, file_hash)
        return result
    except Exception as e:
        logger.error(f"生成摘要失败: {str(e)}")
        return {
            "success": False,
            "error": f"摘要生成失败: {str(e)}",
            "message": "处理请求时发生错误",
            "is_degraded": True
        }

@router.get("/summary/{project_id}/{file_hash}")
async def get_document_summary(project_id: str, file_hash: str, regenerate: bool = False):
    """
    获取文档摘要
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希
        regenerate: 是否重新生成摘要
        
    Returns:
        Dict: 摘要结果
    """
    try:
        logger.info(f"获取文档摘要: 项目={project_id}, 文件={file_hash}, 重新生成={regenerate}")
        
        # 检查摘要服务是否可用
        summary_health = await summary_client.check_health()
        if not summary_health:
            logger.warning("摘要服务不可用，返回降级响应")
            return {
                "success": False,
                "error": "摘要服务当前不可用",
                "message": "摘要服务暂时不可用，请稍后再试",
                "is_degraded": True
            }
            
        # 摘要服务可用，调用获取摘要API
        result = await summary_client.get_document_summary(project_id, file_hash, regenerate)
        return result
    except Exception as e:
        logger.error(f"获取文档摘要失败: {str(e)}")
        return {
            "success": False,
            "error": f"获取摘要失败: {str(e)}",
            "message": "处理请求时发生错误",
            "is_degraded": True
        } 