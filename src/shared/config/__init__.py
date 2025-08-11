#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
共享配置模块
提供统一的配置管理
"""

import os
import sys
import inspect
from pathlib import Path
from typing import Dict, Any

# 从service_settings导入设置，而不是从settings导入
from .service_settings import (
    ServiceSettings,
    AuthServiceSettings, 
    FileServiceSettings,
    FileProcServiceSettings,
    GraphServiceSettings,
    RAGServiceSettings,
    ProjectServiceSettings,
    QuestionServiceSettings,
    ChatServiceSettings,
    LLMServiceSettings,
    LLMSummaryServiceSettings,
    LLMSettings,
    llm_settings_global as llm_settings,
    MODEL_TYPE_OLLAMA,
    MODEL_TYPE_OPENAI,
    MODEL_TYPE_DEEPSEEK,
    MODEL_TYPE_AZURE,
    MODEL_TYPE_VLLM,
    SUPPORTED_MODEL_TYPES
)
# 导入service_config中的函数和变量
from .service_config import (
    get_service_url,
    get_service_host,
    get_service_port,
    service_config
)
from .config_loader import get_env

# 自动检测模块类型并配置相应settings实例
def autodetect_module(frame=None):
    """
    自动检测当前正在运行的模块类型，并返回相应的设置实例
    """
    if frame is None:
        frame = inspect.currentframe().f_back
    
    # 获取调用者所在的模块名称和文件路径
    module_name = frame.f_globals.get('__name__', '')
    module_file = frame.f_globals.get('__file__', '')

    if not module_file:
        # 默认返回基本设置
        return ServiceSettings(service_name="default", port=8000)
    
    module_path = os.path.normpath(module_file)

    # 为各个服务模块返回相应的设置实例
    if '/modules/auth/' in module_path:
        from .service_settings import auth_settings
        return auth_settings
    elif '/modules/file/' in module_path:
        from .service_settings import file_settings
        return file_settings
    elif '/modules/fileproc/' in module_path:
        from .service_settings import fileproc_settings
        return fileproc_settings
    elif '/modules/graph/' in module_path:
        from .service_settings import graph_settings
        return graph_settings
    elif '/modules/lightraglocal/' in module_path:
        from .service_settings import lightraglocal_settings
        return lightraglocal_settings
    elif '/modules/monitoring/' in module_path:
        from .service_settings import monitoring_settings
        return monitoring_settings
    elif '/modules/project/' in module_path:
        from .service_settings import project_settings
        return project_settings
    elif '/modules/question/' in module_path:
        from .service_settings import question_settings
        return question_settings
    elif '/modules/chat/' in module_path:
        from .service_settings import chat_settings
        return chat_settings
    elif '/modules/llm/' in module_path:
        from .service_settings import llm_settings
        return llm_settings
    else:
        # 默认情况下返回基本设置
        return ServiceSettings(service_name="default", port=8000)

# 提供get_settings函数，用于获取当前模块的设置
def get_settings(frame=None):
    """
    获取当前调用模块的配置设置
    如果指定了frame，则使用该frame的上下文
    否则使用调用者的frame
    
    Returns:
        适合当前模块的配置设置实例
    """
    if frame is None:
        frame = inspect.currentframe().f_back
    
    return autodetect_module(frame)

# 注册当前模块的设置实例
current_settings = autodetect_module(inspect.currentframe())

# 导出所有内容
__all__ = [
    'service_config',
    'get_service_url',
    'get_service_host',
    'get_service_port',
    'ServiceSettings',
    'AuthServiceSettings',
    'FileServiceSettings',
    'FileProcServiceSettings',
    'GraphServiceSettings',
    'RAGServiceSettings',
    'ProjectServiceSettings',
    'QuestionServiceSettings',
    'ChatServiceSettings',
    'LLMServiceSettings',
    'LLMSummaryServiceSettings',
    'llm_settings',
    'MODEL_TYPE_OLLAMA',
    'MODEL_TYPE_OPENAI',
    'MODEL_TYPE_DEEPSEEK',
    'MODEL_TYPE_AZURE',
    'MODEL_TYPE_VLLM',
    'SUPPORTED_MODEL_TYPES',
    'autodetect_module',
    'current_settings',
    'get_env'
]