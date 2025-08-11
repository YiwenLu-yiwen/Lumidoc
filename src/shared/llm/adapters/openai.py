#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI适配器实现
提供与OpenAI API的交互
"""

import logging
import json
import httpx
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Union

from .base import BaseLLMAdapter

logger = logging.getLogger(__name__)

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI适配器实现"""
    
    def __init__(self, 
                base_url: str, 
                model_name: str,
                api_key: str,
                timeout: float = 60.0):
        """
        初始化OpenAI适配器
        
        Args:
            base_url: OpenAI API基础URL
            model_name: 模型名称
            api_key: API密钥
            timeout: 请求超时时间(秒)
        """
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.timeout = timeout
        logger.info(f"初始化OpenAI适配器: model={model_name}, url={base_url}")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取HTTP请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def _get_chat_url(self) -> str:
        """获取聊天API URL"""
        url = self.base_url
        
        # 检查是否需要添加API端点路径
        if not url.endswith('/chat/completions') and not '/chat/completions' in url:
            if url.endswith('/'):
                url = url + 'chat/completions'
            else:
                url = url + '/chat/completions'
                
        return url
    
    def _get_embeddings_url(self) -> str:
        """获取嵌入API URL"""
        url = self.base_url
        
        # 检查是否需要添加API端点路径
        if not url.endswith('/embeddings') and not '/embeddings' in url:
            if url.endswith('/'):
                url = url + 'embeddings'
            else:
                url = url + '/embeddings'
                
        return url
    
    async def generate(self, 
                     prompt: str, 
                     system_prompt: Optional[str] = None,
                     **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            system_prompt: 系统提示词
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None and key not in ['system_prompt']:
                params[key] = value
        
        # 调用API
        url = self._get_chat_url()
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI API响应格式错误: {data}")
                    raise Exception(f"OpenAI API响应格式错误: 缺少choices字段")
        except Exception as e:
            logger.error(f"调用OpenAI API失败: {str(e)}")
            # 🔧 修复：抛出异常而不是返回错误字符串
            raise Exception(f"OpenAI API调用失败: {str(e)}")
    
    async def generate_stream(self, 
                            prompt: str, 
                            system_prompt: Optional[str] = None,
                            **kwargs) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            system_prompt: 系统提示词
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本片段
        """
        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None and key not in ['system_prompt']:
                params[key] = value
        
        # 调用API
        url = self._get_chat_url()
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, headers=headers, json=params) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"调用OpenAI API流式生成失败: {str(e)}")
            # 🔧 修复：抛出异常而不是返回错误字符串
            raise Exception(f"OpenAI API流式调用失败: {str(e)}")
    
    async def chat(self, 
                  messages: List[Dict[str, str]], 
                  **kwargs) -> str:
        """
        聊天生成
        
        Args:
            messages: 消息列表，格式为[{"role": "user|system|assistant", "content": "..."}]
            **kwargs: 其他参数
            
        Returns:
            str: 生成的回复
        """
        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        # 调用API
        url = self._get_chat_url()
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI API响应格式错误: {data}")
                    raise Exception(f"OpenAI API响应格式错误: 缺少choices字段")
        except Exception as e:
            logger.error(f"调用OpenAI API失败: {str(e)}")
            # 🔧 修复：抛出异常而不是返回错误字符串
            raise Exception(f"OpenAI API调用失败: {str(e)}")
    
    async def chat_stream(self, 
                         messages: List[Dict[str, str]], 
                         **kwargs) -> AsyncGenerator[str, None]:
        """
        流式聊天生成
        
        Args:
            messages: 消息列表，格式为[{"role": "user|system|assistant", "content": "..."}]
            **kwargs: 其他参数
            
        Yields:
            str: 生成的回复片段
        """
        # 构建请求参数
        params = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        # 调用API
        url = self._get_chat_url()
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=params, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip() or line.strip() == "data: [DONE]":
                            continue
                        try:
                            # 移除 "data: " 前缀
                            if line.startswith("data: "):
                                line = line[6:]
                                
                            data = json.loads(line)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            logger.error(f"解析OpenAI API响应失败: {line}")
        except Exception as e:
            logger.error(f"调用OpenAI流式API失败: {str(e)}")
            yield f"API调用错误: {str(e)}"
    
    async def create_embedding(self, 
                             texts: Union[str, List[str]]) -> List[List[float]]:
        """
        创建文本嵌入
        
        Args:
            texts: 文本或文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        # 确保texts是列表
        if isinstance(texts, str):
            texts = [texts]
        
        # 构建请求参数
        params = {
            "model": self.model_name,
            "input": texts
        }
        
        # 调用API
        url = self._get_embeddings_url()
        headers = self._get_headers()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                if "data" in data:
                    embeddings = []
                    for item in data["data"]:
                        if "embedding" in item:
                            embeddings.append(item["embedding"])
                    return embeddings
                else:
                    logger.error(f"OpenAI嵌入API响应格式错误: {data}")
                    return [[]] * len(texts)
        except Exception as e:
            logger.error(f"调用OpenAI嵌入API失败: {str(e)}")
            return [[]] * len(texts)
    
    @property
    def model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict[str, Any]: 模型信息
        """
        return {
            "type": "openai",
            "name": self.model_name,
            "url": self.base_url
        } 