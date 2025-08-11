"""
错误处理器模块
提供FastAPI错误处理中间件和装饰器
"""

import logging
import traceback
from typing import Callable, Dict, Any, Type, Optional, TypeVar, Union, cast
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import os

from .error_codes import ErrorCode
from .service_errors import ServiceError, ValidationError

# 创建日志记录器
logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')

def handle_service_error(func: Callable[..., T]) -> Callable[..., T]:
    """
    函数装饰器，统一处理服务错误
    将捕获的异常转换为标准ServiceError
    
    Args:
        func: 要装饰的异步或同步函数
    
    Returns:
        装饰后的函数
    """
    import functools
    import inspect
    
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ServiceError:
            # 直接重新抛出已经是标准化的服务错误
            raise
        except (ValueError, TypeError) as e:
            # 转换为验证错误
            raise ValidationError(
                reason=str(e),
                details={"exception_type": e.__class__.__name__}
            )
        except Exception as e:
            # 其他异常转换为通用服务错误
            logger.error(f"服务错误: {str(e)}", exc_info=True)
            raise ServiceError(
                code=ErrorCode.UNKNOWN_ERROR,
                message=f"服务处理错误: {str(e)}",
                details={"exception_type": e.__class__.__name__}
            )
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ServiceError:
            # 直接重新抛出已经是标准化的服务错误
            raise
        except (ValueError, TypeError) as e:
            # 转换为验证错误
            raise ValidationError(
                reason=str(e),
                details={"exception_type": e.__class__.__name__}
            )
        except Exception as e:
            # 其他异常转换为通用服务错误
            logger.error(f"服务错误: {str(e)}", exc_info=True)
            raise ServiceError(
                code=ErrorCode.UNKNOWN_ERROR,
                message=f"服务处理错误: {str(e)}",
                details={"exception_type": e.__class__.__name__}
            )
    
    # 根据函数是否是协程函数选择不同的包装器
    if inspect.iscoroutinefunction(func):
        return cast(Callable[..., T], async_wrapper)
    else:
        return cast(Callable[..., T], sync_wrapper)


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    """
    ServiceError异常处理器
    将ServiceError转换为标准JSON响应
    
    Args:
        request: FastAPI请求对象
        exc: ServiceError异常
        
    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 记录错误日志
    log_level = logging.ERROR if exc.http_status >= 500 else logging.WARNING
    logger.log(
        log_level,
        f"服务错误: [{exc.code.name}] {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.http_status,
            "error_code": exc.code.value,
            "error_type": exc.code.name,
            "client_ip": request.client.host if request.client else None,
            "details": exc.details
        }
    )
    
    # 返回标准错误响应
    return JSONResponse(
        status_code=exc.http_status,
        content=exc.to_dict()
    )


async def validation_error_handler(request: Request, exc: Union[RequestValidationError, PydanticValidationError]) -> JSONResponse:
    """
    验证错误处理器
    处理FastAPI的RequestValidationError或Pydantic的ValidationError
    
    Args:
        request: FastAPI请求对象
        exc: 验证错误异常
        
    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 构建详细错误信息
    errors = []
    for error in exc.errors():
        location = error.get("loc", [])
        location_str = " -> ".join(str(loc) for loc in location if loc)
        errors.append({
            "field": location_str,
            "type": error.get("type"),
            "msg": error.get("msg")
        })
    
    # 记录错误日志
    logger.warning(
        f"请求验证错误: {request.method} {request.url.path}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
            "client_ip": request.client.host if request.client else None
        }
    )
    
    # 返回标准错误响应
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "type": ErrorCode.VALIDATION_ERROR.name,
                "message": "请求数据验证失败",
                "details": {
                    "errors": errors
                }
            }
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    HTTP异常处理器
    处理Starlette的HTTPException
    
    Args:
        request: FastAPI请求对象
        exc: HTTP异常
        
    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 尝试映射到对应的错误代码
    status_to_code = {
        400: ErrorCode.INVALID_REQUEST,
        401: ErrorCode.AUTHENTICATION_FAILED,
        403: ErrorCode.PERMISSION_DENIED,
        404: ErrorCode.NOT_FOUND,
        405: ErrorCode.INVALID_REQUEST,
        409: ErrorCode.ALREADY_EXISTS,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.LLM_RATE_LIMIT,
        500: ErrorCode.UNKNOWN_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
        504: ErrorCode.TIMEOUT
    }
    
    error_code = status_to_code.get(exc.status_code, ErrorCode.UNKNOWN_ERROR)
    
    # 记录错误日志
    log_level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    logger.log(
        log_level,
        f"HTTP异常: {exc.status_code} - {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "client_ip": request.client.host if request.client else None
        }
    )
    
    # 返回标准错误响应
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code.value,
                "type": error_code.name,
                "message": str(exc.detail),
                "details": {}
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    通用异常处理器
    捕获所有未处理的异常
    
    Args:
        request: FastAPI请求对象
        exc: 任何异常
        
    Returns:
        JSONResponse: 标准化的错误响应
    """
    # 获取详细的错误栈
    error_stack = traceback.format_exc()
    
    # 记录详细错误日志
    logger.error(
        f"未处理的异常: {exc.__class__.__name__}: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "exception_type": exc.__class__.__name__,
            "client_ip": request.client.host if request.client else None,
            "error_stack": error_stack
        },
        exc_info=True
    )
    
    # 生产环境中隐藏详细错误信息
    is_debug = bool(int(os.environ.get("DEBUG", "0")))
    error_message = str(exc) if is_debug else "服务器内部错误"
    error_details = {"exception_type": exc.__class__.__name__}
    
    if is_debug:
        error_details["traceback"] = error_stack.split("\n")
    
    # 返回标准错误响应
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.UNKNOWN_ERROR.value,
                "type": ErrorCode.UNKNOWN_ERROR.name,
                "message": error_message,
                "details": error_details
            }
        }
    )


def register_error_handlers(app: FastAPI) -> None:
    """
    注册所有错误处理器到FastAPI应用
    
    Args:
        app: FastAPI应用实例
    """
    # 注册服务错误处理器
    app.add_exception_handler(ServiceError, service_error_handler)
    
    # 注册验证错误处理器
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(PydanticValidationError, validation_error_handler)
    
    # 注册HTTP异常处理器
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # 注册通用异常处理器
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("已注册统一错误处理器") 