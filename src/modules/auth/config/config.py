"""
认证服务配置
使用统一配置系统
"""

from pathlib import Path
from src.shared.config import AuthServiceSettings, get_env

# 创建全局设置实例
settings = AuthServiceSettings()

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent

# JWT密钥绝对路径
JWT_PUBLIC_KEY_PATH = ROOT_DIR / "src" / "modules" / "auth" / "key" / "jwt_public_key.pem"
JWT_PRIVATE_KEY_PATH = ROOT_DIR / "src" / "modules" / "auth" / "key" / "jwt_private_key.pem"

# 为了保持向后兼容性，扩展配置项
class ExtendedAuthSettings:
    # JWT配置
    SECRET_KEY = settings.secret_key
    JWT_ALGORITHM = settings.jwt_algorithm
    ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
    # 重要: 使用绝对路径，与jwt_utils.py保持一致
    jwt_private_key_path = str(JWT_PRIVATE_KEY_PATH)
    jwt_public_key_path = str(JWT_PUBLIC_KEY_PATH)
    
    # 数据库配置 - 直接使用环境变量，不依赖settings.database对象
    DATABASE_URL = get_env('POSTGRES_URL', 'postgresql://stpuser:stppassword@localhost:5432/stpdb')
    POSTGRES_USER = get_env('POSTGRES_USER', 'stpuser')
    POSTGRES_PASSWORD = get_env('POSTGRES_PASSWORD', 'stppassword')
    POSTGRES_DB = get_env('POSTGRES_DB', 'stpdb')
    POSTGRES_HOST = get_env('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = get_env('POSTGRES_PORT', 5432, env_type=int)
    
    # 存储模式配置
    AUTH_STORAGE_MODE = settings.storage_mode
    QUESTION_STORAGE_MODE = get_env('QUESTION_STORAGE_MODE', 'POSTGRES')
    CHAT_STORAGE_MODE = get_env('CHAT_STORAGE_MODE', 'POSTGRES')
    GRAPH_STORAGE_MODE = get_env('GRAPH_STORAGE_MODE', 'NEO4J')
    
    # 环境配置
    ENVIRONMENT = get_env('ENVIRONMENT', 'development')  # 可选值: development, staging, production
    
    # Neo4j配置
    NEO4J_URI = get_env('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = get_env('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = get_env('NEO4J_PASSWORD', '123456789')
    
    # Redis配置
    REDIS_HOST = get_env('REDIS_HOST', 'localhost')
    REDIS_PORT = get_env('REDIS_PORT', 6379, env_type=int)
    REDIS_DB = get_env('REDIS_DB', 0, env_type=int)
    
    # RAG配置
    RAG_DIR = get_env('RAG_DIR', './rag')
    RAG_INDEX_NAME = get_env('RAG_INDEX_NAME', 'default_index')
    RAG_DEFAULT_TOP_K = get_env('RAG_DEFAULT_TOP_K', 5, env_type=int)
    RAG_CHUNK_SIZE = get_env('RAG_CHUNK_SIZE', 1000, env_type=int)
    RAG_CHUNK_OVERLAP = get_env('RAG_CHUNK_OVERLAP', 200, env_type=int)
    
    # 邮件配置
    SMTP_SERVER = get_env('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = get_env('SMTP_PORT', 587, env_type=int)
    SMTP_USERNAME = get_env('SMTP_USERNAME', '')
    SMTP_PASSWORD = get_env('SMTP_PASSWORD', '')
    SMTP_TLS = get_env('SMTP_TLS', True, env_type=bool)
    SMTP_SSL = get_env('SMTP_SSL', False, env_type=bool)
    
    # 其他配置
    DEBUG = get_env('DEBUG', False, env_type=bool)
    
    # 数据库连接配置
    db_user = POSTGRES_USER
    db_password = POSTGRES_PASSWORD
    db_host = POSTGRES_HOST
    db_port = POSTGRES_PORT
    db_name = POSTGRES_DB

# 创建兼容性配置实例
settings = ExtendedAuthSettings() 