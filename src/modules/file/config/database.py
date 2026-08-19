import asyncpg
import logging
from typing import Optional, Dict, Any, List
from .config import settings, db_host, db_port, db_name, db_user, db_password

logger = logging.getLogger(__name__)

class FileServiceDatabase:
    """文件服务模块数据库"""
    _pool: Optional[asyncpg.Pool] = None

    def __init__(self):
        """初始化数据库对象"""
        self._initialized = False
    
    async def initialize(self) -> bool:
        """初始化数据库连接，用于健康检查"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                # 简单查询以验证连接是否正常
                result = await conn.fetchval("SELECT 1")
                self._initialized = (result == 1)
                return self._initialized
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"数据库连接初始化失败: {str(e)}")
            return False
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """获取数据库连接池，作为类方法，如果不存在则创建"""
        if cls._pool is None:
            try:
                # 创建一个数据库连接池
                dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
                cls._pool = await asyncpg.create_pool(dsn=dsn)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"无法创建数据库连接池: {str(e)}")
                raise
        return cls._pool
    
    async def close(self):
        """关闭数据库连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            
    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """执行SQL语句"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
            
    async def fetch(self, query: str, *args, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """执行查询并返回结果集"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args, timeout=timeout)
            return [dict(row) for row in rows]
            
    async def fetchrow(self, query: str, *args, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """执行查询并返回单行结果"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args, timeout=timeout)
            return dict(row) if row else None

    @classmethod
    async def _init_db(cls):
        """初始化数据库表 - 使用统一的数据库表创建系统"""
        # 按照Lumidoc项目原则，使用统一的数据库管理系统
        from ..database.ensure_tables import ensure_all_tables
        
        logger.info("使用统一数据库管理系统初始化表结构...")
        success = await ensure_all_tables()
        
        if not success:
            logger.error("数据库表初始化失败")
            raise Exception("数据库表初始化失败")
        
        logger.info("数据库表初始化完成 - 使用完整表结构（包含RAG字段）")
    
    @classmethod
    async def save_file_content(cls, file_hash: str, markdown_content: str, 
                               metadata: Dict[str, Any], file_type: str, 
                               page_count: int = 0) -> bool:
        """
        保存文件内容到内容存储表
        
        Args:
            file_hash: 文件哈希值
            markdown_content: Markdown内容
            metadata: 元数据
            file_type: 文件类型
            page_count: 页数
            
        Returns:
            bool: 是否成功保存
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            # 先检查内容是否已存在
            content_exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM file_contents WHERE file_hash = $1)',
                file_hash
            )
            
            # 如果已存在，则不需要再次保存
            if content_exists:
                return True
                
            # 保存新内容
            result = await conn.execute('''
                INSERT INTO file_contents 
                (file_hash, markdown_content, metadata, file_type, page_count)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (file_hash) DO NOTHING
            ''', file_hash, markdown_content, metadata, file_type, page_count)
            
            return 'INSERT' in result
    
    @classmethod
    async def link_file_to_project(cls, project_id: str, file_hash: str, 
                                 original_filename: str, status: str = 'completed') -> int:
        """
        将文件链接到项目
        
        Args:
            project_id: 项目ID
            file_hash: 文件哈希值
            original_filename: 原始文件名
            status: 处理状态
            
        Returns:
            int: 关联记录ID
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            # 关联文件到项目
            return await conn.fetchval('''
                INSERT INTO project_files 
                (project_id, file_hash, original_filename, status, updated_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (project_id, file_hash) 
                DO UPDATE SET
                    original_filename = $3,
                    status = $4,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            ''', project_id, file_hash, original_filename, status)
    
    @classmethod
    async def get_file_content(cls, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        获取文件内容
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            Dict[str, Any]: 文件内容记录
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow('''
                SELECT * FROM file_contents
                WHERE file_hash = $1
            ''', file_hash)
            
            if record:
                return dict(record)
            return None
    
    @classmethod
    async def get_project_file(cls, project_id: str, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        获取项目文件信息和内容
        
        Args:
            project_id: 项目ID
            file_hash: 文件哈希值
            
        Returns:
            Dict[str, Any]: 完整的文件信息和内容
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            # 联合查询获取文件信息和内容
            record = await conn.fetchrow('''
                SELECT p.id, p.project_id, p.file_hash, p.original_filename, 
                       p.status, p.created_at, p.updated_at,
                       c.markdown_content, c.metadata, c.file_type, c.page_count
                FROM project_files p
                JOIN file_contents c ON p.file_hash = c.file_hash
                WHERE p.project_id = $1 AND p.file_hash = $2
            ''', project_id, file_hash)
            
            if record:
                return dict(record)
            return None
    
    @classmethod
    async def list_project_files(cls, project_id: str) -> List[Dict[str, Any]]:
        """
        列出项目的所有文件
        
        Args:
            project_id: 项目ID
            
        Returns:
            List[Dict[str, Any]]: 文件列表
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch('''
                SELECT p.id, p.file_hash, p.original_filename, p.status, 
                       p.created_at, p.updated_at, c.file_type, c.page_count
                FROM project_files p
                JOIN file_contents c ON p.file_hash = c.file_hash
                WHERE p.project_id = $1
                ORDER BY p.updated_at DESC
            ''', project_id)
            
            return [dict(record) for record in records]
    
    @classmethod
    async def count_file_references(cls, file_hash: str) -> int:
        """
        计算文件被引用的次数
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            int: 引用次数
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval('''
                SELECT COUNT(*) FROM project_files
                WHERE file_hash = $1
            ''', file_hash)
    
    @classmethod
    async def delete_project_file_link(cls, project_id: str, file_hash: str) -> bool:
        """
        删除项目与文件的关联
        
        Args:
            project_id: 项目ID
            file_hash: 文件哈希值
            
        Returns:
            bool: 是否删除成功
        """
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            # 开始事务
            async with conn.transaction():
                # 1. 删除项目文件链接
                result = await conn.execute('''
                    DELETE FROM project_files
                    WHERE project_id = $1 AND file_hash = $2
                ''', project_id, file_hash)
                
                # 2. 检查文件是否还有其他引用
                ref_count = await cls.count_file_references(file_hash)
                
                # 3. 如果没有其他引用，可以选择性地删除文件内容
                if ref_count == 0 and settings.clean_unused_files:
                    await conn.execute('''
                        DELETE FROM file_contents
                        WHERE file_hash = $1
                    ''', file_hash)
                    
            return 'DELETE' in result 