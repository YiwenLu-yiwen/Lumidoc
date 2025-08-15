from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, JSON
import uuid
from datetime import datetime

# 创建ORM基类
Base = declarative_base()

# 可以在这里定义项目相关的模型类
# 例如:
class Project(Base):
    """项目模型"""
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String(36), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    config = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<Project(id='{self.id}', name='{self.name}')>" 