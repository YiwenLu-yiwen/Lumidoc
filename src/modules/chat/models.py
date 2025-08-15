from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid
from datetime import datetime

Base = declarative_base()

class ChatHistory(Base):
    """聊天历史记录表"""
    __tablename__ = "chat_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    meta_data = Column(JSON, nullable=True)  # 可存储额外信息如模型名称、引用文档等
    
    def __repr__(self):
        return f"<ChatHistory(id='{self.id}', project_id='{self.project_id}', user_id='{self.user_id}')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "meta_data": self.meta_data
        } 