# LightRAG 企业级服务

企业级 LightRAG 服务是 Lumidoc 项目的核心 RAG (检索增强生成) 组件，提供完全项目隔离的文档处理、知识图谱构建与智能问答功能。

## 🚀 企业级特性

### 完全项目隔离
- **独立工作区**: 每个项目拥有完全独立的存储目录
- **数据安全**: 项目间数据完全隔离，无交叉污染
- **并发支持**: 支持数千个项目同时运行
- **自动清理**: 支持项目级别的数据清理和管理

### 高性能架构
- **异步处理**: 全异步架构，支持高并发
- **智能缓存**: LLM响应缓存，避免重复计算
- **批量处理**: 支持批量文档插入和处理
- **流式响应**: 支持流式查询响应

## 📊 当前配置

### LLM 模型配置
- **语言模型**: qwen2.5:3b
- **嵌入模型**: bge-m3:latest  
- **向量维度**: 2048
- **最大令牌**: 4000
- **最大并发**: 2

### 存储配置
- **存储目录**: `./rag_storage`
- **项目格式**: `project_{project_id}/project_{project_id}/`
- **数据文件**: entities, relationships, chunks, cache

## 🏗️ 架构设计

### 企业级服务架构
```
EnterpriseLightRAGService
├── 项目隔离管理
│   ├── 独立工作目录
│   ├── 项目级锁机制
│   └── 实例池管理
├── LightRAG 集成
│   ├── LightRAG 核心引擎
│   ├── 知识图谱构建
│   └── 向量检索
└── 外部服务集成
    ├── LLM 服务客户端
    ├── 嵌入服务
    └── 服务发现注册
```

### 数据流程
```
文档输入 → 内容分析 → 实体抽取 → 关系构建 → 向量存储 → 索引构建
     ↓              ↓          ↓          ↓          ↓          ↓
知识查询 ← 结果生成 ← 关系检索 ← 实体匹配 ← 向量检索 ← 查询解析
```

## 🔧 核心组件

### 1. 企业级服务 (enterprise_lightrag_service.py)

**主要功能**:
- 项目级别的完全隔离
- LightRAG 实例生命周期管理
- 异步文档插入和查询
- 项目统计和健康检查

**核心方法**:
```python
# 文档插入
await service.insert_document(
    project_id="your_project",
    content="文档内容",
    metadata={"source": "来源"}
)

# 知识查询
result = await service.query_project(
    project_id="your_project", 
    query="查询内容",
    mode="hybrid"
)

# 项目统计
stats = service.get_project_stats("your_project")
```

### 2. 企业级路由 (enterprise_rag_routes.py)

**API 端点**:
- `POST /rag/insert` - 文档插入
- `POST /rag/query` - 知识查询  
- `GET /rag/files/{project_id}` - 文件列表
- `GET /rag/status/{project_id}` - 项目状态
- `POST /rag/build/{project_id}` - 索引构建
- `GET /rag/health` - 健康检查

## 🎯 使用示例

### 基本文档处理

```python
from src.modules.lightraglocal.services.enterprise_lightrag_service import get_enterprise_lightrag_service

# 获取服务实例
service = await get_enterprise_lightrag_service()

# 插入企业文档
result = await service.insert_document(
    project_id="enterprise_project",
    content="""
    科技公司InnovateAI专注于人工智能解决方案。
    公司由CEO张伟和CTO李娜共同领导。
    主要产品包括AIAssistant智能助手和DataAnalyzer数据分析平台。
    """,
    metadata={
        "document_type": "company_profile",
        "department": "marketing",
        "version": "1.0"
    }
)

print(f"文档插入{'成功' if result['success'] else '失败'}")
print(f"处理耗时: {result['duration_seconds']:.2f}秒")
```

### 智能知识查询

```python
# 多种查询模式
queries = [
    ("naive", "InnovateAI的CEO是谁？"),
    ("local", "公司的主要产品有哪些？"), 
    ("global", "请介绍一下这家公司的整体情况"),
    ("hybrid", "分析公司的技术团队结构")
]

for mode, query in queries:
    result = await service.query_project(
        project_id="enterprise_project",
        query=query,
        mode=mode
    )
    
    if result["success"]:
        print(f"[{mode}模式] {query}")
        print(f"答案: {result['result']}")
        print(f"耗时: {result['duration_seconds']:.2f}秒\n")
```

### 项目管理

```python
# 获取项目统计
stats = service.get_project_stats("enterprise_project")
print(f"项目存在: {stats['exists']}")
print(f"存储目录: {stats['directory']}")
print(f"文件数量: {stats['file_count']}")

# 获取服务统计
service_stats = service.get_service_stats()
print(f"总项目数: {service_stats['total_projects']}")
print(f"活跃实例: {service_stats['active_instances']}")
```

## 🔧 API 使用

### RESTful API 调用

```bash
# 健康检查
curl http://localhost:8006/rag/health

# 插入文档
curl -X POST http://localhost:8006/rag/insert \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test_project",
    "content": "这是测试文档内容",
    "metadata": {"source": "test"}
  }'

# 查询知识
curl -X POST http://localhost:8006/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test_project", 
    "query": "测试查询",
    "mode": "hybrid"
  }'

# 获取项目文件
curl http://localhost:8006/rag/files/test_project

# 获取项目状态
curl http://localhost:8006/rag/status/test_project
```

## 🌐 前端集成

### 支持的前端功能
- **文档管理**: 上传、列表、状态查询
- **知识图谱**: 实体和关系可视化
- **智能问答**: 多模式查询支持
- **项目管理**: 项目统计和监控

### 前端访问地址
- **主页**: http://localhost:3000
- **项目页**: http://localhost:3000/project/{project_id}/
- **图谱页**: http://localhost:3000/project/{project_id}/graph
- **知识库**: http://localhost:3000/project/{project_id}/rag
- **聊天页**: http://localhost:3000/project/{project_id}/chat

## ⚙️ 配置参数

### 环境变量配置 (.env)

```bash
# LLM 模型配置
LLM_MODEL_NAME=qwen2.5:3b
OLLAMA_EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=2048
LLM_MAX_TOKENS=4000
MAX_ASYNC=2

# 服务配置
LIGHTRAG_HOST=0.0.0.0
LIGHTRAG_PORT=8006
RAG_STORAGE_DIR=./rag_storage

# LLM 服务配置
LLM_SERVICE_URL=http://localhost:8080
LLM_SERVICE_TIMEOUT=120
GATEWAY_URL=http://localhost:8888

# 服务发现配置
REDIS_URL=redis://localhost:6379/0
SERVICE_DISCOVERY_ENABLED=true
```

## 🔍 监控和诊断

### 健康检查响应
```json
{
  "status": "healthy",
  "service": "EnterpriseLightRAGService", 
  "lightrag_available": true,
  "query_param_available": true,
  "base_storage_dir": "./rag_storage",
  "storage_dir_exists": true,
  "active_projects": 3,
  "timestamp": "2025-07-26T00:22:00",
  "storage_writable": true
}
```

### 项目状态响应
```json
{
  "success": true,
  "project_id": "test_project",
  "statuses": {
    "vdb_entities.json": {"status": "ready", "count": 8},
    "vdb_relationships.json": {"status": "ready", "count": 7}, 
    "vdb_chunks.json": {"status": "ready", "count": 1}
  },
  "overall_status": "ready",
  "message": "项目就绪: 8个实体, 7个关系, 1个文档块",
  "stats": {
    "entities_count": 8,
    "relationships_count": 7,
    "chunks_count": 1
  }
}
```

## 🚀 性能指标

### 实际性能数据
- **文档处理**: ~54秒 (443字符企业级文档)
- **查询响应**: 4-12秒 (根据复杂度)
- **并发支持**: 支持数千项目
- **内存占用**: 约90MB (运行时)

### 优化建议
- 大文档建议分块处理
- 频繁查询项目建议保持实例活跃
- 定期清理不用项目释放资源

## 🔒 安全与权限

### 项目隔离
- 每个项目独立存储目录
- 项目间数据完全隔离
- 支持项目级别访问控制

### 数据安全
- 敏感数据不写入日志
- 支持存储加密 (可配置)
- API 认证支持 (通过网关)

## 📞 故障排除

### 常见问题

**Q: 服务启动失败**
A: 检查 LightRAG 库是否正确安装，确认端口8006未被占用

**Q: 查询响应慢**  
A: 检查 LLM 服务是否正常，考虑调整 MAX_ASYNC 参数

**Q: 项目数据丢失**
A: 检查 `./rag_storage` 目录权限，确认存储目录可写

**Q: 内存占用过高**
A: 定期清理不活跃项目，考虑增加服务器内存

### 日志查看
```bash
# 服务日志
tail -f logs/lightrag.log

# 实时监控
curl http://localhost:8006/rag/health | jq .
```

## 🔄 升级说明

### 从旧版本升级
本版本是完全重写的企业级架构，与旧版本不兼容。

**主要变更**:
- 删除了复杂的 workspace_manager 系统
- 移除了 neo4j_project_isolation 依赖
- 简化为直接的项目目录隔离
- 统一使用 enterprise_lightrag_service

**迁移建议**:
- 新项目直接使用企业级服务
- 旧数据需要重新导入处理
- 更新所有 API 调用代码

## 📧 支持联系

如需技术支持或报告问题:
- 查看日志文件: `logs/lightrag.log`
- 检查健康状态: `curl http://localhost:8006/rag/health`
- 项目文档: 参考 FINAL_FRONTEND_TEST_REPORT.md