-- 安装pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建RAG向量表（如果不存在）
CREATE TABLE IF NOT EXISTS rag_default_index_vectors (
    id SERIAL PRIMARY KEY,
    content_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
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

-- 创建RAG文档状态表
CREATE TABLE IF NOT EXISTS rag_default_index_document_status (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档状态表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_project_id_idx ON rag_default_index_document_status(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_document_id_idx ON rag_default_index_document_status(document_id);

-- 创建RAG文档内容表
CREATE TABLE IF NOT EXISTS rag_default_index_document_content (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档内容表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_project_id_idx ON rag_default_index_document_content(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_document_id_idx ON rag_default_index_document_content(document_id);

-- 创建RAG关系表
CREATE TABLE IF NOT EXISTS rag_default_index_relationships (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    project_id TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relation_type, project_id)
);

-- 为关系表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_project_id_idx ON rag_default_index_relationships(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_source_id_idx ON rag_default_index_relationships(source_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_target_id_idx ON rag_default_index_relationships(target_id); 