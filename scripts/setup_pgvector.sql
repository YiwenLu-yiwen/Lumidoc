-- Lumidoc Intelligence 数据库初始化脚本
-- 安装必要的扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================
-- 核心业务表 (UUID系统)
-- =====================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    nickname TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 项目表 (使用UUID主键)
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    description TEXT,
    user_id INTEGER NOT NULL,
    status TEXT DEFAULT 'active',
    project_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    
    -- 添加唯一约束确保用户不能创建重名项目
    CONSTRAINT unique_user_project_name UNIQUE (user_id, name)
);

-- 项目协作者表
CREATE TABLE IF NOT EXISTS project_collaborators (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    
    CONSTRAINT unique_project_collaborator UNIQUE (project_id, user_id)
);

-- 项目文件表
CREATE TABLE IF NOT EXISTS project_files (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    display_name TEXT,
    content_type TEXT,
    size BIGINT,
    status TEXT DEFAULT 'uploaded',
    metadata TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    
    -- RAG处理状态相关字段
    rag_status VARCHAR(20) DEFAULT 'pending',
    rag_processed_at TIMESTAMP,
    rag_error_message VARCHAR(500),
    is_in_rag BOOLEAN DEFAULT FALSE
);

-- 聊天消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    role VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- 项目索引优化
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects (name);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects (user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects (created_at);

-- 关联表索引
CREATE INDEX IF NOT EXISTS idx_project_collaborators_project_id ON project_collaborators(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_status ON project_files(status);
CREATE INDEX IF NOT EXISTS idx_project_files_rag_status ON project_files(rag_status);
CREATE INDEX IF NOT EXISTS idx_chat_messages_project_id ON chat_messages(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);

-- 创建RAG向量表（如果不存在） - 支持UUID项目ID
CREATE TABLE IF NOT EXISTS rag_default_index_vectors (
    id SERIAL PRIMARY KEY,
    content_id TEXT NOT NULL,
    project_id UUID NOT NULL,
    embedding vector(1024),
    metadata JSONB,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为向量创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_vectors_project_id_idx ON rag_default_index_vectors(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_vectors_content_id_idx ON rag_default_index_vectors(content_id);

-- 创建向量索引（使用IVFFlat索引类型，适合大规模数据集）
-- 注意：这需要向量数据才能创建，因此在实际使用中可能需要在插入数据后再创建
-- CREATE INDEX IF NOT EXISTS rag_default_index_vectors_embedding_idx ON rag_default_index_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 创建RAG文档状态表 - 支持UUID项目ID
CREATE TABLE IF NOT EXISTS rag_default_index_document_status (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id UUID NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档状态表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_project_id_idx ON rag_default_index_document_status(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_document_id_idx ON rag_default_index_document_status(document_id);

-- 创建RAG文档内容表 - 支持UUID项目ID
CREATE TABLE IF NOT EXISTS rag_default_index_document_content (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id UUID NOT NULL,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档内容表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_project_id_idx ON rag_default_index_document_content(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_document_id_idx ON rag_default_index_document_content(document_id);

-- 创建RAG关系表 - 支持UUID项目ID
CREATE TABLE IF NOT EXISTS rag_default_index_relationships (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    project_id UUID NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relation_type, project_id)
);

-- 为关系表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_project_id_idx ON rag_default_index_relationships(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_source_id_idx ON rag_default_index_relationships(source_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_target_id_idx ON rag_default_index_relationships(target_id); 