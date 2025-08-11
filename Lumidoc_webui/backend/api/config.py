"""
配置桥接模块
将配置导出到可以被所有模块访问的地方
"""

from Lumidoc_webui.backend.api.config import settings

# 导出设置
__all__ = ['settings'] 