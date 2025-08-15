"""
统一错误处理模块
提供标准化的错误类型和处理机制
"""

from .error_codes import ErrorCode
from .service_errors import ServiceError, NotFoundError, ValidationError, AuthenticationError, AuthorizationError
from .error_handlers import handle_service_error, register_error_handlers

__all__ = [
    'ErrorCode',
    'ServiceError',
    'NotFoundError',
    'ValidationError',
    'AuthenticationError',
    'AuthorizationError',
    'handle_service_error',
    'register_error_handlers'
] 