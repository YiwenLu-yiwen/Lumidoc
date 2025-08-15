from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from src.core.project_orm import Base
import os
from dotenv import load_dotenv

load_dotenv()

# 默认数据库配置
DEFAULT_CONFIG = {
    'user': 'stpuser',
    'password': 'stppassword',
    'host': 'localhost',
    'port': '5432',
    'database': 'stpdb'
}

# 从环境变量获取数据库配置，如果没有则使用默认值
DB_USER = os.getenv("POSTGRES_USER", DEFAULT_CONFIG['user'])
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", DEFAULT_CONFIG['password'])
DB_HOST = os.getenv("POSTGRES_HOST", DEFAULT_CONFIG['host'])
DB_PORT = os.getenv("POSTGRES_PORT", DEFAULT_CONFIG['port'])
DB_NAME = os.getenv("POSTGRES_DB", DEFAULT_CONFIG['database'])

# 构建数据库URL
SQLALCHEMY_DATABASE_URL = os.getenv(
    "POSTGRES_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'stpuser')}:{os.getenv('POSTGRES_PASSWORD', 'stppassword')}@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'stpdb')}"
)

# 添加连接池配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# 创建所有表
def init_db():
    # 检查数据库是否为空
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    if not existing_tables:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建完成！")
    else:
        print("✅ 数据库表已存在，无需创建")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 