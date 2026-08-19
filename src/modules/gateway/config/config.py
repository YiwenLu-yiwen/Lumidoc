"""
Gateway API配置文件
使用统一配置系统，支持环境变量注入
"""

from typing import Dict, List, Optional, Any
from src.shared.config import get_env

class GatewaySettings:
    """Gateway API配置类"""
    
    # 服务基本信息
    service_name: str = "gateway"
    service_version: str = "1.0.0"
    service_description: str = "Lumidoc系统统一API网关"
    
    # 网络配置
    host: str = get_env("GATEWAY_HOST", "0.0.0.0")
    port: int = get_env("GATEWAY_PORT", 8888, env_type=int)
    
    # 调试模式
    debug: bool = get_env("DEBUG", True, env_type=bool)
    
    # 跨域配置
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        "https://127.0.0.1:3000",
        "http://115.29.191.36:3000"
    ]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_headers: List[str] = ["*"]
    cors_credentials: bool = True
    
    # 微服务路由配置
    service_routes: Dict[str, Dict[str, Any]] = {
        "auth": {
            "url": get_env("AUTH_SERVICE_URL", "http://localhost:8007"),
            "prefix": "/api/auth",
            "health_check": "/healthz",
            "timeout": 30.0,
            "retries": 3,
            "strip_prefix": True  # 移除前缀后转发到认证服务
        },
        "chat": {
            "url": get_env("CHAT_SERVICE_URL", "http://localhost:8001"),
            "prefix": "/chat",
            "health_check": "/healthz",
            "timeout": 300.0,  # 聊天服务需要更长时间，增加到5分钟
            "retries": 3,
            "retry_interval": 2.0  # 添加重试间隔
        },
        "file": {
            "url": get_env("FILE_SERVICE_URL", "http://localhost:8004"),
            "prefix": "/api/file",
            "health_check": "/healthz",
            "timeout": 60.0,  # 文件上传可能需要更长时间
            "retries": 3,
            "strip_prefix": True  # 移除前缀后转发到文件服务
        },
        "fileproc": {
            "url": get_env("FILEPROC_SERVICE_URL", "http://localhost:8005"),
            "prefix": "/fileproc",
            "health_check": "/healthz",
            "timeout": 300.0,  # 文件处理可能需要更长时间
            "retries": 2,
            "strip_prefix": True  # 添加标记，表示需要移除前缀
        },
        "graph": {
            "url": get_env("GRAPH_SERVICE_URL", "http://localhost:8003"),
            "prefix": "/graph",
            "health_check": "/healthz",
            "timeout": 30.0,
            "retries": 3
        },
        "lightrag": {
            "url": get_env("RAG_SERVICE_URL", "http://localhost:8006"),
            "prefix": "/api/lightrag",
            "health_check": "/healthz",
            "timeout": 7200.0,  # RAG检索超时时间，2小时适配本地模型
            "retries": 1,     # 本地模型稳定，保持1次重试
            "retry_interval": 2.0,  # 添加重试间隔
            "strip_prefix": False,  # 保持完整路径转发到lightrag服务
            "alt_prefixes": []  # 清空备用前缀
        },
        "llm": {
            "url": get_env("LLM_SERVICE_URL", "http://localhost:8080"),
            "prefix": "/api/v1/llm",
            "health_check": "/healthz",
            "timeout": 7200.0,  # LLM处理超时时间，2小时适配本地模型
            "retries": 1,  # 本地模型稳定，保持1次重试
            "strip_prefix": False  # 保持完整路径转发到LLM服务
        },
        "monitoring": {
            "url": get_env("MONITORING_SERVICE_URL", "http://localhost:8008"),
            "prefix": "/monitoring",
            "health_check": "/healthz",
            "timeout": 30.0,
            "retries": 3
        },
        "project": {
            "url": get_env("PROJECT_SERVICE_URL", "http://localhost:8020"),
            "prefix": "/api/projects",  # 匹配前端请求路径
            "health_check": "/healthz",
            "timeout": 30.0,
            "retries": 3,
            "strip_prefix": False  # 不移除前缀，直接转发完整路径
        },
        "question": {
            "url": get_env("QUESTION_SERVICE_URL", "http://localhost:8002"),
            "prefix": "/question",
            "health_check": "/healthz",
            "timeout": 30.0,
            "retries": 3
        }
    }
    
    # Redis配置（用于服务发现和缓存）
    redis_enabled: bool = get_env("REDIS_ENABLED", False, env_type=bool)
    redis_host: str = get_env("REDIS_HOST", "localhost")
    redis_port: int = get_env("REDIS_PORT", 6379, env_type=int)
    redis_db: int = get_env("REDIS_DB", 0, env_type=int)
    redis_password: str = get_env("REDIS_PASSWORD", "")
    
    # 健康检查配置
    health_check_enabled: bool = get_env("HEALTH_CHECK_ENABLED", True, env_type=bool)
    health_check_interval: int = get_env("HEALTH_CHECK_INTERVAL", 60, env_type=int)  # 设置为60秒，平衡性能和及时性
    health_check_timeout: int = get_env("HEALTH_CHECK_TIMEOUT", 5, env_type=int)  # 减少到5秒，避免阻塞
    
    # 负载均衡配置
    load_balancer_enabled: bool = get_env("LOAD_BALANCER_ENABLED", True, env_type=bool)
    load_balancer_algorithm: str = get_env("LOAD_BALANCER_ALGORITHM", "round_robin")  # round_robin, random, least_connections
    
    # 限流配置
    rate_limit_enabled: bool = get_env("RATE_LIMIT_ENABLED", True, env_type=bool)
    rate_limit_requests: int = get_env("RATE_LIMIT_REQUESTS", 600, env_type=int)  # 增加到每分钟600个请求，给健康检查更多容量
    rate_limit_window: int = get_env("RATE_LIMIT_WINDOW", 60, env_type=int)  # 时间窗口（秒）
    
    # 认证配置
    auth_enabled: bool = get_env("AUTH_ENABLED", True, env_type=bool)  # 恢复认证功能
    auth_exclude_paths: List[str] = [
        "/",
        "/health",
        "/gateway/health",  # 网关健康检查端点
        "/info",
        "/services",
        "/metrics",
        "/docs",
        "/openapi.json",
        # 认证相关端点 - 修正为实际的认证端点路径
        "/api/auth/token",         # 主要的token获取端点
        "/api/auth/login",         # 登录端点
        "/api/auth/register",      # 注册端点
        "/api/auth/refresh",       # 刷新端点
        "/api/auth/reset_password", # 重置密码端点
        # 所有服务的健康检查端点
        "/auth/health",
        "/chat/health", 
        "/file/health",
        "/fileproc/health",
        "/fileproc/api/health",
        "/graph/health",
        "/lightrag/health",
        "/lightrag/healthz",
        "/llm/health",
        "/monitoring/health",
        "/api/projects/health",
        "/question/health",
        # LightRAG测试路径
        "/api/lightrag/lightrag/files/1",
        "/api/lightrag/lightrag/build/1",
        "/api/lightrag/lightrag/status/1",
        # 添加OPTIONS预检请求路径排除，防止CORS问题
        "OPTIONS"
    ]
    
    # 日志配置
    log_level: str = get_env("LOG_LEVEL", "INFO")
    log_format: str = get_env("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # 监控配置
    metrics_enabled: bool = get_env("METRICS_ENABLED", True, env_type=bool)
    metrics_path: str = get_env("METRICS_PATH", "/metrics")
    
    # 静态文件配置
    static_files_enabled: bool = get_env("STATIC_FILES_ENABLED", False, env_type=bool)
    static_files_path: str = get_env("STATIC_FILES_PATH", "/static")
    static_files_dir: str = get_env("STATIC_FILES_DIR", "./static")
    
    @classmethod
    def get_service_url(cls, service_name: str) -> Optional[str]:
        """获取服务URL"""
        service_config = cls.service_routes.get(service_name)
        if service_config:
            return service_config["url"]
        return None
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Optional[Dict[str, Any]]:
        """获取服务配置"""
        return cls.service_routes.get(service_name)
    
    @classmethod
    def get_all_services(cls) -> List[str]:
        """获取所有服务名称"""
        return list(cls.service_routes.keys())

# 创建全局配置实例
settings = GatewaySettings()

# 添加环境变量覆盖
# 暂时注释掉环境变量覆盖，使用硬编码的CORS配置
# if cors_origins_env := get_env("CORS_ORIGINS"):
#     settings.cors_origins = cors_origins_env.split(",")

if auth_exclude_paths_env := get_env("AUTH_EXCLUDE_PATHS"):
    settings.auth_exclude_paths = auth_exclude_paths_env.split(",")

# 确保所有服务URL都有协议前缀
for service_name, service_config in settings.service_routes.items():
    if not service_config["url"].startswith(("http://", "https://")):
        service_config["url"] = f"http://{service_config['url']}" 