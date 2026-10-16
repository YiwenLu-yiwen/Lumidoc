import logging
from sqlalchemy import create_engine, inspect, MetaData, Table, Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(project_root))

# 导入模型
from src.modules.chat.models import ChatHistory
from src.database import Base
from src.shared.logger import initialize_logging, get_logger

# 配置日志
initialize_logging("chat_models_migration")
logger = get_logger(__name__)

def get_database_url():
    """获取数据库连接URL"""
    # 尝试从配置中获取
    try:
        from src.modules.config import settings
        return settings.database_url
    except (ImportError, AttributeError):
        # 从环境变量或默认值获取
        pg_user = os.environ.get("POSTGRES_USER", "postgres")
        pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        pg_host = os.environ.get("POSTGRES_HOST", "localhost")
        pg_port = os.environ.get("POSTGRES_PORT", "5432")
        pg_db = os.environ.get("POSTGRES_DB", "lumidoc")

        # 优先使用POSTGRES_URL环境变量（如果存在）
        if os.environ.get("POSTGRES_URL"):
            return os.environ.get("POSTGRES_URL")

        return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"

def create_tables():
    """创建必要的数据库表"""
    database_url = get_database_url()

    # 创建引擎和会话
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 检查表是否存在
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # 检查chat_history表是否存在
    if "chat_history" not in tables:
        logger.info("chat_history表不存在，创建中...")

        # 创建表
        metadata = MetaData()
        chat_history = Table(
            "chat_history",
            metadata,
            Column("id", String, primary_key=True, index=True),
            Column("project_id", String, ForeignKey("projects.id", ondelete="CASCADE"), index=True),
            Column("user_id", String, index=True),
            Column("role", String, nullable=False),
            Column("content", String, nullable=False),
            Column("timestamp", DateTime, nullable=False, index=True),
            Column("meta_data", JSON, nullable=True)
        )

        metadata.create_all(engine, tables=[chat_history])
        logger.info("chat_history表创建成功")
    else:
        logger.info("chat_history表已存在")

    # 关闭连接
    engine.dispose()

if __name__ == "__main__":
    logger.info("开始创建数据库表...")
    create_tables()
    logger.info("数据库表创建完成")
