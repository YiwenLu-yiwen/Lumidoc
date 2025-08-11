#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM API入口点
导入并组织所有路由
"""

from fastapi import APIRouter
from ..routes.router import router as llm_router

# 创建主路由
router = APIRouter()

# 包含所有子路由
router.include_router(llm_router) 