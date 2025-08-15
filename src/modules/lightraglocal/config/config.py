"""
LightRAG服务配置
使用统一配置系统
"""

import os
from pathlib import Path
from src.shared.config import RAGServiceSettings, get_env

# 创建全局设置实例
settings = RAGServiceSettings()

# 为了保持向后兼容性，提供与原有全局变量相同名称的变量
STORAGE_MODE = settings.storage_mode if hasattr(settings, 'storage_mode') else 'POSTGRES_NEO4J'
WORKING_DIR = settings.working_dir
LLM_MODEL_NAME = settings.llm_model_name if hasattr(settings, 'llm_model_name') else get_env('LLM_MODEL_NAME', 'gpt-3.5-turbo')
LLM_API_KEY = settings.llm_api_key if hasattr(settings, 'llm_api_key') else get_env('LLM_API_KEY', '')
LLM_API_URL = settings.llm_api_url if hasattr(settings, 'llm_api_url') else get_env('LLM_API_URL', '')
OLLAMA_EMBEDDING_URL = settings.ollama_embedding_url if hasattr(settings, 'ollama_embedding_url') else get_env('OLLAMA_EMBEDDING_URL', 'http://localhost:11434')
OLLAMA_EMBEDDING_MODEL = settings.ollama_embedding_model if hasattr(settings, 'ollama_embedding_model') else get_env('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')
DEFAULT_QUERY_MODE = settings.default_query_mode
DEFAULT_STREAM = settings.default_stream

# PostgreSQL配置 - 用于向量存储和KV存储
DATABASE_URL = settings.database_url if hasattr(settings, 'database_url') else get_env('POSTGRES_URL', 'postgresql://stpuser:stppassword@localhost:5432/stpdb')
POSTGRES_HOST = get_env('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(get_env('POSTGRES_PORT', '5432'))
POSTGRES_USER = get_env('POSTGRES_USER', 'stpuser')
POSTGRES_PASSWORD = get_env('POSTGRES_PASSWORD', 'stppassword')
POSTGRES_DATABASE = get_env('POSTGRES_DATABASE', 'stpdb')

# Neo4j配置 - 用于图存储
NEO4J_URI = settings.neo4j_uri if hasattr(settings, 'neo4j_uri') else get_env('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = settings.neo4j_user if hasattr(settings, 'neo4j_user') else get_env('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = settings.neo4j_password if hasattr(settings, 'neo4j_password') else get_env('NEO4J_PASSWORD', 'password')

LOCAL_STORAGE_DIR = settings.lightrag_local_storage_dir
SERVER_PORT = settings.port

# LightRAG存储配置
# 使用PostgreSQL作为KV存储、向量存储和文档状态存储
# 使用Neo4j作为图存储
LIGHTRAG_KV_STORAGE = "UnifiedPGKVStorage"
LIGHTRAG_VECTOR_STORAGE = "UnifiedPGVectorStorage" 
LIGHTRAG_GRAPH_STORAGE = "Neo4JStorage"
LIGHTRAG_DOC_STATUS_STORAGE = "PGDocStatusStorage"

# 为保持兼容性，提供config对象
class LightRAGConfig:
    storage_mode = STORAGE_MODE
    working_dir = WORKING_DIR
    llm_model_name = LLM_MODEL_NAME
    llm_api_key = LLM_API_KEY
    llm_api_url = LLM_API_URL
    ollama_embedding_url = OLLAMA_EMBEDDING_URL
    ollama_embedding_model = OLLAMA_EMBEDDING_MODEL
    default_query_mode = DEFAULT_QUERY_MODE
    default_stream = DEFAULT_STREAM
    database_url = DATABASE_URL
    postgres_host = POSTGRES_HOST
    postgres_port = POSTGRES_PORT
    postgres_user = POSTGRES_USER
    postgres_password = POSTGRES_PASSWORD
    postgres_database = POSTGRES_DATABASE
    neo4j_uri = NEO4J_URI
    neo4j_user = NEO4J_USER
    neo4j_password = NEO4J_PASSWORD
    local_storage_dir = LOCAL_STORAGE_DIR
    server_port = SERVER_PORT
    
    # LightRAG存储配置
    kv_storage = LIGHTRAG_KV_STORAGE
    vector_storage = LIGHTRAG_VECTOR_STORAGE
    graph_storage = LIGHTRAG_GRAPH_STORAGE
    doc_status_storage = LIGHTRAG_DOC_STATUS_STORAGE

# 全局配置实例
config = LightRAGConfig() 