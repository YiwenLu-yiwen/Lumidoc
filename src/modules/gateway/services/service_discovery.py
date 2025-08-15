"""
Gateway服务发现和负载均衡模块
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse
import httpx
import redis.asyncio as redis
from src.modules.gateway.config.config import settings

logger = logging.getLogger(__name__)

@dataclass
class ServiceInstance:
    """服务实例数据类"""
    name: str
    url: str
    health_status: str = "unknown"  # healthy, unhealthy, unknown
    last_health_check: float = 0
    request_count: int = 0
    response_time: float = 0
    error_count: int = 0
    
    def __post_init__(self):
        if self.last_health_check == 0:
            self.last_health_check = time.time()
    
    @property
    def is_healthy(self) -> bool:
        """检查服务实例是否健康"""
        return self.health_status == "healthy"
    
    def record_request(self, response_time: float, success: bool = True):
        """记录请求统计"""
        self.request_count += 1
        self.response_time = (self.response_time + response_time) / 2  # 简单平均
        if not success:
            self.error_count += 1

class ServiceDiscovery:
    """服务发现管理器"""
    
    def __init__(self):
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.round_robin_counters: Dict[str, int] = {}
        
    async def initialize(self):
        """初始化服务发现"""
        logger.info("初始化Gateway服务发现...")
        
        # 初始化Redis连接（如果启用）
        if settings.redis_enabled:
            try:
                self.redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password or None,
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Redis连接成功")
            except Exception as e:
                logger.error(f"Redis连接失败: {e}")
                self.redis_client = None
        
        # 加载静态配置的服务
        await self.load_static_services()
        
        # 启动健康检查任务
        if settings.health_check_enabled:
            self.health_check_task = asyncio.create_task(self.health_check_loop())
            logger.info("健康检查任务已启动")
    
    async def load_static_services(self):
        """加载静态配置的服务"""
        logger.info("加载静态配置的服务...")
        
        for service_name, service_config in settings.service_routes.items():
            service_instance = ServiceInstance(
                name=service_name,
                url=service_config["url"]
            )
            
            if service_name not in self.services:
                self.services[service_name] = []
            self.services[service_name].append(service_instance)
            
            # 初始化轮询计数器
            self.round_robin_counters[service_name] = 0
            
            logger.info(f"加载服务: {service_name} -> {service_config['url']}")
    
    async def get_service_instance(self, service_name: str) -> Optional[ServiceInstance]:
        """获取服务实例（负载均衡）"""
        if service_name not in self.services:
            logger.warning(f"未找到服务: {service_name}")
            return None
        
        instances = self.services[service_name]
        if not instances:
            logger.warning(f"服务 {service_name} 没有可用实例")
            return None
        
        # 过滤健康的实例
        healthy_instances = [inst for inst in instances if inst.is_healthy or inst.health_status == "unknown"]
        
        if not healthy_instances:
            logger.warning(f"服务 {service_name} 没有健康的实例，使用所有实例")
            healthy_instances = instances
        
        # 根据负载均衡算法选择实例
        if settings.load_balancer_algorithm == "round_robin":
            return self._round_robin_select(service_name, healthy_instances)
        elif settings.load_balancer_algorithm == "random":
            return self._random_select(healthy_instances)
        elif settings.load_balancer_algorithm == "least_connections":
            return self._least_connections_select(healthy_instances)
        else:
            # 默认使用轮询
            return self._round_robin_select(service_name, healthy_instances)
    
    def _round_robin_select(self, service_name: str, instances: List[ServiceInstance]) -> ServiceInstance:
        """轮询选择算法"""
        if service_name not in self.round_robin_counters:
            self.round_robin_counters[service_name] = 0
        
        index = self.round_robin_counters[service_name] % len(instances)
        self.round_robin_counters[service_name] += 1
        
        return instances[index]
    
    def _random_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """随机选择算法"""
        return random.choice(instances)
    
    def _least_connections_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """最少连接选择算法"""
        # 这里简化为选择请求计数最少的实例
        return min(instances, key=lambda x: x.request_count)
    
    async def health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await self.perform_health_checks()
                await asyncio.sleep(settings.health_check_interval)
            except Exception as e:
                logger.error(f"健康检查循环出错: {e}")
                await asyncio.sleep(settings.health_check_interval)
    
    async def perform_health_checks(self):
        """执行健康检查 - 序列化执行，避免并发过载"""
        logger.debug("执行健康检查...")
        
        # 序列化执行，而不是并发，避免429限流
        for service_name, instances in self.services.items():
            for instance in instances:
                try:
                    await self.check_instance_health(instance)
                    # 每次检查后稍微延迟，避免过载
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"健康检查 {instance.name} 失败: {e}")
                    continue
    
    async def check_instance_health(self, instance: ServiceInstance):
        """检查单个服务实例的健康状态"""
        try:
            service_config = settings.get_service_config(instance.name)
            if not service_config:
                return
            
            health_check_path = service_config.get("health_check", "/health")
            health_check_url = f"{instance.url.rstrip('/')}{health_check_path}"
            
            start_time = time.time()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    health_check_url,
                    timeout=settings.health_check_timeout,
                    headers={
                        "User-Agent": "STP-Gateway-HealthCheck/1.0",
                        "X-Health-Check": "gateway"  # 额外标识，确保被白名单识别
                    }
                )
                
                if response.status_code == 200:
                    instance.health_status = "healthy"
                    logger.debug(f"服务 {instance.name} 健康检查通过")
                elif response.status_code == 429:
                    # 对于429错误，不改变健康状态，避免频繁检查
                    logger.debug(f"服务 {instance.name} 健康检查被限流(429)，保持当前状态")
                    return  # 直接返回，不改变状态
                else:
                    instance.health_status = "unhealthy"
                    logger.warning(f"服务 {instance.name} 健康检查失败: {response.status_code}")
                    
        except Exception as e:
            instance.health_status = "unhealthy"
            logger.warning(f"服务 {instance.name} 健康检查异常: {e}")
            
        finally:
            instance.last_health_check = time.time()
    
    async def get_all_services_status(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有服务的状态"""
        status = {}
        
        for service_name, instances in self.services.items():
            status[service_name] = []
            for instance in instances:
                status[service_name].append({
                    "url": instance.url,
                    "health_status": instance.health_status,
                    "last_health_check": instance.last_health_check,
                    "request_count": instance.request_count,
                    "response_time": instance.response_time,
                    "error_count": instance.error_count
                })
        
        return status
    
    async def close(self):
        """关闭服务发现"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()

# 全局服务发现实例
service_discovery = ServiceDiscovery()

async def get_service_discovery() -> ServiceDiscovery:
    """获取服务发现实例"""
    return service_discovery 