from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from src.database import Base
from typing import Dict, Any

class ChatHistory(Base):
    """聊天历史数据库模型，用于存储30天以上的归档消息"""
    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, index=True)
    project_id = Column(String, index=True)  # 移除外键引用
    user_id = Column(String, index=True)  # 用户ID
    role = Column(String, nullable=False)  # 消息角色: user, assistant
    content = Column(String, nullable=False)  # 消息内容
    timestamp = Column(DateTime, nullable=False, index=True)  # 时间戳
    meta_data = Column(JSON, nullable=True)  # 元数据，包含迁移信息等

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示形式"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "thinking": (self.meta_data or {}).get("thinking", ""),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "meta_data": self.meta_data or {}
        }
