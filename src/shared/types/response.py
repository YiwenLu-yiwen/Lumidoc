from pydantic import BaseModel
from typing import Any, Dict, Optional, List, Union, TypeVar, Generic

# 通用响应模型
class ApiResponse(BaseModel):
    """通用API响应模型"""
    success: bool
    message: Optional[str] = None
    data: Optional[Union[Dict[str, Any], List[Any], str, int, bool]] = None
    error: Optional[str] = None


# 错误响应模型
class ErrorResponse(BaseModel):
    """API错误响应模型"""
    success: bool = False
    error: str
    code: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


# 分页响应模型
T = TypeVar('T')
class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


class Response(BaseModel):
    """通用响应模型"""
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None 