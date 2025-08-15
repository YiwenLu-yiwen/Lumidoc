import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from fastapi import APIRouter, HTTPException, Depends, Body, FastAPI
import httpx
from src.modules.config import settings
from src.shared.auth import get_current_user
from src.shared.types.response import ApiResponse

# 创建路由
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])
logger = logging.getLogger(__name__)

# 添加监控服务连接检查
async def check_monitoring_service():
    """检查监控服务基本功能（不调用自身）"""
    try:
        # 检查基本功能而不是调用自身的健康检查
        import psutil
        # 简单检查：能否获取系统信息
        _ = psutil.virtual_memory()
        return True
    except Exception as e:
        logger.error(f"监控服务基本功能检查失败: {str(e)}")
        return False

# 添加系统资源检查
async def check_system_resources():
    """检查系统资源"""
    try:
        import psutil
        
        # 检查内存使用率
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return False
            
        # 检查CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            return False
            
        # 检查磁盘使用率
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            return False
            
        return True
    except Exception as e:
        logger.error(f"系统资源检查失败: {str(e)}")
        return False

# 配置健康检查项
health_checker.add_check("monitoring_service", check_monitoring_service, critical=True)
health_checker.add_check("system_resources", check_system_resources, critical=False)

# 注册统一健康检查路由
register_health_routes(app, health_checker)

# 获取监控服务客户端
async def get_monitoring_service():
    """获取监控服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

async def handle_service_response(response: httpx.Response, operation: str) -> Dict[str, Any]:
    """统一处理服务响应"""
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"{operation} failed with status {e.response.status_code}: {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Monitoring service error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"{operation} failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/health", response_model=ApiResponse)
async def check_health(
    user=Depends(get_current_user),
    client=Depends(get_monitoring_service)
):
    """检查服务健康状态"""
    logger.info(f"Checking health status for user {user.id}")
    try:
        response = await client.get(
            f"{settings.monitoring_service_url}/health"
        )
        return await handle_service_response(response, "Check health")
    except Exception as e:
        logger.error(f"Failed to check health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    user=Depends(get_current_user),
    client=Depends(get_monitoring_service)
):
    """获取服务指标"""
    logger.info(f"Getting metrics for user {user.id}")
    try:
        response = await client.get(
            f"{settings.monitoring_service_url}/metrics"
        )
        return await handle_service_response(response, "Get metrics")
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs", response_model=List[Dict[str, Any]])
async def get_logs(
    level: Optional[str] = None,
    limit: Optional[int] = 100,
    user=Depends(get_current_user),
    client=Depends(get_monitoring_service)
):
    """获取服务日志"""
    logger.info(f"Getting logs for user {user.id}")
    try:
        params = {}
        if level:
            params["level"] = level
        if limit:
            params["limit"] = limit
            
        response = await client.get(
            f"{settings.monitoring_service_url}/logs",
            params=params
        )
        return await handle_service_response(response, "Get logs")
    except Exception as e:
        logger.error(f"Failed to get logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_alerts(
    status: Optional[str] = None,
    user=Depends(get_current_user),
    client=Depends(get_monitoring_service)
):
    """获取告警信息"""
    logger.info(f"Getting alerts for user {user.id}")
    try:
        params = {}
        if status:
            params["status"] = status
            
        response = await client.get(
            f"{settings.monitoring_service_url}/alerts",
            params=params
        )
        return await handle_service_response(response, "Get alerts")
    except Exception as e:
        logger.error(f"Failed to get alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 注册路由
app.include_router(router)

# 定义lifespan事件管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    try:
        await health_checker.start()
        logger.info("Monitoring服务启动成功")
        
        # 注册到服务发现
        from src.shared.service_discovery import register_service
        await register_service("monitoring", port=8008, health_check_endpoint="/healthz")
        
    except Exception as e:
        logger.error(f"Monitoring服务启动失败: {str(e)}")
        
    yield
    
    # 关闭事件
    try:
        await health_checker.stop()
        logger.info("Monitoring服务关闭")
        
        # 从服务发现注销
        from src.shared.service_discovery import unregister_service
        await unregister_service("monitoring")
        
    except Exception as e:
        logger.error(f"Monitoring服务关闭失败: {str(e)}")

# 创建FastAPI应用
app = FastAPI(
    title="Monitoring Service", 
    description="监控服务",
    lifespan=lifespan
) 