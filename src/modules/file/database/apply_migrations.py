"""
应用SQL迁移脚本
"""
import asyncio
import logging
import os
from pathlib import Path
from ..config.database import FileServiceDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def apply_migration(file_path: str):
    """应用单个SQL迁移文件"""
    try:
        # 读取SQL文件内容
        with open(file_path, 'r') as f:
            sql = f.read()
        
        if not sql.strip():
            logger.warning(f"迁移文件为空: {file_path}")
            return
        
        # 连接数据库并执行SQL
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 开始事务
            async with conn.transaction():
                logger.info(f"执行迁移: {os.path.basename(file_path)}")
                await conn.execute(sql)
                logger.info(f"迁移成功: {os.path.basename(file_path)}")
        
        await pool.close()
    except Exception as e:
        logger.error(f"迁移失败 {file_path}: {str(e)}")
        raise

async def apply_all_migrations():
    """应用所有SQL迁移文件"""
    # 获取迁移文件目录
    migrations_dir = Path(__file__).parent.parent / "migrations"
    if not migrations_dir.exists():
        logger.error(f"迁移目录不存在: {migrations_dir}")
        return
    
    # 获取所有SQL文件
    migration_files = sorted([str(f) for f in migrations_dir.glob("*.sql")])
    if not migration_files:
        logger.info("没有找到迁移文件")
        return
    
    logger.info(f"找到 {len(migration_files)} 个迁移文件")
    
    # 应用每个迁移文件
    for file_path in migration_files:
        await apply_migration(file_path)

async def apply_specific_migration(migration_name: str):
    """应用指定的迁移文件"""
    # 获取迁移文件目录
    migrations_dir = Path(__file__).parent.parent / "migrations"
    file_path = migrations_dir / migration_name
    
    if not file_path.exists():
        logger.error(f"迁移文件不存在: {file_path}")
        return
    
    await apply_migration(str(file_path))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 应用指定的迁移文件
        migration_name = sys.argv[1]
        asyncio.run(apply_specific_migration(migration_name))
    else:
        # 应用所有迁移文件
        asyncio.run(apply_all_migrations()) 