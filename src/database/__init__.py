"""
统一的数据库配置模块
"""
import os
import logging
import time
import threading
from sqlalchemy import create_engine, inspect, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import DisconnectionError
from dotenv import load_dotenv
from pathlib import Path
import importlib

# 配置日志
logger = logging.getLogger(__name__)

# 默认数据库配置
DEFAULT_DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': '',
    'database': 'lumidoc'
}

# 创建基础模型类
Base = declarative_base()

# 数据库连接池配置
DB_POOL_CONFIG = {
    'pool_size': int(os.environ.get('DB_POOL_SIZE', '5')),
    'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '10')),
    'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
    'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '1800')),
    'pool_pre_ping': True,  # 连接前检查连接有效性
    'connect_args': {
        'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '10'))
    }
}

# 重连配置
DB_RECONNECT_ATTEMPTS = int(os.environ.get('DB_RECONNECT_ATTEMPTS', '3'))
DB_RECONNECT_DELAY = int(os.environ.get('DB_RECONNECT_DELAY', '5'))

# 数据库连接状态
class DBConnectionState:
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    
# 全局变量
engine = None
SessionLocal = None
connection_state = DBConnectionState.INITIALIZING
connection_error = None
initialization_lock = threading.Lock()
_initialized = False

# 连接监听钩子函数
def add_engine_event_listeners(engine):
    """添加数据库连接事件监听器"""
    @event.listens_for(engine, "connect")
    def connect(dbapi_connection, connection_record):
        """连接建立时回调"""
        global connection_state
        connection_state = DBConnectionState.CONNECTED
        logger.debug("数据库连接已建立")
    
    @event.listens_for(engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy):
        """连接检出时回调，检查连接是否有效"""
        global connection_state
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SELECT 1")
        except Exception:
            connection_state = DBConnectionState.ERROR
            # 传播异常以便连接池可以丢弃这个连接
            raise DisconnectionError("数据库连接无效")
        finally:
            cursor.close()
    
    @event.listens_for(engine, "invalidate")
    def invalidate(dbapi_connection, connection_record, exception):
        """连接无效时回调"""
        global connection_state, connection_error
        connection_state = DBConnectionState.DISCONNECTED
        connection_error = exception
        logger.warning(f"数据库连接已失效: {str(exception)}")

# 数据库连接URL
def get_database_url():
    # 尝试加载环境变量
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"已从 {env_path} 加载环境变量")
    
    # 检查POSTGRES_URL环境变量（优先使用）
    postgres_url = os.getenv('POSTGRES_URL')
    if postgres_url:
        logger.info("使用POSTGRES_URL环境变量")
        return postgres_url
    
    # 获取数据库配置
    db_config = {
        'host': os.getenv('POSTGRES_HOST') or DEFAULT_DB_CONFIG['host'],
        'port': os.getenv('POSTGRES_PORT') or DEFAULT_DB_CONFIG['port'],
        'user': os.getenv('POSTGRES_USER') or DEFAULT_DB_CONFIG['user'],
        'password': os.getenv('POSTGRES_PASSWORD') or DEFAULT_DB_CONFIG['password'],
        'database': os.getenv('POSTGRES_DB') or DEFAULT_DB_CONFIG['database']
    }
    
    if not db_config['password']:
        raise RuntimeError("POSTGRES_PASSWORD is required")

    url = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
    logger.info("使用组合配置生成数据库URL")
    return url

def create_db_engine(url: str):
    """创建数据库引擎"""
    try:
        new_engine = create_engine(
            url,
            pool_size=DB_POOL_CONFIG['pool_size'],
            max_overflow=DB_POOL_CONFIG['max_overflow'],
            pool_timeout=DB_POOL_CONFIG['pool_timeout'],
            pool_recycle=DB_POOL_CONFIG['pool_recycle'],
            pool_pre_ping=DB_POOL_CONFIG['pool_pre_ping'],
            connect_args=DB_POOL_CONFIG['connect_args']
        )
        
        # 添加连接事件监听
        add_engine_event_listeners(new_engine)
        
        return new_engine
    except Exception as e:
        logger.error(f"创建数据库引擎失败: {str(e)}")
        raise

# 加载所有模型模块，确保它们都注册到Base中
def _load_models():
    """加载所有模型模块，确保它们被正确注册到Base"""
    logger.info("正在加载数据库模型...")
    
    # 确保modules目录下的子目录有__init__.py文件
    _ensure_init_files()
    
    # 导入模型模块
    _import_model('src.modules.project.models.project')
    _import_model('src.modules.project.models.project_file')
    _import_model('src.modules.auth.models.user')
    _import_model('src.modules.question.models.question')
    _import_model('src.modules.chat.models.chat_history')
    _import_model('src.modules.chat.models.chat_message')
    
    logger.info("数据库模型加载完成")

def _ensure_init_files():
    """确保所有模块目录都有__init__.py文件以便正确导入"""
    project_root = Path(__file__).resolve().parent.parent
    modules_dir = project_root / "modules"
    
    if not modules_dir.exists() or not modules_dir.is_dir():
        return
    
    # 遍历所有模块目录
    for module_dir in modules_dir.iterdir():
        if not module_dir.is_dir() or module_dir.name.startswith('__'):
            continue
            
        # 确保模块根目录有__init__.py
        init_file = module_dir / "__init__.py"
        if not init_file.exists():
            logger.info(f"创建模块初始化文件: {init_file}")
            init_file.touch()
            
        # 检查models目录
        models_dir = module_dir / "models"
        if models_dir.exists() and models_dir.is_dir():
            models_init = models_dir / "__init__.py"
            if not models_init.exists():
                logger.info(f"创建模型初始化文件: {models_init}")
                models_init.touch()

def _import_model(module_path):
    """安全导入模块，避免因单个模块导入失败而中断整个过程"""
    try:
        importlib.import_module(module_path)
        logger.debug(f"已导入模型模块: {module_path}")
        return True
    except ImportError as e:
        logger.warning(f"无法导入模型模块 {module_path}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"导入模型模块 {module_path} 时出错: {str(e)}")
        return False

def check_database_exists(engine_url):
    """检查数据库是否存在，不存在则创建"""
    try:
        # 分解URL，获取数据库名称
        db_parts = engine_url.split("/")
        db_name = db_parts[-1].split("?")[0]
        
        # 创建不指定数据库的连接URL
        default_url = "/".join(db_parts[:-1]) + "/postgres"
        
        # 尝试连接默认数据库
        temp_engine = create_engine(default_url)
        
        with temp_engine.connect() as conn:
            # 检查数据库是否存在 - 修复：使用text()函数包装SQL语句
            result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname=:db_name"), {"db_name": db_name})
            exists = result.scalar() == 1
            
            if not exists:
                logger.info(f"数据库 {db_name} 不存在，开始创建...")
                # 创建数据库 (需要在事务外执行) - 修复：使用text()函数
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(f"CREATE DATABASE {db_name}"))
                logger.info(f"数据库 {db_name} 创建成功")
                return True
            else:
                logger.info(f"数据库 {db_name} 已存在")
                return True
    except Exception as e:
        logger.error(f"检查或创建数据库失败: {str(e)}")
        return False

def init_db():
    """初始化数据库，确保所有表都存在"""
    global engine, SessionLocal, connection_state, connection_error, _initialized, initialization_lock
    
    # 使用锁防止多线程同时初始化
    with initialization_lock:
        if _initialized:
            return True
            
        try:
            # 获取数据库URL
            db_url = get_database_url()
            
            # 检查并创建数据库（如果不存在）
            if not check_database_exists(db_url):
                logger.error("无法确保数据库存在，初始化失败")
                connection_state = DBConnectionState.ERROR
                return False
            
            # 创建引擎
            engine = create_db_engine(db_url)
            
            # 创建会话工厂
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            
            # 加载所有模型
            _load_models()
            
            # 创建表
            logger.info("开始创建数据库表...")
            Base.metadata.create_all(bind=engine)
            
            # 检查已创建的表
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            logger.info(f"数据库中的表: {', '.join(tables)}")
            
            connection_state = DBConnectionState.CONNECTED
            _initialized = True
            logger.info("数据库初始化成功")
            return True
        except Exception as e:
            connection_state = DBConnectionState.ERROR
            connection_error = str(e)
            logger.error(f"数据库初始化失败: {str(e)}")
            return False

def get_db():
    """获取数据库会话的上下文管理器，用于依赖注入"""
    if not _initialized:
        init_db()
        
    if not SessionLocal:
        raise RuntimeError("数据库未初始化")
        
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db():
    """获取异步数据库会话（通过异步包装同步会话）"""
    if not _initialized:
        init_db()
        
    if not SessionLocal:
        raise RuntimeError("数据库未初始化")
        
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def reconnect():
    """尝试重新连接数据库"""
    global engine, SessionLocal, connection_state, _initialized
    
    if connection_state == DBConnectionState.CONNECTED:
        return True
    
    logger.info("尝试重新连接数据库...")
    
    # 重置状态
    _initialized = False
    
    # 关闭现有连接
    if engine:
        engine.dispose()
    
    # 重新初始化
    return init_db()

def ensure_connection(max_attempts=DB_RECONNECT_ATTEMPTS, delay=DB_RECONNECT_DELAY):
    """确保数据库连接可用，如果不可用则尝试重连"""
    global connection_state
    
    if connection_state == DBConnectionState.CONNECTED:
        return True
        
    attempt = 0
    while attempt < max_attempts:
        logger.info(f"尝试连接数据库 (第{attempt+1}次)")
        if reconnect():
            return True
        
        attempt += 1
        if attempt < max_attempts:
            logger.info(f"等待{delay}秒后重试...")
            time.sleep(delay)
    
    logger.error(f"在{max_attempts}次尝试后仍无法连接数据库")
    return False

def get_connection_status():
    """获取数据库连接状态信息"""
    return {
        "state": connection_state,
        "error": connection_error,
        "pool": {
            "size": DB_POOL_CONFIG['pool_size'],
            "overflow": DB_POOL_CONFIG['max_overflow'],
            "timeout": DB_POOL_CONFIG['pool_timeout'],
            "recycle": DB_POOL_CONFIG['pool_recycle'],
        },
        "url": get_database_url().split('@')[-1]  # 不包含密码的URL部分
    }

# 尝试初始化
try:
    init_db()
except Exception as e:
    logger.error(f"数据库初始模块加载时出错: {str(e)}")
    connection_state = DBConnectionState.ERROR
    connection_error = str(e)

# 尝试初始化
try:
    init_db()
except Exception as e:
    logger.error(f"数据库初始模块加载时出错: {str(e)}")
    connection_state = DBConnectionState.ERROR
    connection_error = str(e)
