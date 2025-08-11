"""
配置模型定义
基于Pydantic的配置类，用于验证和管理服务配置
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class SettingsBase(BaseSettings):
    """
    基础配置类，所有配置类应继承此类
    提供从环境变量读取配置的功能
    """
    
    class Config:
        """配置元数据"""
        # 自动从环境变量读取值
        env_file = ".env"
        env_file_encoding = "utf-8"
        # 大小写敏感
        case_sensitive = False
        # 额外配置
        extra = "ignore"


class DatabaseSettings(BaseModel):
    """数据库连接配置"""
    
    engine: str = Field("sqlite", description="数据库引擎")
    host: Optional[str] = Field(None, description="数据库主机")
    port: Optional[int] = Field(None, description="数据库端口")
    username: Optional[str] = Field(None, description="数据库用户名")
    password: Optional[str] = Field(None, description="数据库密码")
    database: str = Field(..., description="数据库名称")
    
    @property
    def connection_string(self) -> str:
        """生成数据库连接字符串"""
        if self.engine == "sqlite":
            return f"sqlite:///{self.database}"
        elif self.engine == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"不支持的数据库引擎: {self.engine}")


class LoggingSettings(BaseModel):
    """日志配置"""
    
    level: str = Field("INFO", description="日志级别")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    file: Optional[str] = Field(None, description="日志文件路径")
    max_size: int = Field(10 * 1024 * 1024, description="单个日志文件最大大小(字节)")
    backup_count: int = Field(5, description="备份日志文件数量")


class ServiceSettings(SettingsBase):
    """
    服务通用配置基类
    所有微服务配置类应该继承此类
    """
    
    # 服务标识
    service_name: str = Field(..., description="服务名称")
    service_version: str = Field("0.1.0", description="服务版本")
    
    # 服务网络配置
    host: str = Field("0.0.0.0", description="服务监听地址")
    port: int = Field(..., description="服务监听端口")
    base_path: str = Field("", description="API基础路径")
    
    # 跨域配置
    cors_origins: List[str] = Field(default_factory=lambda: ["*"], description="允许的跨域来源")
    cors_methods: List[str] = Field(default_factory=lambda: ["*"], description="允许的跨域方法")
    cors_headers: List[str] = Field(default_factory=lambda: ["*"], description="允许的跨域头部")
    
    # 安全配置
    debug: bool = Field(False, description="是否开启调试模式")
    secret_key: Optional[str] = Field(None, description="服务密钥")
    
    # 日志配置
    logging: LoggingSettings = Field(default_factory=LoggingSettings, description="日志配置")
    
    # 数据库配置
    database: Optional[DatabaseSettings] = Field(None, description="数据库配置")
    
    # 其他服务依赖
    dependencies: Dict[str, str] = Field(default_factory=dict, description="依赖服务URL")
    
    # 存储配置
    storage_dir: str = Field("./storage", description="存储目录")
    upload_dir: str = Field("./uploads", description="上传目录")
    content_dir: str = Field("./content", description="内容目录")
    
    @field_validator("dependencies")
    def validate_dependencies(cls, v: Dict[str, str]) -> Dict[str, str]:
        """验证依赖服务URL格式"""
        for service, url in v.items():
            if not url.startswith(("http://", "https://")):
                v[service] = f"http://{url}"
        return v
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析CORS来源"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        """配置元数据"""
        env_prefix = ""  # 各服务应覆盖此值，如 "LLM_" 