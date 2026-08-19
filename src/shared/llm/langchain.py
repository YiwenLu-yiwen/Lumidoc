#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LangChain集成
提供LangChain兼容的LLM类
"""

import logging
import asyncio
from typing import List, Optional
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

from .adapters import create_llm_adapter
from src.shared.config import llm_settings

logger = logging.getLogger(__name__)

class LumidocLangChainLLM(LLM):
    """
    Lumidoc项目的LangChain LLM实现
    使用共享LLM适配器
    """
    
    model_type: str = llm_settings.model_type
    model_name: str = llm_settings.model_name
    temperature: float = llm_settings.temperature
    max_tokens: int = llm_settings.max_tokens
    api_key: Optional[str] = llm_settings.api_key
    system_prompt: Optional[str] = None
    
    def __init__(self, **kwargs):
        """初始化LangChain LLM"""
        super().__init__(**kwargs)
        self._adapter = None
    
    def _init_adapter(self):
        """初始化适配器"""
        if self._adapter is None:
            self._adapter = create_llm_adapter(
                model_type=self.model_type,
                model_name=self.model_name,
                api_key=self.api_key
            )
    
    @property
    def _llm_type(self) -> str:
        """返回LLM类型"""
        return f"lumidoc_{self.model_type}"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> str:
        """
        同步调用LLM
        
        Args:
            prompt: 提示词
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        return asyncio.run(self._acall(prompt, stop, run_manager, **kwargs))
    
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> str:
        """
        异步调用LLM
        
        Args:
            prompt: 提示词
            stop: 停止词列表
            run_manager: 回调管理器
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        try:
            # 初始化适配器
            self._init_adapter()
            
            # 构建参数
            params = {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            
            # 添加系统提示词
            if self.system_prompt:
                params["system_prompt"] = self.system_prompt
            
            # 添加停止词
            if stop:
                params["stop"] = stop
            
            # 合并其他参数
            params.update(kwargs)
            
            # 调用适配器
            return await self._adapter.generate(prompt, **params)
        except Exception as e:
            logger.error(f"LangChain LLM调用失败: {str(e)}")
            return f"LLM调用错误: {str(e)}" 