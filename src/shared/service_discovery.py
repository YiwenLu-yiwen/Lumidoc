"""
简易服务发现模块
提供基于Redis的服务注册与发现功能
"""

import os
import json
import time
import asyncio
import socket
import logging
import random
from typing import Dict, Any, Optional, List
import redis.asyncio as aioredis
import uuid
import httpx
import traceback

# 配置日志
logger = logging.getLogger(__name__)

# Redis配置
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# 服务注册配置
SERVICE_TTL = int(os.environ.get("SERVICE_TTL", "30"))  # 服务注册TTL(秒)
SERVICE_KEY_PREFIX = "lumidoc:services:"
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "10"))  # 心跳间隔(秒)
HEALTH_CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "60"))  # 健康检查间隔(秒)
HEALTH_CHECK_TIMEOUT = int(os.environ.get("HEALTH_CHECK_TIMEOUT", "10"))  # 健康检查超时(秒), 从5秒提高到10秒
HEALTH_CHECK_RETRIES = int(os.environ.get("HEALTH_CHECK_RETRIES", "3"))  # 健康检查重试次数
DEFAULT_HEALTH_CHECK_ENDPOINT = "/healthz"

# 故障转移配置
FAILOVER_RETRY_INTERVAL = int(os.environ.get("FAILOVER_RETRY_INTERVAL", "5"))  # 故障转移重试间隔(秒)
MAX_FAILOVER_RETRIES = int(os.environ.get("MAX_FAILOVER_RETRIES", "3"))  # 最大故障转移重试次数
CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", "5"))  # 熔断器阈值(错误次数)
CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("CIRCUIT_BREAKER_TIMEOUT", "60"))  # 熔断器超时(秒)

# 服务健康状态
class ServiceHealth:
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"

class ServiceRegistry:
    """服务注册表，管理服务的注册与发现"""
    
    def __init__(self):
        """初始化服务注册表"""
        self._redis = None
        self._heartbeat_task = None
        self._health_check_task = None
        self._failover_recovery_task = None
        self._registered_services = {}  # 本地缓存: {service_id: service_info}
        self._service_health = {}  # 健康状态缓存: {service_id: health_status}
        self._service_errors = {}  # 服务错误统计: {service_id: error_count}
        self._circuit_breakers = {}  # 熔断器状态: {service_id: {"open": bool, "until": timestamp}}
        self._instance_id = str(uuid.uuid4())[:8]  # 为每个注册表实例生成唯一ID
        self._connection_retries = 0  # Redis连接重试计数
        self._max_connection_retries = 5  # 最大Redis连接重试次数
        self._is_closing = False  # 是否正在关闭
        logger.debug(f"ServiceRegistry实例初始化，实例ID: {self._instance_id}")
    
    async def connect(self, retry: bool = True) -> bool:
        """
        连接到Redis服务器
        
        Args:
            retry: 是否在失败时重试
            
        Returns:
            bool: 是否连接成功
        """
        if self._redis:
            try:
                # 如果已有连接，检查是否可用
                await self._redis.ping()
                return True
            except (self._redis.exceptions.ConnectionError, self._redis.exceptions.TimeoutError):
                # 连接可能已断开，重新连接
                logger.warning("Redis连接已断开，尝试重新连接")
                await self._close_redis()
        
        # 尝试连接
        try:
            # 使用通用连接URL生成函数
            redis_url = _get_redis_url()
            logger.info(f"连接到Redis: {redis_url.replace('redis://:', 'redis://***:')}")
            
            # 添加连接选项提高可靠性
            self._redis = await aioredis.from_url(
                redis_url,
                decode_responses=True,
                encoding="utf-8",
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                socket_keepalive=True,
                health_check_interval=30
            )
            
            # 测试连接
            await self._redis.ping()
            logger.info("Redis连接已建立")
            return True
        except Exception as e:
            if retry:
                # 重试策略
                retry_delay = 1
                for i in range(1, self._max_connection_retries + 1):
                    logger.warning(f"连接Redis失败，第{i}/{self._max_connection_retries}次重试: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 10)  # 指数退避，最多等待10秒
                    
                    try:
                        # 使用通用连接URL生成函数
                        redis_url = _get_redis_url()
                        
                        self._redis = await aioredis.from_url(
                            redis_url,
                            decode_responses=True,
                            encoding="utf-8",
                            socket_timeout=5.0,
                            socket_connect_timeout=5.0
                        )
                        await self._redis.ping()
                        logger.info("Redis重试连接成功")
                        return True
                    except Exception:
                        pass
            
            logger.error(f"Redis连接失败: {str(e)}")
            self._redis = None
            return False
    
    async def close(self):
        """关闭Redis连接"""
        # 停止所有循环任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._failover_recovery_task and not self._failover_recovery_task.done():
            self._failover_recovery_task.cancel()
            try:
                await self._failover_recovery_task
            except asyncio.CancelledError:
                pass
        
        # 安全关闭Redis连接
        await self._close_redis()
        logger.info("服务注册表已关闭")
    
    async def register_service(self, 
                              service_name: str, 
                              service_id: str = None, 
                              host: str = None, 
                              port: int = None, 
                              metadata: Dict[str, Any] = None,
                              endpoints: Dict[str, str] = None,
                              websocket_endpoints: Dict[str, str] = None,
                              health_check_endpoint: str = None) -> str:
        """
        注册服务实例
        
        Args:
            service_name: 服务名称
            service_id: 服务实例ID，如不提供则自动生成
            host: 服务主机，如不提供则自动检测
            port: 服务端口
            metadata: 服务元数据
            endpoints: 服务端点字典
            websocket_endpoints: WebSocket端点字典，格式: {"endpoint_name": "path"}
            health_check_endpoint: 健康检查端点，如/health
            
        Returns:
            str: 服务实例ID
        """
        await self.connect()
        
        # 生成或使用提供的服务ID
        if not service_id:
            service_id = f"{service_name}-{socket.gethostname()}-{int(time.time())}"
        
        # 获取主机名
        if not host:
            try:
                host = socket.gethostname()
            except OSError:
                host = "localhost"
        
        # 验证端口
        if port is None:
            raise ValueError(f"服务 {service_name} 注册失败: 端口不能为None")
        
        # 使用默认健康检查端点
        if not health_check_endpoint:
            health_check_endpoint = DEFAULT_HEALTH_CHECK_ENDPOINT
        
        # 准备服务信息
        service_info = {
            "service_name": service_name,
            "service_id": service_id,
            "host": host,
            "port": port,
            "metadata": metadata or {},
            "endpoints": endpoints or {},
            "websocket_endpoints": websocket_endpoints or {},
            "health_check_endpoint": health_check_endpoint,
            "health_status": ServiceHealth.STARTING,
            "last_heartbeat": int(time.time()),
            "registration_time": int(time.time()),
            "registry_instance": self._instance_id
        }
        
        try:
            # 注册到Redis
            key = f"{SERVICE_KEY_PREFIX}{service_name}:{service_id}"
            await self._redis.set(key, json.dumps(service_info), ex=SERVICE_TTL)
            logger.info(f"服务已注册: {service_name} (ID: {service_id})")
            
            # 缓存服务信息
            self._registered_services[service_id] = service_info
            self._service_health[service_id] = ServiceHealth.STARTING
            
            # 启动心跳任务
            if not self._heartbeat_task or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # 启动健康检查任务
            if not self._health_check_task or self._health_check_task.done():
                self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # 启动故障转移恢复任务
            if not self._failover_recovery_task or self._failover_recovery_task.done():
                self._failover_recovery_task = asyncio.create_task(self._failover_recovery_loop())
                
            return service_id
        except Exception as e:
            logger.error(f"服务注册失败: {service_name} (ID: {service_id}), 错误: {str(e)}")
            raise
    
    async def deregister_service(self, service_name: str, service_id: str) -> bool:
        """
        注销服务实例
        
        Args:
            service_name: 服务名称
            service_id: 服务实例ID
            
        Returns:
            bool: 是否成功注销
        """
        try:
            await self.connect()
            
            # 先将服务状态更新为停止中
            if service_id in self._registered_services:
                self._registered_services[service_id]["health_status"] = ServiceHealth.STOPPING
                key = f"{SERVICE_KEY_PREFIX}{service_name}:{service_id}"
                await self._redis.set(key, json.dumps(self._registered_services[service_id]), ex=SERVICE_TTL)
            
            # 然后删除服务
            key = f"{SERVICE_KEY_PREFIX}{service_name}:{service_id}"
            result = await self._redis.delete(key)
            
            if result:
                logger.info(f"服务已注销: {service_name} (ID: {service_id})")
                
                # 从本地缓存移除
                if service_id in self._registered_services:
                    del self._registered_services[service_id]
                
                if service_id in self._service_health:
                    del self._service_health[service_id]
                
                if service_id in self._service_errors:
                    del self._service_errors[service_id]
                    
                if service_id in self._circuit_breakers:
                    del self._circuit_breakers[service_id]
                    
                return True
            else:
                logger.warning(f"服务注销失败: {service_name} (ID: {service_id})")
                return False
        except Exception as e:
            logger.error(f"服务注销出错: {service_name} (ID: {service_id}), 错误: {str(e)}")
            return False
    
    async def update_service_health(self, service_id: str, health_status: str, details: Dict[str, Any] = None) -> bool:
        """
        更新服务健康状态
        
        Args:
            service_id: 服务实例ID
            health_status: 健康状态
            details: 健康状态详情
            
        Returns:
            bool: 是否成功更新
        """
        if service_id not in self._registered_services:
            logger.warning(f"尝试更新未注册服务的健康状态: {service_id}")
            return False
        
        try:   
            await self.connect()
            
            service_info = self._registered_services[service_id]
            service_name = service_info["service_name"]
            
            # 更新健康状态
            service_info["health_status"] = health_status
            if details:
                service_info["health_details"] = details
            service_info["last_health_check"] = int(time.time())
            
            # 更新本地缓存
            self._registered_services[service_id] = service_info
            self._service_health[service_id] = health_status
            
            # 根据健康状态更新错误计数
            if health_status != ServiceHealth.HEALTHY and health_status != ServiceHealth.DEGRADED:
                # 增加错误计数
                self._service_errors[service_id] = self._service_errors.get(service_id, 0) + 1
                # 检查是否需要触发熔断
                if self._service_errors[service_id] >= CIRCUIT_BREAKER_THRESHOLD:
                    self._open_circuit(service_id)
            else:
                # 重置错误计数
                self._service_errors[service_id] = 0
                # 如果服务恢复健康，关闭熔断器
                if service_id in self._circuit_breakers:
                    self._close_circuit(service_id)
            
            # 更新Redis
            key = f"{SERVICE_KEY_PREFIX}{service_name}:{service_id}"
            await self._redis.set(key, json.dumps(service_info), ex=SERVICE_TTL)
            
            logger.debug(f"服务健康状态已更新: {service_name} (ID: {service_id}) -> {health_status}")
            return True
        except Exception as e:
            logger.error(f"更新服务健康状态失败: {service_id}, 错误: {str(e)}")
            return False
    
    async def get_service_instances(self, service_name: str, healthy_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取服务实例列表
        
        Args:
            service_name: 服务名称
            healthy_only: 是否只返回健康的实例
            
        Returns:
            List[Dict[str, Any]]: 服务实例列表
        """
        try:
            await self.connect()
            
            pattern = f"{SERVICE_KEY_PREFIX}{service_name}:*"
            keys = await self._redis.keys(pattern)
            
            if not keys:
                return []
                
            # 使用管道批量获取
            pipeline = self._redis.pipeline()
            for key in keys:
                pipeline.get(key)
            
            results = await pipeline.execute()
            
            instances = []
            
            for result in results:
                if result:
                    try:
                        instance = json.loads(result)
                        # 如果指定只返回健康实例，则过滤
                        if healthy_only:
                            if instance.get("health_status") in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED):
                                instances.append(instance)
                        else:
                            instances.append(instance)
                    except json.JSONDecodeError:
                        continue
            
            # 按健康状态排序，健康的实例排在前面
            instances.sort(key=lambda x: 0 if x.get("health_status") == ServiceHealth.HEALTHY else 
                                        1 if x.get("health_status") == ServiceHealth.DEGRADED else 
                                        2)
            
            return instances
        except Exception as e:
            logger.error(f"获取服务实例列表失败: {service_name}, 错误: {str(e)}")
            # 在Redis不可用时，返回本地已知的实例（不完整但可能还能用）
            local_instances = []
            for service_id, info in self._registered_services.items():
                if info["service_name"] == service_name:
                    if healthy_only and self._service_health.get(service_id) not in (ServiceHealth.HEALTHY, ServiceHealth.DEGRADED):
                        continue
                    local_instances.append(info)
            logger.warning(f"从本地缓存返回{len(local_instances)}个{service_name}实例")
            return local_instances
    
    async def get_websocket_url(self, service_name: str, endpoint_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
        """
        获取服务的WebSocket URL
        
        Args:
            service_name: 服务名称
            endpoint_name: WebSocket端点名称
            preferred_host: 优先选择的主机
            healthy_only: 是否只返回健康的实例
            
        Returns:
            Optional[str]: WebSocket URL
        """
        try:
            instances = await self.get_service_instances(service_name, healthy_only)
            
            if not instances:
                logger.warning(f"无法找到服务: {service_name}")
                return None
            
            # 如果有preferred_host，优先选择该主机
            if preferred_host:
                preferred_instances = [instance for instance in instances if instance["host"] == preferred_host]
                if preferred_instances:
                    instance = preferred_instances[0]
                else:
                    instance = random.choice(instances)
            else:
                # 随机选择一个实例，但偏向健康实例
                healthy_instances = [instance for instance in instances if instance.get("health_status") == ServiceHealth.HEALTHY]
                if healthy_instances:
                    instance = random.choice(healthy_instances)
                else:
                    instance = random.choice(instances)
            
            # 检查实例是否有指定的WebSocket端点
            websocket_endpoints = instance.get("websocket_endpoints", {})
            if endpoint_name not in websocket_endpoints:
                logger.warning(f"服务 {service_name} 实例 {instance['service_id']} 没有WebSocket端点: {endpoint_name}")
                return None
            
            endpoint_path = websocket_endpoints[endpoint_name]
            host = instance["host"]
            port = instance["port"]
            
            # 构建WebSocket URL
            if port == 80:
                ws_url = f"ws://{host}{endpoint_path}"
            elif port == 443:
                ws_url = f"wss://{host}{endpoint_path}"
            else:
                ws_url = f"ws://{host}:{port}{endpoint_path}"
            
            return ws_url
            
        except Exception as e:
            logger.error(f"获取WebSocket URL失败: {service_name}/{endpoint_name}, 错误: {str(e)}")
            return None

    async def get_service_url(self, service_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
        """
        获取服务URL
        
        Args:
            service_name: 服务名称
            preferred_host: 优先选择的主机
            healthy_only: 是否只返回健康的实例
            
        Returns:
            Optional[str]: 服务URL
        """
        # 先检查此服务名是否有熔断
        if self._is_circuit_open(service_name):
            logger.warning(f"服务{service_name}当前已熔断，无法获取服务URL")
            # 检查是否有特殊的回退URL配置
            fallback_url_env = f"{service_name.upper()}_FALLBACK_URL"
            fallback_url = os.environ.get(fallback_url_env)
            if fallback_url:
                logger.info(f"使用服务{service_name}的回退URL: {fallback_url}")
                return fallback_url
            return None
            
        try:
            instances = await self.get_service_instances(service_name, healthy_only)
            
            if not instances:
                # 如果没有健康实例，尝试获取非健康实例（如果初始请求是健康实例）
                if healthy_only:
                    instances = await self.get_service_instances(service_name, False)
                    if instances:
                        logger.warning(f"服务{service_name}没有健康实例，使用不健康实例")
                        
            if not instances:
                # 如果还是没有实例，尝试使用环境变量中的服务URL
                url_env = f"{service_name.upper()}_SERVICE_URL"
                url = os.environ.get(url_env)
                if url:
                    logger.info(f"使用环境变量中的服务URL: {url}")
                    return url
                    
                logger.warning(f"无法找到服务: {service_name}")
                return None
            
            # 如果有preferred_host，优先选择该主机
            if preferred_host:
                preferred_instances = [instance for instance in instances if instance["host"] == preferred_host]
                if preferred_instances:
                    instance = preferred_instances[0]
                else:
                    # 没有找到preferred_host，使用随机选择
                    instance = random.choice(instances)
            else:
                # 随机选择一个实例，但偏向健康实例
                healthy_instances = [instance for instance in instances if instance.get("health_status") == ServiceHealth.HEALTHY]
                if healthy_instances:
                    instance = random.choice(healthy_instances)
                else:
                    instance = random.choice(instances)
            
            host = instance["host"]
            port = instance["port"]
            
            # 如果端口是80或443，不加入URL
            if port == 80:
                return f"http://{host}"
            elif port == 443:
                return f"https://{host}"
            else:
                return f"http://{host}:{port}"
        except Exception as e:
            logger.error(f"获取服务URL失败: {service_name}, 错误: {str(e)}")
            # 尝试从环境变量中获取服务URL作为备选
            url_env = f"{service_name.upper()}_SERVICE_URL"
            url = os.environ.get(url_env)
            if url:
                logger.info(f"使用环境变量中的服务URL: {url}")
                return url
            return None
    
    async def get_all_services(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取所有注册的服务
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: 按服务名分组的服务实例列表
        """
        try:
            await self.connect()
            
            # 获取所有服务键
            keys = await self._redis.keys(f"{SERVICE_KEY_PREFIX}*")
            
            if not keys:
                return {}
                
            # 使用管道批量获取
            pipeline = self._redis.pipeline()
            for key in keys:
                pipeline.get(key)
            
            results = await pipeline.execute()
            
            # 按服务名分组
            services = {}
            
            for result in results:
                if result:
                    try:
                        instance = json.loads(result)
                        service_name = instance["service_name"]
                        if service_name not in services:
                            services[service_name] = []
                        services[service_name].append(instance)
                    except json.JSONDecodeError:
                        continue
            
            # 对每个服务的实例列表按健康状态排序
            for service_name in services:
                services[service_name].sort(key=lambda x: 0 if x.get("health_status") == ServiceHealth.HEALTHY else 
                                                        1 if x.get("health_status") == ServiceHealth.DEGRADED else 
                                                        2)
            
            return services
        except Exception as e:
            logger.error(f"获取所有服务失败: {str(e)}")
            return {}
    
    async def list_services(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        列出所有注册的服务 (get_all_services的别名)
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: 按服务名分组的服务实例列表
        """
        return await self.get_all_services()
    
    def _is_circuit_open(self, service_name: str) -> bool:
        """检查服务的熔断器是否打开"""
        # 检查每个实例的熔断状态
        now = time.time()
        for service_id, breaker in self._circuit_breakers.items():
            if service_id.startswith(service_name) and breaker.get("open", False):
                # 检查熔断器是否超时
                until = breaker.get("until", 0)
                if until > now:
                    return True
                else:
                    # 熔断器超时，进入半开状态
                    self._half_open_circuit(service_id)
        return False
    
    def _open_circuit(self, service_id: str):
        """打开服务的熔断器"""
        service_name = self._registered_services.get(service_id, {}).get("service_name", "unknown")
        logger.warning(f"为服务{service_name}(ID:{service_id})打开熔断器")
        self._circuit_breakers[service_id] = {
            "open": True,
            "until": time.time() + CIRCUIT_BREAKER_TIMEOUT,
            "state": "open"
        }
    
    def _close_circuit(self, service_id: str):
        """关闭服务的熔断器"""
        service_name = self._registered_services.get(service_id, {}).get("service_name", "unknown")
        logger.info(f"为服务{service_name}(ID:{service_id})关闭熔断器")
        if service_id in self._circuit_breakers:
            self._circuit_breakers[service_id] = {
                "open": False,
                "state": "closed"
            }
            # 重置错误计数
            self._service_errors[service_id] = 0
    
    def _half_open_circuit(self, service_id: str):
        """将熔断器置为半开状态"""
        service_name = self._registered_services.get(service_id, {}).get("service_name", "unknown")
        logger.info(f"为服务{service_name}(ID:{service_id})设置熔断器为半开状态")
        self._circuit_breakers[service_id] = {
            "open": False,
            "state": "half-open"
        }
    
    async def _heartbeat_loop(self):
        """心跳循环，定期发送心跳更新"""
        logger.debug("心跳循环已启动")
        while not self._is_closing:
            try:
                await self._send_heartbeats()
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                logger.debug("心跳循环已取消")
                break
            except Exception as e:
                logger.error(f"心跳循环出错: {str(e)}")
                await asyncio.sleep(HEARTBEAT_INTERVAL)
    
    async def _send_heartbeats(self):
        """发送所有注册服务的心跳"""
        try:
            if not self._redis:
                await self.connect()
                
            # 更新每个服务的心跳时间
            now = int(time.time())
            
            # 使用管道批量处理
            pipeline = self._redis.pipeline()
            
            for service_id, service_info in list(self._registered_services.items()):
                service_name = service_info["service_name"]
                service_info["last_heartbeat"] = now
                
                key = f"{SERVICE_KEY_PREFIX}{service_name}:{service_id}"
                pipeline.set(key, json.dumps(service_info), ex=SERVICE_TTL)
                
                # 更新本地缓存
                self._registered_services[service_id] = service_info
                
            # 执行所有命令
            await pipeline.execute()
            
            logger.debug(f"已发送{len(self._registered_services)}个服务的心跳")
        except Exception as e:
            logger.error(f"发送心跳出错: {str(e)}")
            # 尝试重新连接Redis
            self._redis = None
            try:
                await self.connect(retry=False)
            except Exception:
                pass
    
    async def _health_check_loop(self):
        """健康检查循环，定期检查服务健康状态"""
        logger.debug("健康检查循环已启动")
        while not self._is_closing:
            try:
                await self._check_services_health()
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                logger.debug("健康检查循环已取消")
                break
            except Exception as e:
                logger.error(f"健康检查循环出错: {str(e)}")
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    
    async def _check_services_health(self):
        """检查所有服务的健康状态"""
        if not self._registered_services:
            return
            
        logger.debug(f"开始检查{len(self._registered_services)}个服务的健康状态")
        
        for service_id, service_info in list(self._registered_services.items()):
            # 只检查配置了健康检查端点的服务
            health_check_endpoint = service_info.get("health_check_endpoint")
            if not health_check_endpoint:
                continue
                
            service_name = service_info["service_name"]
            host = service_info["host"]
            port = service_info["port"]
            
            # 组装健康检查URL
            health_check_url = f"http://{host}:{port}{health_check_endpoint}"
            
            # 添加特殊请求头，标识为服务发现请求，避免被限流
            headers = {
                "X-Service-Discovery-Check": "true"
            }
            
            # 实现重试逻辑
            for retry in range(HEALTH_CHECK_RETRIES):
                try:
                    async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                        logger.debug(f"检查服务健康状态(尝试{retry+1}/{HEALTH_CHECK_RETRIES}): {service_name} (ID: {service_id}) -> {health_check_url}")
                        response = await client.get(health_check_url, headers=headers)
                        
                        if response.status_code == 200:
                            health_status = ServiceHealth.HEALTHY
                            health_details = None
                            
                            # 尝试解析响应体
                            try:
                                data = response.json()
                                if isinstance(data, dict):
                                    status = data.get("status")
                                    if status and status.lower() == "degraded":
                                        health_status = ServiceHealth.DEGRADED
                                    health_details = data
                            except ValueError:
                                pass
                            
                            # 更新健康状态
                            await self.update_service_health(service_id, health_status, health_details)
                            break  # 成功获取状态，退出重试循环
                        else:
                            if retry == HEALTH_CHECK_RETRIES - 1:  # 最后一次尝试
                                await self.update_service_health(service_id, ServiceHealth.UNHEALTHY, {
                                    "error": f"健康检查返回非200状态码: {response.status_code}"
                                })
                            logger.warning(f"服务健康检查返回非200状态码(尝试{retry+1}/{HEALTH_CHECK_RETRIES}): {service_name}, 状态码: {response.status_code}")
                            await asyncio.sleep(1)  # 短暂等待后重试
                            
                except httpx.TimeoutException:
                    if retry == HEALTH_CHECK_RETRIES - 1:  # 最后一次尝试
                        logger.warning(f"服务健康检查超时: {service_name} (ID: {service_id})")
                        await self.update_service_health(service_id, ServiceHealth.UNHEALTHY, {
                            "error": "健康检查超时"
                        })
                    else:
                        logger.debug(f"服务健康检查超时(尝试{retry+1}/{HEALTH_CHECK_RETRIES}): {service_name}, 将重试")
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    if retry == HEALTH_CHECK_RETRIES - 1:  # 最后一次尝试
                        logger.warning(f"服务健康检查失败: {service_name} (ID: {service_id}), 错误: {str(e)}")
                        await self.update_service_health(service_id, ServiceHealth.UNHEALTHY, {
                            "error": str(e)
                        })
                    else:
                        logger.debug(f"服务健康检查失败(尝试{retry+1}/{HEALTH_CHECK_RETRIES}): {service_name}, 错误: {str(e)}, 将重试")
                        await asyncio.sleep(1)
    
    async def _failover_recovery_loop(self):
        """故障转移恢复循环，尝试恢复熔断的服务"""
        logger.debug("故障转移恢复循环已启动")
        while not self._is_closing:
            try:
                await self._check_circuit_breakers()
                await asyncio.sleep(FAILOVER_RETRY_INTERVAL)
            except asyncio.CancelledError:
                logger.debug("故障转移恢复循环已取消")
                break
            except Exception as e:
                logger.error(f"故障转移恢复循环出错: {str(e)}")
                await asyncio.sleep(FAILOVER_RETRY_INTERVAL)
    
    async def _check_circuit_breakers(self):
        """检查并尝试恢复熔断的服务"""
        now = time.time()
        
        # 检查所有熔断器
        for service_id, breaker in list(self._circuit_breakers.items()):
            # 只处理打开状态的熔断器
            if breaker.get("open", False):
                # 检查熔断器是否已超时
                until = breaker.get("until", 0)
                if until <= now:
                    # 将熔断器设置为半开状态
                    self._half_open_circuit(service_id)
            
            # 处理半开状态的熔断器
            elif breaker.get("state") == "half-open":
                # 尝试重新检查服务健康状态
                try:
                    if service_id in self._registered_services:
                        service_info = self._registered_services[service_id]
                        service_name = service_info["service_name"]
                        
                        # 如果服务有健康检查端点，执行检查
                        health_check_endpoint = service_info.get("health_check_endpoint")
                        if health_check_endpoint:
                            host = service_info["host"]
                            port = service_info["port"]
                            health_check_url = f"http://{host}:{port}{health_check_endpoint}"
                            
                            logger.info(f"尝试恢复服务: {service_name} (ID: {service_id})")
                            
                            # 添加特殊请求头，标识为服务发现请求，避免被限流
                            headers = {
                                "X-Service-Discovery-Check": "true"
                            }
                            
                            async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                                response = await client.get(health_check_url, headers=headers)
                                
                                if response.status_code == 200:
                                    # 服务恢复正常，关闭熔断器
                                    self._close_circuit(service_id)
                                    await self.update_service_health(service_id, ServiceHealth.HEALTHY)
                                    logger.info(f"服务已恢复: {service_name} (ID: {service_id})")
                                else:
                                    # 服务仍不可用，重新打开熔断器
                                    self._open_circuit(service_id)
                                    await self.update_service_health(service_id, ServiceHealth.UNHEALTHY)
                                    logger.warning(f"服务恢复失败，重新熔断: {service_name} (ID: {service_id})")
                        else:
                            # 没有健康检查端点，直接关闭熔断器
                            self._close_circuit(service_id)
                except Exception as e:
                    # 恢复检查失败，重新打开熔断器
                    self._open_circuit(service_id)
                    logger.warning(f"服务恢复检查失败，错误: {str(e)}")

    async def _close_redis(self):
        """安全关闭Redis连接"""
        if self._redis:
            try:
                await self._redis.close()
                logger.debug("Redis连接已关闭")
            except Exception as e:
                logger.warning(f"关闭Redis连接时出错: {str(e)}")
            finally:
                self._redis = None

class ServiceClient:
    """服务客户端，用于获取服务连接信息"""
    
    _instance = None
    _registry = None
    
    @classmethod
    async def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = ServiceClient()
            await cls._instance._init_registry()
        return cls._instance
    
    async def _init_registry(self):
        """初始化服务注册表"""
        self._registry = ServiceRegistry()
        try:
            await self._registry.connect()
        except Exception as e:
            logger.warning(f"连接到服务注册表失败: {str(e)}")
            # 继续，部分功能可能不可用，但后续可能会自动重连
    
    async def get_service_url(self, service_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
        """
        获取服务URL
        
        Args:
            service_name: 服务名称
            preferred_host: 优先选择的主机
            healthy_only: 是否只返回健康的实例
            
        Returns:
            Optional[str]: 服务URL
        """
        if not self._registry:
            await self._init_registry()
        
        try:
            return await self._registry.get_service_url(service_name, preferred_host, healthy_only)
        except Exception as e:
            logger.error(f"获取服务URL失败: {service_name}, 错误: {str(e)}")
            
            # 回退到环境变量配置的URL
            url_env = f"{service_name.upper()}_SERVICE_URL"
            url = os.environ.get(url_env)
            if url:
                logger.info(f"使用环境变量中的服务URL: {url}")
                return url
            return None

    async def get_websocket_url(self, service_name: str, endpoint_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
        """
        获取服务的WebSocket URL
        
        Args:
            service_name: 服务名称  
            endpoint_name: WebSocket端点名称
            preferred_host: 优先选择的主机
            healthy_only: 是否只返回健康的实例
            
        Returns:
            Optional[str]: WebSocket URL
        """
        if not self._registry:
            await self._init_registry()
        
        try:
            return await self._registry.get_websocket_url(service_name, endpoint_name, preferred_host, healthy_only)
        except Exception as e:
            logger.error(f"获取WebSocket URL失败: {service_name}/{endpoint_name}, 错误: {str(e)}")
            return None
    
    async def call_service(self, service_name: str, endpoint: str, method: str = "GET", 
                          params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None,
                          json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                          timeout: float = 30.0, use_service_auth: bool = False) -> Dict[str, Any]:
        """
        调用服务API端点
        
        Args:
            service_name: 服务名称
            endpoint: API端点路径
            method: HTTP方法
            params: URL查询参数
            data: 表单数据
            json_data: JSON数据
            headers: 请求头
            timeout: 请求超时时间
            use_service_auth: 是否使用服务间认证
            
        Returns:
            Dict[str, Any]: API响应结果
        """
        # 调用全局的call_service函数
        return await call_service(
            service_name=service_name,
            endpoint=endpoint,
            method=method,
            params=params,
            data=data,
            json_data=json_data,
            headers=headers,
            timeout=timeout,
            use_service_auth=use_service_auth
        )

    async def close(self):
        """关闭客户端"""
        if self._registry:
            await self._registry.close()
            self._registry = None
        ServiceClient._instance = None

# 全局服务注册表实例
service_registry = ServiceRegistry()

# 获取服务客户端单例
async def get_service_client(service_name: str = None):
    """
    获取服务客户端实例
    
    Args:
        service_name: 服务名称，可选
        
    Returns:
        ServiceClient: 服务客户端实例
    """
    client = await ServiceClient.get_instance()
    return client

# 获取服务URL的便捷函数
async def get_service_url(service_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
    """获取服务URL"""
    client = await get_service_client()
    return await client.get_service_url(service_name, preferred_host, healthy_only)

# 获取WebSocket URL的便捷函数
async def get_websocket_url(service_name: str, endpoint_name: str, preferred_host: Optional[str] = None, healthy_only: bool = True) -> Optional[str]:
    """获取WebSocket URL"""
    client = await get_service_client()
    return await client.get_websocket_url(service_name, endpoint_name, preferred_host, healthy_only)

# 获取服务注册表实例，便于其他服务使用
async def get_service_registry():
    """
    获取服务注册表实例
    
    Returns:
        ServiceRegistry: 服务注册表实例
    """
    global service_registry
    if service_registry and not service_registry._redis:
        await service_registry.connect()
    return service_registry

def normalize_endpoint(endpoint: str) -> str:
    """
    规范化端点路径
    
    Args:
        endpoint: 原始端点路径
        
    Returns:
        str: 规范化后的端点路径
    """
    # 如果endpoint为None，返回空字符串
    if endpoint is None:
        return ""
        
    # 去除开头和结尾的空格
    endpoint = endpoint.strip()
    
    # 移除开头的斜杠
    normalized = endpoint.lstrip('/')
    
    # 确保endpoint不为空
    if not normalized:
        return ""
        
    # 如果已经有api前缀，保持原样
    if normalized.startswith('api/'):
        return normalized
    
    # 健康检查和状态端点不需要添加前缀
    if normalized in ['health', 'healthz', 'status', 'metrics', 'ping', 'readiness', 'liveness']:
        return normalized
        
    # 文件服务、RAG服务等内容访问路径
    content_patterns = ['content/', 'info/', 'rag/']
    if any(normalized.startswith(pattern) for pattern in content_patterns):
        # 这些路径需要添加api前缀
        return f"api/{normalized}"
        
    # 如果已经有版本前缀，保持原样
    if normalized.startswith(('v1/', 'v2/')):
        return normalized
        
    # 特定服务的特殊路径
    special_paths = ['file/', 'auth/', 'chat/', 'graph/', 'question/', 'project/', 'lightraglocal/']
    if any(normalized.startswith(prefix) for prefix in special_paths):
        # 已有服务前缀，但仍需添加api/前缀
        return f"api/{normalized}"
    
    # 默认添加api前缀
    return f"api/{normalized}"

async def call_service(service_name: str, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, 
                  data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, 
                  headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, use_service_auth: bool = False) -> Dict[str, Any]:
    """
    调用服务API端点的通用函数
    
    Args:
        service_name: 服务名称
        endpoint: API端点路径
        method: HTTP方法 (GET, POST, PUT, DELETE等)
        params: URL查询参数
        data: 表单数据
        json_data: JSON数据
        headers: 请求头
        timeout: 请求超时时间(秒)
        use_service_auth: 是否使用服务间认证
        
    Returns:
        Dict[str, Any]: API响应结果
    """
    try:
        # 添加重试逻辑
        max_retries = 3
        retry_count = 0
        last_error = None
        
        # 获取调用方服务名称用于日志记录
        caller_service = os.environ.get("SERVICE_NAME", "unknown")
        
        # 尝试从环境变量获取直接服务URL
        direct_url_env = f"{service_name.upper()}_SERVICE_URL"
        direct_url = os.environ.get(direct_url_env)
        
        while retry_count < max_retries:
            try:
                # 首先尝试使用直接URL（如果有）
                service_url = None
                if direct_url:
                    service_url = direct_url
                    logger.debug(f"[{service_name} <- {caller_service}] 使用环境变量中的直接URL: {direct_url}")
                else:
                    # 否则尝试通过服务发现获取URL
                    service_url = await get_service_url(service_name)
                
                if not service_url:
                    logger.error(f"[{service_name} <- {caller_service}] 无法获取服务URL")
                    
                    # 检查是否有备选URL
                    fallback_url_env = f"{service_name.upper()}_FALLBACK_URL"
                    fallback_url = os.environ.get(fallback_url_env)
                    if fallback_url:
                        logger.info(f"[{service_name} <- {caller_service}] 使用备选URL: {fallback_url}")
                        service_url = fallback_url
                    else:
                        return {"success": False, "error": f"无法获取服务URL: {service_name}"}
                
                # 规范化端点路径    
                normalized_endpoint = normalize_endpoint(endpoint)
                
                # 构建完整的API URL
                full_url = f"{service_url}/{normalized_endpoint}"
                
                # 添加默认headers
                if headers is None:
                    headers = {}
                if 'Content-Type' not in headers and (json_data is not None):
                    headers['Content-Type'] = 'application/json'
                    
                # 添加服务间认证
                if use_service_auth:
                    # 使用服务间认证令牌
                    service_token = os.environ.get("SERVICE_AUTH_TOKEN")
                    if not service_token:
                        raise RuntimeError("SERVICE_AUTH_TOKEN is required")
                    headers["Authorization"] = f"Service {service_token}"
                
                # 记录API调用信息
                logger.info(f"[{service_name} <- {caller_service}] 调用服务API: {method} {full_url}")
                
                # 创建httpx客户端
                async with httpx.AsyncClient(timeout=timeout) as client:
                    # 准备请求参数
                    request_kwargs = {
                        "params": params,
                        "headers": headers
                    }
                    
                    # 根据请求方法添加body数据
                    if method.upper() in ["POST", "PUT", "PATCH"]:
                        if json_data is not None:
                            request_kwargs["json"] = json_data
                        elif data is not None:
                            request_kwargs["data"] = data
                    
                    # 发送请求
                    try:
                        response = await client.request(method, full_url, **request_kwargs)
                        
                        # 检查响应状态
                        try:
                            response.raise_for_status()
                            # 尝试解析JSON响应
                            try:
                                result = response.json()
                                logger.debug(f"[{service_name} <- {caller_service}] 请求成功: {method} {full_url}")
                                return result
                            except json.JSONDecodeError:
                                # 如果响应不是JSON，返回文本内容
                                logger.warning(f"[{service_name} <- {caller_service}] 响应不是有效的JSON: {response.text[:100]}...")
                                return {"success": True, "data": response.text}
                        except httpx.HTTPStatusError as e:
                            error_msg = f"HTTP错误: {e.response.status_code}"
                            try:
                                error_detail = e.response.json()
                                error_msg = f"{error_msg} - {error_detail.get('detail', '')}"
                            except ValueError:
                                error_msg = f"{error_msg} - {e.response.text[:100]}"
                            
                            logger.error(f"[{service_name} <- {caller_service}] 调用服务API失败，{error_msg}")
                            last_error = error_msg
                            
                            # 重试逻辑
                            if e.response.status_code >= 500 or e.response.status_code == 429:
                                # 服务器错误或请求过多，重试
                                retry_count += 1
                                if retry_count < max_retries:
                                    wait_time = min(2 ** retry_count, 30)  # 指数退避策略
                                    logger.warning(f"[{service_name} <- {caller_service}] 请求失败 (第{retry_count}次), HTTP {e.response.status_code}, {wait_time}秒后重试")
                                    await asyncio.sleep(wait_time)
                                    continue
                            
                            # 如果是404错误且使用的是服务发现URL，尝试使用备选URL
                            if e.response.status_code == 404 and not direct_url:
                                fallback_url_env = f"{service_name.upper()}_FALLBACK_URL"
                                fallback_url = os.environ.get(fallback_url_env)
                                if fallback_url and retry_count < max_retries:
                                    logger.info(f"[{service_name} <- {caller_service}] 尝试使用备选URL: {fallback_url}")
                                    direct_url = fallback_url
                                    retry_count += 1
                                    continue
                            
                            # 不重试其他错误
                            return {"success": False, "error": error_msg}
                            
                    except httpx.RequestError as e:
                        # 网络错误、连接问题等
                        error_msg = f"请求错误: {str(e)}"
                        logger.error(f"[{service_name} <- {caller_service}] {error_msg}")
                        last_error = error_msg
                        
                        # 如果使用服务发现URL失败，尝试使用备选URL
                        if not direct_url:
                            fallback_url_env = f"{service_name.upper()}_FALLBACK_URL"
                            fallback_url = os.environ.get(fallback_url_env)
                            if fallback_url:
                                logger.info(f"[{service_name} <- {caller_service}] 尝试使用备选URL: {fallback_url}")
                                direct_url = fallback_url
                                retry_count += 1
                                if retry_count < max_retries:
                                    continue
                        else:
                            # 重试
                            retry_count += 1
                            if retry_count < max_retries:
                                wait_time = min(2 ** retry_count, 30)  # 指数退避策略
                                logger.warning(f"[{service_name} <- {caller_service}] 请求失败 (第{retry_count}次), {wait_time}秒后重试")
                                await asyncio.sleep(wait_time)
                                continue
                        
                        return {"success": False, "error": error_msg}
            
            except Exception as e:
                error_msg = f"调用服务异常: {str(e)}"
                logger.error(f"[{service_name} <- {caller_service}] {error_msg}")
                logger.error(traceback.format_exc())
                last_error = error_msg
                
                # 重试
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)  # 指数退避策略
                    logger.warning(f"[{service_name} <- {caller_service}] 请求失败 (第{retry_count}次), {wait_time}秒后重试")
                    await asyncio.sleep(wait_time)
                    continue
                
                return {"success": False, "error": error_msg}
        
        # 达到最大重试次数
        return {"success": False, "error": f"达到最大重试次数 ({max_retries}): {last_error}"}
                
    except Exception as e:
        logger.error(f"调用服务异常: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}

# 模块级的便捷函数
_global_registry = None

async def get_global_registry():
    """获取全局服务注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ServiceRegistry()
        await _global_registry.connect()
    return _global_registry

async def register_service(service_name: str, 
                          service_id: str = None, 
                          host: str = None, 
                          port: int = None, 
                          metadata: Dict[str, Any] = None,
                          endpoints: Dict[str, str] = None,
                          websocket_endpoints: Dict[str, str] = None,
                          health_check_endpoint: str = None) -> str:
    """
    注册服务实例
    
    Args:
        service_name: 服务名称
        service_id: 服务实例ID，如不提供则自动生成
        host: 服务主机，如不提供则自动检测
        port: 服务端口
        metadata: 服务元数据
        endpoints: 服务端点字典
        websocket_endpoints: WebSocket端点字典
        health_check_endpoint: 健康检查端点，如/health
        
    Returns:
        str: 服务实例ID
    """
    registry = await get_global_registry()
    return await registry.register_service(
        service_name=service_name,
        service_id=service_id,
        host=host,
        port=port,
        metadata=metadata,
        endpoints=endpoints,
        websocket_endpoints=websocket_endpoints,
        health_check_endpoint=health_check_endpoint
    )

async def unregister_service(service_name: str, service_id: str = None) -> bool:
    """
    注销服务实例
    
    Args:
        service_name: 服务名称
        service_id: 服务实例ID，如不提供则注销所有实例
        
    Returns:
        bool: 是否成功注销
    """
    registry = await get_global_registry()
    if service_id:
        return await registry.deregister_service(service_name, service_id)
    else:
        # 如果没有指定service_id，尝试注销所有当前实例
        instances = await registry.get_service_instances(service_name)
        success = True
        for instance in instances:
            if instance.get("host") == socket.gethostname():
                result = await registry.deregister_service(service_name, instance["service_id"])
                success = success and result
        return success

def _get_redis_url() -> str:
    """获取Redis连接URL"""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379") 
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_db = os.getenv("REDIS_DB", "0")
    
    # 构建Redis连接URL
    if redis_password:
        # 修正密码格式，确保正确处理特殊字符
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}"
