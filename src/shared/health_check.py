"""
健康检查模块
提供统一的服务健康状态监控与上报
"""

import os
import logging
import asyncio
import time
import json
import socket
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Set, Tuple
import psutil
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, APIRouter
import sys
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import status
import inspect
import traceback

from src.shared.service_discovery import ServiceHealth, get_service_client
from src.database import get_connection_status
from src.shared.models.health_models import HealthResponse, ServiceHealthCheck

# 配置日志
logger = logging.getLogger(__name__)

# 健康检查配置
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
MAX_MEMORY_PERCENT = float(os.getenv("MAX_MEMORY_PERCENT", "90.0"))
MAX_CPU_PERCENT = float(os.getenv("MAX_CPU_PERCENT", "90.0"))
MAX_DISK_PERCENT = float(os.getenv("MAX_DISK_PERCENT", "90.0"))
MIN_FREE_MEMORY_MB = int(os.getenv("MIN_FREE_MEMORY_MB", "100")) 
REDIS_URL = os.getenv("REDIS_URL", f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}")

# 状态定义
class ServiceStatus:
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"

# 健康指标定义
class HealthMetric:
    def __init__(self, name: str, status: str = ServiceStatus.UNKNOWN, value: Any = None, 
                 threshold: Any = None, message: str = None):
        self.name = name
        self.status = status
        self.value = value
        self.threshold = threshold
        self.message = message
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp
        }

class HealthChecker:
    """健康检查器"""
    
    def __init__(self, service_name: str, service_id: str = None):
        """初始化健康检查器"""
        self.service_name = service_name
        self.service_id = service_id or str(uuid.uuid4())
        self.version = os.environ.get("VERSION", "1.0.0")
        self.checks = []
        self.db_connections = []
        self.redis_connections = []
        self.service_connections = []
        self.startup_time = datetime.now()
        self._running = False
        self._check_task = None
        
    async def start(self):
        """启动健康检查器"""
        if self._running:
            return
            
        self._running = True
        logger.info(f"健康检查器已启动: {self.service_name}")
        return self
        
    async def stop(self):
        """停止健康检查器"""
        if not self._running:
            return
            
        self._running = False
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            
        logger.info(f"健康检查器已停止: {self.service_name}")
        
    def add_check(self, name: str, check_fn, critical: bool = False):
        """添加健康检查项"""
        self.checks.append({
            "name": name,
            "check": check_fn,
            "critical": critical
        })
        
    def add_db_connection(self, name: str, connection):
        """添加数据库连接检查"""
        self.db_connections.append({
            "name": name,
            "connection": connection
        })
        
    def add_redis_connection(self, name: str, connection):
        """添加Redis连接检查"""
        self.redis_connections.append({
            "name": name,
            "connection": connection
        })
        
    def add_service_connection(self, service_name: str):
        """添加服务连接检查"""
        self.service_connections.append(service_name)
        
    async def check_health(self) -> Dict[str, Any]:
        """
        执行所有健康检查
        
        Returns:
            Dict[str, Any]: 健康检查结果
        """
        result = {
            "status": "ok",
            "service_id": self.service_id or "unknown",
            "service_name": self.service_name,
            "version": self.version,
            "timestamp": datetime.now().isoformat(),
            "checks": {}  # 改为字典格式
        }
        
        # 执行所有自定义检查
        critical_failure = False
        for check in self.checks:
            check_name = check["name"]
            check_fn = check["check"]
            critical = check["critical"]
            
            try:
                status = await check_fn() if inspect.iscoroutinefunction(check_fn) else check_fn()
                result["checks"][check_name] = {
                    "status": "ok" if status else "error",
                    "critical": critical
                }
                
                if not status and critical:
                    critical_failure = True
            except Exception as e:
                result["checks"][check_name] = {
                    "status": "error", 
                    "message": str(e),
                    "critical": critical
                }
                if critical:
                    critical_failure = True

        # 检查数据库连接
        for db in self.db_connections:
            db_name = db["name"]
            db_conn = db["connection"]
            try:
                if hasattr(db_conn, "initialize") and callable(db_conn.initialize):
                    status = await db_conn.initialize()
                else:
                    # 默认方法
                    status = True  # 假设连接正常
                    
                result["checks"][f"db_{db_name}"] = {
                    "status": "ok" if status else "error",
                    "critical": True
                }
                
                if not status:
                    critical_failure = True
            except Exception as e:
                result["checks"][f"db_{db_name}"] = {
                    "status": "error", 
                    "message": str(e),
                    "critical": True
                }
                critical_failure = True

        # 检查Redis连接
        for redis in self.redis_connections:
            redis_name = redis["name"]
            redis_conn = redis["connection"]
            try:
                if redis_conn:
                    status = await redis_conn.ping()
                    result["checks"][f"redis_{redis_name}"] = {
                        "status": "ok" if status else "error",
                        "critical": True
                    }
                    
                    if not status:
                        critical_failure = True
                else:
                    result["checks"][f"redis_{redis_name}"] = {
                        "status": "error", 
                        "message": "Redis连接为空",
                        "critical": True
                    }
                    critical_failure = True
            except Exception as e:
                result["checks"][f"redis_{redis_name}"] = {
                    "status": "error", 
                    "message": str(e),
                    "critical": True
                }
                critical_failure = True
                
        # 检查服务连接
        for service in self.service_connections:
            service_name = service["name"]
            service_url = service["url"]
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    headers = {"X-Service-Discovery-Check": "true"}
                    response = await client.get(f"{service_url}/health", headers=headers)
                    
                    if response.status_code == 200:
                        # 如果返回200，则服务正常
                        result["checks"][f"service_{service_name}"] = {
                            "status": "ok",
                            "critical": True
                        }
                    else:
                        # 否则服务异常
                        result["checks"][f"service_{service_name}"] = {
                            "status": "error", 
                            "message": f"HTTP {response.status_code}",
                            "critical": True
                        }
                        critical_failure = True
            except Exception as e:
                result["checks"][f"service_{service_name}"] = {
                    "status": "error", 
                    "message": str(e),
                    "critical": True
                }
                critical_failure = True
        
        # 如果有关键检查失败，则整体状态为错误
        if critical_failure:
            result["status"] = "error"
            
        return result

# 单例健康检查器
_health_checker = None

async def get_health_checker(service_name: str, service_id: str = None) -> HealthChecker:
    """获取健康检查器单例"""
    global _health_checker
    if _health_checker is None:
        _health_checker = create_health_checker(service_name, service_id)
        await _health_checker.start()
    return _health_checker

def create_health_checker(service_name: str, service_id: str = None) -> HealthChecker:
    """创建健康检查器"""
    checker = HealthChecker(service_name, service_id)
    # 不启动自动检查，由应用控制启动
    return checker

def register_health_routes(app: FastAPI, checker: HealthChecker):
    """注册健康检查路由"""
    router = APIRouter()
    
    # 用于请求限流的计数器和时间
    request_counts = {}
    last_reset_time = datetime.now()
    max_requests_per_minute = 30  # 每分钟最大请求数
    
    # 添加限流函数
    def should_throttle(client_ip):
        nonlocal last_reset_time
        
        # 每分钟重置计数器
        now = datetime.now()
        if (now - last_reset_time).total_seconds() > 60:
            request_counts.clear()
            last_reset_time = now
            
        # 增加当前IP的请求计数
        request_counts[client_ip] = request_counts.get(client_ip, 0) + 1
        
        # 如果超过限制，返回True表示应该限流
        return request_counts[client_ip] > max_requests_per_minute
    
    @router.get("/health")
    async def health_check(request: Request, response: Response):
        """
        健康检查端点
        返回服务健康状态
        """
        client_ip = request.client.host
        
        # 检查请求头中是否包含服务发现标记，如果有则不进行限流
        is_service_discovery = request.headers.get("X-Service-Discovery-Check") == "true"
        
        # 只对非服务发现请求进行限流
        if not is_service_discovery and should_throttle(client_ip):
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
            return {"status": "error", "message": "请求过于频繁，请稍后再试"}
            
        health_data = await checker.check_health()
        return health_data

    @router.get("/api/health", response_model=HealthResponse)
    async def api_health_check(request: Request, response: Response):
        """
        API健康检查端点
        返回服务健康状态
        """
        # 获取客户端IP
        client_ip = request.client.host
        
        # 检查是否应该限流
        if "X-Service-Discovery-Check" not in request.headers and should_throttle(client_ip):
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
            return {
                "status": "error", 
                "message": "Too many requests", 
                "service": checker.service_name,
                "version": checker.version,
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
        
        try:
            # 执行健康检查
            health_data = await checker.check_health()
            
            # 直接使用health_data构建HealthResponse
            return HealthResponse(
                status=health_data["status"],
                service=health_data["service_name"],
                version=health_data["version"],
                timestamp=health_data["timestamp"],
                checks=health_data["checks"]
            )
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            logger.error(traceback.format_exc())
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                "status": "error",
                "message": str(e), 
                "service": checker.service_name,
                "version": checker.version,
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
        
    # 注册路由
    app.include_router(router, tags=["health"])

async def register_health_service(app: FastAPI, service_name: str, service_id: str = None):
    """向服务发现注册健康检查服务"""
    # 创建健康检查器
    checker = await get_health_checker(service_name, service_id)
    
    # 注册健康检查路由
    register_health_routes(app, checker)
    
    # 向服务发现注册服务
    try:
        service_client = await get_service_client()
        host = socket.gethostname()
        # 使用传入的app中的配置获取端口
        # 注意：FastAPI本身不存储端口信息，通常需要从环境变量获取
        # 但为了确保正确性，这里从SERVICE_PORT环境变量获取
        port = int(os.getenv("SERVICE_PORT", "8085"))
        
        # 确保端口信息与实际运行端口一致
        logger.info(f"向服务发现注册服务: {service_name}, 主机: {host}, 端口: {port}")
        
        await service_client._registry.register_service(
            service_name=service_name,
            service_id=service_id,
            host=host,
            port=port,
            health_check_endpoint="/healthz",  # 使用标准Kubernetes健康检查路径
            metadata={
                "version": os.getenv("SERVICE_VERSION", "unknown"),
                "start_time": checker.startup_time.isoformat()
            }
        )
        logger.info(f"服务已注册到服务发现: {service_name}")
    except Exception as e:
        logger.error(f"向服务发现注册服务失败: {str(e)}")
    
    # 应用启动时的健康检查
    @app.on_event("startup")
    async def startup_health_check():
        logger.info(f"启动健康检查: {service_name}")
        await checker.start()
    
    # 应用关闭时的清理
    @app.on_event("shutdown")
    async def shutdown_health_check():
        logger.info(f"停止健康检查: {service_name}")
        await checker.stop()
        
        # 注销服务
        try:
            await service_client._registry.deregister_service(service_name, service_id or checker.service_id)
            logger.info(f"服务已从服务发现注销: {service_name}")
        except Exception as e:
            logger.error(f"从服务发现注销服务失败: {str(e)}")
    
    return checker

def get_system_info() -> Dict[str, Any]:
    """获取系统信息"""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "hostname": socket.gethostname(),
            "system": {
                "platform": sys.platform,
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round((memory.total - memory.available) / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent
            },
            "environment": {
                "env_mode": os.getenv("ENVIRONMENT", "unknown"),
                "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true"
            }
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        return {"error": str(e)}

async def check_service_health(service_name: str) -> Tuple[bool, Dict[str, Any]]:
    """检查指定服务的健康状态"""
    try:
        service_client = await get_service_client()
        service_url = await service_client.get_service_url(service_name, healthy_only=False)
        
        if not service_url:
            return False, {"error": f"无法找到服务: {service_name}"}
        
        health_url = f"{service_url}/health"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            
            if response.status_code == 200:
                health_data = response.json()
                is_healthy = health_data.get("status") == ServiceStatus.OK
                return is_healthy, health_data
            else:
                return False, {"error": f"服务健康检查返回非200状态码: {response.status_code}"}
    except Exception as e:
        return False, {"error": f"服务健康检查失败: {str(e)}"}

async def check_all_services_health() -> Dict[str, Dict[str, Any]]:
    """检查所有已注册服务的健康状态"""
    try:
        service_client = await get_service_client()
        services = await service_client._registry.get_all_services()
        
        results = {}
        
        for service_name, instances in services.items():
            service_results = []
            
            for instance in instances:
                service_id = instance.get("service_id")
                host = instance.get("host")
                port = instance.get("port")
                health_endpoint = instance.get("health_check_endpoint")
                
                if host and port and health_endpoint:
                    health_url = f"http://{host}:{port}{health_endpoint}"
                    
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.get(health_url)
                            
                            if response.status_code == 200:
                                health_data = response.json()
                                service_results.append({
                                    "service_id": service_id,
                                    "host": host,
                                    "port": port,
                                    "status": health_data.get("status", ServiceStatus.UNKNOWN),
                                    "data": health_data
                                })
                            else:
                                service_results.append({
                                    "service_id": service_id,
                                    "host": host,
                                    "port": port,
                                    "status": ServiceStatus.ERROR,
                                    "error": f"返回状态码: {response.status_code}"
                                })
                    except Exception as e:
                        service_results.append({
                            "service_id": service_id,
                            "host": host,
                            "port": port,
                            "status": ServiceStatus.ERROR,
                            "error": str(e)
                        })
            
            results[service_name] = service_results
        
        return results
    except Exception as e:
        logger.error(f"检查所有服务健康状态失败: {str(e)}")
        return {"error": str(e)}

def create_health_middleware():
    """创建健康检查中间件"""
    async def health_middleware(request: Request, call_next):
        """中间件：记录服务健康状态和请求性能"""
        start_time = time.time()
        
        # 处理请求
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # 添加性能指标头
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
        except Exception as e:
            # 全局异常处理
            process_time = time.time() - start_time
            logger.error(f"请求处理异常: {request.url.path} - {str(e)}")
            
            # 获取健康状态
            health_data = {"status": ServiceStatus.ERROR, "error": str(e)}
            if _health_checker:
                health_data = _health_checker.get_health()
            
            return Response(
                content=json.dumps({
                    "error": str(e),
                    "path": request.url.path,
                    "process_time": process_time,
                    "health": health_data
                }),
                media_type="application/json",
                status_code=500
            )
    
    return health_middleware 

# 创建默认的健康检查路由器
health_check_router = APIRouter()

@health_check_router.get("/health")
async def default_health_check():
    """默认健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@health_check_router.get("/healthz")
async def kubernetes_health_check():
    """Kubernetes健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@health_check_router.get("/ready")
async def readiness_check():
    """就绪检查端点"""
    return {"status": "ready", "timestamp": datetime.now().isoformat()}

@health_check_router.get("/live")
async def liveness_check():
    """存活检查端点"""
    return {"status": "alive", "timestamp": datetime.now().isoformat()} 