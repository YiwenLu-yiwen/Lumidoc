#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一LLM服务配置文件
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.shared.config.service_settings import llm_settings_global as llm_base_config

class LLMServiceSettings(BaseSettings):
    """LLM服务配置类"""

    # 服务配置 - 使用共享配置
    service_name: str = "llm"
    service_version: str = "1.0.0"
    host: str = Field("0.0.0.0", validation_alias=AliasChoices("HOST", "host"))
    port: int = Field(
        8080, validation_alias=AliasChoices("LLM_SERVICE_PORT", "port")
    )

    # LLM相关配置 - 使用共享LLM配置
    llm_model_type: str = llm_base_config.model_type
    llm_model_name: str = llm_base_config.model_name
    llm_api_key: str = llm_base_config.api_key
    llm_base_url: str = llm_base_config.base_url
    llm_temperature: float = llm_base_config.temperature
    llm_max_tokens: int = llm_base_config.max_tokens
    embedding_model_name: str = llm_base_config.embedding_model_name

    # 请求超时配置
    request_timeout: float = llm_base_config.request_timeout

    # 摘要特定配置
    summary_max_length: int = llm_base_config.summary_max_length
    summary_min_compression: float = llm_base_config.summary_min_compression

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

# 创建配置实例
settings = LLMServiceSettings()
