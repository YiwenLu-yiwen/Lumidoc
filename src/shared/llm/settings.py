#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM设置模块
提供统一的LLM配置设置
"""

import os
from typing import Optional
from dataclasses import dataclass

@dataclass
class LLMSettings:
    """LLM配置设置"""
    
    # 模型设置
    model_type: str = "ollama"
    model_name: str = "qwen3:1.7b"
    
    # API 密钥
    api_key: Optional[str] = None
    
    # 接口URL
    ollama_api_url: str = "http://localhost:11434"
    openai_api_url: str = "https://api.openai.com/v1"
    deepseek_api_url: str = "https://api.deepseek.com/v1"
    vllm_api_url: str = "http://localhost:8000"
    
    # 请求参数
    request_timeout: float = 300.0
    max_retries: int = 3
    
    # 性能参数
    cache_enabled: bool = True
    cache_ttl: int = 86400  # 24小时
    
    def __post_init__(self):
        """初始化后处理"""
        # 从环境变量加载配置
        self.model_type = os.environ.get("LLM_MODEL_TYPE", self.model_type)
        self.model_name = os.environ.get("LLM_MODEL_NAME", self.model_name)
        self.api_key = os.environ.get("LLM_API_KEY", self.api_key)
        self.request_timeout = float(os.environ.get("LLM_REQUEST_TIMEOUT", str(self.request_timeout)))
        
        # 各服务API URL
        self.ollama_api_url = os.environ.get("OLLAMA_API_URL", self.ollama_api_url)
        self.openai_api_url = os.environ.get("OPENAI_API_URL", self.openai_api_url)
        self.deepseek_api_url = os.environ.get("DEEPSEEK_API_URL", self.deepseek_api_url)
        self.vllm_api_url = os.environ.get("VLLM_API_URL", self.vllm_api_url)
        
        # 缓存设置
        self.cache_enabled = os.environ.get("LLM_CACHE_ENABLED", "true").lower() == "true"
        if "LLM_CACHE_TTL" in os.environ:
            self.cache_ttl = int(os.environ.get("LLM_CACHE_TTL"))

# 创建全局设置实例
llm_settings = LLMSettings() 