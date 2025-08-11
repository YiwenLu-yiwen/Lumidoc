import os
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, BackgroundTasks, Path, Body, FastAPI
from fastapi.responses import FileResponse, JSONResponse
import httpx
import shutil
from pathlib import Path as PathLib
from src.modules.config import settings
from .auth_routes import get_current_user

from src.shared.types.file import FileInfo, FileUploadResponse, FileProcessingStatus
from src.shared.types.response import ApiResponse

# 创建FastAPI应用
app = FastAPI()

# 创建路由
router = APIRouter(prefix="/api/file", tags=["file"])
logger = logging.getLogger(__name__)

# 获取基础目录的函数
def get_base_dir() -> PathLib:
    return PathLib(__file__).resolve().parents[3]

# 获取项目目录的函数
def get_project_dir(project_id: str) -> PathLib:
    return PathLib(__file__).resolve().parents[3] / "backend" / "projects" / project_id

# 获取文件处理服务客户端
async def get_file_service():
    """获取文件处理服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

# 从服务实例获取文件服务URL
def get_file_service_url() -> str:
    """获取文件服务URL"""
    # 优先使用环境变量中的配置
    if hasattr(settings, 'file_service_url') and settings.file_service_url:
        return settings.file_service_url
    
    # 默认值
    return "http://localhost:5000"

# 处理服务响应的辅助函数
async def handle_service_response(response, operation_name):
    if response.status_code == 200:
        return response.json()
    logger.error(f"{operation_name} failed with status {response.status_code}: {response.text}")
    raise HTTPException(status_code=response.status_code, detail=response.text)

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    client=Depends(get_file_service)
):
    """上传文件"""
    logger.info(f"Uploading file {file.filename} for user {user.id}")
    try:
        files = {"file": (file.filename, file.file, file.content_type)}
        response = await client.post(
            f"{settings.file_service_url}/file/upload",
            files=files
        )
        return await handle_service_response(response, "Upload file")
    except Exception as e:
        logger.error(f"Failed to upload file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=List[FileInfo])
async def list_files(
    user=Depends(get_current_user),
    client=Depends(get_file_service)
):
    """获取文件列表"""
    logger.info(f"Listing files for user {user.id}")
    try:
        response = await client.get(
            f"{settings.file_service_url}/file/list"
        )
        return await handle_service_response(response, "List files")
    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{file_id}", response_model=FileProcessingStatus)
async def get_file_status(
    file_id: str,
    user=Depends(get_current_user),
    client=Depends(get_file_service)
):
    """获取文件处理状态"""
    logger.info(f"Getting status for file {file_id} for user {user.id}")
    try:
        response = await client.get(
            f"{settings.file_service_url}/file/status/{file_id}"
        )
        return await handle_service_response(response, "Get file status")
    except Exception as e:
        logger.error(f"Failed to get file status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{file_id}", response_model=ApiResponse)
async def delete_file(
    file_id: str,
    user=Depends(get_current_user),
    client=Depends(get_file_service)
):
    """删除文件"""
    logger.info(f"Deleting file {file_id} for user {user.id}")
    try:
        response = await client.delete(
            f"{settings.file_service_url}/file/{file_id}"
        )
        return await handle_service_response(response, "Delete file")
    except Exception as e:
        logger.error(f"Failed to delete file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 添加项目文件删除路由
@router.delete("/projects/{project_id}/files/{file_path:path}", response_model=ApiResponse)
async def delete_project_file(
    project_id: int,
    file_path: str,
    user=Depends(get_current_user),
    client=Depends(get_file_service)
):
    """删除项目文件"""
    from .services import file_service
    
    logger.info(f"删除项目{project_id}文件: {file_path}, 用户: {user.id}")
    try:
        # 从URL解码文件路径
        from urllib.parse import unquote
        try:
            decoded_path = unquote(file_path)
        except:
            decoded_path = file_path
            
        # 调用文件服务删除文件
        try:
            result = await file_service.delete(
                f"/projects/{project_id}/files/{decoded_path}"
            )
            
            logger.info(f"成功删除项目{project_id}文件: {decoded_path}")
            return ApiResponse(
                success=True,
                message=f"文件 {decoded_path} 删除成功",
                data=result
            )
        except httpx.HTTPStatusError as e:
            # 特殊处理404错误，将其视为成功（文件已不存在）
            if e.response.status_code == 404:
                logger.warning(f"文件不存在或已被删除: {decoded_path}")
                return ApiResponse(
                    success=True,
                    message=f"文件 {decoded_path} 已不存在或已被删除",
                    data={"file_path": decoded_path, "file_not_found": True}
                )
            else:
                # 其他HTTP错误正常抛出
                raise
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"删除项目文件失败: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_msg)

# 注册路由
app.include_router(router) 