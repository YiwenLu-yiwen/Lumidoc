from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.database import Base

class QuestionBase(BaseModel):
    """题目基础模型"""
    content: str
    question_type: str
    difficulty: str
    options: Optional[List[str]] = None
    answer: str
    explanation: str
    source_content: str

class QuestionCreate(QuestionBase):
    """创建题目模型"""
    pass

class QuestionUpdate(BaseModel):
    """更新题目模型"""
    content: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None

class QuestionInDB(QuestionBase):
    """数据库中的题目模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Question(Base):
    """题目模型"""
    __tablename__ = "questions"

    id = Column(String(50), primary_key=True)
    set_id = Column(String(50), ForeignKey("question_sets.id"))
    type = Column(String(20))  # 题目类型：单选题、多选题、判断题
    difficulty = Column(Integer, default=1)  # 难度：1-3
    content = Column(Text)  # 题目内容
    options = Column(JSON, default=[])  # 选项（仅选择题有）
    answer = Column(Text)  # 正确答案
    explanation = Column(Text)  # 解析
    tags = Column(JSON, default=[])  # 知识点标签
    created_at = Column(DateTime, default=datetime.now)

    # 关联题集
    question_set = relationship("QuestionSet", back_populates="questions")

class QuestionGenerationRequest(BaseModel):
    """题目生成请求模型"""
    content: str
    num_questions: int
    question_type: str
    difficulty: str

class QuestionGenerationResponse(BaseModel):
    """题目生成响应模型"""
    questions: List[Question]
    status: str
    message: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

class QuestionSet(Base):
    """题集模型"""
    __tablename__ = "question_sets"

    id = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    meta_info = Column(JSON, default={})  # 将metadata改为meta_info，避免与SQLAlchemy保留字冲突

    # 关联题目
    questions = relationship("Question", back_populates="question_set", cascade="all, delete-orphan")
