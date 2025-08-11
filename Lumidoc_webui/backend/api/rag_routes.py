import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, File, UploadFile, FastAPI
import httpx
from src.modules.config import settings
from .auth_routes import get_current_user
from src.shared.types.rag import (
    LightRAGQuery, LightRAGResponse, 
    LightRAGBuildRequest, LightRAGBuildResponse,
    LightRAGMode
)
from src.shared.types.response import ApiResponse
import sys
import os
import traceback
from src.shared.logger import get_logger
from src.database import get_db
from sqlalchemy.orm import Session
from ..api.services import file_service
from .project_routes import ensure_url_protocol
from src.shared.clients import default_lightrag_client as lightrag_service

# 创建FastAPI应用
app = FastAPI(
    title="RAG API",
    description="轻量级知识检索服务API",
    version="1.0.0"
)

# 创建路由
router = APIRouter(prefix="/api/projects", tags=["lightrag"])
logger = logging.getLogger(__name__)

# 获取RAG服务客户端
async def get_rag_service():
    """获取RAG服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

async def handle_service_response(response: httpx.Response, operation: str) -> Dict[str, Any]:
    """处理服务响应"""
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"{operation} failed: {response.status_code} - {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)

@router.post("/{project_id}/build", response_model=LightRAGBuildResponse)
async def build_rag(
    project_id: str,
    request: LightRAGBuildRequest,
    user=Depends(get_current_user),
    client=Depends(get_rag_service)
):
    """构建RAG索引"""
    logger.info(f"Building RAG index for project {project_id} for user {user.id}")
    try:
        response = await client.post(
            f"{ensure_url_protocol(settings.rag_service_url)}/build/{project_id}",
            json=request.dict()
        )
        return await handle_service_response(response, "Build RAG index")
    except Exception as e:
        logger.error(f"Failed to build RAG index: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/status", response_model=LightRAGBuildResponse)
async def get_rag_status(
    project_id: str,
    user=Depends(get_current_user),
    client=Depends(get_rag_service)
):
    """获取RAG构建状态"""
    logger.info(f"Getting RAG status for project {project_id} for user {user.id}")
    try:
        response = await client.get(
            f"{ensure_url_protocol(settings.rag_service_url)}/status/{project_id}"
        )
        return await handle_service_response(response, "Get RAG status")
    except Exception as e:
        logger.error(f"Failed to get RAG status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/files", response_model=List[str])
async def get_rag_files(
    project_id: str,
    user=Depends(get_current_user),
    client=Depends(get_rag_service)
):
    """获取RAG索引使用的文件列表"""
    logger.info(f"Getting RAG files for project {project_id} for user {user.id}")
    try:
        response = await client.get(
            f"{ensure_url_protocol(settings.rag_service_url)}/files/{project_id}"
        )
        return await handle_service_response(response, "Get RAG files")
    except Exception as e:
        logger.error(f"Failed to get RAG files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/query", response_model=LightRAGResponse)
async def query_rag(
    project_id: str,
    query: LightRAGQuery,
    user=Depends(get_current_user),
    client=Depends(get_rag_service)
):
    """查询RAG"""
    logger.info(f"Querying RAG for project {project_id} for user {user.id}")
    try:
        response = await client.post(
            f"{ensure_url_protocol(settings.rag_service_url)}/query/{project_id}",
            json=query.dict()
        )
        return await handle_service_response(response, "Query RAG")
    except Exception as e:
        logger.error(f"Failed to query RAG: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 注册路由
app.include_router(router) 