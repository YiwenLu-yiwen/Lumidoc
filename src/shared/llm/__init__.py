"""
LLM共享库
提供统一的LLM服务调用工具
"""

# 配置
from src.shared.config import (
    llm_settings,
    MODEL_TYPE_OLLAMA, 
    MODEL_TYPE_OPENAI, 
    MODEL_TYPE_DEEPSEEK, 
    MODEL_TYPE_AZURE,
    MODEL_TYPE_VLLM,
    SUPPORTED_MODEL_TYPES
)

# 适配器
from .adapters import (
    BaseLLMAdapter,
    OllamaAdapter,
    OpenAIAdapter,
    DeepseekAdapter,
    VLLMAdapter,
    create_llm_adapter
)

# LangChain集成
from .langchain import LumidocLangChainLLM

# 旧版客户端（保留向后兼容）
from .client import LLMClient, default_client

__all__ = [
    # 配置
    "llm_settings",
    "MODEL_TYPE_OLLAMA",
    "MODEL_TYPE_OPENAI",
    "MODEL_TYPE_DEEPSEEK",
    "MODEL_TYPE_AZURE",
    "MODEL_TYPE_VLLM",
    "SUPPORTED_MODEL_TYPES",
    
    # 适配器
    "BaseLLMAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "DeepseekAdapter",
    "VLLMAdapter",
    "create_llm_adapter",
    
    # LangChain集成
    "LumidocLangChainLLM",
    
    # 旧版客户端
    "LLMClient",
    "default_client"
] 