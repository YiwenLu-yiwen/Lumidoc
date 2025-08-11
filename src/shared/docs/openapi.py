"""
OpenAPI文档工具
提供FastAPI应用的OpenAPI/Swagger文档定制功能
"""

import os
from typing import Dict, Any, List, Optional, Callable
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRouter

def setup_swagger_ui(
    app: FastAPI,
    title: str,
    version: str,
    custom_middleware: bool = True,
    swagger_js_url: Optional[str] = None,
    swagger_css_url: Optional[str] = None,
    redoc_js_url: Optional[str] = None,
    enable_redoc: bool = True
) -> None:
    """
    设置自定义Swagger UI和ReDoc文档
    
    Args:
        app: FastAPI应用实例
        title: API标题
        version: API版本
        custom_middleware: 是否添加自定义中间件来保护文档
        swagger_js_url: 自定义Swagger JS URL
        swagger_css_url: 自定义Swagger CSS URL
        redoc_js_url: 自定义ReDoc JS URL
        enable_redoc: 是否启用ReDoc
    """
    # 关闭默认文档路由
    app.docs_url = None
    app.redoc_url = None
    
    # 自定义文档配置
    swagger_js = swagger_js_url or "https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js"
    swagger_css = swagger_css_url or "https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css"
    redoc_js = redoc_js_url or "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
    
    # 自定义OpenAPI模式
    def custom_openapi() -> Dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
            
        openapi_schema = get_openapi(
            title=title,
            version=version,
            description=app.description,
            routes=app.routes,
        )
        
        # 添加API版本标签和其他自定义信息
        openapi_schema["info"]["x-api-version"] = version
        openapi_schema["info"]["x-service-name"] = title.lower().replace(" ", "-")
        
        # 添加安全定义（如果应用中配置了安全）
        if hasattr(app, "security_schemes") and app.security_schemes:
            if "components" not in openapi_schema:
                openapi_schema["components"] = {}
            openapi_schema["components"]["securitySchemes"] = app.security_schemes
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    # 设置自定义OpenAPI模式
    app.openapi = custom_openapi
    
    # 添加文档路由
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """自定义Swagger UI文档"""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url=swagger_js,
            swagger_css_url=swagger_css,
        )
        
    # 添加ReDoc文档路由
    if enable_redoc:
        @app.get("/redoc", include_in_schema=False)
        async def custom_redoc_html():
            """自定义ReDoc文档"""
            return get_redoc_html(
                openapi_url=app.openapi_url,
                title=f"{title} - ReDoc",
                redoc_js_url=redoc_js,
            )
    
    # 添加保护中间件（如果需要）
    if custom_middleware and os.getenv("API_DOCS_PASSWORD"):
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import Response, JSONResponse
        import base64
        
        class DocsAuthMiddleware(BaseHTTPMiddleware):
            """保护API文档的中间件"""
            
            async def dispatch(self, request: Request, call_next: Callable) -> Response:
                """检查文档路径的Basic认证"""
                path = request.url.path
                if path in ["/docs", "/redoc", "/openapi.json"]:
                    # 从环境变量获取密码
                    password = os.getenv("API_DOCS_PASSWORD", "")
                    auth_header = request.headers.get("Authorization", "")
                    
                    # 如果未配置密码或已提供正确认证，允许访问
                    if not password or auth_header.startswith("Basic "):
                        if not password:
                            return await call_next(request)
                            
                        # 验证Basic认证
                        try:
                            credentials = auth_header.split(" ")[1]
                            decoded = base64.b64decode(credentials).decode("utf-8")
                            username, provided_password = decoded.split(":")
                            if provided_password == password:
                                return await call_next(request)
                        except Exception:
                            pass
                    
                    # 未通过认证，返回401并请求Basic认证
                    headers = {"WWW-Authenticate": 'Basic realm="API Documentation"'}
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Unauthorized"},
                        headers=headers
                    )
                
                # 非文档路径，正常处理
                return await call_next(request)
        
        # 添加中间件
        app.add_middleware(DocsAuthMiddleware)


def add_api_metadata(
    app: FastAPI,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_url: Optional[str] = None,
    license_name: Optional[str] = "MIT",
    license_url: Optional[str] = None,
    terms_of_service: Optional[str] = None,
    tags_metadata: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    添加API元数据到OpenAPI文档
    
    Args:
        app: FastAPI应用实例
        contact_name: 联系人姓名
        contact_email: 联系人邮箱
        contact_url: 联系人URL
        license_name: 许可证名称
        license_url: 许可证URL
        terms_of_service: 服务条款URL
        tags_metadata: 标签元数据列表
    """
    # 构建联系人信息
    contact = {}
    if contact_name:
        contact["name"] = contact_name
    if contact_email:
        contact["email"] = contact_email
    if contact_url:
        contact["url"] = contact_url
    
    # 构建许可证信息
    license_info = {}
    if license_name:
        license_info["name"] = license_name
    if license_url:
        license_info["url"] = license_url
    
    # 更新元数据
    if contact:
        app.contact = contact
    if license_info:
        app.license_info = license_info
    if terms_of_service:
        app.terms_of_service = terms_of_service
    if tags_metadata:
        app.openapi_tags = tags_metadata


def add_api_route_tags(
    router: APIRouter,
    tags: List[str],
    prefix_description: Optional[str] = None
) -> None:
    """
    为APIRouter中的所有路由添加统一标签
    
    Args:
        router: APIRouter实例
        tags: 要添加的标签列表
        prefix_description: 路由前缀的描述（将添加到操作描述中）
    """
    # 遍历所有路由
    for route in router.routes:
        # 为每个路由添加标签
        if not hasattr(route, "tags") or route.tags is None:
            route.tags = []
        route.tags.extend(tags)
        
        # 添加前缀描述（如果提供）
        if prefix_description and hasattr(route, "description") and route.description:
            # 只有在描述不为空时添加
            prefix = f"{prefix_description}: "
            if not route.description.startswith(prefix):
                route.description = f"{prefix}{route.description}" 


def setup_openapi(
    app: FastAPI,
    title: Optional[str] = None,
    version: Optional[str] = "1.0.0",
    description: Optional[str] = None,
    contact: Optional[Dict[str, str]] = None,
    license_info: Optional[Dict[str, str]] = None,
    enable_swagger: bool = True,
    enable_redoc: bool = True,
    swagger_js_url: Optional[str] = None,
    swagger_css_url: Optional[str] = None,
    redoc_js_url: Optional[str] = None,
    protected: bool = False
) -> None:
    """
    设置OpenAPI文档
    
    Args:
        app: FastAPI应用实例
        title: API标题
        version: API版本
        description: API描述
        contact: 联系人信息
        license_info: 许可证信息
        enable_swagger: 是否启用Swagger UI
        enable_redoc: 是否启用ReDoc
        swagger_js_url: 自定义Swagger JS URL
        swagger_css_url: 自定义Swagger CSS URL
        redoc_js_url: 自定义ReDoc JS URL
        protected: 是否保护文档访问
    """
    # 获取默认值
    api_title = title or app.title or "API"
    api_version = version or "1.0.0"
    api_description = description or app.description or "API文档"
    
    # 设置应用元数据
    app.title = api_title
    app.version = api_version
    app.description = api_description
    
    # 设置联系人信息
    if contact:
        app.contact = contact
    
    # 设置许可证信息
    if license_info:
        app.license_info = license_info
    
    # 设置Swagger UI
    if enable_swagger:
        setup_swagger_ui(
            app=app,
            title=api_title,
            version=api_version,
            custom_middleware=protected,
            swagger_js_url=swagger_js_url,
            swagger_css_url=swagger_css_url,
            redoc_js_url=redoc_js_url,
            enable_redoc=enable_redoc
        )
    
    # 添加额外的OpenAPI信息
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
            
        openapi_schema = get_openapi(
            title=api_title,
            version=api_version,
            description=api_description,
            routes=app.routes,
        )
        
        # 添加自定义信息
        openapi_schema["info"]["x-api-version"] = api_version
        openapi_schema["info"]["x-service-name"] = api_title.lower().replace(" ", "-")
        openapi_schema["info"]["x-generated-by"] = "STP Platform"
        
        # 添加服务器信息
        openapi_schema["servers"] = [
            {"url": "/", "description": "当前服务器"}
        ]
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi 