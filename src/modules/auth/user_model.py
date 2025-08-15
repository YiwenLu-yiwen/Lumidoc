from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
import re

# 临时邮箱域名黑名单
TEMP_EMAIL_DOMAINS = {
    '10minutemail.com', 'temp-mail.org', 'guerrillamail.com', 'mailinator.com',
    'tempmail.net', 'throwaway.email', 'yopmail.com', 'maildrop.cc',
    'sharklasers.com', 'getnada.com', 'tempail.com', 'burnermail.io',
    '24-7temp.com', 'disposablemail.com', 'fakemail.net', 'mohmal.com',
    'emailtemporal.org', 'mytrashmail.com', 'tempinbox.com', 'dispostable.com',
    '33mail.com', 'e4ward.com', '20minutemail.com', 'fakeinbox.com',
    'temporaryforwarding.com', 'armyspy.com', 'cuvox.de', 'dayrep.com',
    'einrot.com', 'fleckens.hu', 'gustr.com', 'jourrapide.com',
    'rhyta.com', 'superrito.com', 'teleworm.us', 'quickemailverification.com'
}

class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=4, description="用户名至少4位")
    email: EmailStr = Field(..., description="邮箱地址（必填）")
    nickname: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    
    @validator('email')
    def validate_email(cls, v):
        """验证邮箱地址不能为临时邮箱"""
        if not v:
            raise ValueError('邮箱地址是必填项')
        
        # 提取域名
        email_domain = v.split('@')[-1].lower()
        
        # 检查是否在临时邮箱黑名单中
        if email_domain in TEMP_EMAIL_DOMAINS:
            raise ValueError(f'不允许使用临时邮箱地址：{email_domain}')
        
        # 检查是否为常见的临时邮箱模式
        temp_patterns = [
            r'.*temp.*',
            r'.*disposable.*',
            r'.*throw.*away.*',
            r'.*fake.*',
            r'.*trash.*',
            r'.*spam.*',
            r'.*guerrilla.*'
        ]
        
        for pattern in temp_patterns:
            if re.match(pattern, email_domain):
                raise ValueError(f'不允许使用临时邮箱地址：{email_domain}')
        
        return v

class UserCreate(UserBase):
    """用户创建模型"""
    password: str = Field(..., min_length=6, description="密码至少6位")

class UserUpdate(BaseModel):
    """用户更新模型"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime

class User(UserBase):
    """用户响应模型"""
    id: int
    nickname: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    } 