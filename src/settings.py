"""
Lumidoc项目全局配置模块
提供统一的配置访问接口
"""

import os
import json
from typing import Dict, Any

# 默认LightRAG配置
DEFAULT_LIGHTRAG_CONFIG = {
    "embed_model": "bge-small-zh-v1.5",
    "index_mode": "auto",
    "rerank_model": "bce-reranker-base",
    "use_rerank": True,
    "chunk_size": 512,
    "chunk_overlap": 50
}

# 默认LLM配置
DEFAULT_LLM_CONFIG = {
    "api_key": "",
    "base_url": "https://api.deepseek-ai.com/v1",
    "temperature": 0.7,
    "max_tokens": 2000,
    "model": "deepseek-chat"
}

def get_lightrag_config() -> Dict[str, Any]:
    """获取LightRAG配置"""
    # 尝试从环境变量读取配置
    config_str = os.getenv("LIGHTRAG_CONFIG")

    if config_str:
        try:
            # 尝试解析JSON配置
            config = json.loads(config_str)
            return {**DEFAULT_LIGHTRAG_CONFIG, **config}
        except (json.JSONDecodeError, TypeError):
            pass

    return DEFAULT_LIGHTRAG_CONFIG

def get_llm_config() -> Dict[str, Any]:
    """获取LLM配置"""
    # 尝试从环境变量读取配置
    config_str = os.getenv("LLM_CONFIG")

    if config_str:
        try:
            # 尝试解析JSON配置
            config = json.loads(config_str)
            return {**DEFAULT_LLM_CONFIG, **config}
        except (json.JSONDecodeError, TypeError):
            pass

    # 如果没有配置字符串，则从单独的环境变量读取
    config = DEFAULT_LLM_CONFIG.copy()

    if os.getenv("LLM_API_KEY"):
        config["api_key"] = os.getenv("LLM_API_KEY")

    if os.getenv("LLM_BASE_URL"):
        config["base_url"] = os.getenv("LLM_BASE_URL")

    if os.getenv("LLM_TEMPERATURE"):
        try:
            config["temperature"] = float(os.getenv("LLM_TEMPERATURE"))
        except (TypeError, ValueError):
            pass

    if os.getenv("LLM_MAX_TOKENS"):
        try:
            config["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS"))
        except (TypeError, ValueError):
            pass

    if os.getenv("LLM_MODEL"):
        config["model"] = os.getenv("LLM_MODEL")

    return config
