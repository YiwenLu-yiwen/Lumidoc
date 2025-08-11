# 微服务客户端库

本目录包含STP项目中各个微服务的客户端实现，用于服务间通信。

## 客户端列表

### LLMServiceClient

位于`llm_service_client.py`，提供对LLM服务的高级访问，支持以下特性：

- **双模式运行**：支持本地模式和远程模式，可自动切换
- **高级功能**：提供摘要、品牌信息处理、知识框架分析等高级功能
- **错误处理**：内置完善的错误处理和重试机制
- **超时控制**：支持所有操作的超时控制

适用场景：需要高级LLM功能的微服务，如问答系统、知识提取等。

```python
from src.shared.clients import default_llm_client

# 使用默认客户端
summary = await default_llm_client.process_summary("需要摘要的文本内容")

# 或者创建新实例
from src.shared.clients import LLMServiceClient
client = LLMServiceClient()
result = await client.process_brand_info("品牌相关文本")
```

### LightRAGServiceClient

位于`lightrag_client.py`，提供对LightRAG服务的访问，支持以下特性：

- **文档检索**：支持语义搜索、混合搜索等多种检索模式
- **知识库管理**：支持文档添加、删除等操作
- **双模式运行**：支持本地模式和远程模式
- **错误处理**：内置完善的错误处理和日志记录

适用场景：需要文档检索、知识库访问的微服务。

```python
from src.shared.clients import default_lightrag_client

# 搜索文档
docs = await default_lightrag_client.search(
    project_id="project-123",
    query="查询文本",
    top_k=5
)

# 添加文档
result = await default_lightrag_client.add_documents(
    project_id="project-123",
    document_list=[{"id": "doc1", "text": "文档内容", "metadata": {"source": "file.pdf"}}]
)
```

## 与其他客户端的区别

### 与src/shared/llm/client.py的区别

`src/shared/llm/client.py`中的`LLMClient`是一个更轻量级的客户端，主要用于直接调用LLM API，如生成文本、聊天等。它是`src/shared/llm`包的一部分，专注于LLM模型的直接访问。

而`src/shared/clients/llm_service_client.py`中的`LLMServiceClient`则是一个更高级的客户端，提供了更多业务逻辑相关的功能，如摘要生成、品牌信息处理等。

两者的使用场景不同：
- 需要直接访问LLM API的场景使用`LLMClient`
- 需要高级LLM功能的场景使用`LLMServiceClient` 