# 统一LLM服务

统一LLM服务是STP项目的核心模块，提供各种LLM处理能力，包括文本生成、聊天、摘要、问答等功能。该服务替代了原有的llm_summary和llm_chat服务，实现了功能整合与代码优化。

## 架构设计

本服务遵循STP项目微服务架构原则，采用了以下设计：

1. **分层架构**
   - API层：处理HTTP请求和响应
   - 服务层：实现核心业务逻辑
   - 共享基础层：基于src/shared/llm的底层能力

2. **配置管理**
   - 使用`src/shared/config/service_settings.py`中的`llm_settings`进行统一配置管理
   - 服务特定配置保留在服务内部

3. **接口兼容**
   - 提供向后兼容的API，以平滑过渡

## 功能概述

- **文本生成**：提供通用文本生成能力
- **聊天生成**：支持多轮对话的聊天生成
- **摘要生成**：从长文本中提取关键信息生成摘要
- **问答处理**：根据上下文回答问题
- **JSON任务处理**：解析返回JSON格式的任务结果

所有功能均支持同步和异步调用方式，部分功能支持流式响应。

## API接口

### 文本生成

```
POST /api/v1/llm/generate
```

请求体示例：

```json
{
  "prompt": "讲一个关于人工智能的故事",
  "temperature": 0.7,
  "max_tokens": 500,
  "stream": false
}
```

### 聊天生成

```
POST /api/v1/llm/chat
```

请求体示例：

```json
{
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手"},
    {"role": "user", "content": "介绍一下你自己"}
  ],
  "temperature": 0.7,
  "max_tokens": 500,
  "stream": false
}
```

### 摘要生成

```
POST /api/v1/llm/summary
```

请求体示例：

```json
{
  "content": "需要摘要的长文本内容...",
  "temperature": 0.3,
  "max_tokens": 200
}
```

### 问答处理

```
POST /api/v1/llm/question
```

请求体示例：

```json
{
  "question": "什么是人工智能?",
  "context": "人工智能是计算机科学的一个领域...",
  "temperature": 0.5,
  "max_tokens": 300
}
```

## 兼容说明

为保持向后兼容，服务提供了与旧版本`llm_summary`和`llm_chat`服务兼容的接口：

```
POST /api/v1/llm/legacy/summary
```

## 项目结构

```
src/
├── modules/
│   └── llm/                    # 统一LLM服务
│       ├── api/                # API层
│       │   ├── endpoints.py    # API入口
│       │   └── models.py       # 请求响应模型
│       ├── config/             # 服务配置
│       │   └── config.py       # 配置定义
│       ├── routes/             # 路由定义
│       │   └── router.py       # API路由
│       ├── services/           # 服务实现
│       │   └── llm_service.py  # 核心服务逻辑
│       ├── Dockerfile          # 容器定义
│       ├── README.md           # 服务文档
│       ├── __init__.py         # 模块初始化
│       └── main.py             # 服务入口
└── shared/
    ├── config/                 # 共享配置 
    │   └── service_settings.py # 包含LLM统一配置
    └── llm/                    # LLM共享库
        ├── adapters/           # 模型适配器
        └── langchain.py        # 框架集成
```

## 部署指南

### 环境变量

| 变量名 | 说明 | 默认值 |
|-------|------|--------|
| SERVICE_NAME | 服务名称 | llm-service |
| PORT | 服务端口 | 8080 |
| LLM_MODEL_TYPE | LLM模型类型 | ollama |
| LLM_MODEL_NAME | LLM模型名称 | qwen3:1.7b |
| LLM_API_KEY | API密钥 | - |
| LLM_TEMPERATURE | 温度参数 | 0.2 |
| LLM_MAX_TOKENS | 最大生成令牌数 | 2000 |

### Docker部署

```bash
# 构建镜像
docker build -t stp/llm-service -f src/modules/llm/Dockerfile .

# 运行容器
docker run -p 8080:8080 -e LLM_API_KEY=your_api_key stp/llm-service
```

### 本地运行

```bash
# 使用start_services.sh启动
./start_services.sh

# 手动启动
python -m src.modules.llm.main
```

## 与其他服务的关系

本服务替代了原有的`llm_summary`和`llm_chat`服务，其他服务需相应更新调用方式：

1. 文件服务(file)现在应调用llm服务的摘要API
2. 聊天服务(chat)现在应调用llm服务的聊天API
3. 问题服务(question)现在应调用llm服务的问答API

## 许可证

STP项目内部使用 