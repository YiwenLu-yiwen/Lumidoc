from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from src.database import Base

class ChatMessage(Base):
    """聊天消息数据库模型"""
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id = Column(Integer)  # 允许为空
    content = Column(String, nullable=False)
    is_user = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, nullable=False)
