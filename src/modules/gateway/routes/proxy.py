"""
Gateway代理路由处理器
"""

import logging
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from src.modules.gateway.services.proxy import get_request_proxy, RequestProxy
from src.modules.gateway.config.config import settings

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# 获取代理依赖
async def get_proxy() -> RequestProxy:
    """获取代理实例"""
    return await get_request_proxy()

# 动态创建服务路由
def create_service_routes():
    """动态创建所有服务的路由"""
    
    for service_name, service_config in settings.service_routes.items():
        prefix = service_config.get("prefix", f"/{service_name}")
        
        # 为每个服务创建路由处理器
        create_service_route(service_name, prefix)
        
        # 支持额外的前缀路径
        alt_prefixes = service_config.get("alt_prefixes", [])
        for alt_prefix in alt_prefixes:
            create_service_route(service_name, alt_prefix)

def create_service_route(service_name: str, prefix: str):
    """为指定服务创建路由"""
    
    # 创建通用路由处理器
    async def service_handler(
        request: Request,
        proxy: RequestProxy = Depends(get_proxy)
    ) -> Response:
        """服务路由处理器"""
        logger.info(f"代理请求到服务: {service_name}, 路径: {request.url.path}")
        
        try:
            # 代理请求到目标服务
            response = await proxy.proxy_request(
                request=request,
                service_name=service_name
            )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"代理请求失败: {service_name} - {str(e)}")
            raise HTTPException(
                status_code=502,
                detail=f"服务 {service_name} 代理失败"
            )
    
    # 注册路由 - 匹配所有HTTP方法和路径
    router.add_api_route(
        f"{prefix}/{{path:path}}",
        service_handler,
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        name=f"{service_name}_proxy"
    )
    
    # 注册根路径路由
    router.add_api_route(
        prefix,
        service_handler,
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        name=f"{service_name}_root_proxy"
    )
    
    logger.info(f"已注册服务路由: {service_name} -> {prefix}")

# 健康检查路由
@router.get("/health", tags=["健康检查"])
@router.get("/gateway/health", tags=["健康检查"])  # 添加gateway前缀的路由
async def gateway_health():
    """Gateway健康检查"""
    from src.modules.gateway.services.service_discovery import get_service_discovery
    
    try:
        service_discovery = await get_service_discovery()
        services_status = await service_discovery.get_all_services_status()
        
        # 计算整体健康状态
        total_services = 0
        healthy_services = 0
        
        for service_name, instances in services_status.items():
            for instance in instances:
                total_services += 1
                if instance["health_status"] == "healthy":
                    healthy_services += 1
        
        health_ratio = healthy_services / total_services if total_services > 0 else 0
        
        return {
            "status": "healthy" if health_ratio >= 0.5 else "unhealthy",
            "gateway_version": settings.service_version,
            "total_services": total_services,
            "healthy_services": healthy_services,
            "health_ratio": health_ratio,
            "services": services_status
        }
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# 服务状态路由
@router.get("/services", tags=["服务管理"])
async def get_services_status():
    """获取所有服务状态"""
    from src.modules.gateway.services.service_discovery import get_service_discovery
    
    try:
        service_discovery = await get_service_discovery()
        services_status = await service_discovery.get_all_services_status()
        
        return {
            "success": True,
            "services": services_status,
            "total_services": len(services_status)
        }
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取服务状态失败: {str(e)}"
        )

# 服务重新发现路由
@router.post("/services/refresh", tags=["服务管理"])
async def refresh_services():
    """重新发现服务"""
    from src.modules.gateway.services.service_discovery import get_service_discovery
    
    try:
        service_discovery = await get_service_discovery()
        await service_discovery.load_static_services()
        
        return {
            "success": True,
            "message": "服务重新发现完成"
        }
        
    except Exception as e:
        logger.error(f"服务重新发现失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"服务重新发现失败: {str(e)}"
        )

# 根路径路由
@router.get("/", tags=["信息"])
async def gateway_root():
    """Gateway根路径"""
    return {
        "message": "欢迎使用Lumidoc系统API网关",
        "name": settings.service_name,
        "version": settings.service_version,
        "description": settings.service_description,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "info": "/info", 
            "services": "/services",
            "docs": "/docs"
        },
        "available_services": list(settings.service_routes.keys())
    }

# API文档路由
@router.get("/info", tags=["信息"])
async def gateway_info():
    """Gateway信息"""
    return {
        "name": settings.service_name,
        "version": settings.service_version,
        "description": settings.service_description,
        "services": list(settings.service_routes.keys()),
        "configuration": {
            "auth_enabled": settings.auth_enabled,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "health_check_enabled": settings.health_check_enabled,
            "load_balancer_enabled": settings.load_balancer_enabled,
            "load_balancer_algorithm": settings.load_balancer_algorithm
        }
    }

# 初始化时创建所有服务路由
create_service_routes()

logger.info(f"Gateway路由初始化完成，已注册 {len(settings.service_routes)} 个服务路由") 