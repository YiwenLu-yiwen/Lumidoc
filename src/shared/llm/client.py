"""
LLM服务客户端

提供访问LLM核心服务的通用客户端
"""

import logging
from typing import Dict, List, Optional, Union, AsyncGenerator, Any

from ..config_utils import get_service_url

# 配置日志
logger = logging.getLogger(__name__)

class LLMClient:
    """LLM客户端类"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 60):
        """
        初始化LLM客户端
        
        Args:
            base_url: LLM服务基础URL，如果为None则从配置或环境变量获取
            timeout: 请求超时时间(秒)
        """
        # 获取LLM服务URL
        if base_url is None:
            base_url = get_service_url("LLM") or "http://localhost:8080"
        
        self.base_url = base_url
        self.timeout = timeout
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Any:
        """通用请求方法"""
        import httpx
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, params=params, json=json_data)
            response.raise_for_status()
            return response.json()
    
    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET请求包装"""
        return await self._request("GET", endpoint, params=params)
    
    async def _post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """POST请求包装"""
        return await self._request("POST", endpoint, json_data=json)
    
    async def _stream_post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """流式POST请求包装"""
        # 这里需要实现流式处理，暂时返回空
        # TODO: 实现真正的流式处理
        response = await self._post(endpoint, json)
        yield response.get("text", "")
    
    async def list_models(self, model_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        Args:
            model_type: 模型类型，可选值："llm", "embedding"
            
        Returns:
            List[Dict[str, Any]]: 模型列表
        """
        params = {}
        if model_type:
            params["type"] = model_type
            
        response = await self._get("/models", params=params)
        return response.get("models", [])
    
    async def generate(self, 
                     prompt: str, 
                     model: Optional[str] = None,
                     system_prompt: Optional[str] = None,
                     temperature: Optional[float] = None,
                     max_tokens: Optional[int] = None,
                     **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            model: 模型名称
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        data = {"prompt": prompt}
        
        if model:
            data["model"] = model
        if system_prompt:
            data["system_prompt"] = system_prompt
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
            
        # 添加其他参数
        for key, value in kwargs.items():
            data[key] = value
        
        response = await self._post("/generate", json=data)
        return response.get("text", "")
    
    async def generate_stream(self, 
                            prompt: str, 
                            model: Optional[str] = None,
                            system_prompt: Optional[str] = None,
                            temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None,
                            **kwargs) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            model: 模型名称
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本片段
        """
        data = {"prompt": prompt}
        
        if model:
            data["model"] = model
        if system_prompt:
            data["system_prompt"] = system_prompt
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
            
        # 添加其他参数
        for key, value in kwargs.items():
            data[key] = value
        
        # 使用服务客户端的流处理
        async for chunk in self._stream_post("/stream", json=data):
            yield chunk
    
    async def chat(self, 
                 messages: List[Dict[str, str]], 
                 model: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """
        聊天生成
        
        Args:
            messages: 消息列表，格式为[{"role": "user|system|assistant", "content": "..."}]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的回复
        """
        data = {"messages": messages}
        
        if model:
            data["model"] = model
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
            
        # 添加其他参数
        for key, value in kwargs.items():
            data[key] = value
        
        response = await self._post("/chat", json=data)
        return response.get("text", "")
    
    async def chat_stream(self, 
                        messages: List[Dict[str, str]], 
                        model: Optional[str] = None,
                        temperature: Optional[float] = None,
                        max_tokens: Optional[int] = None,
                        **kwargs) -> AsyncGenerator[str, None]:
        """
        流式聊天生成
        
        Args:
            messages: 消息列表，格式为[{"role": "user|system|assistant", "content": "..."}]
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的回复片段
        """
        data = {"messages": messages}
        
        if model:
            data["model"] = model
        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
            
        # 添加其他参数
        for key, value in kwargs.items():
            data[key] = value
        
        # 使用服务客户端的流处理
        async for chunk in self._stream_post("/chat/stream", json=data):
            yield chunk
    
    async def create_embedding(self, 
                            texts: Union[str, List[str]], 
                            model: Optional[str] = None) -> List[List[float]]:
        """
        创建文本嵌入
        
        Args:
            texts: 文本或文本列表
            model: 嵌入模型
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        data = {"input": texts}
        
        if model:
            data["model"] = model
        
        response = await self._post("/embeddings", json=data)
        
        # 处理OpenAI格式响应
        if "data" in response:
            embeddings = []
            for item in response["data"]:
                if "embedding" in item:
                    embeddings.append(item["embedding"])
            return embeddings
        
        return []

# 创建默认客户端实例
default_client = LLMClient()
