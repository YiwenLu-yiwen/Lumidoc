"""
聊天模块数据库迁移工具，用于创建和更新数据库表
"""

import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.modules.chat.config.config import settings
from src.modules.chat.models.chat_history import Base, ChatHistory

logger = logging.getLogger(__name__)

def create_database_engine():
    """创建数据库引擎"""
    connection_string = settings.postgres_url
    logger.info(f"创建数据库连接: {connection_string}")
    return create_engine(connection_string)

def check_table_exists(engine, table_name):
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def create_tables(engine):
    """创建所有表"""
    try:
        Base.metadata.create_all(engine)
        logger.info("成功创建表结构")
    except Exception as e:
        logger.error(f"创建表时出错: {str(e)}")
        raise

def rename_metadata_column():
    """将metadata字段重命名为meta_data（如有需要）"""
    engine = create_database_engine()
    
    # 检查metadata列是否存在（如果存在则需要重命名）
    inspector = inspect(engine)
    if 'chat_history' in inspector.get_table_names():
        columns = [column['name'] for column in inspector.get_columns('chat_history')]
        
        if 'metadata' in columns and 'meta_data' not in columns:
            logger.info("检测到metadata列，将重命名为meta_data以避免与SQLAlchemy关键字冲突")
            
            try:
                # 执行重命名操作
                with engine.connect() as connection:
                    connection.execute("ALTER TABLE chat_history RENAME COLUMN metadata TO meta_data")
                logger.info("成功将metadata列重命名为meta_data")
            except Exception as e:
                logger.error(f"重命名metadata列时出错: {str(e)}")
                # 继续执行，不中断流程
    
def run_migrations():
    """运行所有迁移操作"""
    try:
        # 创建数据库引擎
        engine = create_database_engine()
        
        # 检查chat_history表是否存在
        if not check_table_exists(engine, 'chat_history'):
            logger.info("聊天历史表不存在，正在创建...")
            create_tables(engine)
        else:
            logger.info("聊天历史表已存在")
            
            # 检查并修复metadata列名问题
            rename_metadata_column()
            
        logger.info("数据库迁移完成")
        
        # 返回会话工厂，允许调用者创建会话
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
    except Exception as e:
        logger.error(f"执行数据库迁移时出错: {str(e)}")
        raise

if __name__ == "__main__":
    # 配置日志
    from src.shared.logger import initialize_logging, get_logger
    initialize_logging("chat_db_migration")
    logger = get_logger(__name__)
    
    # 运行迁移
    run_migrations()
    
    print("数据库迁移完成") 