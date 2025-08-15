# 企业级 LightRAG 服务模块

# 使用企业级 LightRAG 服务
from .enterprise_lightrag_service import (
    get_enterprise_lightrag_service,
    initialize_lightrag_service,
    EnterpriseLightRAGService
)

# 向后兼容：保持原有的导入方式
try:
    import asyncio
    lightrag_service = asyncio.run(get_enterprise_lightrag_service())
except:
    lightrag_service = None

# 导出企业级组件
__all__ = [
    "get_enterprise_lightrag_service",
    "initialize_lightrag_service", 
    "EnterpriseLightRAGService",
    "lightrag_service"  # 向后兼容
]