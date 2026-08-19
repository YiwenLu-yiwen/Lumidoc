#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM适配器基础类型定义
为vLLM适配器提供必要的类型
"""

from abc import ABC, abstractmethod
from typing import List, Optional, TypedDict

class Message(TypedDict):
    """聊天消息类型"""
    role: str
    content: str

class CompletionOptions:
    """完成选项"""
    
    def __init__(self, 
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 timeout: Optional[float] = None,
                 stop_sequences: Optional[List[str]] = None):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.stop_sequences = stop_sequences or []


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""
    
    @abstractmethod
    async def generate_completion(self, 
                                prompt: str, 
                                options: Optional[CompletionOptions] = None) -> str:
        """生成文本完成"""
        pass
    
    @abstractmethod
    async def generate_chat_completion(self, 
                                     messages: List[Message], 
                                     options: Optional[CompletionOptions] = None) -> str:
        """生成对话完成"""
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入"""
        pass 