from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union


class ApiResponse(BaseModel):
    """通用API响应模型"""
    success: bool
    message: Optional[str] = None
    data: Optional[Union[Dict[str, Any], List[Any], str, int, bool]] = None
    error: Optional[str] = None 