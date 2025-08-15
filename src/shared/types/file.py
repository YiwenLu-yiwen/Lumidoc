from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class FileStatus(str, Enum):
    """文件状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileProcessingStatus(str, Enum):
    """文件处理状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileInfo(BaseModel):
    """文件信息模型"""
    file_hash: str
    name: str
    path: str
    size: int
    type: str
    created_at: datetime
    updated_at: datetime
    status: str = "pending"
    metadata: Optional[Dict[str, Any]] = None


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    message: str
    file_hash: str
    task_id: Optional[str] = None


class FileProcessRequest(BaseModel):
    """文件处理请求模型"""
    file_path: str = Field(..., description="文件路径")
    project_id: str = Field(..., description="项目ID")
    options: Optional[Dict[str, Any]] = Field(None, description="处理选项")


class FileProcessingResponse(BaseModel):
    """文件处理响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: FileProcessingStatus = Field(..., description="处理状态")
    progress: float = Field(0.0, description="处理进度")
    message: str = Field(..., description="处理消息")
    result: Optional[Dict[str, Any]] = Field(None, description="处理结果")


class FileListResponse(BaseModel):
    """文件列表响应模型"""
    files: List[FileInfo] = Field(default_factory=list, description="文件列表")
    total: int = Field(0, description="总文件数")
    page: int = Field(1, description="当前页码")
    size: int = Field(10, description="每页大小")


class FileProcessingStatus(BaseModel):
    """文件处理状态"""
    status: str
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None 