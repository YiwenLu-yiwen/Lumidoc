"""
文件处理任务模块 - 重构版
所有实际处理逻辑已迁移到fileproc微服务
"""

import os
import asyncio
import hashlib
import json
import uuid
from typing import Dict, Any, Optional, List, Union, BinaryIO
from pathlib import Path
import time
import logging
import aiofiles
import traceback
from datetime import datetime

from .config.database import FileServiceDatabase
from src.shared.storage import get_storage
from src.shared.logger import get_logger
from src.shared.config import FileServiceSettings
from src.shared.service_discovery import ServiceClient, call_service
from src.shared.models.api_models import ApiResponse

# 设置日志
logger = logging.getLogger(__name__)

# 进行中的任务
_tasks = {}
_results = {}

def hash_content(content: Union[bytes, str]) -> str:
    """计算内容哈希值"""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()[:16]  # 使用前16个字符足够识别

async def process_file(
    file_content: Union[bytes, BinaryIO],
    file_hash: str,
    original_filename: str,
    content_type: str,
    project_id: str
) -> str:
    """
    处理文件 - 创建任务并提交给fileproc服务
    
    Args:
        file_content: 文件内容或文件对象
        file_hash: 文件哈希
        original_filename: 原始文件名
        content_type: 文件类型
        project_id: 项目ID
        
    Returns:
        str: 任务ID
    """
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 创建任务状态
    _tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "任务已创建，等待处理",
        "timestamp": time.time()
    }
    
    # 创建异步任务
    asyncio.create_task(
        _process_file_async(
            task_id=task_id,
            file_content=file_content,
            file_hash=file_hash,
            original_filename=original_filename,
            content_type=content_type,
            project_id=project_id
        )
    )
    
    return task_id

async def _process_file_async(
    task_id: str,
    file_content: Union[bytes, BinaryIO],
    file_hash: str,
    original_filename: str,
    content_type: str,
    project_id: str
) -> None:
    """
    异步处理文件的实际任务 - 保存文件并提交处理请求到fileproc服务
    
    Args:
        task_id: 任务ID
        file_content: 文件内容或文件对象
        file_hash: 文件哈希
        original_filename: 原始文件名
        content_type: 文件类型
        project_id: 项目ID
    """
    temp_file_path = None
    try:
        # 更新任务状态
        _tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "message": "正在保存文件",
            "timestamp": time.time()
        }
        
        # 获取存储系统
        storage = await get_storage(directory_type="upload")
        
        # 确保是字节内容
        if not isinstance(file_content, bytes):
            if hasattr(file_content, 'read'):
                file_content = file_content.read()
                if isinstance(file_content, str):
                    file_content = file_content.encode('utf-8')
            
        # 更新进度
        _tasks[task_id]["progress"] = 30
        _tasks[task_id]["message"] = "文件已保存，准备提交处理"
        
        # 创建临时文件以供处理
        settings = FileServiceSettings()
        temp_dir = Path(settings.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        file_extension = Path(original_filename).suffix
        temp_file_path = temp_dir / f"{file_hash}{file_extension}"
        with open(temp_file_path, 'wb') as f:
            f.write(file_content)
        
        # 更新进度
        _tasks[task_id]["progress"] = 50
        _tasks[task_id]["message"] = "提交到fileproc服务处理"
        
        # 提交到fileproc服务处理
        response = await call_service(
            service_name="fileproc",
            endpoint=f"process/{file_hash}",
            method="POST",
            data={"project_id": project_id}
        )
        
        if not response or not response.get("success", False):
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["message"] = f"提交处理失败: {response.get('error', '未知错误')}"
            logger.error(f"提交fileproc处理失败: {response}")
            return
            
        fileproc_task_id = response.get("task_id")
        
        # 更新任务状态
        _tasks[task_id]["status"] = "submitted"
        _tasks[task_id]["progress"] = 80
        _tasks[task_id]["message"] = f"文件已提交到fileproc服务处理，任务ID: {fileproc_task_id}"
        _tasks[task_id]["fileproc_task_id"] = fileproc_task_id
        
        # 更新数据库中的任务ID映射
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE project_files 
                SET processing_task_id = $1, status = 'processing' 
                WHERE project_id = $2 AND file_hash = $3
                """,
                fileproc_task_id, project_id, file_hash
            )
        
        # 清理临时文件
        if temp_file_path and temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
                
    except Exception as e:
        logger.error(f"处理文件失败: {str(e)}")
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["message"] = f"处理失败: {str(e)}"
        
        # 尝试清理临时文件
        if temp_file_path and temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except:
                pass

async def get_task_progress(task_id: str) -> Dict[str, Any]:
    """
    获取任务进度
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict[str, Any]: 任务进度信息
    """
    task_info = _tasks.get(task_id, {})
    
    # 如果任务已提交到fileproc服务，则查询fileproc服务获取最新状态
    if task_info and task_info.get("status") == "submitted":
        fileproc_task_id = task_info.get("fileproc_task_id")
        if fileproc_task_id:
            try:
                # 查询fileproc任务状态
                status_response = await call_service(
                    service_name="fileproc",
                    endpoint=f"api/status/{fileproc_task_id}",
                    method="GET",
                    # 添加cache busting参数避免缓存
                    params={"_cb": int(time.time() * 1000)}
                )
                
                if status_response:
                    logger.info(f"从fileproc获取到任务状态: {fileproc_task_id} -> {status_response}")
                    
                    # 获取状态信息
                    status = status_response.get("status", "unknown")
                    progress = status_response.get("progress", 0)
                    message = status_response.get("message", "")
                    
                    # 如果状态为completed或failed，同步更新本地状态
                    if status in ["completed", "failed"]:
                        # 更新本地任务状态
                        _tasks[task_id] = {
                            "status": status,
                            "progress": 100,
                            "message": message,
                            "fileproc_task_id": fileproc_task_id,
                            "timestamp": time.time(),
                            "updated_at": datetime.now().isoformat()
                        }
                        
                        # 同步更新数据库中的文件状态
                        try:
                            # 获取文件哈希和项目ID
                            pool = await FileServiceDatabase.get_pool()
                            async with pool.acquire() as conn:
                                # 查询与任务关联的文件
                                file_record = await conn.fetchrow(
                                    """
                                    SELECT file_hash, project_id FROM project_files
                                    WHERE processing_task_id = $1
                                    """,
                                    fileproc_task_id
                                )
                                
                                if file_record:
                                    file_hash = file_record["file_hash"]
                                    project_id = file_record["project_id"]
                                    
                                    # 更新文件状态
                                    await conn.execute(
                                        """
                                        UPDATE project_files
                                        SET status = $3, processed_at = NOW()
                                        WHERE file_hash = $1 AND project_id = $2
                                        """,
                                        file_hash, project_id, status
                                    )
                                    
                                    logger.info(f"已同步更新文件状态: file_hash={file_hash}, project_id={project_id}, status={status}")
                        except Exception as db_err:
                            logger.error(f"更新文件状态失败: {str(db_err)}")
                            logger.error(traceback.format_exc())
                    
                    # 更新并返回最新状态
                    return {
                        "task_id": task_id,
                        "fileproc_task_id": fileproc_task_id,
                        "status": status,
                        "progress": progress,
                        "message": message
                    }
            except Exception as e:
                logger.error(f"获取fileproc任务状态失败: {str(e)}")
                logger.error(traceback.format_exc())
    
    # 如果没有提交到fileproc或查询失败，返回本地状态
    if not task_info:
        return {
            "task_id": task_id,
            "status": "not_found",
            "progress": 0,
            "message": "任务不存在"
        }
    
    return {
        "task_id": task_id,
        "status": task_info.get("status", "unknown"),
        "progress": task_info.get("progress", 0),
        "message": task_info.get("message", "")
    }

async def get_task_result(task_id: str) -> Dict[str, Any]:
    """
    获取任务结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        Dict[str, Any]: 任务结果
    """
    task_info = _tasks.get(task_id, {})
    
    # 如果任务已提交到fileproc服务，则查询fileproc服务获取结果
    if task_info and task_info.get("status") == "submitted":
        fileproc_task_id = task_info.get("fileproc_task_id")
        if fileproc_task_id:
            try:
                # 查询fileproc任务结果
                result_response = await call_service(
                    service_name="fileproc",
                    endpoint=f"result/{fileproc_task_id}",
                    method="GET"
                )
                
                if result_response:
                    # 缓存结果并返回
                    _results[task_id] = result_response
                    return result_response
            except Exception as e:
                logger.error(f"获取fileproc任务结果失败: {str(e)}")
    
    # 如果有缓存的结果，返回缓存结果
    result = _results.get(task_id)
    if result:
        return result
    
    # 否则返回基本状态信息
    if not task_info:
        return {
            "success": False,
            "task_id": task_id,
            "message": "任务不存在"
        }
    
    return {
        "success": task_info.get("status") == "completed",
        "task_id": task_id,
        "status": task_info.get("status", "unknown"),
        "message": task_info.get("message", "")
    }

def _get_file_type(filename: str) -> str:
    """
    根据文件名获取文件类型
    
    Args:
        filename: 文件名
        
    Returns:
        str: 文件类型
    """
    extension = Path(filename).suffix.lower()
    
    # 文本文件
    if extension in ['.txt', '.md', '.rst']:
        return 'text'
    # Markdown文件
    elif extension == '.md':
        return 'markdown'
    # Office文档
    elif extension in ['.doc', '.docx']:
        return 'word'
    elif extension in ['.xls', '.xlsx']:
        return 'excel'
    elif extension in ['.ppt', '.pptx']:
        return 'powerpoint'
    # PDF文件
    elif extension == '.pdf':
        return 'pdf'
    # 图片文件
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
        return 'image'
    # 代码文件
    elif extension in ['.py', '.js', '.java', '.c', '.cpp', '.h', '.html', '.css', '.php']:
        return 'code'
    # 默认类型
    else:
        return 'unknown' 