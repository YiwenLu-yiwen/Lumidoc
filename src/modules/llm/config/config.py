#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一LLM服务配置文件
"""

import os
from pydantic import Field, validator
from src.shared.base_config import BaseSettings
from src.shared.config import llm_settings
from src.shared.config.service_settings import llm_settings_global as llm_base_config

class LLMServiceSettings(BaseSettings):
    """LLM服务配置类"""
    
    # 服务配置 - 使用共享配置
    service_name: str = Field("llm", env="SERVICE_NAME")
    service_version: str = Field("1.0.0", env="SERVICE_VERSION")
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8080, env="PORT")
    
    # LLM相关配置 - 使用共享LLM配置
    llm_model_type: str = Field(llm_base_config.model_type, env="LLM_MODEL_TYPE")
    llm_model_name: str = Field(llm_base_config.model_name, env="LLM_MODEL_NAME")
    llm_api_key: str = Field(llm_base_config.api_key, env="LLM_API_KEY")
    llm_base_url: str = Field(llm_base_config.base_url, env="LLM_BASE_URL")
    llm_temperature: float = Field(llm_base_config.temperature, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(llm_base_config.max_tokens, env="LLM_MAX_TOKENS")
    
    # 请求超时配置
    request_timeout: float = Field(llm_base_config.request_timeout, env="REQUEST_TIMEOUT")
    
    # 摘要特定配置
    summary_max_length: int = Field(llm_base_config.summary_max_length, env="SUMMARY_MAX_LENGTH")
    summary_min_compression: float = Field(llm_base_config.summary_min_compression, env="SUMMARY_MIN_COMPRESSION")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"  # 忽略额外的环境变量
    }

# 创建配置实例
settings = LLMServiceSettings() 