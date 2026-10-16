from sqlalchemy import Column, Text, Boolean, DateTime, Integer
from sqlalchemy.sql import func, text
from src.database import Base

class User(Base):
    """用户数据库模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(Text, unique=True, index=True, nullable=False)
    username = Column(Text, unique=True, index=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    nickname = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, server_default=text('CURRENT_TIMESTAMP'), onupdate=func.now())
