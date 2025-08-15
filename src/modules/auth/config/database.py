import asyncpg
from typing import Optional
from .config import settings

class AuthDatabase:
    """认证模块数据库"""
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """获取数据库连接池"""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
                min_size=5,
                max_size=20
            )
            await cls._init_db()
        return cls._pool

    @classmethod
    async def _init_db(cls):
        """初始化数据库表"""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
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

    @classmethod
    async def close(cls):
        """关闭数据库连接池"""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None 