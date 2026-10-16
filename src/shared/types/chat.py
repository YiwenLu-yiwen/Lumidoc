from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class ChatMessage(BaseModel):
    """聊天消息模型"""
    id: Optional[str] = None
    session_id: str = "legacy"
    role: str
    content: str
    timestamp: Optional[Union[float, str, datetime]] = None

    @field_validator('timestamp', mode='before')
    @classmethod
    def validate_timestamp(cls, v):
        """验证时间戳，支持字符串、datetime和数字类型"""
        if v is None:
            return v
        if isinstance(v, (float, int)):
            return v
        if isinstance(v, str):
            try:
                # 尝试转换为数字
                return float(v)
            except ValueError:
                # 如果无法转换为数字，保留字符串格式
                return v
        if isinstance(v, datetime):
            return v
        return v


class ChatSession(BaseModel):
    """聊天会话模型"""
    session_id: str
    project_id: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    graph_analysis: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """聊天请求模型"""
    content: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    use_stream: Optional[bool] = False
    model: Optional[str] = Field(
        None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:/-]+$"
    )


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    session_id: str


class GraphAnalysisRequest(BaseModel):
    """图谱分析请求模型"""
    query: str
    project_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
