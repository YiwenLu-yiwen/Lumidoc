#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
问题服务启动入口
"""

import uvicorn
import sys
import os

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 更新配置导入
from STP_webui.backend.api.question_routes import app
from src.shared.config import QuestionServiceSettings
settings_base = QuestionServiceSettings()
from .config.config import settings

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 