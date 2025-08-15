# API网关服务 (Gateway Service)

## 概述

API网关服务是STP平台的统一入口，负责请求路由、认证授权、限流控制、负载均衡和服务发现。作为微服务架构的核心组件，网关提供统一的API管理和安全防护。

## 服务信息

- **服务名称**: gateway
- **默认端口**: 8888
- **协议**: HTTP/HTTPS, WebSocket
- **依赖**: Redis (服务发现), Auth Service (认证)

## 核心功能

### 1. 请求路由
- 基于路径的智能路由
- 动态服务发现
- 负载均衡策略
- 故障转移支持

### 2. 认证授权
- JWT令牌验证
- 统一认证入口
- 角色权限控制
- API访问控制

### 3. 限流控制
- 用户级限流
- API级限流
- 动态限流调整
- 突发请求处理

### 4. 安全防护
- CORS跨域处理
- 请求过滤和清洗
- DDoS攻击防护
- 恶意请求检测

## 项目结构

```
src/modules/gateway/
├── README_DETAILED.md      # 本详细文档
├── main.py                 # 服务启动入口
├── config/
│   └── config.py           # 网关配置
├── middleware/
│   ├── auth.py             # 认证中间件
│   └── rate_limit.py       # 限流中间件
├── routes/
│   └── proxy.py            # 代理路由
├── services/
│   ├── proxy.py            # 代理服务
│   └── service_discovery.py # 服务发现
├── logs/                   # 服务日志
└── Dockerfile              # 容器化配置
```

## 路由配置

### 服务路由映射

```python
# 服务路由表
SERVICE_ROUTES = {
    "/auth": {
        "service": "auth",
        "port": 8007,
        "health_check": "/health",
        "timeout": 30
    },
    "/chat": {
        "service": "chat", 
        "port": 8001,
        "health_check": "/health",
        "websocket": True
    },
    "/files": {
        "service": "file",
        "port": 8004,
        "health_check": "/health",
        "max_body_size": "100MB"
    },
    "/lightrag": {
        "service": "lightraglocal",
        "port": 8006, 
        "health_check": "/healthz",
        "timeout": 120
    },
    "/llm": {
        "service": "llm",
        "port": 8080,
        "health_check": "/health",
        "timeout": 60
    },
    "/projects": {
        "service": "project",
        "port": 8020,
        "health_check": "/health"
    }
}
```

### 路由匹配规则

```python
async def route_request(self, request: Request) -> dict:
    """智能路由匹配"""
    path = request.url.path
    
    # 精确匹配
    for route_prefix, config in SERVICE_ROUTES.items():
        if path.startswith(route_prefix):
            return await self.get_service_instance(config["service"])
    
    # 默认路由
    return await self.get_default_service()
```

## 认证中间件

### JWT认证流程

```python
class AuthMiddleware:
    async def authenticate_request(self, request: Request) -> Optional[dict]:
        """验证请求认证"""
        # 1. 提取JWT令牌
        token = self.extract_token(request)
        if not token:
            return None
            
        # 2. 验证令牌有效性
        try:
            payload = await self.auth_service.verify_token(token)
            return {
                "user_id": payload["user_id"],
                "username": payload["username"], 
                "role": payload["role"]
            }
        except JWTError:
            return None
    
    def extract_token(self, request: Request) -> Optional[str]:
        """从请求中提取令牌"""
        # Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
            
        # Query parameter
        return request.query_params.get("token")
```

### 权限控制

```python
# API权限配置
API_PERMISSIONS = {
    "/auth/register": {"allow_anonymous": True},
    "/auth/login": {"allow_anonymous": True},
    "/files/upload": {"roles": ["user", "admin"]},
    "/admin/*": {"roles": ["admin"]},
    "/projects/*/delete": {"roles": ["admin", "project_owner"]}
}

async def check_permissions(self, path: str, user: dict) -> bool:
    """检查用户权限"""
    permission = self.match_permission_rule(path)
    
    if permission.get("allow_anonymous"):
        return True
        
    if not user:
        return False
        
    required_roles = permission.get("roles", [])
    return user["role"] in required_roles
```

## 限流机制

### 限流策略

```python
class RateLimiter:
    def __init__(self):
        self.redis_client = redis.Redis()
        
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """检查限流状态"""
        current_time = int(time.time())
        window_start = current_time - window
        
        # 清理过期记录
        await self.redis_client.zremrangebyscore(key, 0, window_start)
        
        # 检查当前请求数
        current_count = await self.redis_client.zcard(key)
        
        if current_count >= limit:
            return False
            
        # 记录当前请求
        await self.redis_client.zadd(key, {str(current_time): current_time})
        await self.redis_client.expire(key, window)
        
        return True
```

### 限流配置

```python
# 限流规则
RATE_LIMIT_RULES = {
    "global": {"limit": 1000, "window": 60},      # 全局限流
    "user": {"limit": 100, "window": 60},         # 用户限流  
    "ip": {"limit": 200, "window": 60},           # IP限流
    "api": {
        "/auth/login": {"limit": 5, "window": 60},  # 登录限流
        "/files/upload": {"limit": 10, "window": 60} # 上传限流
    }
}
```

## 负载均衡

### 负载均衡算法

```python
class LoadBalancer:
    def __init__(self):
        self.algorithms = {
            "round_robin": self.round_robin,
            "weighted_round_robin": self.weighted_round_robin,
            "least_connections": self.least_connections,
            "ip_hash": self.ip_hash
        }
    
    async def select_instance(self, service_name: str, 
                            algorithm: str = "round_robin") -> dict:
        """选择服务实例"""
        instances = await self.service_discovery.get_healthy_instances(service_name)
        
        if not instances:
            raise ServiceUnavailableError(f"No healthy instances for {service_name}")
            
        return await self.algorithms[algorithm](instances)
    
    async def round_robin(self, instances: list) -> dict:
        """轮询算法"""
        key = f"lb:rr:{hash(str(instances))}"
        index = await self.redis_client.incr(key) % len(instances)
        return instances[index]
```

### 健康检查

```python
class HealthChecker:
    async def check_service_health(self, service_config: dict) -> bool:
        """检查服务健康状态"""
        try:
            health_url = f"http://{service_config['host']}:{service_config['port']}{service_config['health_check']}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=5) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.warning(f"Health check failed for {service_config}: {e}")
            return False
```

## 服务发现

### Redis服务注册

```python
class ServiceDiscovery:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.service_prefix = "service:"
        
    async def register_service(self, service_name: str, instance_info: dict):
        """注册服务实例"""
        instance_key = f"{self.service_prefix}{service_name}:{instance_info['id']}"
        
        await self.redis_client.hset(instance_key, mapping={
            "host": instance_info["host"],
            "port": instance_info["port"], 
            "health_check": instance_info["health_check"],
            "status": "healthy",
            "last_heartbeat": int(time.time())
        })
        
        await self.redis_client.expire(instance_key, 60)  # 60秒过期
    
    async def discover_services(self, service_name: str) -> list:
        """发现服务实例"""
        pattern = f"{self.service_prefix}{service_name}:*"
        keys = await self.redis_client.keys(pattern)
        
        instances = []
        for key in keys:
            instance_data = await self.redis_client.hgetall(key)
            if instance_data.get("status") == "healthy":
                instances.append(instance_data)
                
        return instances
```

## 请求代理

### HTTP代理

```python
class HTTPProxy:
    async def proxy_request(self, request: Request, target_service: dict) -> Response:
        """代理HTTP请求"""
        # 构建目标URL
        target_url = f"http://{target_service['host']}:{target_service['port']}{request.url.path}"
        
        # 复制请求头（排除某些头部）
        headers = dict(request.headers)
        headers.pop('host', None)
        headers.pop('content-length', None)
        
        # 添加代理头部
        headers['X-Forwarded-For'] = request.client.host
        headers['X-Forwarded-Proto'] = request.url.scheme
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                data=await request.body(),
                timeout=target_service.get('timeout', 30)
            ) as response:
                # 构建响应
                content = await response.read()
                return Response(
                    content=content,
                    status_code=response.status,
                    headers=dict(response.headers)
                )
```

### WebSocket代理

```python
class WebSocketProxy:
    async def proxy_websocket(self, websocket: WebSocket, target_service: dict):
        """代理WebSocket连接"""
        target_url = f"ws://{target_service['host']}:{target_service['port']}{websocket.url.path}"
        
        async with websockets.connect(target_url) as target_ws:
            # 双向数据转发
            await asyncio.gather(
                self.forward_to_target(websocket, target_ws),
                self.forward_to_client(target_ws, websocket)
            )
    
    async def forward_to_target(self, client_ws: WebSocket, target_ws):
        """转发客户端消息到目标服务"""
        try:
            while True:
                message = await client_ws.receive_text()
                await target_ws.send(message)
        except WebSocketDisconnect:
            pass
```

## 监控和日志

### 请求日志

```python
class RequestLogger:
    async def log_request(self, request: Request, response: Response, 
                         processing_time: float):
        """记录请求日志"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "status_code": response.status_code,
            "processing_time": processing_time,
            "content_length": len(response.body) if response.body else 0
        }
        
        logger.info(json.dumps(log_data))
```

### 性能指标

```python
# 关键指标收集
METRICS = {
    "request_count": Counter(),
    "request_duration": Histogram(),
    "error_count": Counter(),
    "active_connections": Gauge()
}

async def record_metrics(self, request: Request, response: Response, duration: float):
    """记录性能指标"""
    METRICS["request_count"].inc()
    METRICS["request_duration"].observe(duration)
    
    if response.status_code >= 400:
        METRICS["error_count"].inc()
```

## 配置管理

### 环境变量

```bash
# 网关服务配置
GATEWAY_PORT=8888
GATEWAY_HOST=0.0.0.0

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=123456789
REDIS_DB=0

# 认证服务配置  
AUTH_SERVICE_URL=http://localhost:8007
JWT_PUBLIC_KEY_PATH=key/jwt_public_key.pem

# 代理配置
PROXY_TIMEOUT=30
MAX_REQUEST_SIZE=100MB
WEBSOCKET_TIMEOUT=300

# 限流配置
RATE_LIMIT_ENABLED=true
DEFAULT_RATE_LIMIT=100
RATE_LIMIT_WINDOW=60
```

### 动态配置

```python
class DynamicConfig:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.config_key = "gateway:config"
        
    async def get_config(self, key: str, default=None):
        """获取动态配置"""
        value = await self.redis_client.hget(self.config_key, key)
        return json.loads(value) if value else default
    
    async def update_config(self, key: str, value):
        """更新动态配置"""
        await self.redis_client.hset(self.config_key, key, json.dumps(value))
        
        # 通知配置更新
        await self.redis_client.publish("config:update", json.dumps({
            "key": key,
            "value": value
        }))
```

## 部署和运维

### 1. 启动服务

```bash
# 开发环境
python -m src.modules.gateway.main

# 生产环境  
uvicorn src.modules.gateway.main:app --host 0.0.0.0 --port 8888 --workers 4
```

### 2. 高可用部署

```bash
# 多实例部署
uvicorn src.modules.gateway.main:app --host 0.0.0.0 --port 8888 &
uvicorn src.modules.gateway.main:app --host 0.0.0.0 --port 8889 &

# 使用Nginx负载均衡
upstream gateway {
    server 127.0.0.1:8888;
    server 127.0.0.1:8889;
}
```

### 3. 健康检查

```bash
# 网关健康检查
curl http://localhost:8888/health

# 服务发现状态
curl http://localhost:8888/debug/services

# 限流状态查看
curl http://localhost:8888/debug/rate-limits
```

## 故障排除

### 常见问题

1. **服务路由失败**
   - 检查服务发现状态
   - 验证目标服务健康状态
   - 确认路由配置正确

2. **认证失败**
   - 检查JWT公钥配置
   - 验证认证服务连接
   - 确认令牌格式正确

3. **限流误触发**
   - 检查限流规则配置
   - 监控Redis连接状态
   - 调整限流阈值

### 调试工具

```bash
# 查看网关状态
curl http://localhost:8888/debug/status

# 检查路由表
curl http://localhost:8888/debug/routes

# 监控实时请求
curl http://localhost:8888/debug/requests
```

## 扩展功能

### 1. API版本管理
- 版本路由支持
- 向后兼容处理
- 版本切换策略

### 2. 缓存层
- 响应缓存
- 智能缓存失效
- 缓存预热机制

### 3. 监控告警
- 实时监控面板
- 异常自动告警
- 性能分析报告