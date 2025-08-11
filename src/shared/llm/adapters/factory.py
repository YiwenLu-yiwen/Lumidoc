#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM适配器工厂
提供创建不同类型LLM适配器的工厂方法
"""

import os
import logging
from typing import Optional

from .base import BaseLLMAdapter
from ..settings import llm_settings

# 配置日志
logger = logging.getLogger(__name__)

# 模型类型常量
MODEL_TYPE_OLLAMA = "ollama"
MODEL_TYPE_OPENAI = "openai"
MODEL_TYPE_DEEPSEEK = "deepseek"
MODEL_TYPE_VLLM = "vllm"

def create_llm_adapter(
    model_type: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> BaseLLMAdapter:
    """
    创建LLM适配器
    
    Args:
        model_type: 模型类型
        model_name: 模型名称
        api_key: API密钥
        **kwargs: 其他参数
        
    Returns:
        BaseLLMAdapter: LLM适配器实例
    """
    # 导入适配器
    from .ollama import OllamaAdapter
    from .openai import OpenAIAdapter
    from .deepseek import DeepseekAdapter
    
    # 条件导入vllm - 如果不存在则忽略
    try:
        from .vllm import VLLMAdapter
        has_vllm = True
    except ModuleNotFoundError:
        logger.warning("未找到vllm模块，VLLM适配器将不可用")
        has_vllm = False
    
    # 确保有效的模型类型 - 如果未提供，尝试从环境变量获取，最后回退到默认值
    if not model_type:
        model_type = os.environ.get("LLM_MODEL_TYPE", None)
    
    # 如果仍然没有有效的模型类型，回退到 ollama
    if not model_type:
        logger.warning("未指定模型类型，回退到默认值：ollama")
        model_type = MODEL_TYPE_OLLAMA
    
    # 如果选择了VLLM但不可用，则回退到Ollama
    if model_type == MODEL_TYPE_VLLM and not has_vllm:
        logger.warning("选择了VLLM但模块不可用，回退到Ollama")
        model_type = MODEL_TYPE_OLLAMA
    
    # 确保有效的模型名称 - 如果未提供，尝试从环境变量获取，最后回退到默认值
    if not model_name:
        model_name = os.environ.get("LLM_MODEL_NAME", None)
    
    # 如果仍然没有有效的模型名称，基于模型类型选择默认名称
    if not model_name:
        if model_type == MODEL_TYPE_OLLAMA:
            model_name = "qwen3:1.7b"
            logger.warning(f"未指定模型名称，回退到 ollama 默认值：{model_name}")
        elif model_type == MODEL_TYPE_OPENAI:
            model_name = "gpt-3.5-turbo"
            logger.warning(f"未指定模型名称，回退到 OpenAI 默认值：{model_name}")
        elif model_type == MODEL_TYPE_DEEPSEEK:
            model_name = "deepseek-v2"
            logger.warning(f"未指定模型名称，回退到 Deepseek 默认值：{model_name}")
        elif model_type == MODEL_TYPE_VLLM and has_vllm:
            model_name = "baichuan2-13b"
            logger.warning(f"未指定模型名称，回退到 vLLM 默认值：{model_name}")
    
    logger.info(f"创建LLM适配器: type={model_type}, model={model_name}")
    
    # 根据模型类型创建适配器
    if model_type == MODEL_TYPE_OLLAMA:
        # 获取 ollama 基础 URL - 如果未提供，尝试从环境变量获取
        ollama_base_url = kwargs.get("base_url", None) or os.environ.get("OLLAMA_API_URL", None)
        
        # 如果仍然没有，使用 llm_settings 或默认值
        if not ollama_base_url:
            ollama_base_url = llm_settings.ollama_api_url or "http://localhost:11434"
            logger.warning(f"未指定 Ollama API URL，使用默认值：{ollama_base_url}")
        
        return OllamaAdapter(
            base_url=ollama_base_url,
            model_name=model_name,
            timeout=kwargs.get("timeout", llm_settings.request_timeout)
        )
    elif model_type == MODEL_TYPE_OPENAI:
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY", None)
            
        if not api_key:
            raise ValueError("OpenAI适配器需要API密钥")
        
        return OpenAIAdapter(
            base_url=kwargs.get("base_url", llm_settings.openai_api_url),
            model_name=model_name,
            api_key=api_key,
            timeout=kwargs.get("timeout", llm_settings.request_timeout)
        )
    elif model_type == MODEL_TYPE_DEEPSEEK:
        if not api_key:
            api_key = os.environ.get("DEEPSEEK_API_KEY", None)
            
        if not api_key:
            raise ValueError("Deepseek适配器需要API密钥")
        
        return DeepseekAdapter(
            base_url=kwargs.get("base_url", llm_settings.deepseek_api_url),
            model_name=model_name,
            api_key=api_key,
            timeout=kwargs.get("timeout", llm_settings.request_timeout)
        )
    elif model_type == MODEL_TYPE_VLLM and has_vllm:
        vllm_api_url = kwargs.get("api_url", None) or os.environ.get("VLLM_API_URL", None)
        
        if not vllm_api_url:
            vllm_api_url = llm_settings.vllm_api_url or "http://localhost:8000"
            logger.warning(f"未指定 vLLM API URL，使用默认值：{vllm_api_url}")
        
        return VLLMAdapter(
            api_url=vllm_api_url,
            model_name=model_name,
            api_key=api_key
        )
    else:
        raise ValueError(f"不支持的模型类型: {model_type}") 