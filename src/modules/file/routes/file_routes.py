from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException, Query, Header, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any, Union
import os
import logging
import urllib.parse
import traceback
from pydantic import BaseModel
from datetime import datetime
import io
import httpx

from ..file_processor_service import FileProcessorService as FileService  # 重命名导入以避免冲突
from ..config.database import FileServiceDatabase
from src.shared.file.schemas import FileUploadResponse
from src.shared.types.file import FileInfo
from src.shared.types.response import ApiResponse
from src.shared.service_discovery import call_service
from src.shared.auth import User
from src.shared.project_access import (
    require_project_access,
    require_project_access_dependency,
    require_service_access,
)

# 初始化日志
logger = logging.getLogger(__name__)

# 创建API路由组
router = APIRouter(
    prefix="/api/file",
    tags=["file"],
    responses={404: {"description": "Not found"}},
)

# 创建文件处理服务实例
file_service = FileService()

# 依赖项函数
def get_file_service():
    """获取文件服务实例"""
    return file_service

# 企业级认证依赖函数（支持查询参数token）
async def get_current_user_or_service_with_query(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> User:
    """
    企业级认证依赖函数，支持用户认证和服务间认证，支持从查询参数获取token
    
    Args:
        authorization: 认证头（可以是Bearer或Service格式）
        token: 查询参数中的token（用于iframe等场景）
        
    Returns:
        User: 用户对象
    """
    # 优先使用Header中的authorization，如果没有则尝试使用查询参数中的token
    auth_token = authorization
    if not auth_token and token:
        auth_token = f"Bearer {token}"
        logger.info("从查询参数获取认证令牌")
    
    if not auth_token:
        logger.warning("缺少认证令牌")
        raise HTTPException(status_code=401, detail="缺少认证令牌")
    
    try:
        # 检查是否是服务间调用
        if auth_token.startswith("Service "):
            service_token = auth_token.replace("Service ", "")
            expected_token = os.environ.get("SERVICE_AUTH_TOKEN")
            
            if not expected_token:
                logger.error("未配置服务间认证令牌")
                raise HTTPException(status_code=500, detail="服务配置错误")
            
            if service_token == expected_token:
                # 服务间认证成功，返回系统用户
                return User(
                    id=0,
                    username="system",
                    email="system@service.internal",
                    is_active=True,
                    is_superuser=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            else:
                logger.warning("服务间认证失败: 无效的服务令牌")
                raise HTTPException(status_code=401, detail="服务间认证失败")
        
        # 处理用户Bearer认证
        elif auth_token.startswith("Bearer "):
            token_value = auth_token.replace("Bearer ", "")
            
            # 调用认证服务验证令牌
            auth_service_url = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8007")
            verify_url = f"{auth_service_url}/api/verify"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    verify_url,
                    headers={"Authorization": f"Bearer {token_value}"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"认证服务返回数据: {user_data}")
                    
                    # 处理认证服务返回的数据格式差异
                    user_id = user_data.get("id") or user_data.get("user_id")
                    username = user_data.get("username")
                    email = user_data.get("email") or f"{username}@local.user"  # 为没有email的用户生成默认email
                    
                    logger.info(f"处理后的用户数据: id={user_id}, username={username}, email={email}")
                    
                    return User(
                        id=user_id,
                        username=username,
                        email=email,
                        is_active=user_data.get("is_active", True),
                        is_superuser=user_data.get("is_superuser", False),
                        created_at=datetime.fromisoformat(user_data.get("created_at")) if user_data.get("created_at") else datetime.now(),
                        updated_at=datetime.fromisoformat(user_data.get("updated_at")) if user_data.get("updated_at") else datetime.now()
                    )
                else:
                    logger.warning(f"用户认证失败: {response.status_code}")
                    raise HTTPException(status_code=401, detail="认证令牌无效")
        else:
            logger.warning("认证令牌格式错误")
            raise HTTPException(status_code=401, detail="认证令牌格式错误")
            
    except httpx.RequestError as e:
        logger.error(f"认证服务请求失败: {e}")
        raise HTTPException(status_code=500, detail="认证服务不可用")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"认证过程出错: {e}")
        raise HTTPException(status_code=500, detail="认证过程出错")

# 企业级认证依赖函数
async def get_current_user_or_service(
    authorization: Optional[str] = Header(None)
) -> User:
    """
    企业级认证依赖函数，支持用户认证和服务间认证
    
    Args:
        authorization: 认证头（可以是Bearer或Service格式）
        
    Returns:
        User: 用户对象
    """
    if not authorization:
        logger.warning("缺少认证令牌")
        raise HTTPException(status_code=401, detail="缺少认证令牌")
    
    try:
        # 检查是否是服务间调用
        if authorization.startswith("Service "):
            service_token = authorization.replace("Service ", "")
            expected_token = os.environ.get("SERVICE_AUTH_TOKEN")
            
            if not expected_token:
                logger.error("未配置服务间认证令牌")
                raise HTTPException(status_code=500, detail="服务配置错误")
            
            if service_token == expected_token:
                # 服务间认证成功，返回系统用户
                return User(
                    id=0,
                    username="system",
                    email="system@service.internal",
                    is_active=True,
                    is_superuser=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
            else:
                logger.warning("服务间认证失败: 无效的服务令牌")
                raise HTTPException(status_code=401, detail="无效的服务令牌")
        
        # 用户JWT认证
        elif authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
            
            # 调用认证服务验证token
            from src.shared.service_client import ServiceClient
            client = ServiceClient()
            
            try:
                # 使用GET方法和Authorization头验证token
                auth_response = await client.call_service(
                    service_name="auth",
                    endpoint="/api/verify",
                    method="GET",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if not auth_response:
                    logger.warning("认证服务无响应")
                    raise HTTPException(status_code=401, detail="认证服务无响应")
                
                # 检查认证结果
                if not auth_response.get("valid"):
                    logger.warning("JWT令牌验证失败")
                    raise HTTPException(status_code=401, detail="JWT令牌验证失败")
                
                # 构造用户对象
                user_id = auth_response.get("user_id")
                username = auth_response.get("username")
                
                if not user_id:
                    logger.warning("JWT令牌验证成功但用户ID无效")
                    raise HTTPException(status_code=401, detail="用户信息无效")
                
                return User(
                    id=user_id,
                    username=username or str(user_id),
                    email=f"{username}@example.com" if username else f"user{user_id}@example.com",
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                
            except HTTPException:
                raise
            except Exception as auth_error:
                logger.error(f"认证服务调用失败: {str(auth_error)}")
                raise HTTPException(status_code=401, detail="认证服务不可用")
        
        else:
            logger.warning("无效的认证格式")
            raise HTTPException(status_code=401, detail="无效的认证格式")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"认证失败: {str(e)}")
        raise HTTPException(status_code=401, detail="认证失败")

# 内容注册模型
class ContentRegisterModel(BaseModel):
    file_hash: str
    markdown_content: str
    metadata: Union[str, Dict[str, Any]]
    file_type: str
    page_count: int = 1

# 文件状态更新模型
class FileStatusUpdateModel(BaseModel):
    file_hash: str
    project_id: str
    status: str

# 项目文件记录创建模型
class FileRecordCreateModel(BaseModel):
    file_hash: str
    project_id: str
    name: str
    path: str
    size: int
    type: str
    status: str = "processing"

# 添加批量删除文件的请求模型
class BatchDeleteModel(BaseModel):
    project_id: str
    file_hashes: List[str]

# RAG文件添加请求模型
class AddToRagModel(BaseModel):
    project_id: str
    file_hash: str

# 添加到RAG的响应模型
class AddToRagResponse(BaseModel):
    success: bool
    message: str
    file_hash: str
    status: str

# 修改项目相关路由，确保使用/api/projects前缀
@router.post(
    "/upload/{project_id}",
    response_model=FileUploadResponse,
    dependencies=[Depends(require_project_access_dependency)],
)
async def upload_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    process: bool = Form(True)
):
    """
    上传文件并可选择立即处理
    
    Args:
        project_id: 项目ID
        file: 上传的文件
        process: 是否立即处理文件
        
    Returns:
        FileUploadResponse: 上传响应
    """
    return await file_service.upload_file(file, project_id, process, request.headers.get("x-operation-id"))

@router.get("/status/{task_id}")
async def get_processing_status(task_id: str):
    """
    获取文件处理状态
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict[str, Any]: 处理状态信息
    """
    try:
        status = await file_service.get_processing_status(task_id)
        if not status:
            return {
                "status": "failed",
                "progress": 100,
                "message": "任务处理失败，请检查文件格式或重新上传",
                "task_id": task_id
            }
        return status
    except Exception as e:
        logger.error(f"获取文件处理状态失败: {str(e)}")
        return {
            "status": "failed",
            "progress": 100,
            "message": f"获取处理状态失败: {str(e)}",
            "task_id": task_id
        }

@router.post("/process/{file_id}")
async def submit_file_processing(
    file_id: str,
    project_id: str
):
    """
    提交文件处理请求
    
    Args:
        file_id: 文件ID
        project_id: 项目ID
        
    Returns:
        Dict[str, Any]: 处理任务信息
    """
    try:
        # 修改这里，直接使用file_service获取文件信息，不依赖Depends对象
        file_info = await file_service.get_file_info(project_id, file_id)
        if not file_info or not file_info.get("success", False):
            logger.warning(f"文件不存在: {file_id}, 项目ID: {project_id}")
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
        
        # 获取文件哈希值
        file_hash = file_info.get("file_hash")
        
        # 直接通过服务发现调用fileproc模块的处理API
        response = await call_service(
            service_name="fileproc",
            endpoint=f"api/process/{file_id}",
            method="POST",
            params={"project_id": project_id},
            use_service_auth=True
        )
        
        if not response or not response.get("success", False):
            logger.error(f"提交处理任务失败: {response}")
            raise HTTPException(status_code=500, detail="提交处理任务失败")
        
        task_id = response.get("task_id")
        
        # 更新数据库中的任务ID
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE project_files 
                SET processing_task_id = $1 
                WHERE id = $2 AND project_id::text = $3::text
                """,
                task_id, int(file_id), project_id
            )
        
        # 返回任务信息
        return {
            "success": True,
            "message": "文件处理任务已提交",
            "task_id": task_id,
            "file_id": file_id,
            "file_hash": file_hash
        }
        
    except HTTPException as ex:
        raise ex
    except Exception as e:
        logger.error(f"提交文件处理请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交处理任务失败: {str(e)}")

@router.get(
    "/list/{project_id}",
    response_model=List[FileInfo],
    dependencies=[Depends(require_project_access_dependency)],
)
async def list_project_files(project_id: str):
    """
    获取项目文件列表
    
    Args:
        project_id: 项目ID
        
    Returns:
        List[FileInfo]: 文件列表
    """
    try:
        files = await file_service.list_files(project_id)
        
        # 确保每个文件对象都包含必要的字段
        for file in files:
            # 确保name字段存在并优先使用原始文件名
            if "name" not in file or not file["name"]:
                file["name"] = file.get("filename", "未命名文件")
            elif "filename" in file and file["filename"]:
                # 如果有原始文件名，优先使用原始文件名
                file["name"] = file["filename"]
                
            # 确保type字段存在
            if "type" not in file or not file["type"]:
                file["type"] = file.get("file_type", file.get("content_type", "application/octet-stream"))
        
        return files
    except Exception as e:
        logger.error(f"获取项目文件列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取项目文件列表失败: {str(e)}")

# 添加兼容路由，支持前端使用的路径格式
@router.get(
    "/api/projects/{project_id}/files",
    response_model=List[FileInfo],
    dependencies=[Depends(require_project_access_dependency)],
)
async def list_project_files_compat(project_id: str):
    """
    获取项目文件列表（兼容前端路径格式）
    
    Args:
        project_id: 项目ID
        
    Returns:
        List[FileInfo]: 文件列表
    """
    return await list_project_files(project_id)

# Gateway转发路径现在在main.py中直接注册，避免路径冲突


@router.get(
    "/content/global/{content_hash}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_service_access)],
)
async def get_content_by_hash(content_hash: str):
    """
    通过哈希值获取文件内容

    Args:
        content_hash: 文件哈希值

    Returns:
        Dict[str, Any]: 文件内容
    """
    try:
        result = await file_service.get_content_by_hash(content_hash)
        if not result.get("success", False):
            # 不再直接抛出404错误，而是返回带有错误信息的响应
            return {
                "success": False,
                "message": result.get("message", "未找到文件内容"),
                "error": result.get("error", "文件内容不存在或尚未处理完成"),
                "file_hash": content_hash
            }
        return result
    except Exception as e:
        logger.error(f"获取文件内容失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"获取文件内容失败: {str(e)}",
            "error": str(e),
            "file_hash": content_hash
        }


@router.get(
    "/content/{project_id}/{file_hash}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_document_content(project_id: str, file_hash: str):
    """
    获取文档内容
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希值
        
    Returns:
        Dict[str, Any]: 文档内容
    """
    result = await file_service.get_document_content(project_id, file_hash)
    if not result.get("success", False):
        raise HTTPException(status_code=404, detail=result.get("message", "文档未找到"))
    return result

@router.get(
    "/preview/{project_id}/{file_hash}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def preview_markdown_content(project_id: str, file_hash: str):
    """
    预览处理后的Markdown文件内容
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希值
        
    Returns:
        Dict[str, Any]: 包含Markdown内容的响应
    """
    try:
        # 首先获取文件信息，确认文件存在
        file_info = await file_service.get_file_info(project_id, file_hash)
        if not file_info or not file_info.get("success", False):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 获取文件内容
        content = await file_service.get_file_content(file_hash)
        if not content:
            raise HTTPException(status_code=404, detail="文件内容不存在")
            
        # 获取文件名
        filename = file_info.get("filename", f"{file_hash}")
        
        # 返回包含内容的响应
        return {
            "success": True,
            "filename": filename,
            "file_hash": file_hash,
            "content": content,
            "content_type": "text/markdown"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览Markdown文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"预览Markdown文件失败: {str(e)}")

@router.get(
    "/download/markdown/{project_id}/{file_hash}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def download_markdown_content(project_id: str, file_hash: str):
    """
    下载处理后的文本文件
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希值
        
    Returns:
        StreamingResponse: 文本文件流
    """
    try:
        # 首先获取文件信息，确认文件存在
        file_info = await file_service.get_file_info(project_id, file_hash)
        if not file_info or not file_info.get("success", False):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 获取文件内容
        content = await file_service.get_file_content(file_hash)
        if not content:
            raise HTTPException(status_code=404, detail="文件内容不存在")
            
        # 获取文件名，现在应该使用txt格式
        filename = file_info.get("filename", f"{file_hash}.txt")
        if not filename.endswith(".txt"):
            # 如果文件名有其他扩展名，替换为.txt
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            filename = f"{base_name}.txt"
            
        # 创建响应
        return StreamingResponse(
            content=io.StringIO(content),
            media_type="text/plain",  # 修改为text/plain
            headers={
                "Content-Disposition": f'attachment; filename*=UTF-8\'\'{urllib.parse.quote(filename, safe="")}'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

@router.get(
    "/summary/{project_id}/{file_hash}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_document_summary(project_id: str, file_hash: str, regenerate: bool = False):
    """
    获取文档摘要
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希值
        regenerate: 是否重新生成摘要
        
    Returns:
        Dict[str, Any]: 文档摘要
    """
    try:
        # 调用fileproc服务获取摘要
        result = await call_service(
            service_name="fileproc",
            endpoint=f"summary/{project_id}/{file_hash}",
            method="GET",
            params={"regenerate": "true" if regenerate else "false"}
        )
        if not result or not result.get("success", False):
            raise HTTPException(status_code=404, detail=result.get("message", "获取摘要失败"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档摘要失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取摘要失败: {str(e)}")

@router.delete(
    "/{project_id}/{file_hash}",
    response_model=ApiResponse,
    dependencies=[Depends(require_project_access_dependency)],
)
async def delete_file(project_id: str, file_hash: str, request: Request):
    """
    删除文件
    
    Args:
        project_id: 项目ID
        file_hash: 文件哈希值
        
    Returns:
        ApiResponse: 删除结果
    """
    logger.info(f"接收到删除文件请求，项目ID: {project_id}, 文件哈希: {file_hash}")
    try:
        # 确保文件哈希值正确格式
        file_hash = file_hash.strip()
        project_id = project_id.strip()
        
        logger.info(f"开始删除文件，项目ID: {project_id}, 文件哈希: {file_hash}")
        result = await file_service.delete_file(file_hash, project_id, request.headers.get("x-operation-id"))
        
        # 即使文件不存在，也返回成功状态，避免前端显示错误
        logger.info(f"文件删除操作结果: {result}, 项目ID: {project_id}, 文件哈希: {file_hash}")
        return ApiResponse(
            success=True,
            message=f"文件删除成功: {file_hash}" if result else f"文件不存在或已删除: {file_hash}"
        )
    except Exception as e:
        logger.error(f"删除文件时发生错误: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="删除文件失败，请重试") from e

# 添加以项目文件路径格式直接删除文件的路由
@router.delete(
    "/projects/{project_id}/files/{file_path:path}",
    response_model=ApiResponse,
    dependencies=[Depends(require_project_access_dependency)],
)
async def delete_project_file_by_path(project_id: str, file_path: str, request: Request):
    """
    根据文件路径删除项目文件（支持WebUI调用格式）
    
    Args:
        project_id: 项目ID
        file_path: 文件路径（文件名）
        
    Returns:
        ApiResponse: 删除结果
    """
    logger.info(f"接收到删除项目文件请求，项目ID: {project_id}, 文件路径: {file_path}")
    try:
        # 将project_id转换为整数
        try:
            project_id_int = int(project_id)
            logger.info(f"项目ID转换为整数: {project_id_int}")
        except ValueError:
            logger.error(f"项目ID格式错误，无法转换为整数: {project_id}")
            return ApiResponse(
                success=False,
                message=f"项目ID格式错误，无法转换为整数: {project_id}",
                data={"project_id": project_id, "file_path": file_path}
            )
        
        # 处理URL编码问题 - 尝试解码文件路径
        try:
            # 先尝试解码一次，处理前端传来的已编码路径
            decoded_path = urllib.parse.unquote(file_path)
            # 如果解码后含有%，可能需要第二次解码
            if "%" in decoded_path:
                double_decoded = urllib.parse.unquote(decoded_path)
                logger.info(f"二次解码文件路径: {double_decoded}")
                decoded_path = double_decoded
            logger.info(f"解码后的文件路径: {decoded_path}")
        except Exception as e:
            logger.error(f"解码文件路径失败: {str(e)}")
            decoded_path = file_path  # 如果解码失败，使用原始路径
        
        # 处理Windows风格的路径（替换反斜杠为正斜杠）
        decoded_path = decoded_path.replace("\\", "/")
        
        # 提取基本文件名（不含路径）
        basic_filename = os.path.basename(decoded_path)
        logger.info(f"提取的基本文件名: {basic_filename}")
        
        # 尝试通过文件名从数据库检索对应的文件哈希
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 使用LIKE查询匹配文件名（不区分大小写）
            file_record = await conn.fetchrow(
                """
                SELECT file_hash, name FROM project_files 
                WHERE project_id = $1 AND (name = $2 OR name LIKE $2)
                """,
                project_id_int, basic_filename
            )
            
            if file_record:
                file_hash = file_record["file_hash"]
                file_name = file_record["name"]
                logger.info(f"通过name字段匹配到文件: {file_name}")
                logger.info(f"找到对应文件哈希: {file_hash}, 文件: {file_name}")
                
                # 使用文件处理服务删除文件
                result = await file_service.delete_file(file_hash, project_id, request.headers.get("x-operation-id"))
                
                if result:
                    logger.info(f"文件删除成功，项目ID: {project_id}, 文件: {file_name}")
                    return ApiResponse(
                        success=True,
                        message=f"文件删除成功: {file_name}",
                        data={"file_path": file_path, "project_id": project_id}
                    )
                else:
                    logger.warning(f"文件删除失败，项目ID: {project_id}, 文件: {file_name}")
                    # 返回友好的错误消息
                    return ApiResponse(
                        success=False,
                        message=f"文件删除失败: {file_name}",
                        data={"file_path": file_path, "project_id": project_id},
                        error="删除操作未成功完成"
                    )
            else:
                # 文件未找到
                logger.warning(f"文件不存在或匹配失败: {basic_filename}")
                return ApiResponse(
                    success=False,
                    message=f"找不到文件: {basic_filename}",
                    data={"file_path": file_path, "project_id": project_id},
                    error="文件不存在"
                )
    except Exception as e:
        error_msg = f"删除文件失败: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@router.get(
    "/info/{project_id}/{file_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_file_info(
    project_id: str,
    file_id: str,
    current_user: User = Depends(get_current_user_or_service),
    file_service: FileService = Depends(get_file_service)
):
    """
    获取文件信息
    """
    try:
        # 检查文件是否存在
        file_info = await file_service.get_file_info(project_id, file_id)
        
        if not file_info or not file_info.get("success", False):
            logger.warning(f"文件不存在: {file_id}, 项目ID: {project_id}")
            return {"success": False, "message": "文件不存在"}
            
        # 确保返回file_hash
        if "file_hash" not in file_info and "id" in file_info:
            file_info["file_hash"] = file_info["id"]
            
        return file_info
    except Exception as e:
        logger.error(f"获取文件信息失败: {str(e)}")
        return {"success": False, "message": f"获取文件信息失败: {str(e)}"}

@router.post("/batch-delete", response_model=ApiResponse)
async def batch_delete_files(
    data: BatchDeleteModel,
    request: Request,
):
    """
    批量删除文件
    
    Args:
        data: 包含项目ID和文件哈希列表的请求体
        
    Returns:
        ApiResponse: 删除结果
    """
    await require_project_access(request, data.project_id)
    logger.info(f"接收到批量删除请求，项目ID: {data.project_id}, 文件数量: {len(data.file_hashes)}")
    
    try:
        # 使用文件处理服务批量删除文件
        result = await file_service.batch_delete_files(data.project_id, data.file_hashes)
        
        return ApiResponse(
            success=result["success"],
            message=result["message"],
            data={
                "deleted": result["deleted"],
                "failed": result["failed"],
                "project_id": data.project_id
            }
        )
    except Exception as e:
        logger.error(f"批量删除文件过程中出错: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse(
            success=False,
            message="批量删除文件时发生错误",
            data={"project_id": data.project_id},
            error=str(e)
        )

@router.post(
    "/register/content",
    response_model=ApiResponse,
    dependencies=[Depends(require_service_access)],
)
async def register_file_content(
    content: ContentRegisterModel,
    current_user: User = Depends(get_current_user_or_service)
):
    """
    注册文件内容
    
    将文件的Markdown内容和元数据保存到数据库
    
    Args:
        content: 文件内容模型
    
    Returns:
        ApiResponse: API响应
    """
    try:
        result = await file_service.register_file_content(
            file_hash=content.file_hash,
            markdown_content=content.markdown_content,
            metadata=content.metadata,
            file_type=content.file_type,
            page_count=content.page_count
        )
        
        return ApiResponse(
            success=True,
            message="文件内容注册成功",
            data=result
        )
    except Exception as e:
        logger.error(f"文件内容注册失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse(
            success=False,
            message=f"文件内容注册失败: {str(e)}"
        )

@router.post(
    "/update/status",
    response_model=ApiResponse,
    dependencies=[Depends(require_service_access)],
)
async def update_file_status(
    status_update: FileStatusUpdateModel,
    current_user: User = Depends(get_current_user_or_service)
):
    """
    更新文件状态
    
    更新项目文件的状态
    
    Args:
        status_update: 文件状态更新模型
    
    Returns:
        ApiResponse: API响应
    """
    try:
        result = await file_service.update_file_status(
            file_hash=status_update.file_hash,
            project_id=status_update.project_id,
            status=status_update.status
        )
        
        return ApiResponse(
            success=True,
            message="文件状态更新成功",
            data=result
        )
    except Exception as e:
        logger.error(f"文件状态更新失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse(
            success=False,
            message=f"文件状态更新失败: {str(e)}"
        )

@router.post(
    "/create_record",
    response_model=ApiResponse,
    dependencies=[Depends(require_service_access)],
)
async def create_file_record(
    record: FileRecordCreateModel,
    current_user: User = Depends(get_current_user_or_service)
):
    """
    创建文件记录
    
    在project_files表中创建文件记录，用于关联file_contents表
    
    Args:
        record: 文件记录创建模型
    
    Returns:
        ApiResponse: API响应
    """
    try:
        logger.info(f"创建文件记录: file_hash={record.file_hash}, project_id={record.project_id}, name={record.name}")
        
        # 检查是否已存在
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                """
                SELECT COUNT(*) FROM project_files
                WHERE project_id = $1 AND file_hash = $2
                """,
                int(record.project_id), record.file_hash
            )
            
            if exists > 0:
                logger.info(f"文件记录已存在，无需创建: file_hash={record.file_hash}")
                return ApiResponse(
                    success=True,
                    message="文件记录已存在",
                    data={"file_hash": record.file_hash, "project_id": record.project_id}
                )
            
            # 创建新记录
            await conn.execute(
                """
                INSERT INTO project_files
                (project_id, name, path, size, type, file_hash, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                int(record.project_id), record.name, record.path, 
                record.size, record.type, record.file_hash, record.status
            )
            
            logger.info(f"文件记录已创建: file_hash={record.file_hash}")
            
            return ApiResponse(
                success=True,
                message="文件记录创建成功",
                data={
                    "file_hash": record.file_hash,
                    "project_id": record.project_id,
                    "name": record.name,
                    "status": record.status
                }
            )
    except Exception as e:
        logger.error(f"创建文件记录失败: {str(e)}")
        logger.error(traceback.format_exc())
        return ApiResponse(
            success=False,
            message=f"创建文件记录失败: {str(e)}"
        )

@router.get(
    "/list/pending",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_service_access)],
)
async def list_pending_files(
    current_user: User = Depends(get_current_user_or_service),
    file_service: FileService = Depends(get_file_service)
):
    """
    获取所有待处理状态的文件列表
    
    Returns:
        Dict[str, Any]: 包含待处理文件列表的响应
    """
    try:
        pending_files = await file_service.list_pending_files()
        return {
            "success": True,
            "files": pending_files,
            "total": len(pending_files)
        }
    except Exception as e:
        logger.error(f"获取待处理文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取待处理文件列表失败: {str(e)}")

# 添加文件到RAG的接口
@router.post("/add-to-rag", response_model=AddToRagResponse)
async def add_file_to_rag(
    data: AddToRagModel,
    request: Request,
    current_user: User = Depends(get_current_user_or_service),
):
    """
    将文件添加到RAG知识库
    
    Args:
        data: 包含项目ID和文件哈希的请求数据
        
    Returns:
        ApiResponse: 添加结果
    """
    try:
        await require_project_access(request, data.project_id)
        logger.info(f"添加文件到RAG: project_id={data.project_id}, file_hash={data.file_hash}")
        
        # 获取文件信息
        file_info = await file_service.get_file_info(data.project_id, data.file_hash)
        if not file_info or not file_info.get("success", False):
            logger.warning(f"文件不存在: {data.file_hash}, 项目ID: {data.project_id}")
            raise HTTPException(status_code=404, detail=f"文件不存在: {data.file_hash}")
        
        # 检查文件状态是否为completed或imported
        file_status = file_info.get("status", "")
        
        # 如果文件已经添加到RAG，返回成功
        if file_status == "imported":
            return AddToRagResponse(
                success=True,
                message="文件已经添加到RAG知识库",
                file_hash=data.file_hash,
                status="imported"
            )
        
        # 只有处理完成的文件才能添加到RAG
        if file_status != "completed":
            logger.warning(f"文件状态不是completed，无法添加到RAG: {data.file_hash}, 状态: {file_status}")
            raise HTTPException(
                status_code=400, 
                detail=f"只有处理完成的文件才能添加到RAG，当前状态: {file_status}"
            )
            
        # 获取文件内容
        try:
            content_response = await file_service.get_document_content(data.project_id, data.file_hash)
            
            # 提取实际的文件内容
            actual_content = ""
            if content_response and content_response.get("success"):
                data_field = content_response.get("data", {})
                actual_content = data_field.get("markdown_content", "")
            
            logger.info(f"获取到文件内容: 大小={len(actual_content)}")
        except Exception as content_err:
            logger.error(f"获取文件内容发生异常: {str(content_err)}")
            raise HTTPException(status_code=500, detail=f"获取文件内容失败: {str(content_err)}")
            
        if not actual_content:
            logger.warning(f"无法获取文件内容: {data.file_hash}")
            raise HTTPException(status_code=500, detail=f"无法获取文件内容: {data.file_hash}")
        
        # 准备文件元数据
        file_metadata = {
            "filename": file_info.get("filename", ""),
            "file_hash": data.file_hash,
            "project_id": data.project_id,
            "timestamp": datetime.now().isoformat(),
            "file_type": file_info.get("file_type", ""),
            "size": file_info.get("size", 0),
            "path": file_info.get("path", ""),  # 添加文件路径信息
            "storage_path": file_info.get("storage_path", "")  # 添加存储路径信息
        }
        
        # Step 1: 调用RAG服务插入文件内容
        logger.info(f"调用LightRAG服务插入文件: project_id={data.project_id}, file_hash={data.file_hash}")
        try:
            rag_response = await call_service(
                service_name="lightraglocal",
                endpoint="rag/insert",  # 确保使用正确的端点路径
                method="POST",
                json_data={
                    "project_id": data.project_id,
                    "content": actual_content,
                    "metadata": file_metadata
                }
            )
            logger.info(f"LightRAG服务响应: {rag_response}")
            
            # 检查响应是否表示服务发现失败
            if rag_response and not rag_response.get("success", False) and "无法获取服务URL" in str(rag_response.get("error", "")):
                logger.warning("服务发现失败，尝试直接调用LightRAG服务")
                raise Exception("Service discovery failed")
                
        except Exception as rag_err:
            logger.error(f"调用LightRAG服务失败: {str(rag_err)}", exc_info=True)
            # 严格遵循项目原则：所有服务间调用必须通过Gateway
            rag_response = {"success": False, "error": f"LightRAG服务调用失败: {str(rag_err)}"}
            # 尝试通过build_rag端点构建，这是一个备选方案
            try:
                logger.info("尝试通过build_rag端点构建RAG索引")
                rag_response = await call_service(
                    service_name="lightraglocal",
                    endpoint=f"rag/build/{data.project_id}",
                    method="POST",
                    json_data={
                        "selected_files": [data.file_hash]
                    }
                )
                logger.info(f"build_rag响应: {rag_response}")
            except Exception as build_err:
                logger.error(f"尝试build_rag也失败: {str(build_err)}")
                rag_response = {
                    "success": False, 
                    "error": f"调用RAG服务失败: {str(rag_err)}，备选方案也失败: {str(build_err)}"
                }
        
        if not rag_response or not rag_response.get("success", False):
            logger.error(f"RAG服务插入文件失败: {data.file_hash}, 错误: {rag_response.get('error', '未知错误')}")
            return AddToRagResponse(
                success=False,
                message=f"添加文件到RAG失败: {rag_response.get('error', '未知错误')}",
                file_hash=data.file_hash,
                status=file_status  # 保持原状态，允许重试
            )
        
        # Step 2: 使用LLM处理文件内容 - 从lightraglocal模块获取prompt
        llm_success = False
        graph_success = False
        error_message = ""
        
        try:
            # 导入LLM_SUMMARY_PROMPT
            from src.modules.lightraglocal.prompt import LLM_SUMMARY_PROMPT
            
            # 调用LLM服务进行处理
            llm_response = await call_service(
                service_name="llm",
                endpoint="generate",
                method="POST",
                json_data={
                    "text": actual_content,
                    "system_prompt": LLM_SUMMARY_PROMPT,
                    "project_id": data.project_id,
                    "file_id": data.file_hash
                }
            )
            
            if not llm_response or not llm_response.get("success", False):
                logger.warning(f"LLM处理文件内容失败: {data.file_hash}, 错误: {llm_response.get('error', '未知错误')}")
                error_message = f"LLM处理失败: {llm_response.get('error', '未知错误')}"
            else:
                llm_success = True
                summary = llm_response.get("summary", "")
                entities = llm_response.get("entities", [])
                relationships = llm_response.get("relationships", [])
                
                # Step 3: 将处理结果存入Neo4j
                try:
                    # 调用graph服务处理实体和关系
                    graph_data = {
                        "nodes": [],
                        "edges": []
                    }
                    
                    # 添加文档节点
                    document_node = {
                        "id": f"doc_{data.file_hash}",
                        "label": file_metadata.get("filename", "文档"),
                        "type": "document",
                        "properties": {
                            "file_hash": data.file_hash,
                            "summary": summary,
                            "project_id": data.project_id
                        }
                    }
                    graph_data["nodes"].append(document_node)
                    
                    # 添加实体节点和关系
                    for entity in entities:
                        entity_id = f"entity_{entity.get('id', datetime.now().timestamp())}"
                        entity_node = {
                            "id": entity_id,
                            "label": entity.get("name", "未命名实体"),
                            "type": entity.get("type", "unknown"),
                            "properties": {
                                "description": entity.get("description", ""),
                                "project_id": data.project_id
                            }
                        }
                        graph_data["nodes"].append(entity_node)
                        
                        # 添加文档到实体的关系
                        doc_entity_edge = {
                            "id": f"edge_{document_node['id']}_{entity_id}",
                            "source": document_node["id"],
                            "target": entity_id,
                            "label": "包含",
                            "properties": {
                                "project_id": data.project_id
                            }
                        }
                        graph_data["edges"].append(doc_entity_edge)
                    
                    # 添加实体间的关系
                    for rel in relationships:
                        source_id = f"entity_{rel.get('source_id')}"
                        target_id = f"entity_{rel.get('target_id')}"
                        rel_edge = {
                            "id": f"edge_{source_id}_{target_id}",
                            "source": source_id,
                            "target": target_id,
                            "label": rel.get("type", "关联"),
                            "properties": {
                                "description": rel.get("description", ""),
                                "strength": rel.get("strength", 1),
                                "project_id": data.project_id
                            }
                        }
                        graph_data["edges"].append(rel_edge)
                    
                    # 调用graph服务添加节点和边
                    graph_response = await call_service(
                        service_name="graph",
                        endpoint=f"project/{data.project_id}/add",
                        method="POST",
                        json_data=graph_data
                    )
                    
                    if not graph_response or not graph_response.get("success", False):
                        logger.warning(f"添加到知识图谱失败: {data.file_hash}, 错误: {graph_response.get('error', '未知错误')}")
                        error_message = f"知识图谱存储失败: {graph_response.get('error', '未知错误')}"
                    else:
                        graph_success = True
                
                except Exception as graph_err:
                    logger.error(f"知识图谱处理失败: {str(graph_err)}")
                    logger.error(traceback.format_exc())
                    error_message = f"知识图谱处理失败: {str(graph_err)}"
            
        except ImportError as e:
            logger.warning(f"无法导入LLM_SUMMARY_PROMPT: {str(e)}")
            error_message = f"无法导入LLM_SUMMARY_PROMPT: {str(e)}"
        except Exception as llm_err:
            logger.warning(f"LLM处理或Neo4j存储过程出错: {str(llm_err)}")
            logger.error(traceback.format_exc())
            error_message = f"LLM处理或Neo4j存储过程出错: {str(llm_err)}"
        
        # 如果RAG添加成功，但LLM处理或Neo4j存储失败，我们仍然认为基本功能成功了
        # 但返回的状态应该反映出部分失败
        if llm_success and graph_success:
            # 全部成功，更新文件状态为imported
            await file_service.update_file_status(data.file_hash, data.project_id, "imported")
            
            return AddToRagResponse(
                success=True,
                message="文件已成功添加到RAG知识库",
                file_hash=data.file_hash,
                status="imported"
            )
        else:
            # RAG添加成功但其他处理失败，仍然更新文件状态为imported
            # 因为文件已经被成功添加到RAG索引中
            await file_service.update_file_status(data.file_hash, data.project_id, "imported")
            
            return AddToRagResponse(
                success=True,
                message=f"文件已添加到RAG知识库，但后续处理出现问题: {error_message}",
                file_hash=data.file_hash,
                status="imported"  # 仍然设置为导入状态
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加文件到RAG失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"添加文件到RAG失败: {str(e)}")

# 处理无文件名的下载请求（返回错误）
@router.get(
    "/projects/{project_id}/files/download/",
    dependencies=[Depends(require_project_access_dependency)],
)
@router.head(
    "/projects/{project_id}/files/download/",
    dependencies=[Depends(require_project_access_dependency)],
)
async def download_no_filename(
    project_id: str,
    download: bool = Query(False), 
    preview: bool = Query(False),
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query)
):
    """
    处理没有提供文件名的下载请求
    
    Args:
        project_id: 项目ID
        download: 是否下载模式
        preview: 是否预览模式
        
    Returns:
        HTTPException: 400错误
    """
    logger.warning(f"下载请求缺少文件名参数: 项目ID={project_id}, 下载={download}, 预览={preview}")
    raise HTTPException(
        status_code=400, 
        detail="下载请求必须提供文件名。请使用格式: /projects/{project_id}/files/download/{filename}"
    )

# 新增: 项目文件下载API
@router.get(
    "/projects/{project_id}/files/download/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
@router.head(
    "/projects/{project_id}/files/download/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def download_file(
    project_id: str, 
    file_name: str, 
    download: bool = Query(False), 
    preview: bool = Query(False),
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query)
):
    """
    下载项目文件（支持MinIO存储）
    
    Args:
        project_id: 项目ID
        file_name: 文件名
        download: 是否下载模式
        
    Returns:
        StreamingResponse: 文件流
    """
    try:
        # URL解码文件名
        import urllib.parse
        decoded_file_name = urllib.parse.unquote(file_name)
        logger.info(f"原始文件名: {file_name}, 解码后: {decoded_file_name}")
        
        # 首先查找文件信息
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 查询文件记录，支持多种文件名匹配
            file_record = await conn.fetchrow(
                """
                SELECT * FROM project_files 
                WHERE project_id::text = $1::text AND (name = $2 OR name = $3 OR file_hash = $4 OR file_hash = $5)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                project_id, file_name, decoded_file_name, file_name, decoded_file_name
            )
            
            if not file_record:
                raise HTTPException(status_code=404, detail="文件不存在")
            
            # 获取存储配置
            storage_type = os.environ.get("STORAGE_TYPE", "local")
            
            if storage_type == "s3":
                # 使用MinIO/S3存储
                from src.shared.storage.storage_factory import get_storage
                
                # 获取upload目录的存储实例
                storage = await get_storage(directory_type="upload")
                
                # 构建MinIO中的文件路径
                file_hash = file_record['file_hash']
                file_extension = file_record.get('name', '').split('.')[-1] if '.' in file_record.get('name', '') else ''
                
                # 尝试多种可能的路径格式
                possible_paths = [
                    f"uploads/{project_id}/{file_hash}.{file_extension}" if file_extension else f"uploads/{project_id}/{file_hash}",
                    f"uploads/{project_id}/{file_hash}",
                    f"uploads/{file_hash}.{file_extension}" if file_extension else f"uploads/{file_hash}",
                    f"uploads/{file_hash}",
                    f"{file_hash}.{file_extension}" if file_extension else f"{file_hash}",
                    f"{file_hash}",
                    f"uploads/{file_record['name']}",
                    file_record['path']
                ]
                
                found_path = None
                for path in possible_paths:
                    if await storage.file_exists(path):
                        found_path = path
                        break
                
                if not found_path:
                    raise HTTPException(status_code=404, detail="文件在存储中不存在")
                
                minio_path = found_path
                
                # 从MinIO获取文件内容
                file_content = await storage.get_file(minio_path)
                
                # 获取文件信息
                file_type = file_record.get('type', 'application/octet-stream')
                display_name = file_record.get('name', file_name)
                
                # 创建文件流
                def file_generator():
                    if isinstance(file_content, str):
                        # 文本内容，转换为字节
                        yield file_content.encode('utf-8')
                    else:
                        # 二进制内容
                        if isinstance(file_content, bytes):
                            yield file_content
                        else:
                            # 文件对象
                            for chunk in file_content:
                                yield chunk
                
                # 设置响应头
                headers = {
                    "Accept-Ranges": "bytes"
                }
                
                import urllib.parse
                encoded_filename = urllib.parse.quote(display_name, safe='')
                
                if download:
                    headers["Content-Disposition"] = f'attachment; filename*=UTF-8\'\'{encoded_filename}'
                else:
                    headers["Content-Disposition"] = f'inline; filename*=UTF-8\'\'{encoded_filename}'
                
                return StreamingResponse(
                    file_generator(),
                    media_type=file_type,
                    headers=headers
                )
            
            else:
                # 使用本地文件系统（原有逻辑）
                file_path = file_record['path']
                if not file_path or not os.path.exists(file_path):
                    raise HTTPException(status_code=404, detail="文件不存在或已被删除")
                
                # 获取文件信息
                file_size = os.path.getsize(file_path)
                file_type = file_record.get('type', 'application/octet-stream')
                display_name = file_record.get('name', file_name)
                
                # 创建文件流
                def file_generator():
                    with open(file_path, "rb") as file:
                        yield from file
                
                # 设置响应头
                headers = {
                    "Content-Length": str(file_size),
                    "Accept-Ranges": "bytes"
                }
                
                import urllib.parse
                encoded_filename = urllib.parse.quote(display_name, safe='')
                
                if download:
                    headers["Content-Disposition"] = f'attachment; filename*=UTF-8\'\'{encoded_filename}'
                else:
                    headers["Content-Disposition"] = f'inline; filename*=UTF-8\'\'{encoded_filename}'
                
                return StreamingResponse(
                    file_generator(),
                    media_type=file_type,
                    headers=headers
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")

# 处理无文件名的内容请求（返回错误）
@router.get(
    "/projects/{project_id}/files/content/",
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_content_no_filename(
    project_id: str,
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query)
):
    """
    处理没有提供文件名的内容请求
    
    Args:
        project_id: 项目ID
        
    Returns:
        HTTPException: 400错误
    """
    logger.warning(f"内容请求缺少文件名参数: 项目ID={project_id}")
    raise HTTPException(
        status_code=400, 
        detail="内容请求必须提供文件名。请使用格式: /projects/{project_id}/files/content/{filename}"
    )

# 新增: 项目文件内容获取API
@router.get(
    "/projects/{project_id}/files/content/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_file_content(
    project_id: str, 
    file_name: str,
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query),
    processed_only: bool = False
):
    """
    获取项目文件的处理后内容（支持MinIO存储）
    
    Args:
        project_id: 项目ID
        file_name: 文件名
        
    Returns:
        Dict[str, Any]: 文件内容和元数据
    """
    try:
        # URL解码文件名
        import urllib.parse
        decoded_file_name = urllib.parse.unquote(file_name)
        logger.info(f"原始文件名: {file_name}, 解码后: {decoded_file_name}")
        
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 查询文件记录
            file_record = await conn.fetchrow(
                """
                SELECT * FROM project_files 
                WHERE project_id::text = $1::text AND (name = $2 OR name = $3 OR file_hash = $4 OR file_hash = $5)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                project_id, file_name, decoded_file_name, file_name, decoded_file_name
            )
            
            if not file_record:
                raise HTTPException(status_code=404, detail="文件不存在")
            
            file_hash = file_record['file_hash']
            
            # 首先尝试从数据库获取处理后的内容
            content_record = await conn.fetchrow(
                """
                SELECT markdown_content, metadata 
                FROM file_contents 
                WHERE file_hash = $1
                """,
                file_hash
            )
            
            if content_record and content_record['markdown_content']:
                return {
                    "success": True,
                    "content": content_record['markdown_content'],
                    "metadata": content_record.get('metadata'),
                    "file_type": "text/markdown",
                    "status": "processed"
                }
            
            # 如果数据库中没有，尝试从存储系统获取
            storage_type = os.environ.get("STORAGE_TYPE", "local")
            
            if storage_type == "s3":
                # 使用MinIO/S3存储
                from src.shared.storage.storage_factory import get_storage
                
                try:
                    # 首先尝试从content目录获取处理后的文件
                    content_storage = await get_storage(directory_type="content")
                    content_path = f"{file_hash}.txt"
                    
                    if await content_storage.file_exists(content_path):
                        content = await content_storage.get_file(content_path)
                        if isinstance(content, bytes):
                            content = content.decode("utf-8")
                        return {
                            "success": True,
                            "content": content,
                            "metadata": None,
                            "file_type": "text/markdown",
                            "status": "processed"
                        }
                    
                    if processed_only:
                        raise HTTPException(status_code=409, detail="文档处理结果尚未生成，请等待处理完成或重新上传失败文件")

                    # 如果没有处理后的内容，尝试获取原始文件
                    upload_storage = await get_storage(directory_type="upload")
                    
                    # 尝试多种可能的路径
                    file_extension = file_record.get('name', '').split('.')[-1] if '.' in file_record.get('name', '') else ''
                    possible_paths = [
                        f"uploads/{project_id}/{file_hash}.{file_extension}" if file_extension else f"uploads/{project_id}/{file_hash}",
                        f"uploads/{project_id}/{file_hash}",
                        f"uploads/{file_hash}.{file_extension}" if file_extension else f"uploads/{file_hash}",
                        f"uploads/{file_hash}",
                        f"{file_hash}.{file_extension}" if file_extension else f"{file_hash}",
                        f"{file_hash}",
                        f"uploads/{file_record['name']}",
                        file_record['path']
                    ]
                    
                    original_content = None
                    for path in possible_paths:
                        if await upload_storage.file_exists(path):
                            original_content = await upload_storage.get_file(path)
                            break
                    
                    if original_content:
                        # 检查文件类型，只返回文本类型的内容
                        file_type = file_record.get('type', '').lower()
                        if any(t in file_type for t in ['text/', 'application/json', 'application/xml', 'text/plain']):
                            if isinstance(original_content, bytes):
                                try:
                                    original_content = original_content.decode('utf-8')
                                except UnicodeDecodeError:
                                    original_content = original_content.decode('utf-8', errors='replace')
                            
                            return {
                                "success": True,
                                "content": original_content,
                                "metadata": None,
                                "file_type": file_type,
                                "status": "raw"
                            }
                        else:
                            raise HTTPException(status_code=400, detail="文件类型不支持内容预览")
                    else:
                        raise HTTPException(status_code=404, detail="文件在存储中不存在")
                        
                except HTTPException:
                    raise
                except Exception as storage_error:
                    logger.error(f"从存储系统获取文件内容失败: {str(storage_error)}")
                    raise HTTPException(status_code=500, detail=f"获取文件内容失败: {str(storage_error)}")
            
            else:
                if processed_only:
                    raise HTTPException(status_code=409, detail="文档处理结果尚未生成，请等待处理完成或重新上传失败文件")
                # 使用本地文件系统（原有逻辑）
                file_path = file_record.get('path')
                if file_path and os.path.exists(file_path):
                    # 读取文件内容（仅支持文本文件）
                    file_type = file_record.get('type', '').lower()
                    if any(t in file_type for t in ['text/', 'application/json', 'application/xml']):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        return {
                            "success": True,
                            "content": content,
                            "metadata": None,
                            "file_type": file_type,
                            "status": "raw"
                        }
                    else:
                        raise HTTPException(status_code=400, detail="文件类型不支持内容预览")
                else:
                    raise HTTPException(status_code=404, detail="文件内容不存在")
                        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件内容失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"获取文件内容失败: {str(e)}")

# 兼容路由：支持前端 /api/projects/{project_id}/files/content/{file_name} 格式
@router.get(
    "/api/projects/{project_id}/files/content/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def get_file_content_compat(
    project_id: str, 
    file_name: str,
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query)
):
    """
    获取项目文件的处理后内容（兼容前端路径格式）
    
    Args:
        project_id: 项目ID
        file_name: 文件名
        
    Returns:
        Dict[str, Any]: 文件内容和元数据
    """
    return await get_file_content(project_id, file_name, token, current_user)

# 兼容路由：支持前端 /api/projects/{project_id}/files/download/{file_name} 格式
@router.get(
    "/api/projects/{project_id}/files/download/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
@router.head(
    "/api/projects/{project_id}/files/download/{file_name:path}",
    dependencies=[Depends(require_project_access_dependency)],
)
async def download_file_compat(
    project_id: str, 
    file_name: str, 
    download: bool = Query(False), 
    preview: bool = Query(False),
    token: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_or_service_with_query)
):
    """
    下载项目文件（兼容前端路径格式）
    
    Args:
        project_id: 项目ID
        file_name: 文件名
        download: 是否下载模式
        
    Returns:
        StreamingResponse: 文件流
    """
    return await download_file(project_id, file_name, download, preview, token, current_user)
