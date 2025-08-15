#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理路由模块
"""

from .process_routes import router as process_router
from .diagnostic_routes import diagnostics_router
from .stream_routes import stream_router

# 确保导出正确的路由器，用于主应用程序注册
__all__ = ['process_router', 'diagnostics_router', 'stream_router'] 