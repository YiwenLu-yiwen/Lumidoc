"""
通用的微服务客户端基类
提供本地/远程调用、超时控制、错误处理等共享功能
"""

import os
import asyncio
import logging
import uuid
import time
import importlib
from typing import Optional, Dict, Any, Callable, Awaitable, TypeVar, Generic, Type
import httpx
from fastapi import HTTPException
import functools
from concurrent.futures import TimeoutError as ConcurrentTimeoutError

# 返回值类型
T = TypeVar('T')

# 配置日志
logger = logging.getLogger(__name__)

# 默认超时设置（秒）
DEFAULT_TIMEOUT = float(os.getenv('SERVICE_REQUEST_TIMEOUT', '60.0'))

class ServiceClientBase(Generic[T]):
    """
    通用微服务客户端基类
    
    提供以下功能：
    1. 本地/远程调用自动切换
    2. 统一的错误处理
    3. 请求追踪
    4. 超时控制
    """
    
    # 服务模式选项
    MODE_LOCAL = "LOCAL"   # 仅使用本地实现
    MODE_REMOTE = "REMOTE" # 仅使用远程API
    MODE_AUTO = "AUTO"     # 优先本地，失败时回退到远程
    
    def __init__(
        self,
        service_name: str,
        service_url: str,
        local_module_path: Optional[str] = None,
        local_service_name: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """
        初始化服务客户端
        
        Args:
            service_name: 服务名称，用于日志
            service_url: 服务URL
            local_module_path: 本地实现的导入路径，如"src.modules.myservice.services.service"
            local_service_name: 本地服务的变量名，如"my_service"
            timeout: 请求超时时间（秒）
        """
        self.service_name = service_name
        self.service_url = service_url
        self.local_module_path = local_module_path
        self.local_service_name = local_service_name or f"{service_name.lower()}_service"
        
        # 获取服务模式
        mode_env = f"{service_name.upper()}_SERVICE_MODE"
        self.service_mode = os.getenv(mode_env, 'AUTO').upper()
        
        # 配置超时
        timeout_env = f"{service_name.upper()}_SERVICE_TIMEOUT"
        self.timeout = float(timeout or os.getenv(timeout_env, DEFAULT_TIMEOUT))
        
        # 初始化本地服务
        self._local_service: Optional[T] = None
        self._local_service_lock = asyncio.Lock()
        
        # 日志记录初始配置
        logger.info(f"{service_name}服务客户端初始化: 模式={self.service_mode}, URL={self.service_url}, 超时={self.timeout}秒")
    
    async def _get_local_service(self) -> Optional[T]:
        """获取本地服务实现"""
        if not self.local_module_path:
            return None
            
        if self._local_service is None:
            async with self._local_service_lock:
                if self._local_service is None:
                    try:
                        # 动态导入本地服务
                        module = importlib.import_module(self.local_module_path)
                        self._local_service = getattr(module, self.local_service_name)
                        logger.info(f"已成功加载本地{self.service_name}服务实现")
                    except ImportError as e:
                        logger.error(f"无法加载本地{self.service_name}服务实现: {str(e)}")
                        if self.service_mode == self.MODE_LOCAL:
                            raise HTTPException(
                                status_code=500, 
                                detail=f"已配置LOCAL模式但无法加载本地{self.service_name}服务: {str(e)}"
                            )
                        
        return self._local_service
    
    async def _exec_with_timeout(self, coro: Awaitable[T], timeout: float, error_msg: str) -> T:
        """添加超时的协程执行"""
        try:
            return await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            logger.error(f"操作超时: {error_msg}, 超时限制: {timeout}秒")
            raise HTTPException(status_code=504, detail=error_msg)
    
    def handle_service_errors(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """统一的服务错误处理装饰器"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request_id = str(uuid.uuid4())[:8]  # 生成请求追踪ID
            start_time = time.time()
            
            # 记录请求开始
            method_name = func.__name__
            logger.debug(f"[{request_id}] 开始调用 {self.service_name}.{method_name}, 参数: {kwargs}")
            
            try:
                # 执行原始方法
                result = await func(*args, **kwargs)
                
                # 记录请求结束
                duration = time.time() - start_time
                logger.debug(f"[{request_id}] {self.service_name}.{method_name} 调用完成, 耗时: {duration:.3f}秒")
                return result
                
            except HTTPException as e:
                # 直接重新抛出HTTP异常，保留状态码
                logger.error(f"[{request_id}] {self.service_name}.{method_name} HTTP错误: {e.status_code}, {e.detail}")
                raise
                
            except Exception as e:
                # 转换其他异常为HTTP异常
                logger.error(f"[{request_id}] {self.service_name}.{method_name} 错误: {str(e)}", exc_info=True)
                # 标准化错误响应
                raise HTTPException(status_code=500, detail=f"{self.service_name}服务错误: {str(e)}")
                
        return wrapper
        
    async def call_remote_api(
        self, 
        endpoint: str, 
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> Any:
        """
        调用远程API
        
        Args:
            endpoint: API端点路径
            method: HTTP方法
            params: 查询参数
            data: 请求体数据
            headers: 请求头
            timeout: 超时时间（秒）
            
        Returns:
            Any: API响应
        """
        full_url = f"{self.service_url}/{endpoint.lstrip('/')}"
        request_id = str(uuid.uuid4())[:8]
        
        # 设置默认请求头
        request_headers = {
            "X-Request-ID": request_id
        }
        if headers:
            request_headers.update(headers)
        
        # 使用传入的超时或默认超时
        request_timeout = timeout or self.timeout
        
        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(full_url, params=params, headers=request_headers)
                elif method.upper() == "POST":
                    response = await client.post(full_url, params=params, json=data, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await client.put(full_url, params=params, json=data, headers=request_headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(full_url, params=params, json=data, headers=request_headers)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")
                
                response.raise_for_status()
                
                # 尝试返回JSON，如果不是JSON则返回文本
                try:
                    return response.json()
                except:
                    return response.text
                    
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            detail = f"远程{self.service_name}服务返回错误状态: {status_code}"
            
            # 尝试从响应中提取更详细的错误信息
            try:
                error_data = e.response.json()
                if "detail" in error_data:
                    detail = error_data["detail"]
            except:
                pass
                
            raise HTTPException(status_code=status_code, detail=detail)
            
        except httpx.RequestError as e:
            logger.error(f"[{request_id}] {self.service_name}服务请求错误: {str(e)}")
            raise HTTPException(status_code=503, detail=f"{self.service_name}服务不可用: {str(e)}")
            
        except Exception as e:
            logger.error(f"[{request_id}] {self.service_name}服务调用出错: {str(e)}")
            raise HTTPException(status_code=500, detail=f"{self.service_name}服务调用失败: {str(e)}")

# 为了保持向后兼容性，从service_discovery导入ServiceClient
# 这样依赖于service_client.py中的ServiceClient的代码可以继续工作
from .service_discovery import ServiceClient 