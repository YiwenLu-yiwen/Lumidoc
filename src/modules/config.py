from pydantic_settings import BaseSettings
import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

# 确保加载项目根目录的.env文件
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)
    print(f"已从 {ENV_FILE} 加载环境变量")
else:
    print(f"警告: 未找到.env文件在 {ENV_FILE}")

# 从URL中提取端口的工具函数
def get_port_from_url(url, default_port):
    if not url:
        return default_port
    try:
        parsed = urlparse(url)
        return parsed.port or default_port
    except Exception:
        return default_port

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = os.getenv("POSTGRES_URL", "postgresql://stpuser:stppassword@localhost:5432/stpdb")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "stpuser")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "stppassword")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "stpdb")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    
    # 存储模式配置
    AUTH_STORAGE_MODE: str = os.getenv("AUTH_STORAGE_MODE", "POSTGRES")
    QUESTION_STORAGE_MODE: str = os.getenv("QUESTION_STORAGE_MODE", "POSTGRES")
    CHAT_STORAGE_MODE: str = os.getenv("CHAT_STORAGE_MODE", "POSTGRES")
    GRAPH_STORAGE_MODE: str = os.getenv("GRAPH_STORAGE_MODE", "NEO4J")
    
    # 模块服务配置 - URL
    project_service_url: str = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8020")
    chat_service_url: str = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")
    question_service_url: str = os.getenv("QUESTION_SERVICE_URL", "http://localhost:8002")
    graph_service_url: str = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8003")
    file_service_url: str = os.getenv("FILE_SERVICE_URL", "http://localhost:8004")
    fileproc_service_url: str = os.getenv("FILEPROC_SERVICE_URL", "http://localhost:8005")
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "http://localhost:8006")
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8007")
    monitoring_service_url: str = os.getenv("MONITORING_SERVICE_URL", "http://localhost:8008")
    
    # 服务端口配置 - 从URL中提取，不再需要单独配置
    @property
    def project_service_port(self) -> int:
        return get_port_from_url(self.project_service_url, 8020)
    
    @property
    def chat_service_port(self) -> int:
        return get_port_from_url(self.chat_service_url, 8001)
    
    @property
    def question_service_port(self) -> int:
        return get_port_from_url(self.question_service_url, 8002)
    
    @property
    def graph_service_port(self) -> int:
        return get_port_from_url(self.graph_service_url, 8003)
    
    @property
    def file_service_port(self) -> int:
        return get_port_from_url(self.file_service_url, 8004)
    
    @property
    def fileproc_service_port(self) -> int:
        return get_port_from_url(self.fileproc_service_url, 8005)
    
    @property
    def rag_service_port(self) -> int:
        return get_port_from_url(self.rag_service_url, 8006)
    
    @property
    def auth_service_port(self) -> int:
        return get_port_from_url(self.auth_service_url, 8007)
    
    @property
    def monitoring_service_port(self) -> int:
        return get_port_from_url(self.monitoring_service_url, 8008)
    
    # 前端配置 - 使用相同的方式处理
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    @property
    def frontend_port(self) -> int:
        return get_port_from_url(self.frontend_url, 3000)
    
    # RAG配置
    RAG_DEFAULT_TOP_K: int = int(os.getenv("RAG_DEFAULT_TOP_K", "5"))
    RAG_CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    RAG_CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
    RAG_DIR: str = os.getenv("RAG_DIR", "./rag")
    RAG_INDEX_NAME: str = os.getenv("RAG_INDEX_NAME", "default_index")
    DEFAULT_QUERY_MODE: str = os.getenv("DEFAULT_QUERY_MODE", "naive")
    DEFAULT_STREAM: bool = os.getenv("DEFAULT_STREAM", "false").lower() in ("true", "1", "t")
    
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Neo4j配置
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "123456789")
    
    # 其他配置
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "t")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "RS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    SKIP_TOKEN_VERIFICATION: bool = os.getenv("SKIP_TOKEN_VERIFICATION", "false").lower() in ("true", "1", "t")

    # 基础配置
    project_name: str = os.getenv("PROJECT_NAME", "STP")
    
    # API密钥配置
    api_key: str = os.environ.get("API_KEY", "")
    deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
    azure_api_key: str = os.environ.get("AZURE_API_KEY", "")
    sonica_api_key: str = os.environ.get("SONICA_API_KEY", "")
    
    # LLM 配置
    LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:8080")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen3:1.7b")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    
    # Ollama 配置
    OLLAMA_EMBEDDING_URL: str = os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434")
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3")

    model_config = {
        "env_file": str(ENV_FILE),
        "case_sensitive": True,
        "extra": "allow"  # 允许额外字段
    }

settings = Settings() 