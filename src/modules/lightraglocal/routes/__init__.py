"""
LightRAG路由模块 - 企业级版本
"""

# 使用企业级路由
from .enterprise_rag_routes import router as enterprise_router

# 默认使用企业级路由
router = enterprise_router

__all__ = ["router", "enterprise_router"] 