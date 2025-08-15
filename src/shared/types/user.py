"""
共享的用户类型定义
"""

from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel

class User(BaseModel):
    """用户模型定义"""
    id: Union[int, str]  # 同时接受整数或字符串ID
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True
    }

# UserResponse 作为 User 的别名，保持兼容性
UserResponse = User

class UserCreate(BaseModel):
    """用户创建模型"""
    username: str
    password: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    
class UserUpdate(BaseModel):
    """用户更新模型"""
    email: Optional[str] = None
    nickname: Optional[str] = None
    password: Optional[str] = None 