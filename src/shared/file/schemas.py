"""
文件服务共享的数据模式定义
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class FileProcessingStatusEnum(str, Enum):
    """文件处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class FileUploadRequest(BaseModel):
    """文件上传请求"""
    project_id: str = Field(..., description="项目ID")
    process: bool = Field(True, description="是否立即处理文件")

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件ID(哈希值)")
    filename: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小(字节)")
    content_type: str = Field(..., description="文件MIME类型")
    upload_time: str = Field(..., description="上传时间")
    task_id: Optional[str] = Field(None, description="处理任务ID")
    status: FileProcessingStatusEnum = Field(FileProcessingStatusEnum.PENDING, description="处理状态")
    exists: bool = Field(False, description="文件是否已存在")
    success: bool = Field(True, description="上传是否成功")
    message: str = Field("文件上传成功", description="上传结果消息")
    file_hash: str = Field(..., description="文件内容哈希值")

class FileProcessingTask(BaseModel):
    """文件处理任务"""
    task_id: str = Field(..., description="任务ID")
    file_id: str = Field(..., description="文件ID")
    project_id: str = Field(..., description="项目ID")
    original_filename: str = Field(..., description="原始文件名")
    content_type: str = Field(..., description="文件MIME类型")
    temp_path: str = Field(..., description="临时文件路径")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    status: FileProcessingStatusEnum = Field(FileProcessingStatusEnum.PENDING, description="处理状态")
    error_message: Optional[str] = Field(None, description="错误信息")

class FileProcessingStatusResponse(BaseModel):
    """文件处理状态响应"""
    task_id: str
    file_id: str
    status: FileProcessingStatusEnum
    progress: float = Field(0.0, description="处理进度(0-100)")
    message: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None 