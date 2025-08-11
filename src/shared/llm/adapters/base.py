#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM适配器基类
定义所有LLM适配器必须实现的接口
"""

import abc
from typing import Dict, List, Any, Optional, AsyncGenerator, Union

class BaseLLMAdapter(abc.ABC):
    """LLM适配器基类"""
    
    @abc.abstractmethod
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
        pass
    
    @abc.abstractmethod
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
        pass
    
    @abc.abstractmethod
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
        pass
    
    @abc.abstractmethod
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
        pass
    
    @abc.abstractmethod
    async def create_embedding(self, 
                             texts: Union[str, List[str]]) -> List[List[float]]:
        """
        创建文本嵌入
        
        Args:
            texts: 文本或文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        pass
    
    @property
    @abc.abstractmethod
    def model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict[str, Any]: 模型信息
        """
        pass 