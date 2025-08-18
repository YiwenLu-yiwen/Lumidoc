-- Lumidoc Intelligence 数据库初始化脚本 (UUID版本)
-- 此脚本为新部署创建完整的数据库结构，使用UUID作为项目主键

-- 安装必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================
-- 核心业务表
-- =====================================

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

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects (name);
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects (user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects (created_at);

-- =====================================
-- 项目关联表
-- =====================================

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

-- =====================================
-- RAG和向量存储表
-- =====================================

-- RAG向量表
CREATE TABLE IF NOT EXISTS rag_default_index_vectors (
    id SERIAL PRIMARY KEY,
    content_id TEXT NOT NULL,
    project_id UUID NOT NULL,
    embedding vector(1024),
    metadata JSONB,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RAG文档状态表
CREATE TABLE IF NOT EXISTS rag_default_index_document_status (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id UUID NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RAG文档内容表
CREATE TABLE IF NOT EXISTS rag_default_index_document_content (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id UUID NOT NULL,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RAG关系表
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

-- =====================================
-- 索引优化
-- =====================================

-- 项目文件表索引
CREATE INDEX IF NOT EXISTS idx_project_files_project_id ON project_files(project_id);
CREATE INDEX IF NOT EXISTS idx_project_files_status ON project_files(status);
CREATE INDEX IF NOT EXISTS idx_project_files_rag_status ON project_files(rag_status);
CREATE INDEX IF NOT EXISTS idx_project_files_is_in_rag ON project_files(is_in_rag);

-- 聊天消息表索引
CREATE INDEX IF NOT EXISTS idx_chat_messages_project_id ON chat_messages(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp);

-- RAG表索引
CREATE INDEX IF NOT EXISTS idx_rag_vectors_project_id ON rag_default_index_vectors(project_id);
CREATE INDEX IF NOT EXISTS idx_rag_vectors_content_id ON rag_default_index_vectors(content_id);
CREATE INDEX IF NOT EXISTS idx_rag_doc_status_project_id ON rag_default_index_document_status(project_id);
CREATE INDEX IF NOT EXISTS idx_rag_doc_content_project_id ON rag_default_index_document_content(project_id);
CREATE INDEX IF NOT EXISTS idx_rag_relationships_project_id ON rag_default_index_relationships(project_id);

-- 向量索引（在有数据后创建）
-- CREATE INDEX IF NOT EXISTS idx_rag_vectors_embedding ON rag_default_index_vectors 
-- USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =====================================
-- 数据完整性检查
-- =====================================

-- 验证UUID扩展已安装
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp') THEN
        RAISE EXCEPTION 'uuid-ossp extension is required but not installed';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'vector extension is required but not installed';
    END IF;
    
    RAISE NOTICE 'Database initialization completed successfully with UUID support';
END $$;