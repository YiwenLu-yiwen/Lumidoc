# LightRAG集成说明

## 概述

本模块已经根据真实的LightRAG源代码进行了完整的重构和修复，现在支持：

1. **正确的存储后端配置**：PostgreSQL用于向量存储和KV存储，Neo4j用于图存储
2. **用户文件选择功能**：用户可以选择特定文件进入LightRAG处理
3. **完整的RAG流程**：文档上传 → Docling处理 → 用户选择 → LightRAG处理 → 存储到PostgreSQL和Neo4j

## 主要修复内容

### 1. 存储配置修复

**修复前**：使用本地文件存储，没有正确配置数据库
**修复后**：
- KV存储：`PGKVStorage` (PostgreSQL)
- 向量存储：`PGVectorStorage` (PostgreSQL) 
- 图存储：`Neo4JStorage` (Neo4j)
- 文档状态存储：`PGDocStatusStorage` (PostgreSQL)

### 2. LightRAG服务重构

**主要改进**：
- 使用真实的LightRAG库而不是自定义实现
- 正确配置存储后端
- 实现项目隔离（通过namespace_prefix）
- 支持异步操作
- 集成Lumidoc项目的LLM服务

### 3. 新增API接口

#### 文件选择接口
```http
POST /api/rag/projects/{project_id}/files/select
Content-Type: application/json

{
    "file_ids": ["file1", "file2", "file3"]
}
```

#### 知识图谱接口
```http
GET /api/rag/projects/{project_id}/knowledge-graph?node_label=*&max_depth=3&max_nodes=1000
```

#### 查询接口
```http
POST /api/rag/projects/{project_id}/query
Content-Type: application/json

{
    "query": "什么是人工智能？",
    "mode": "hybrid"
}
```

#### 文档管理接口
```http
GET /api/rag/projects/{project_id}/documents
DELETE /api/rag/projects/{project_id}/documents
```

## 使用流程

### 1. 环境配置

确保以下环境变量已正确设置：

```bash
# PostgreSQL配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DATABASE=lumidoc

# Neo4j配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<set-in-deployment-environment>

# LightRAG配置
CHUNK_SIZE=1200
CHUNK_OVERLAP_SIZE=100
```

### 2. 启动服务

```bash
# 启动PostgreSQL (Docker)
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=lumidoc \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# 启动Neo4j (Docker)  
docker run -d --name neo4j \
  -e NEO4J_AUTH=neo4j/password \
  -p 7474:7474 -p 7687:7687 \
  neo4j:latest

# 启动LightRAG服务
cd src/modules/lightraglocal
python main.py
```

### 3. 测试功能

```bash
# 运行测试脚本
python src/modules/lightraglocal/test_lightrag.py
```

### 4. 完整工作流程

1. **文件上传**：用户通过文件服务上传文档
2. **Docling处理**：文件处理服务使用Docling提取文本内容
3. **文件选择**：用户通过前端选择要进入LightRAG的文件
4. **LightRAG处理**：
   - 文档分块（chunking）
   - 实体和关系提取
   - 向量化存储到PostgreSQL
   - 图谱存储到Neo4j
5. **查询和检索**：用户可以进行智能问答和知识图谱查询

## 数据存储结构

### PostgreSQL表结构

- `LIGHTRAG_DOC_FULL`：完整文档内容
- `LIGHTRAG_DOC_CHUNKS`：文档分块
- `LIGHTRAG_VDB_ENTITY`：实体向量
- `LIGHTRAG_VDB_RELATION`：关系向量
- `LIGHTRAG_VDB_CHUNKS`：分块向量
- `LIGHTRAG_DOC_STATUS`：文档处理状态

### Neo4j图结构

- 节点：实体（Entity）
- 边：关系（Relationship）
- 属性：实体类型、描述、关键词等

## 性能优化

1. **批量处理**：支持批量插入文档
2. **异步操作**：所有数据库操作都是异步的
3. **连接池**：使用数据库连接池提高性能
4. **索引优化**：在关键字段上创建索引
5. **分块策略**：可配置的文档分块大小和重叠

## 故障排除

### 常见问题

1. **LightRAG导入失败**
   - 检查LightRAG源代码路径是否正确
   - 确保所有依赖包已安装

2. **数据库连接失败**
   - 检查PostgreSQL和Neo4j服务是否启动
   - 验证连接配置是否正确

3. **嵌入向量生成失败**
   - 检查LLM服务是否可用
   - 系统会自动回退到本地TF-IDF方法

4. **查询无结果**
   - 确认文档已正确插入
   - 检查查询模式设置

### 日志调试

查看日志文件：
```bash
tail -f src/logs/lightrag_local.log
```

## 技术架构

```
用户界面
    ↓
文件服务 (上传)
    ↓  
文件处理服务 (Docling)
    ↓
LightRAG服务 (本模块)
    ↓
┌─────────────────┬─────────────────┐
│   PostgreSQL    │     Neo4j       │
│  (向量+KV存储)   │   (图存储)      │
└─────────────────┴─────────────────┘
```

## 扩展性

- 支持多项目隔离
- 支持水平扩展
- 支持自定义嵌入模型
- 支持自定义LLM模型
- 支持插件化存储后端
