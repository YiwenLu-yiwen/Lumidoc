from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from src.shared.time_utils import utc_now_naive

# 创建ORM基类
Base = declarative_base()

# 可以在这里定义项目相关的模型类
# 例如:
class Project(Base):
    """项目模型"""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    user_id = Column(Integer, nullable=False, index=True)  # 保持用户ID为整数
    status = Column(String(20), nullable=False, default='active')
    project_metadata = Column(JSON, nullable=False, default=dict)
    
    def __repr__(self):
        return f"<Project(id='{self.id}', name='{self.name}')>"
