"""
配置加载工具
提供统一的环境变量处理和配置文件加载
"""

import os
import json
import yaml
import logging
from typing import Any, Dict, Optional, Union, TypeVar, Type, cast
from pathlib import Path
from pydantic import BaseModel, create_model
from dotenv import load_dotenv

# 定义日志记录器
logger = logging.getLogger(__name__)

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

# 自动加载项目根目录的.env文件
env_file = ROOT_DIR / '.env'
if env_file.exists():
    logger.info(f"加载环境变量文件: {env_file}")
    load_dotenv(env_file)

# 类型变量
T = TypeVar('T')

def get_env(key: str, default: Any = None, required: bool = False, env_type: Type[T] = str) -> T:
    """
    从环境变量中获取配置值，支持类型转换
    
    Args:
        key: 环境变量名
        default: 默认值
        required: 是否必须
        env_type: 期望的类型
        
    Returns:
        转换后的环境变量值
    
    Raises:
        ValueError: 当required=True且环境变量不存在时抛出
    """
    value = os.environ.get(key)
    
    # 检查是否存在且必须
    if value is None:
        if required:
            raise ValueError(f"必需的环境变量 '{key}' 未设置")
        return default
    
    # 类型转换
    try:
        if env_type is bool:
            # 特殊处理布尔值
            return cast(T, value.lower() in ('true', '1', 'yes', 'y', 'on'))
        elif env_type is int:
            return cast(T, int(value))
        elif env_type is float:
            return cast(T, float(value))
        elif env_type is list:
            # 处理列表，用逗号分隔
            return cast(T, [item.strip() for item in value.split(',')])
        elif env_type is dict:
            # 尝试解析JSON
            return cast(T, json.loads(value))
        else:
            # 默认为字符串或其他直接转换
            return cast(T, value)
    except Exception as e:
        logger.warning(f"环境变量 '{key}' 转换为类型 {env_type.__name__} 失败: {e}")
        return default


def _yaml_to_dict(yaml_path: Union[str, Path]) -> Dict[str, Any]:
    """
    加载YAML文件为字典
    
    Args:
        yaml_path: YAML文件路径
        
    Returns:
        解析后的字典
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        logger.warning(f"配置文件不存在: {yaml_path}")
        return {}
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"解析YAML文件失败: {yaml_path}, 错误: {e}")
        return {}


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    env_prefix: str = "",
    config_model: Optional[Type[BaseModel]] = None,
    nested_delimiter: str = "__"
) -> Union[Dict[str, Any], BaseModel]:
    """
    加载配置，支持从配置文件和环境变量获取
    环境变量优先级高于配置文件
    
    Args:
        config_path: 配置文件路径
        env_prefix: 环境变量前缀
        config_model: Pydantic模型类，如果提供则返回模型实例
        nested_delimiter: 嵌套字段的分隔符
        
    Returns:
        配置字典或模型实例
    """
    # 默认配置
    config: Dict[str, Any] = {}
    
    # 从配置文件加载
    if config_path:
        file_path = Path(config_path) if isinstance(config_path, str) else config_path
        file_ext = file_path.suffix.lower()
        
        if file_ext in ['.yaml', '.yml']:
            config.update(_yaml_to_dict(file_path))
        elif file_ext == '.json':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception as e:
                logger.error(f"解析JSON文件失败: {file_path}, 错误: {e}")
        else:
            logger.warning(f"不支持的配置文件类型: {file_ext}")
    
    # 从环境变量覆盖配置
    for env_key, env_value in os.environ.items():
        # 检查前缀
        if env_prefix and not env_key.startswith(env_prefix):
            continue
            
        # 移除前缀
        key = env_key[len(env_prefix):] if env_prefix else env_key
        
        # 处理嵌套结构
        if nested_delimiter in key:
            parts = key.split(nested_delimiter)
            current = config
            for part in parts[:-1]:
                # 创建嵌套字典
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = env_value
        else:
            config[key] = env_value
    
    # 如果提供了模型，则转换为模型实例
    if config_model:
        try:
            return config_model(**config)
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            # 创建临时模型以允许部分配置
            temp_model = create_model(
                'TempConfig',
                **{k: (type(v), v) for k, v in config.items()}
            )
            return temp_model(**config)
    
    return config 