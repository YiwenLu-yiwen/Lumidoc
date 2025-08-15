"""
API版本控制工具
提供FastAPI应用的API版本管理功能
"""

from typing import Dict, Any, Optional, List, Callable, Type, TypeVar, Union
from fastapi import FastAPI, APIRouter, Depends, Header, Path, Request, Response
from fastapi.routing import APIRoute
import re
import warnings

T = TypeVar('T')

class VersionedAPIRouter(APIRouter):
    """
    支持版本控制的API路由器
    允许按版本隔离和管理API端点
    """
    
    def __init__(
        self, 
        *args, 
        version: str = "1", 
        deprecated_versions: Optional[List[str]] = None,
        **kwargs
    ):
        """
        初始化版本控制API路由器
        
        Args:
            version: API版本，例如 "1"
            deprecated_versions: 已弃用的版本列表
            *args, **kwargs: 传递给FastAPI APIRouter的参数
        """
        # 确保前缀格式正确
        prefix = kwargs.get("prefix", "")
        if prefix and not prefix.startswith("/"):
            prefix = f"/{prefix}"
        
        # 构建带版本的前缀
        version_prefix = f"/v{version}"
        if prefix:
            version_prefix = f"{version_prefix}{prefix}"
        
        # 更新前缀
        kwargs["prefix"] = version_prefix
        
        # 初始化父类
        super().__init__(*args, **kwargs)
        
        # 保存版本信息
        self.version = version
        self.deprecated_versions = deprecated_versions or []
        
        # 添加版本标签
        tags = kwargs.get("tags", [])
        if f"v{version}" not in tags:
            self.tags.append(f"v{version}")


def version_header(
    request: Request,
    response: Response,
    api_version: Optional[str] = Header(None, alias="X-API-Version"),
    accept_header: Optional[str] = Header(None, alias="Accept")
) -> str:
    """
    从请求头中提取API版本
    支持X-API-Version头或Accept头中的版本信息
    
    Args:
        request: 请求对象
        response: 响应对象
        api_version: X-API-Version头的值
        accept_header: Accept头的值
        
    Returns:
        API版本字符串，默认为最新版本
    """
    # 默认版本
    default_version = "latest"
    version = default_version
    
    # 从X-API-Version头中获取
    if api_version:
        version = api_version
    
    # 从Accept头中解析版本
    # 例如: "application/json;version=2"
    elif accept_header:
        version_pattern = r"version=([^;]+)"
        match = re.search(version_pattern, accept_header)
        if match:
            version = match.group(1)
    
    # 规范化版本字符串
    if version != "latest":
        # 移除任何非数字和点的字符
        version = re.sub(r"[^0-9.]", "", version)
    
    # 设置响应头中的API版本
    response.headers["X-API-Version"] = version
    
    return version


def create_versioned_app(title: str, description: Optional[str] = None) -> FastAPI:
    """
    创建支持版本控制的FastAPI应用
    
    Args:
        title: API标题
        description: API描述
        
    Returns:
        FastAPI应用实例
    """
    app = FastAPI(title=title, description=description)
    
    # 添加版本检测中间件
    @app.middleware("http")
    async def version_middleware(request: Request, call_next: Callable) -> Response:
        """处理API版本中间件"""
        response = await call_next(request)
        
        # 获取路由中的版本信息
        path = request.url.path
        version_match = re.match(r"/v([^/]+)", path)
        
        if version_match:
            version = version_match.group(1)
            # 添加版本响应头
            response.headers["X-API-Version"] = version
            
            # 检查是否是弃用版本
            deprecated_versions = getattr(app, "deprecated_versions", [])
            if version in deprecated_versions:
                response.headers["X-API-Deprecated"] = "True"
                response.headers["X-API-Deprecation-Info"] = "This API version is deprecated and will be removed in future releases."
        
        return response
    
    return app


def include_versioned_routers(
    app: FastAPI,
    routers: Dict[str, APIRouter],
    deprecated_versions: Optional[List[str]] = None
) -> None:
    """
    将多个版本的路由器添加到应用
    
    Args:
        app: FastAPI应用实例
        routers: 版本和路由器的映射，例如 {"1": router_v1, "2": router_v2}
        deprecated_versions: 已弃用的版本列表
    """
    deprecated = deprecated_versions or []
    
    # 保存弃用版本信息
    app.deprecated_versions = deprecated
    
    # 注册每个版本的路由器
    for version, router in routers.items():
        # 检查是否已弃用
        if version in deprecated:
            # 添加弃用警告
            for route in router.routes:
                if hasattr(route, "deprecated") and not route.deprecated:
                    # 只标记未明确标记为弃用的路由
                    route.deprecated = True
        
        # 将路由器包含到应用
        app.include_router(router)
    
    # 创建最新版本的重定向
    latest_version = max(routers.keys(), key=lambda v: [int(x) for x in v.split(".")])
    latest_router = routers[latest_version]
    
    # 为最新版本创建未版本化路由
    for route in latest_router.routes:
        if isinstance(route, APIRoute):
            # 从路由路径中移除版本前缀
            path = route.path
            unversioned_path = re.sub(r"^/v[^/]+", "", path)
            
            # 添加到应用
            app.add_api_route(
                path=unversioned_path,
                endpoint=route.endpoint,
                response_model=route.response_model,
                status_code=route.status_code,
                tags=route.tags + ["latest"],
                dependencies=route.dependencies,
                summary=route.summary,
                description=f"[Latest: v{latest_version}] {route.description or ''}",
                response_description=route.response_description,
                deprecated=route.deprecated,
                methods=route.methods,
                operation_id=route.name,
                include_in_schema=route.include_in_schema,
                response_model_exclude_none=route.response_model_exclude_none,
                response_model_exclude_unset=route.response_model_exclude_unset,
                response_model_exclude_defaults=route.response_model_exclude_defaults,
                response_model_include=route.response_model_include,
                response_model_exclude=route.response_model_exclude,
            ) 


def get_version_info() -> Dict[str, Any]:
    """
    获取API版本信息
    
    Returns:
        Dict[str, Any]: 版本信息字典
    """
    return {
        "version": "1.0.0",
        "api_version": "v1",
        "build_timestamp": "2024-01-01T00:00:00Z",
        "supported_versions": ["v1"],
        "deprecated_versions": [],
        "service_name": "STP API",
        "description": "STP智能工具平台API服务",
        "features": [
            "用户认证",
            "文件管理",
            "项目管理",
            "聊天服务",
            "知识图谱",
            "LLM集成",
            "RAG增强"
        ],
        "endpoints": {
            "auth": "/auth",
            "chat": "/chat",
            "file": "/file",
            "fileproc": "/fileproc",
            "graph": "/graph",
            "rag": "/rag",
            "llm": "/llm",
            "monitoring": "/monitoring",
            "project": "/project",
            "question": "/question"
        }
    }


def get_service_version(service_name: str) -> Dict[str, Any]:
    """
    获取特定服务的版本信息
    
    Args:
        service_name: 服务名称
        
    Returns:
        Dict[str, Any]: 服务版本信息
    """
    base_info = get_version_info()
    
    service_versions = {
        "auth": "1.0.0",
        "chat": "1.0.0", 
        "file": "1.0.0",
        "fileproc": "1.0.0",
        "graph": "1.0.0",
        "lightrag": "1.0.0",
        "llm": "1.0.0",
        "monitoring": "1.0.0",
        "project": "1.0.0",
        "question": "1.0.0",
        "gateway": "1.0.0"
    }
    
    return {
        "service": service_name,
        "version": service_versions.get(service_name, "1.0.0"),
        "api_version": base_info["api_version"],
        "build_timestamp": base_info["build_timestamp"],
        "description": f"STP {service_name}服务",
        "status": "active"
    } 