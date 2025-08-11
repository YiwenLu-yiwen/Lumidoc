import httpx
from fastapi import HTTPException, status
import logging
from typing import Dict, Any, Optional, Union, TypeVar, Generic, Type
from pydantic import BaseModel
import json
import os
# 导入共享的服务发现模块
from src.shared.service_discovery import get_service_url, call_service

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# 从环境变量获取服务URL，提供默认值
def get_env_url(name, default_url):
    """
    获取服务URL，优先使用环境变量
    
    Args:
        name: 环境变量名
        default_url: 默认URL
        
    Returns:
        str: 服务URL，确保包含协议
    """
    url = os.environ.get(name, default_url)
    # 确保URL包含协议
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

# 服务URL常量
CHAT_SERVICE_URL = get_env_url("CHAT_SERVICE_URL", "http://localhost:8001")
FILE_SERVICE_URL = get_env_url("FILE_SERVICE_URL", "http://localhost:8004")
GRAPH_SERVICE_URL = get_env_url("GRAPH_SERVICE_URL", "http://localhost:8003")
QUESTION_SERVICE_URL = get_env_url("QUESTION_SERVICE_URL", "http://localhost:8002")
PROJECT_SERVICE_URL = get_env_url("PROJECT_SERVICE_URL", "http://localhost:8020")

class ServiceClient(Generic[T]):
    """
    通用微服务客户端封装
    提供统一的请求处理和错误处理
    支持类型转换和验证
    """
    
    def __init__(self, base_url: str, response_model: Optional[Type[T]] = None):
        """
        初始化服务客户端
        
        Args:
            base_url: 微服务基础URL
            response_model: 响应数据的Pydantic模型类型
        """
        # 确保URL包含协议
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
        self.base_url = base_url
        self.response_model = response_model
        self._client = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,  # 增加超时时间到60秒
                verify=True  # 始终启用SSL验证
            )
        return self._client
    
    async def close(self):
        """关闭客户端连接"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def get_service_url(self, service_name: str) -> str:
        """
        使用服务发现获取服务URL
        
        Args:
            service_name: 服务名称
            
        Returns:
            str: 服务的完整URL
        """
        from src.shared.service_discovery import get_service_url
        
        try:
            # 使用服务发现获取URL
            url = await get_service_url(service_name)
            if url:
                logger.info(f"通过服务发现获取到 {service_name} 服务URL: {url}")
                return url
            
            # 服务发现失败时回退到预设URL
            logger.warning(f"服务发现未找到 {service_name} 服务，使用预设URL: {self.base_url}")
            return self.base_url
        except Exception as e:
            logger.error(f"获取服务URL时出错: {str(e)}")
            return self.base_url
    
    async def _handle_response(self, response: httpx.Response, operation: str) -> Dict[str, Any]:
        """统一处理响应和错误"""
        try:
            response.raise_for_status()
            data = response.json()
            
            # 如果指定了响应模型，验证响应数据
            if self.response_model:
                try:
                    validated_data = self.response_model.parse_obj(data)
                    return validated_data.dict()
                except Exception as e:
                    logger.warning(f"Response validation failed: {str(e)}")
                    # 如果验证失败，仍然返回原始数据
            
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"{operation} failed with status {e.response.status_code}: {e.response.text}")
            try:
                error_data = e.response.json()
                detail = error_data.get("detail", str(e))
            except:
                detail = str(e)
            
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Service error: {detail}"
            )
        except Exception as e:
            logger.error(f"{operation} failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Internal server error: {str(e)}"
            )
    
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, stream: bool = False) -> Union[Dict[str, Any], httpx.Response]:
        """发送GET请求"""
        client = await self.get_client()
        # 确保URL包含协议
        url = self.base_url
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        url = f"{url}{path}"
        logger.info(f"GET {url} params={params}")
        
        if stream:
            # 直接返回响应，不进行额外处理，让调用者负责读取和关闭
            return await client.get(url, params=params, headers=headers, timeout=60.0)
        else:
            response = await client.get(url, params=params, headers=headers)
            return await self._handle_response(response, f"GET {path}")
    
    async def post(self, path: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, stream: bool = False) -> Union[Dict[str, Any], httpx.Response]:
        """发送POST请求"""
        client = await self.get_client()
        # 确保URL包含协议
        url = self.base_url
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        url = f"{url}{path}"
        
        if data and json_data:
            raise ValueError("Cannot specify both data and json_data")
        
        # 处理流式请求
        if stream:
            logger.info(f"流式 POST {url} json={json_data or data}")
            # 直接返回响应，不进行额外处理，让调用者负责读取和关闭
            if json_data:
                return await client.post(url, json=json_data, headers=headers, timeout=60.0)
            else:
                return await client.post(url, data=data, headers=headers, timeout=60.0)
        # 处理普通请求
        else:
            try:
                if json_data:
                    logger.info(f"普通 POST {url} json={json_data}")
                    response = await client.post(url, json=json_data, headers=headers)
                else:
                    logger.info(f"普通 POST {url} data={data}")
                    response = await client.post(url, data=data, headers=headers)
                
                return await self._handle_response(response, f"POST {path}")
            except Exception as e:
                logger.error(f"POST请求错误: {str(e)}")
                raise e
    
    async def put(self, path: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """发送PUT请求"""
        client = await self.get_client()
        # 确保URL包含协议
        url = self.base_url
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        url = f"{url}{path}"
        
        if data and json_data:
            raise ValueError("Cannot specify both data and json_data")
        
        if json_data:
            logger.info(f"PUT {url} json={json_data}")
            response = await client.put(url, json=json_data, headers=headers)
        else:
            logger.info(f"PUT {url} data={data}")
            response = await client.put(url, data=data, headers=headers)
        
        return await self._handle_response(response, f"PUT {path}")
    
    async def delete(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """发送DELETE请求"""
        client = await self.get_client()
        # 确保URL包含协议
        url = self.base_url
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        url = f"{url}{path}"
        logger.info(f"DELETE {url} params={params}")
        
        response = await client.delete(url, params=params, headers=headers)
        return await self._handle_response(response, f"DELETE {path}")


# 定义各个服务的客户端
class ChatServiceClient(ServiceClient):
    """聊天服务客户端"""
    def __init__(self):
        super().__init__(CHAT_SERVICE_URL)

class FileServiceClient(ServiceClient):
    """文件服务客户端"""
    def __init__(self):
        super().__init__(FILE_SERVICE_URL)

class GraphServiceClient(ServiceClient):
    """图谱服务客户端"""
    def __init__(self):
        super().__init__(GRAPH_SERVICE_URL)

class QuestionServiceClient(ServiceClient):
    """问题服务客户端"""
    def __init__(self):
        super().__init__(QUESTION_SERVICE_URL)

class ProjectServiceClient(ServiceClient):
    """项目服务客户端"""
    def __init__(self):
        super().__init__(PROJECT_SERVICE_URL)

# 单例服务客户端，避免重复创建
chat_service = ChatServiceClient()
file_service = FileServiceClient()
graph_service = GraphServiceClient()
question_service = QuestionServiceClient()
project_service = ProjectServiceClient()

# 向外提供ensure_url_protocol函数保持向后兼容性
def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url 