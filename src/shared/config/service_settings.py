"""
微服务配置类
基于共享配置工具提供标准化的微服务配置模型
"""

from typing import Dict, List, Optional, Any, Union, ClassVar
from pydantic import Field, validator
import os
from pathlib import Path

from .settings import SettingsBase, ServiceSettings, DatabaseSettings, LoggingSettings
from .config_loader import get_env

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class AuthServiceSettings(ServiceSettings):
    """认证服务配置"""
    
    # 服务标识
    service_name: str = "auth"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("AUTH_SERVICE_PORT", 8007, env_type=int))
    
    # JWT配置
    secret_key: str = Field(default_factory=lambda: get_env("SECRET_KEY", "your-secret-key-here"))
    jwt_algorithm: str = Field(default_factory=lambda: get_env("JWT_ALGORITHM", "RS256"))
    access_token_expire_minutes: int = Field(default_factory=lambda: get_env("ACCESS_TOKEN_EXPIRE_MINUTES", 1440, env_type=int))
    skip_token_verification: bool = Field(default_factory=lambda: get_env("SKIP_TOKEN_VERIFICATION", False, env_type=bool))
    
    # 默认JWT密钥路径
    jwt_private_key_path: str = Field(
        default_factory=lambda: get_env(
            "JWT_PRIVATE_KEY_PATH", 
            str(ROOT_DIR / "src" / "modules" / "auth" / "key" / "jwt_private_key.pem")
        )
    )
    jwt_public_key_path: str = Field(
        default_factory=lambda: get_env(
            "JWT_PUBLIC_KEY_PATH", 
            str(ROOT_DIR / "src" / "modules" / "auth" / "key" / "jwt_public_key.pem")
        )
    )
    
    # 存储配置
    storage_mode: str = Field(default_factory=lambda: get_env("AUTH_STORAGE_MODE", "POSTGRES"))
    local_storage_dir: str = Field(default_factory=lambda: get_env("AUTH_LOCAL_STORAGE_DIR", "data/auth"))
    
    model_config = {
        "env_prefix": "AUTH_"
    }


class FileServiceSettings(ServiceSettings):
    """文件服务配置"""
    
    # 服务标识
    service_name: str = "file"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("FILE_SERVICE_PORT", 8004, env_type=int))
    
    # 存储配置
    storage_type: str = Field(default_factory=lambda: get_env("STORAGE_TYPE", "local"))
    storage_dir: str = Field(default_factory=lambda: get_env("STORAGE_DIR", "./storage"))
    upload_dir: str = Field(default_factory=lambda: get_env("UPLOAD_DIR", "./uploads"))
    temp_dir: str = Field(default_factory=lambda: get_env("TEMP_DIR", "./temp"))
    
    # 文件处理配置
    max_file_size: int = Field(default_factory=lambda: get_env("MAX_FILE_SIZE", 10485760, env_type=int))
    clean_unused_files: bool = Field(default_factory=lambda: get_env("CLEAN_UNUSED_FILES", True, env_type=bool))
    save_original_files: bool = Field(default_factory=lambda: get_env("SAVE_ORIGINAL_FILES", False, env_type=bool))
    
    # S3配置
    s3_endpoint: str = Field(default_factory=lambda: get_env("S3_ENDPOINT", "http://localhost:9000"))
    s3_access_key: str = Field(default_factory=lambda: get_env("S3_ACCESS_KEY", "minioadmin"))
    s3_secret_key: str = Field(default_factory=lambda: get_env("S3_SECRET_KEY", "minioadmin"))
    s3_bucket: str = Field(default_factory=lambda: get_env("S3_BUCKET", "data"))
    s3_region: str = Field(default_factory=lambda: get_env("S3_REGION", "us-east-1"))
    
    # 健康检查配置
    health_check_endpoint: str = Field(default_factory=lambda: get_env("HEALTH_CHECK_ENDPOINT", "/healthz"))
    
    def get_absolute_storage_dir(self) -> Path:
        """获取绝对存储目录路径"""
        path = Path(self.storage_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.storage_dir
    
    def get_absolute_upload_dir(self) -> Path:
        """获取绝对上传目录路径"""
        path = Path(self.upload_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.upload_dir
    
    def get_absolute_temp_dir(self) -> Path:
        """获取绝对临时目录路径"""
        path = Path(self.temp_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.temp_dir
    
    model_config = {
        "env_prefix": "FILE_"
    }


class FileProcServiceSettings(ServiceSettings):
    """文件处理服务配置"""
    
    # 服务标识
    service_name: str = "fileproc"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("FILEPROC_SERVICE_PORT", 8005, env_type=int))
    
    # 存储配置 - 与文件服务保持一致
    storage_type: str = Field(default_factory=lambda: get_env("STORAGE_TYPE", "local"))
    storage_dir: str = Field(default_factory=lambda: get_env("STORAGE_DIR", "./storage"))
    upload_dir: str = Field(default_factory=lambda: get_env("UPLOAD_DIR", "./uploads"))
    temp_dir: str = Field(default_factory=lambda: get_env("TEMP_DIR", "./temp"))
    max_file_size: int = Field(default_factory=lambda: get_env("MAX_FILE_SIZE", 10485760, env_type=int))
    
    # 文件处理配置
    instance_id: str = Field(default_factory=lambda: get_env("INSTANCE_ID", "file_service_1"))
    file_processing_queue: str = Field(default_factory=lambda: get_env("FILE_PROCESSING_QUEUE", "file_processing"))
    file_processing_workers: int = Field(default_factory=lambda: get_env("FILE_PROCESSING_WORKERS", 2, env_type=int))
    enable_ocr: bool = Field(default_factory=lambda: get_env("ENABLE_OCR", False, env_type=bool))
    use_gpu: bool = Field(default_factory=lambda: get_env("USE_GPU", False, env_type=bool))
    
    # 健康检查配置
    health_check_endpoint: str = Field(default_factory=lambda: get_env("HEALTH_CHECK_ENDPOINT", "/healthz"))
    
    # 允许的文件扩展名
    allowed_extensions: List[str] = [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", 
        ".pptx", ".ppt", ".txt", ".csv", ".json",
        ".md", ".html", ".htm", ".xml", ".jpg", 
        ".png", ".jpeg"
    ]
    
    def get_absolute_storage_dir(self) -> Path:
        """获取绝对存储目录路径"""
        path = Path(self.storage_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.storage_dir
    
    def get_absolute_upload_dir(self) -> Path:
        """获取绝对上传目录路径"""
        path = Path(self.upload_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.upload_dir
    
    def get_absolute_temp_dir(self) -> Path:
        """获取绝对临时目录路径"""
        path = Path(self.temp_dir)
        if path.is_absolute():
            return path
        return ROOT_DIR / self.temp_dir
    
    model_config = {
        "env_prefix": "FILEPROC_"
    }


class RAGServiceSettings(ServiceSettings):
    """RAG服务配置"""
    
    # 服务标识
    service_name: str = "rag"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("RAG_SERVICE_PORT", 8006, env_type=int))
    
    # RAG配置
    working_dir: str = Field(default_factory=lambda: get_env("RAG_DIR", "./rag"))
    index_name: str = Field(default_factory=lambda: get_env("RAG_INDEX_NAME", "default_index"))
    default_top_k: int = Field(default_factory=lambda: get_env("RAG_DEFAULT_TOP_K", 5, env_type=int))
    chunk_size: int = Field(default_factory=lambda: get_env("RAG_CHUNK_SIZE", 1000, env_type=int))
    chunk_overlap: int = Field(default_factory=lambda: get_env("RAG_CHUNK_OVERLAP", 200, env_type=int))
    default_query_mode: str = Field(default_factory=lambda: get_env("RAG_DEFAULT_QUERY_MODE", "naive"))
    default_stream: bool = Field(default_factory=lambda: get_env("RAG_DEFAULT_STREAM", False, env_type=bool))
    
    # FAISS配置
    faiss_storage_mode: str = Field(default_factory=lambda: get_env("FAISS_STORAGE_MODE", "LOCAL"))
    faiss_index_type: str = Field(default_factory=lambda: get_env("FAISS_INDEX_TYPE", "FLAT"))
    faiss_use_gpu: bool = Field(default_factory=lambda: get_env("FAISS_USE_GPU", False, env_type=bool))
    faiss_num_partitions: int = Field(default_factory=lambda: get_env("FAISS_NUM_PARTITIONS", 1, env_type=int))
    
    # LightRAG本地存储
    lightrag_local_storage_dir: str = Field(default_factory=lambda: get_env("LIGHTRAG_LOCAL_STORAGE_DIR", "data/lightrag"))
    
    # 文件上传目录 - 与文件服务保持一致
    upload_dir: str = Field(default_factory=lambda: get_env("UPLOAD_DIR", "./uploads"))
    
    def get_absolute_rag_dir(self, project_id: str = None) -> Path:
        """
        获取绝对RAG目录路径
        
        Args:
            project_id: 可选的项目ID，如果提供则返回特定项目的RAG目录
            
        Returns:
            Path: 绝对路径
        """
        path = Path(self.working_dir)
        if path.is_absolute():
            base_path = path
        else:
            base_path = ROOT_DIR / self.working_dir
            
        if project_id:
            return base_path / project_id
        return base_path
    
    def get_absolute_upload_dir(self, project_id: str = None) -> Path:
        """
        获取绝对上传目录路径
        
        Args:
            project_id: 可选的项目ID，如果提供则返回特定项目的上传目录
            
        Returns:
            Path: 绝对路径
        """
        path = Path(self.upload_dir)
        if path.is_absolute():
            base_path = path
        else:
            base_path = ROOT_DIR / self.upload_dir
            
        if project_id:
            return base_path / project_id
        return base_path
    
    model_config = {
        "env_prefix": "RAG_"
    }


class ChatServiceSettings(ServiceSettings):
    """聊天服务配置"""
    
    # 服务标识
    service_name: str = "chat"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("CHAT_SERVICE_PORT", 8001, env_type=int))
    
    # 聊天配置
    max_history_messages: int = Field(default_factory=lambda: get_env("MAX_HISTORY_MESSAGES", 5, env_type=int))
    session_timeout: int = Field(default_factory=lambda: get_env("SESSION_TIMEOUT", 3600, env_type=int))
    
    # 存储配置
    storage_mode: str = Field(default_factory=lambda: get_env("CHAT_STORAGE_MODE", "POSTGRES"))
    
    model_config = {
        "env_prefix": "CHAT_"
    }


class LLMSummaryServiceSettings(ServiceSettings):
    """LLM摘要服务配置"""
    
    # 服务标识
    service_name: str = "llm_summary"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("LLM_SUMMARY_SERVICE_PORT", 8009, env_type=int))
    
    # 摘要配置
    summary_max_length: int = Field(default_factory=lambda: get_env("SUMMARY_MAX_LENGTH", 1000, env_type=int))
    enable_structured_output: bool = Field(default_factory=lambda: get_env("ENABLE_STRUCTURED_OUTPUT", True, env_type=bool))
    enable_cache: bool = Field(default_factory=lambda: get_env("ENABLE_CACHE", True, env_type=bool))
    cache_ttl: int = Field(default_factory=lambda: get_env("CACHE_TTL", 86400, env_type=int))
    
    model_config = {
        "env_prefix": "LLM_SUMMARY_"
    }


class QuestionServiceSettings(ServiceSettings):
    """问答服务配置"""
    
    # 服务标识
    service_name: str = "question"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("QUESTION_SERVICE_PORT", 8002, env_type=int))
    
    # 存储配置
    storage_mode: str = Field(default_factory=lambda: get_env("QUESTION_STORAGE_MODE", "POSTGRES"))
    local_storage_dir: str = Field(default_factory=lambda: get_env("QUESTION_LOCAL_STORAGE_DIR", "data/questions"))
    
    model_config = {
        "env_prefix": "QUESTION_"
    }


class GraphServiceSettings(ServiceSettings):
    """图谱服务配置"""
    
    # 服务标识
    service_name: str = "graph"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("GRAPH_SERVICE_PORT", 8003, env_type=int))
    
    # 存储配置
    storage_mode: str = Field(default_factory=lambda: get_env("GRAPH_STORAGE_MODE", "NEO4J"))
    
    model_config = {
        "env_prefix": "GRAPH_"
    }


class ProjectServiceSettings(ServiceSettings):
    """项目服务配置"""
    
    # 服务标识
    service_name: str = "project"
    service_version: str = "0.1.0"
    
    # 服务网络配置
    port: int = Field(default_factory=lambda: get_env("PROJECT_SERVICE_PORT", 8020, env_type=int))
    
    # 项目存储配置
    local_storage_dir: str = Field(default_factory=lambda: get_env("PROJECT_LOCAL_STORAGE_DIR", "data/projects"))
    
    model_config = {
        "env_prefix": "PROJECT_"
    }


# 定义全局常量
MODEL_TYPE_OLLAMA = "ollama"
MODEL_TYPE_OPENAI = "openai"
MODEL_TYPE_DEEPSEEK = "deepseek"
MODEL_TYPE_AZURE = "azure"
MODEL_TYPE_VLLM = "vllm"

# 支持的模型类型列表
SUPPORTED_MODEL_TYPES = [
    MODEL_TYPE_OLLAMA,
    MODEL_TYPE_OPENAI,
    MODEL_TYPE_DEEPSEEK,
    MODEL_TYPE_AZURE,
    MODEL_TYPE_VLLM
]

class LLMSettings(SettingsBase):
    """LLM统一配置类"""
    
    # 模型类型常量 - 使用ClassVar标记为类变量而非字段
    MODEL_TYPE_OLLAMA: ClassVar[str] = MODEL_TYPE_OLLAMA
    MODEL_TYPE_OPENAI: ClassVar[str] = MODEL_TYPE_OPENAI
    MODEL_TYPE_DEEPSEEK: ClassVar[str] = MODEL_TYPE_DEEPSEEK
    MODEL_TYPE_AZURE: ClassVar[str] = MODEL_TYPE_AZURE
    MODEL_TYPE_VLLM: ClassVar[str] = MODEL_TYPE_VLLM
    SUPPORTED_MODEL_TYPES: ClassVar[List[str]] = SUPPORTED_MODEL_TYPES
    
    # 模型基本配置
    model_type: str = Field(default_factory=lambda: get_env("LLM_MODEL_TYPE", "ollama"))
    model_name: str = Field(default_factory=lambda: get_env("LLM_MODEL_NAME", "qwen3:1.7b"))
    api_key: Optional[str] = Field(default_factory=lambda: get_env("LLM_API_KEY", ""))
    
    # 生成参数
    temperature: float = Field(default_factory=lambda: get_env("LLM_TEMPERATURE", 0.2, env_type=float))
    max_tokens: int = Field(default_factory=lambda: get_env("LLM_MAX_TOKENS", 2000, env_type=int))
    request_timeout: float = Field(default_factory=lambda: get_env("LLM_REQUEST_TIMEOUT", 60.0, env_type=float))
    
    # API端点配置
    deepseek_api_url: str = Field(default_factory=lambda: get_env("DEEPSEEK_API_URL", "https://api.deepseek.com"))
    openai_api_url: str = Field(default_factory=lambda: get_env("OPENAI_API_URL", "https://api.openai.com/v1"))
    azure_api_url: Optional[str] = Field(default_factory=lambda: get_env("AZURE_API_URL", ""))
    ollama_api_url: str = Field(default_factory=lambda: get_env("OLLAMA_API_URL", "http://localhost:11434"))
    vllm_api_url: str = Field(default_factory=lambda: get_env("VLLM_API_URL", "http://localhost:8080"))
    
    # 为了向后兼容而保留的选项
    ollama_url: str = Field(default_factory=lambda: get_env("OLLAMA_URL", "http://localhost:11434"))
    
    # 嵌入模型配置
    embedding_model_type: str = Field(default_factory=lambda: get_env("EMBEDDING_MODEL_TYPE", "ollama"))
    embedding_model_name: str = Field(default_factory=lambda: get_env("DEFAULT_EMBEDDING_MODEL", "bge-m3"))
    embedding_url: str = Field(default_factory=lambda: get_env("OLLAMA_EMBEDDING_URL", "http://localhost:11434"))
    
    # 摘要特定配置
    summary_max_length: int = Field(default_factory=lambda: get_env("SUMMARY_MAX_LENGTH", 1000, env_type=int))
    summary_min_compression: float = Field(default_factory=lambda: get_env("SUMMARY_MIN_COMPRESSION", 0.25, env_type=float))
    enable_structured_output: bool = Field(default_factory=lambda: get_env("ENABLE_STRUCTURED_OUTPUT", True, env_type=bool))
    
    # 缓存配置
    enable_cache: bool = Field(default_factory=lambda: get_env("ENABLE_CACHE", True, env_type=bool))
    cache_ttl: int = Field(default_factory=lambda: get_env("CACHE_TTL", 86400, env_type=int))
    
    # vLLM特有配置
    vllm_tensor_parallel_size: int = Field(default_factory=lambda: get_env("VLLM_TENSOR_PARALLEL_SIZE", 1, env_type=int))
    vllm_max_concurrent_requests: int = Field(default_factory=lambda: get_env("VLLM_MAX_CONCURRENT_REQUESTS", 100, env_type=int))
    vllm_gpu_memory_utilization: float = Field(default_factory=lambda: get_env("VLLM_GPU_MEMORY_UTILIZATION", 0.9, env_type=float))
    
    @property
    def base_url(self) -> str:
        """根据模型类型返回相应的基础URL"""
        if self.model_type == self.MODEL_TYPE_OLLAMA:
            return self.ollama_api_url
        elif self.model_type == self.MODEL_TYPE_OPENAI:
            return self.openai_api_url
        elif self.model_type == self.MODEL_TYPE_DEEPSEEK:
            return self.deepseek_api_url
        elif self.model_type == self.MODEL_TYPE_AZURE:
            return self.azure_api_url or ""
        elif self.model_type == self.MODEL_TYPE_VLLM:
            return self.vllm_api_url
        else:
            return ""
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_prefix": "LLM_"
    }

# 创建全局LLM配置实例
llm_settings_global = LLMSettings()

class LLMServiceSettings(ServiceSettings):
    """LLM服务配置类"""
    
    # 服务信息
    service_name: str = "llm-service"
    service_version: str = "1.0.0"
    
    # 服务端口
    port: int = Field(default_factory=lambda: get_env("LLM_SERVICE_PORT", 8080, env_type=int))
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "env_prefix": "LLM_"
    }

# 创建各服务设置实例
auth_settings = AuthServiceSettings()
file_settings = FileServiceSettings()
fileproc_settings = FileProcServiceSettings()
graph_settings = GraphServiceSettings()
lightraglocal_settings = RAGServiceSettings()
monitoring_settings = ServiceSettings(service_name="monitoring", port=8008)
project_settings = ProjectServiceSettings()
question_settings = QuestionServiceSettings()
chat_settings = ChatServiceSettings()
llm_settings = LLMServiceSettings() 