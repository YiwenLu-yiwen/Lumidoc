import asyncpg
from typing import Optional
import os

class Database:
    """统一数据库管理"""
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """获取数据库连接池"""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 5432)),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres'),
                database=os.getenv('DB_NAME', 'stp'),
                min_size=10,  # 最小连接数
                max_size=100,  # 最大连接数
                max_queries=50000,  # 每个连接最大查询数
                max_inactive_connection_lifetime=300,  # 不活跃连接最大存活时间
                command_timeout=60,  # 命令超时时间
                statement_timeout=60,  # SQL语句超时时间
                timeout=30,  # 连接超时时间
                connection_class=asyncpg.Connection
            )
            await cls._init_db()
        return cls._pool

    @classmethod
    async def _init_db(cls):
        """初始化数据库表"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            # 创建用户表
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_superuser BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建文件处理表
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    id SERIAL PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    instance_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                CREATE INDEX IF NOT EXISTS idx_processed_files_status ON processed_files(status);
                CREATE INDEX IF NOT EXISTS idx_processed_files_instance_id ON processed_files(instance_id);
            ''')

    @classmethod
    async def close(cls):
        """关闭数据库连接池"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None 