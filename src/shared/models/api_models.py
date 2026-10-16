"""
API响应模型定义
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ApiResponse(BaseModel):
    """API响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
