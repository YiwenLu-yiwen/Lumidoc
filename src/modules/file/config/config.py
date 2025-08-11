"""
文件处理服务配置
使用统一配置系统
"""

from pathlib import Path
from src.shared.config import FileServiceSettings, get_env

# 创建全局设置实例
settings = FileServiceSettings()

# 数据库连接属性
db_host = get_env("POSTGRES_HOST", "localhost")
db_port = get_env("POSTGRES_PORT", 5432, env_type=int)
db_name = get_env("POSTGRES_DB", "stpdb")
db_user = get_env("POSTGRES_USER", "stpuser")
db_password = get_env("POSTGRES_PASSWORD", "stppassword")

# 配置使用方法示例
"""
# 服务基本配置
port = settings.port
debug = settings.debug

# 存储配置
storage_type = settings.storage_type
storage_dir = settings.storage_dir
models_dir = settings.models_dir

# 数据库访问
if settings.database:
    db_url = settings.database.connection_string
"""

# 额外的辅助方法，保持与旧版本兼容
def get_db_url() -> str:
    """获取数据库连接URL"""
    if not settings.database:
        # 从环境变量构建连接字符串
        db_host = get_env("POSTGRES_HOST", "localhost")
        db_port = get_env("POSTGRES_PORT", 5432, env_type=int)
        db_name = get_env("POSTGRES_DB", "stpdb")
        db_user = get_env("POSTGRES_USER", "stpuser")
        db_password = get_env("POSTGRES_PASSWORD", "stppassword")
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return settings.database.connection_string

def get_absolute_storage_dir() -> Path:
    """获取绝对存储目录路径"""
    path = Path(settings.storage_dir)
    if path.is_absolute():
        return path
    # 相对于项目根目录
    return Path.cwd() / settings.storage_dir

def get_absolute_models_dir() -> Path:
    """获取绝对模型目录路径"""
    path = Path(settings.models_dir)
    if path.is_absolute():
        return path
    # 相对于项目根目录
    return Path.cwd() / settings.models_dir

def get_redis_url() -> str:
    """获取Redis连接URL"""
    redis_host = get_env("REDIS_HOST", "localhost")
    redis_port = get_env("REDIS_PORT", 6379, env_type=int)
    redis_db = get_env("REDIS_DB", 0, env_type=int)
    redis_password = get_env("REDIS_PASSWORD", "")
    
    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}" 