"""
文件上传服务实现
负责接收文件并将处理任务发送到队列
"""

import os
import logging
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import UploadFile, HTTPException
import aiofiles
import asyncio

from src.shared.utils.redis_queue import RedisQueue
from src.shared.file.schemas import (
    FileUploadResponse, 
    FileProcessingTask,
    FileProcessingStatusEnum,
    FileProcessingStatusResponse
)

logger = logging.getLogger(__name__)

# 默认上传目录
DEFAULT_UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads"))
# 文件处理队列名
FILE_PROCESSING_QUEUE = os.environ.get("FILE_PROCESSING_QUEUE", "file_processing")

class FileUploadService:
    """文件上传服务"""
    
    def __init__(self, upload_dir: Optional[Path] = None):
        """
        初始化文件上传服务
        
        Args:
            upload_dir: 上传文件存储目录
        """
        self.upload_dir = upload_dir or DEFAULT_UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.gettempdir()) / "file_uploads"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.queue_client = RedisQueue(queue_name=FILE_PROCESSING_QUEUE)
        
        logger.info(f"文件上传服务已初始化，上传目录: {self.upload_dir}")
        
    async def upload_and_queue(self, file: UploadFile, project_id: str, process: bool = True) -> FileUploadResponse:
        """
        上传文件并将处理任务加入队列
        
        Args:
            file: 上传的文件
            project_id: 项目ID
            process: 是否处理文件
            
        Returns:
            FileUploadResponse: 上传响应
        """
        try:
            # 生成文件ID
            file_id = str(uuid.uuid4())
            original_filename = file.filename
            content_type = file.content_type or "application/octet-stream"
            
            # 确保项目目录存在
            project_dir = self.upload_dir / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存到临时文件
            temp_file_path = self.temp_dir / f"{file_id}_{original_filename}"
            
            # 读取并写入文件内容
            content = await file.read()
            file_size = len(content)
            
            async with aiofiles.open(temp_file_path, 'wb') as f:
                await f.write(content)
                
            logger.info(f"文件已上传到临时位置: {temp_file_path}")
                
            # 如果不需要处理，直接返回
            task_id = None
            status = FileProcessingStatusEnum.PENDING
            
            if process:
                # 创建处理任务
                processing_task = FileProcessingTask(
                    task_id=str(uuid.uuid4()),
                    file_id=file_id,
                    project_id=project_id,
                    original_filename=original_filename,
                    content_type=content_type,
                    temp_path=str(temp_file_path),
                    status=FileProcessingStatusEnum.PENDING
                )
                
                # 将任务加入队列
                task_id = await self.queue_client.enqueue(processing_task.dict(), processing_task.task_id)
                logger.info(f"文件处理任务已入队: {task_id}")
            else:
                # 不处理，直接移动到上传目录
                target_path = project_dir / f"{file_id}_{original_filename}"
                temp_file_path.rename(target_path)
                logger.info(f"文件已保存(不处理): {target_path}")
                status = FileProcessingStatusEnum.COMPLETED
                
            # 构建响应
            response = FileUploadResponse(
                file_id=file_id,
                filename=original_filename,
                size=file_size,
                content_type=content_type,
                upload_time=str(asyncio.get_event_loop().time()),
                task_id=task_id,
                status=status
            )
            
            return response
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")
            
    async def get_task_status(self, task_id: str) -> FileProcessingStatusResponse:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            FileProcessingStatusResponse: 任务状态
        """
        try:
            # 从Redis获取任务状态
            task_data = await self.queue_client.get_task_status(task_id)
            
            if not task_data:
                raise HTTPException(status_code=404, detail=f"找不到任务: {task_id}")
                
            # 解析任务数据
            try:
                if isinstance(task_data.get("data"), str):
                    import json
                    task_data_parsed = json.loads(task_data.get("data", "{}"))
                else:
                    task_data_parsed = task_data.get("data", {})
            except Exception:
                task_data_parsed = {}
                
            # 构建响应
            file_id = task_data_parsed.get("file_id", "")
            status_str = task_data.get("status", "pending")
            
            # 转换状态
            try:
                status = FileProcessingStatusEnum(status_str)
            except ValueError:
                status = FileProcessingStatusEnum.PENDING
                
            # 计算进度
            progress = 0.0
            if status == FileProcessingStatusEnum.COMPLETED:
                progress = 100.0
            elif status == FileProcessingStatusEnum.PROCESSING:
                # 可以从任务数据中获取更精确的进度
                progress = float(task_data.get("progress", 0.0))
                
            # 获取错误信息
            error = task_data.get("error") if status == FileProcessingStatusEnum.FAILED else None
            
            # 完成时间
            completed_at = task_data.get("updated_at") if status in [FileProcessingStatusEnum.COMPLETED, FileProcessingStatusEnum.FAILED] else None
            
            return FileProcessingStatusResponse(
                task_id=task_id,
                file_id=file_id,
                status=status,
                progress=progress,
                message=task_data.get("message"),
                error=error,
                completed_at=completed_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")
            
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        取消处理任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 操作结果
        """
        try:
            # 检查任务状态
            task_data = await self.queue_client.get_task_status(task_id)
            
            if not task_data:
                raise HTTPException(status_code=404, detail=f"找不到任务: {task_id}")
                
            # 只能取消待处理或处理中的任务
            status = task_data.get("status")
            if status not in ["pending", "processing"]:
                return {
                    "success": False,
                    "message": f"无法取消状态为 {status} 的任务"
                }
                
            # 更新任务状态为已取消
            await self.queue_client.update_task_status(
                task_id=task_id,
                status="cancelled",
                error="任务已手动取消"
            )
            
            return {
                "success": True,
                "message": "任务已取消",
                "task_id": task_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}") 