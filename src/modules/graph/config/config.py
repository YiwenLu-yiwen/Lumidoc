"""
图谱服务配置
使用统一配置系统
"""

import os
from pathlib import Path
from typing import Dict, Any
from src.shared.config import GraphServiceSettings, get_env

# 创建全局设置实例
settings_base = GraphServiceSettings()

# 为了保持向后兼容性，提供与原有全局变量相同名称的变量
class ExtendedGraphSettings:
    """图谱服务扩展配置项，保持向后兼容性"""
    
    # 存储模式配置
    storage_mode: str = settings_base.storage_mode
    
    # Neo4j 配置
    neo4j_uri: str = get_env("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = get_env("NEO4J_USER", "neo4j")
    neo4j_password: str = get_env("NEO4J_PASSWORD", "password")
    
    # 本地存储配置
    local_storage_dir: str = get_env("GRAPH_LOCAL_STORAGE_DIR", "./data/graphs")
    
    # 默认节点和边的样式
    default_node_size: int = 10
    default_node_color: str = "#1f77b4"
    default_edge_size: int = 1
    default_edge_color: str = "#999999"
    
    # 布局配置
    default_layout: str = "force"  # 可选: "force", "circular", "grid", "hierarchical"
    layout_config: Dict[str, Dict[str, Any]] = {
        "force": {
            "link_distance": 100,
            "charge": -100,
            "gravity": 0.1,
            "theta": 0.8
        },
        "circular": {
            "radius": 200,
            "start_angle": 0,
            "end_angle": 2 * 3.14159
        },
        "grid": {
            "rows": 5,
            "cols": 5,
            "spacing": 100
        },
        "hierarchical": {
            "direction": "LR",  # 可选: "LR", "RL", "TB", "BT"
            "node_separation": 100,
            "level_separation": 200
        }
    }
    
    # 图谱分析配置
    analysis_config: Dict[str, Any] = {
        "key_node_threshold": 0.2,  # 关键节点阈值（前20%）
        "key_relationship_threshold": 0.2,  # 关键关系阈值（前20%）
        "relationship_strength_weights": {
            "is_a": 1.5,
            "part_of": 1.5,
            "related_to": 0.8,
            "similar_to": 0.8,
            "default": 1.0
        }
    }
    
    # 缓存配置
    cache_config: Dict[str, Any] = {
        "enabled": True,
        "ttl": 3600,  # 缓存时间（秒）
        "max_size": 1000  # 最大缓存条目数
    }

# 创建配置实例
settings = ExtendedGraphSettings()

# 为了保持向后兼容性，提供与原有全局变量相同名称的变量
STORAGE_MODE = settings.storage_mode
NEO4J_URI = settings.neo4j_uri
NEO4J_USER = settings.neo4j_user
NEO4J_PASSWORD = settings.neo4j_password
LOCAL_STORAGE_DIR = settings.local_storage_dir
DEFAULT_NODE_SIZE = settings.default_node_size
DEFAULT_NODE_COLOR = settings.default_node_color
DEFAULT_EDGE_SIZE = settings.default_edge_size
DEFAULT_EDGE_COLOR = settings.default_edge_color
DEFAULT_LAYOUT = settings.default_layout
LAYOUT_CONFIG = settings.layout_config
ANALYSIS_CONFIG = settings.analysis_config
CACHE_CONFIG = settings.cache_config 

# 图可视化配置
node_type_colors = {
    "Person": "#1f77b4",
    "Organization": "#ff7f0e",
    "Concept": "#2ca02c",
    "Event": "#d62728",
    "Location": "#9467bd",
    "Product": "#8c564b",
    "Document": "#e377c2",
    "default": "#7f7f7f"
}

edge_default_color = "#999"

# 临时目录配置
temp_dir = "./temp" 