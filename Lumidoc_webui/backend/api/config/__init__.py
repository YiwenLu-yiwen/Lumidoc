"""
配置桥接模块
确保所有服务可以通过统一的路径导入配置

使用方法：
from config import settings
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

# 导入src/modules/config中的settings
from src.modules.config import settings

# 向上导出settings
__all__ = ['settings'] 