"""
服务错误类定义
提供标准化的异常类层次结构
"""

from typing import Dict, Any, Optional
from .error_codes import ErrorCode

class ServiceError(Exception):
    """服务错误基类，所有业务错误都应继承此类"""
    
    def __init__(
        self, 
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR, 
        message: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None
    ):
        """
        初始化服务错误
        
        Args:
            code: 错误代码枚举
            message: 错误消息，如果为None则使用code的默认消息
            details: 错误详情，可包含额外上下文
        """
        self.code = code
        self.message = message or code.message
        self.details = details or {}
        
        # 构建完整的错误消息
        full_message = f"[{code.name}] {self.message}"
        if details:
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            full_message += f" - {detail_str}"
            
        super().__init__(full_message)
    
    @property
    def http_status(self) -> int:
        """返回对应的HTTP状态码"""
        return self.code.http_status
    
    def to_dict(self) -> Dict[str, Any]:
        """将错误转换为字典，用于API响应"""
        return {
            "error": {
                "code": self.code.value,
                "type": self.code.name,
                "message": self.message,
                "details": self.details
            }
        }


class NotFoundError(ServiceError):
    """资源未找到错误"""
    
    def __init__(self, resource_type: str, resource_id: Any, message: Optional[str] = None):
        """
        初始化未找到错误
        
        Args:
            resource_type: 资源类型
            resource_id: 资源标识
            message: 自定义错误消息
        """
        details = {
            "resource_type": resource_type,
            "resource_id": str(resource_id)
        }
        
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message or f"未找到{resource_type}: {resource_id}",
            details=details
        )


class ValidationError(ServiceError):
    """数据验证错误"""
    
    def __init__(self, field: Optional[str] = None, reason: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        初始化验证错误
        
        Args:
            field: 验证失败的字段
            reason: 验证失败原因
            details: 额外详情
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if reason:
            error_details["reason"] = reason
            
        message = "数据验证失败"
        if field and reason:
            message = f"字段 '{field}' 验证失败: {reason}"
        elif field:
            message = f"字段 '{field}' 验证失败"
        elif reason:
            message = f"验证失败: {reason}"
            
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            details=error_details
        )


class AuthenticationError(ServiceError):
    """认证错误"""
    
    def __init__(self, message: Optional[str] = None, reason: Optional[str] = None):
        """
        初始化认证错误
        
        Args:
            message: 自定义错误消息
            reason: 认证失败原因
        """
        details = {}
        if reason:
            details["reason"] = reason
            
        super().__init__(
            code=ErrorCode.AUTHENTICATION_FAILED,
            message=message or "认证失败",
            details=details
        )


class AuthorizationError(ServiceError):
    """授权错误"""
    
    def __init__(self, resource: Optional[str] = None, permission: Optional[str] = None, message: Optional[str] = None):
        """
        初始化授权错误
        
        Args:
            resource: 请求访问的资源
            permission: 需要的权限
            message: 自定义错误消息
        """
        details = {}
        if resource:
            details["resource"] = resource
        if permission:
            details["permission"] = permission
            
        default_message = "权限不足"
        if resource and permission:
            default_message = f"没有权限 '{permission}' 访问资源 '{resource}'"
        elif resource:
            default_message = f"没有权限访问资源 '{resource}'"
        elif permission:
            default_message = f"缺少权限 '{permission}'"
            
        super().__init__(
            code=ErrorCode.PERMISSION_DENIED,
            message=message or default_message,
            details=details
        ) 