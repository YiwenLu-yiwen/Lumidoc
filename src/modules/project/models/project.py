from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from src.database import Base
from src.shared.types.project import ProjectStatus
import uuid

class Project(Base):
    """项目数据库模型"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)  # 确保项目名称必填
    description = Column(Text, nullable=True)
    user_id = Column(Integer, nullable=False)  # 确保用户ID必填
    status = Column(String(20), default=ProjectStatus.ACTIVE.value, nullable=False)
    project_metadata = Column(JSONB, default={}, nullable=False)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)  # 确保有默认值且非空
    updated_at = Column(DateTime, onupdate=func.now())  # 允许为空

    # 关联文件
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    # 关联协作者
    collaborators = relationship("ProjectCollaborator", back_populates="project", cascade="all, delete-orphan")

class ProjectCollaborator(Base):
    """项目协作者模型 - 需要重建数据库表结构"""
    __tablename__ = "project_collaborators"

    # 注意：数据库中没有这些字段，需要通过迁移添加
    id = Column(Integer, primary_key=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, nullable=False)  # 去除外键约束
    role = Column(String, nullable=False)  # owner, editor, viewer
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)  # 确保有默认值且非空
    updated_at = Column(DateTime, onupdate=func.now())  # 允许为空

    # 定义关系
    project = relationship("Project", back_populates="collaborators")
