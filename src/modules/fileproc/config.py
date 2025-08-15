#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理服务配置
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.shared.config import FileProcServiceSettings, get_env

# 创建全局设置实例
try:
    settings = FileProcServiceSettings()
    print(f"文件处理服务配置加载成功: 端口={settings.port}")
except Exception as e:
    print(f"文件处理服务配置加载失败: {str(e)}")
    raise  # 配置加载失败应该立即停止服务

# 确保必要的目录存在
for directory in [settings.storage_dir, settings.upload_dir, settings.temp_dir]:
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f"已创建目录: {directory}") 