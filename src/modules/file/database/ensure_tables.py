"""
确保数据库表结构正确
"""

import logging
import asyncio
import os
from ..config.database import FileServiceDatabase

logger = logging.getLogger(__name__)

# 创建项目表
CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    user_id INTEGER,
    status TEXT DEFAULT 'active',
    project_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER
)
"""

# 创建项目合作者表
CREATE_PROJECT_COLLABORATORS_TABLE = """
CREATE TABLE IF NOT EXISTS project_collaborators (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, user_id)
)
"""

# 创建问题集表
CREATE_QUESTION_SETS_TABLE = """
CREATE TABLE IF NOT EXISTS question_sets (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER,
    metadata JSONB DEFAULT '{}'
)
"""

# 创建问题表
CREATE_QUESTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    set_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    answer TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by INTEGER,
    metadata JSONB DEFAULT '{}'
)
"""

# 创建聊天消息表
CREATE_CHAT_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    user_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
"""

# 创建项目文件表
CREATE_PROJECT_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS project_files (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    size BIGINT NOT NULL,
    type TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'pending',
    processing_task_id TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    -- RAG处理状态相关字段
    rag_status VARCHAR(20) DEFAULT 'pending',
    rag_processed_at TIMESTAMP,
    rag_error_message VARCHAR(500),
    is_in_rag BOOLEAN DEFAULT FALSE,
    UNIQUE(project_id, file_hash)
)
"""

# 创建文件内容表
CREATE_FILE_CONTENTS_TABLE = """
CREATE TABLE IF NOT EXISTS file_contents (
    file_hash TEXT PRIMARY KEY,
    markdown_content TEXT,
    metadata JSONB DEFAULT '{}',
    file_type TEXT NOT NULL,
    page_count INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    summary TEXT
)
"""

# 创建文件总结文档表
CREATE_LLM_SUMMARY_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS llm_summary_documents (
    id SERIAL PRIMARY KEY,
    file_hash TEXT NOT NULL REFERENCES file_contents(file_hash),
    summary TEXT NOT NULL,
    summary_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)
"""

# 创建任务表
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    task_metadata JSONB DEFAULT '{}'
)
"""

# 创建项目RAG文件关联表
CREATE_PROJECT_RAG_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS project_rag_files (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    selected_by INTEGER,
    status TEXT DEFAULT 'active',
    rag_metadata JSONB DEFAULT '{}',
    UNIQUE(project_id, file_hash)
)
"""

# 单独添加外键约束
ADD_PROJECT_RAG_FILES_FK = """
ALTER TABLE project_rag_files 
ADD CONSTRAINT fk_project_rag_files_project_file 
FOREIGN KEY (project_id, file_hash) 
REFERENCES project_files(project_id, file_hash) 
ON DELETE CASCADE
"""

# 创建索引
INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_project_files_file_hash ON project_files(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_project_files_status ON project_files(status)",
    "CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_file_contents_file_hash ON file_contents(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)",
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_project_id ON chat_messages(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_questions_set_id ON questions(set_id)",
    "CREATE INDEX IF NOT EXISTS idx_project_rag_files_project_id ON project_rag_files(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_project_rag_files_file_hash ON project_rag_files(file_hash)",
    "CREATE INDEX IF NOT EXISTS idx_project_rag_files_status ON project_rag_files(status)",
    # RAG状态字段索引
    "CREATE INDEX IF NOT EXISTS idx_project_files_rag_status ON project_files(rag_status)",
    "CREATE INDEX IF NOT EXISTS idx_project_files_is_in_rag ON project_files(is_in_rag)",
    "CREATE INDEX IF NOT EXISTS idx_project_files_project_rag ON project_files(project_id, rag_status)"
]

# 定义问题索引创建语句
CREATE_QUESTIONS_INDEX = "CREATE INDEX IF NOT EXISTS idx_questions_set_id ON questions(set_id)"

async def ensure_file_contents_table():
    """
    确保file_contents表存在，并有正确的结构
    """
    try:
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 检查表是否存在
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'file_contents'
                )
                """
            )
            
            if not exists:
                logger.info("file_contents表不存在，正在创建...")
                # 创建表
                await conn.execute(
                    """
                    CREATE TABLE file_contents (
                        file_hash TEXT PRIMARY KEY,
                        markdown_content TEXT,
                        metadata JSONB DEFAULT '{}',
                        file_type TEXT,
                        page_count INTEGER DEFAULT 0,
                        summary TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                    
                    CREATE INDEX idx_file_contents_hash ON file_contents(file_hash);
                    """
                )
                logger.info("file_contents表创建完成")
            else:
                # 检查是否需要添加字段
                columns = await conn.fetch(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'file_contents'
                    """
                )
                column_names = [row['column_name'] for row in columns]
                
                # 检查并添加必要的字段
                if 'summary' not in column_names:
                    logger.info("添加summary字段到file_contents表")
                    await conn.execute(
                        "ALTER TABLE file_contents ADD COLUMN summary TEXT"
                    )
                
                if 'metadata' not in column_names:
                    logger.info("添加metadata字段到file_contents表")
                    await conn.execute(
                        "ALTER TABLE file_contents ADD COLUMN metadata JSONB DEFAULT '{}'"
                    )
                
                logger.info("file_contents表结构已验证")
            
            # 确保project_files表结构完整
            await ensure_project_files_table_structure(conn)
            
            logger.info("所有数据库表结构验证完成")
    except Exception as e:
        logger.error(f"验证数据库表结构时出错: {str(e)}")
        raise

async def ensure_project_files_table_structure(conn):
    """
    确保project_files表具有完整的结构，包括所有必要的列
    """
    try:
        # 检查project_files表是否存在
        project_files_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'project_files'
            )
            """
        )
        
        if not project_files_exists:
            logger.info("project_files表不存在，正在创建完整表结构...")
            await conn.execute(CREATE_PROJECT_FILES_TABLE)
            logger.info("project_files表创建完成")
            return
            
        # 表存在，检查所有必要的列
        columns = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'project_files'
            ORDER BY ordinal_position
            """
        )
        column_names = [row['column_name'] for row in columns]
        
        logger.info(f"当前project_files表列: {', '.join(column_names)}")
        
        # 定义必要的列及其类型
        required_columns = {
            'id': 'SERIAL PRIMARY KEY',
            'project_id': 'INTEGER NOT NULL',
            'name': 'TEXT NOT NULL',
            'path': 'TEXT NOT NULL', 
            'size': 'BIGINT NOT NULL',
            'type': 'TEXT NOT NULL',
            'file_hash': 'TEXT NOT NULL',
            'file_metadata': 'JSONB DEFAULT \'{}\'',
            'created_at': 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'updated_at': 'TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'status': 'TEXT DEFAULT \'pending\'',
            'processing_task_id': 'TEXT',
            'processed_at': 'TIMESTAMP WITH TIME ZONE',
            # RAG处理状态相关字段
            'rag_status': 'VARCHAR(20) DEFAULT \'pending\'',
            'rag_processed_at': 'TIMESTAMP',
            'rag_error_message': 'VARCHAR(500)',
            'is_in_rag': 'BOOLEAN DEFAULT FALSE'
        }
        
        # 检查并添加缺失的列
        added_columns = []
        for col_name, col_definition in required_columns.items():
            if col_name not in column_names and col_name != 'id':  # id是主键，不能后添加
                logger.info(f"添加缺失列 {col_name} 到project_files表")
                try:
                    # 对于file_hash这样的关键列，需要特殊处理
                    if col_name == 'file_hash':
                        await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} TEXT")
                        # 为现有数据生成临时的file_hash值
                        await conn.execute("""
                            UPDATE project_files 
                            SET file_hash = 'legacy_' || id::text || '_' || extract(epoch from created_at)::text
                            WHERE file_hash IS NULL OR file_hash = ''
                        """)
                        # 然后设置NOT NULL约束
                        await conn.execute(f"ALTER TABLE project_files ALTER COLUMN {col_name} SET NOT NULL")
                    else:
                        # 对特殊列进行特殊处理
                        if col_name == 'status':
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} TEXT DEFAULT 'pending'")
                        elif col_name == 'processed_at':
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} TIMESTAMP WITH TIME ZONE")
                        elif col_name == 'file_metadata':
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} JSONB DEFAULT '{{}}'")
                        elif col_name == 'created_at':
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
                        elif col_name == 'updated_at':
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} TIMESTAMP WITH TIME ZONE DEFAULT NOW()")
                        else:
                            # 对于其他列，提取列定义
                            col_def_parts = col_definition.split(' ', 1)
                            if len(col_def_parts) > 1:
                                col_type_and_constraints = col_def_parts[1]
                            else:
                                col_type_and_constraints = 'TEXT'  # 默认类型
                            await conn.execute(f"ALTER TABLE project_files ADD COLUMN {col_name} {col_type_and_constraints}")
                    added_columns.append(col_name)
                except Exception as e:
                    logger.error(f"添加列 {col_name} 失败: {str(e)}")
                    # 对于关键列，如果添加失败，需要重新创建表
                    if col_name == 'file_hash':
                        logger.warning("file_hash列添加失败，需要重新创建project_files表")
                        await recreate_project_files_table(conn)
                        return
        
        if added_columns:
            logger.info(f"已添加列: {', '.join(added_columns)}")
        
        # 确保必要的索引存在
        await ensure_project_files_indices(conn)
        
        # 确保唯一约束存在
        await ensure_project_files_constraints(conn)
        
        logger.info("project_files表结构验证和修复完成")
        
    except Exception as e:
        logger.error(f"确保project_files表结构时出错: {str(e)}")
        raise

async def recreate_project_files_table(conn):
    """
    重新创建project_files表（作为最后的手段）
    """
    try:
        logger.warning("正在重新创建project_files表...")
        
        # 备份现有数据
        backup_data = await conn.fetch("SELECT * FROM project_files")
        logger.info(f"备份了 {len(backup_data)} 条记录")
        
        # 删除旧表
        await conn.execute("DROP TABLE IF EXISTS project_files CASCADE")
        
        # 创建新表
        await conn.execute(CREATE_PROJECT_FILES_TABLE)
        
        # 恢复数据，为缺失的file_hash生成值
        for row in backup_data:
            row_dict = dict(row)
            if 'file_hash' not in row_dict or not row_dict.get('file_hash'):
                # 生成一个基于ID和创建时间的hash值
                import hashlib
                hash_source = f"{row_dict.get('id', '')}_{row_dict.get('name', '')}_{row_dict.get('created_at', '')}"
                row_dict['file_hash'] = hashlib.md5(hash_source.encode()).hexdigest()
            
            # 插入数据
            columns = list(row_dict.keys())
            values = list(row_dict.values())
            placeholders = ', '.join(['$' + str(i+1) for i in range(len(values))])
            
            await conn.execute(
                f"INSERT INTO project_files ({', '.join(columns)}) VALUES ({placeholders})",
                *values
            )
        
        logger.info("project_files表重新创建完成，数据已恢复")
        
    except Exception as e:
        logger.error(f"重新创建project_files表失败: {str(e)}")
        raise

async def ensure_project_files_indices(conn):
    """
    确保project_files表和project_rag_files表的所有必要索引存在
    """
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_project_files_file_hash ON project_files(file_hash)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_status ON project_files(status)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_processing_task_id ON project_files(processing_task_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_rag_files_project_id ON project_rag_files(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_rag_files_file_hash ON project_rag_files(file_hash)",
        "CREATE INDEX IF NOT EXISTS idx_project_rag_files_status ON project_rag_files(status)",
        # RAG状态字段索引
        "CREATE INDEX IF NOT EXISTS idx_project_files_rag_status ON project_files(rag_status)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_is_in_rag ON project_files(is_in_rag)",
        "CREATE INDEX IF NOT EXISTS idx_project_files_project_rag ON project_files(project_id, rag_status)"
    ]
    
    for index_sql in indices:
        try:
            await conn.execute(index_sql)
        except Exception as e:
            logger.warning(f"创建索引失败: {index_sql}, 错误: {str(e)}")

async def ensure_project_files_constraints(conn):
    """
    确保project_files表的约束存在
    """
    try:
        # 检查UNIQUE约束是否存在
        constraint_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE table_name = 'project_files' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name LIKE '%project_id%file_hash%'
            )
        """)
        
        if not constraint_exists:
            logger.info("添加project_files表的UNIQUE约束...")
            try:
                await conn.execute(
                    "ALTER TABLE project_files ADD CONSTRAINT uk_project_files_project_id_file_hash UNIQUE (project_id, file_hash)"
                )
            except Exception as e:
                logger.warning(f"添加UNIQUE约束失败: {str(e)}")
                # 可能存在重复数据，先清理重复数据
                await conn.execute("""
                    DELETE FROM project_files 
                    WHERE id NOT IN (
                        SELECT MIN(id) FROM project_files 
                        GROUP BY project_id, file_hash
                    )
                """)
                # 再次尝试添加约束
                await conn.execute(
                    "ALTER TABLE project_files ADD CONSTRAINT uk_project_files_project_id_file_hash UNIQUE (project_id, file_hash)"
                )
                logger.info("清理重复数据后，UNIQUE约束添加成功")
                
    except Exception as e:
        logger.warning(f"确保约束时出错: {str(e)}")

async def ensure_projects_table():
    """
    确保projects表存在，并有正确的结构（包括user_id列）
    """
    try:
        pool = await FileServiceDatabase.get_pool()
        async with pool.acquire() as conn:
            # 检查表是否存在
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'projects'
                )
                """
            )
            
            if not exists:
                logger.info("projects表不存在，正在创建...")
                await conn.execute(CREATE_PROJECTS_TABLE)
                logger.info("projects表创建完成")
            else:
                # 检查并添加缺失的列
                columns = await conn.fetch(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'projects'
                    """
                )
                column_names = [row['column_name'] for row in columns]
                
                # 检查并添加user_id列
                if 'user_id' not in column_names:
                    logger.info("添加user_id字段到projects表")
                    await conn.execute(
                        "ALTER TABLE projects ADD COLUMN user_id INTEGER"
                    )
                
                # 检查并添加status列
                if 'status' not in column_names:
                    logger.info("添加status字段到projects表")
                    await conn.execute(
                        "ALTER TABLE projects ADD COLUMN status TEXT DEFAULT 'active'"
                    )
                
                logger.info("projects表结构已验证和修复")
            
            logger.info("projects表结构验证完成")
    except Exception as e:
        logger.error(f"验证projects表结构时出错: {str(e)}")
        raise

async def ensure_all_tables() -> bool:
    """
    确保所有必要的表都存在
    
    Returns:
        bool: 是否成功初始化表
    """
    try:
        logger.info("开始初始化数据库表")
        
        # 首先确保projects表结构正确
        await ensure_projects_table()
        
        # 使用类方法获取连接池
        pool = await FileServiceDatabase.get_pool()
        
        # 使用连接池执行SQL
        async with pool.acquire() as conn:
            # 创建项目表
            await conn.execute(CREATE_PROJECTS_TABLE)
            
            # 创建项目合作者表
            await conn.execute(CREATE_PROJECT_COLLABORATORS_TABLE)
            
            # 创建问题集表
            await conn.execute(CREATE_QUESTION_SETS_TABLE)
            
            # 创建问题表
            await conn.execute(CREATE_QUESTIONS_TABLE)
            
            # 创建聊天记录表
            await conn.execute(CREATE_CHAT_MESSAGES_TABLE)
            
            # 🔧 关键修复：先创建基础表并确保结构完整
            logger.info("创建项目文件表...")
            await conn.execute(CREATE_PROJECT_FILES_TABLE)
            
            # 🔧 立即验证和修复project_files表结构
            logger.info("验证project_files表结构...")
            await ensure_project_files_table_structure(conn)
            
            # 创建文件内容表
            await conn.execute(CREATE_FILE_CONTENTS_TABLE)
            
            # 创建LLM摘要文档表
            await conn.execute(CREATE_LLM_SUMMARY_DOCUMENTS_TABLE)
            
            # 创建任务表
            await conn.execute(CREATE_TASKS_TABLE)
            
            # 🔧 在创建外键约束表之前，再次确认file_hash列存在
            logger.info("验证外键引用列是否存在...")
            file_hash_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'project_files' AND column_name = 'file_hash'
                )
            """)
            
            if not file_hash_exists:
                logger.error("project_files表中file_hash列不存在，无法创建外键约束")
                raise Exception("file_hash列不存在，无法创建project_rag_files表")
            
            # 现在安全创建项目RAG文件关联表
            logger.info("创建项目RAG文件关联表...")
            try:
                await conn.execute(CREATE_PROJECT_RAG_FILES_TABLE)
                logger.info("project_rag_files表创建成功")
                
                # 检查外键约束是否已存在
                fk_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints 
                        WHERE constraint_name = 'fk_project_rag_files_project_file'
                        AND table_name = 'project_rag_files'
                    )
                """)
                
                if not fk_exists:
                    logger.info("添加project_rag_files表外键约束...")
                    try:
                        await conn.execute(ADD_PROJECT_RAG_FILES_FK)
                        logger.info("外键约束添加成功")
                    except Exception as fk_e:
                        logger.warning(f"添加外键约束失败: {str(fk_e)}")
                else:
                    logger.info("外键约束已存在，跳过")
                    
            except Exception as e:
                logger.error(f"创建project_rag_files表失败: {str(e)}")
                # 继续执行，但不创建相关索引
            
            try:
                # 创建问题索引
                await conn.execute(CREATE_QUESTIONS_INDEX)
            except Exception as e:
                logger.warning(f"创建索引失败: {CREATE_QUESTIONS_INDEX}, 错误: {str(e)}")
                
            # 创建所有其他索引，但先检查表是否存在
            for index_sql in INDICES:
                try:
                    # 检查索引涉及的表是否存在
                    if "project_rag_files" in index_sql:
                        # 检查project_rag_files表是否存在
                        table_exists = await conn.fetchval("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'project_rag_files'
                            )
                        """)
                        if not table_exists:
                            logger.warning(f"跳过索引创建（表不存在）: {index_sql}")
                            continue
                    
                    await conn.execute(index_sql)
                    logger.debug(f"索引创建成功: {index_sql}")
                except Exception as e:
                    logger.warning(f"创建索引失败: {index_sql}, 错误: {str(e)}")
            
            # 打印表列表
            tables = await conn.fetch("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
            table_names = [table['tablename'] for table in tables]
            logger.info(f"数据库中的表: {', '.join(table_names)}")
        
        # 🔧 最后确保所有表结构完整性
        logger.info("最终验证表结构...")
        await ensure_file_contents_table()
        logger.info("表结构验证和修复完成")
            
        logger.info("数据库表初始化完成")
        return True
    except Exception as e:
        logger.error(f"初始化数据库表失败: {str(e)}")
        return False

async def init_database():
    """初始化数据库表结构"""
    return await ensure_all_tables() 