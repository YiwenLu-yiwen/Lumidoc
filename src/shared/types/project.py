from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class ProjectStatus(str, Enum):
    """项目状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProjectBase(BaseModel):
    """项目基础模型"""
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    """项目创建模型"""
    pass


class ProjectUpdate(ProjectBase):
    """项目更新模型"""
    name: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectResponse(ProjectBase):
    """项目响应模型"""
    id: int
    status: ProjectStatus
    project_metadata: dict = {}
    created_at: str
    updated_at: Optional[str] = None

    model_config = {
        "from_attributes": True
    } 