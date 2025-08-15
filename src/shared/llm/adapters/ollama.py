#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ollama适配器实现
提供与Ollama API的交互
"""

import logging
import json
import httpx
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator, Union

from .base import BaseLLMAdapter

logger = logging.getLogger(__name__)

class OllamaAdapter(BaseLLMAdapter):
    """Ollama适配器实现"""
    
    def __init__(self, 
                base_url: str, 
                model_name: str,
                timeout: float = 180.0):
        """
        初始化Ollama适配器
        
        Args:
            base_url: Ollama API基础URL
            model_name: 模型名称
            timeout: 请求超时时间(秒)
        """
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout
        logger.info(f"初始化Ollama适配器: model={model_name}, url={base_url}")
    
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
        # 构建请求参数
        params = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }
        
        # 添加系统提示词
        if system_prompt:
            params["system"] = system_prompt
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        # 调用API
        url = f"{self.base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                if "response" in data:
                    return data["response"]
                else:
                    logger.error(f"Ollama API响应格式错误: {data}")
                    raise Exception(f"Ollama API响应格式错误: 缺少response字段")
        except Exception as e:
            logger.error(f"调用Ollama API失败: {str(e)}")
            # 🔧 修复：抛出异常而不是返回错误字符串
            raise Exception(f"Ollama API调用失败: {str(e)}")
    
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
        # 构建请求参数
        params = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True
        }
        
        # 添加系统提示词
        if system_prompt:
            params["system"] = system_prompt
        
        # 添加其他参数
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value
        
        # 调用API
        url = f"{self.base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", url, json=params, headers={"Content-Type": "application/json"}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            logger.error(f"解析Ollama API响应失败: {line}")
        except Exception as e:
            logger.error(f"调用Ollama流式API失败: {str(e)}")
            # 🔧 修复：抛出异常而不是返回错误字符串
            raise Exception(f"Ollama API流式调用失败: {str(e)}")
    
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
        url = f"{self.base_url}/api/chat"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"发送请求到Ollama API: {url}")
                
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=params
                )
                response.raise_for_status()
                data = response.json()
                
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"]
                else:
                    logger.error(f"Ollama API响应格式错误: {data}")
                    raise Exception(f"Ollama API响应格式错误: 缺少message.content字段")
        except httpx.TimeoutException as e:
            logger.error(f"调用Ollama API超时: {str(e)}")
            raise Exception(f"Ollama API调用超时: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"调用Ollama API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Ollama API HTTP错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"调用Ollama API失败: {str(e)}")
            raise Exception(f"Ollama API调用失败: {str(e)}")
    
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
        # Ollama的chat API需要特殊处理
        system_prompt = None
        prompt = ""
        
        # 提取系统提示词和最后一条用户消息
        for message in messages:
            if message["role"] == "system":
                system_prompt = message["content"]
            elif message["role"] == "user":
                prompt = message["content"]
        
        # 如果没有用户消息，使用最后一条消息
        if not prompt and messages:
            prompt = messages[-1]["content"]
        
        # 调用generate_stream方法
        async for chunk in self.generate_stream(prompt, system_prompt, **kwargs):
            yield chunk
    
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
        
        embeddings = []
        url = f"{self.base_url}/api/embeddings"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for text in texts:
                    params = {
                        "model": self.model_name,
                        "prompt": text
                    }
                    
                    response = await client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json=params
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if "embedding" in data:
                        embeddings.append(data["embedding"])
                    else:
                        logger.error(f"Ollama嵌入API响应格式错误: {data}")
                        embeddings.append([])
            
            return embeddings
        except Exception as e:
            logger.error(f"调用Ollama嵌入API失败: {str(e)}")
            return [[]] * len(texts)
    
    @property
    def model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict[str, Any]: 模型信息
        """
        return {
            "type": "ollama",
            "name": self.model_name,
            "url": self.base_url
        } 