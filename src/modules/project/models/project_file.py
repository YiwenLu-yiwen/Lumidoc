from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship
from src.database import Base

class ProjectFile(Base):
    """项目文件数据库模型"""
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name = Column(String(100), nullable=False)
    path = Column(String(255), nullable=False)
    size = Column(Integer)  # 允许为空
    type = Column(String(50))  # 允许为空
    file_metadata = Column(JSON)  # 允许为空

    # RAG处理状态相关字段
    rag_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    rag_processed_at = Column(DateTime)  # RAG处理完成时间
    rag_error_message = Column(String(500))  # RAG处理错误信息
    is_in_rag = Column(Boolean, default=False)  # 是否已添加到RAG知识库

    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now())

    # 定义关系
    project = relationship("Project", back_populates="files")
