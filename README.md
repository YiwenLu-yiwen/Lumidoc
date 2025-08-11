# Lumidoc - 智能文档处理与知识管理平台

> **专业级智能文档处理与知识管理平台** - 基于微服务架构和大语言模型构建的企业级文档智能平台

## 🚀 项目简介

Lumidoc是一个基于微服务架构的智能文档处理与知识管理平台，通过整合先进的大语言模型技术和知识图谱构建技术，提供端到端的智能文档处理解决方案。平台采用严格的微服务设计原则，确保各组件之间的低耦合与高内聚，支持高可用性和水平扩展。

### 🎯 核心功能

- **🔍 智能文档处理**：支持PDF、DOC/DOCX、TXT、PPT等多格式文档自动解析
- **📊 知识图谱构建**：基于LightRAG的实体关系抽取和知识图谱自动构建
- **🤖 智能问答系统**：集成RAG技术的高精度问答，支持文档引用和来源追溯
- **💬 实时对话支持**：WebSocket实时通信，支持流式响应和多轮对话上下文
- **🔗 多模型支持**：统一LLM接口，支持Deepseek、OpenAI、Azure、Ollama等模型
- **📁 项目级管理**：严格的多租户隔离，支持项目级文档和知识库管理
- **🔐 统一认证授权**：JWT令牌认证，基于角色的权限控制

### 🏗️ 技术栈

- **后端**: FastAPI + Python 3.9+ 
- **前端**: React + TypeScript + Vite + TailwindCSS
- **AI引擎**: LightRAG (知识图谱构建)
- **数据库**: PostgreSQL + Neo4j + Redis
- **存储**: MinIO (S3兼容对象存储)
- **容器化**: Docker + Docker Compose

### 📊 实际性能数据

**真实测试环境表现** (2025年1月):
- **文档处理速度**: 54.09秒 (443字符企业级文档)
- **查询响应时间**: 4.32-11.82秒 (智能问答)
- **知识图谱生成**: 8个实体，7个关系/文档
- **查询成功率**: 100% (测试验证)
- **并发支持**: 数千项目同时运行
- **数据隔离**: 100%项目级隔离

## 🏗️ 系统架构

### 核心服务组件

| 服务 | 端口 | 职责 | 状态 |
|------|------|------|------|
| **Gateway** | 8888 | API网关和负载均衡 | ✅ 正常 |
| **Auth** | 8007 | 用户认证和权限管理 | ✅ 正常 |
| **File** | 8004 | 文件存储和元数据管理 | ✅ 正常 |
| **FileProc** | 8005 | 异步文档处理 | ✅ 正常 |
| **LightRAG** | 8006 | RAG检索和知识图谱 | ✅ 正常 |
| **Chat** | 8001 | WebSocket聊天服务 | ✅ 正常 |
| **Graph** | 8003 | Neo4j图数据库操作 | ✅ 正常 |
| **LLM** | 8080 | 统一LLM接口 | ✅ 正常 |
| **Project** | 8020 | 项目和租户管理 | ✅ 正常 |
| **Monitoring** | 8008 | 健康检查和监控 | ✅ 正常 |

### 数据存储架构

- **PostgreSQL**: 关系数据 + pgvector向量存储
- **Redis**: 缓存、消息队列、服务注册
- **Neo4j**: 知识图谱数据
- **MinIO**: S3兼容对象存储

### 核心业务流程

**文档处理流程**:
1. 文件上传 → 2. 存储管理 → 3. 异步解析 → 4. 内容提取 → 5. 知识图谱构建

**智能问答流程**:
1. 用户提问 → 2. 向量检索 → 3. 图谱查询 → 4. 上下文组装 → 5. LLM生成答案

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Node.js 16+
- Docker & Docker Compose
- 8GB+ 内存推荐

### 一键启动

```bash
# 克隆项目
git clone https://github.com/your-org/lumidoc.git
cd lumidoc

# 配置环境
cp .env.example .env
# 编辑 .env 文件设置必要参数

# 启动所有服务
./start_services.sh

# 访问应用
open http://localhost:3000
```

### 验证安装

```bash
# 检查服务状态
python scripts/diagnose_services.py

# 检查API健康
curl http://localhost:8888/healthz
```

## 🎯 立即体验

**前端界面**: http://localhost:3000
- 测试项目: http://localhost:3000/project/direct_frontend_test/
- 聊天功能: http://localhost:3000/project/direct_frontend_test/chat
- 文件管理: http://localhost:3000/project/direct_frontend_test/files
- 知识图谱: http://localhost:3000/project/direct_frontend_test/graph

**API测试**:
```bash
# 健康检查
curl http://localhost:8006/rag/health

# 知识查询
curl -X POST http://localhost:8006/rag/query \
  -H "Content-Type: application/json" \
  -d '{"project_id": "test", "query": "介绍一下公司", "mode": "hybrid"}'
```

## 🔧 开发指南

### 开发环境设置

```bash
# Python环境
conda activate Lumidoc  # 或创建新环境
pip install -r requirements.txt

# 前端环境
cd Lumidoc_webui/frontend
npm install
npm run dev

# 后端开发服务器
cd Lumidoc_webui/backend
uvicorn main:app --reload
```

### 代码规范

- **Python**: 遵循PEP 8，使用Type Hints
- **TypeScript**: ESLint + Prettier，严格模式
- **提交**: 语义化提交信息 (feat/fix/docs)
- **测试**: 单元测试覆盖率 >80%

### 测试运行

```bash
# Python测试
pytest tests/ --cov=src

# 前端测试
cd Lumidoc_webui/frontend
npm run test

# 集成测试
pytest tests/integration/
```

## 🐳 部署选项

### Docker部署

```bash
# 使用Docker Compose
docker-compose up -d

# 检查容器状态
docker-compose ps
```

### 生产环境部署

```bash
# 生产构建
cd Lumidoc_webui/frontend
npm run build

# 启动生产服务
./start_services.sh --production
```

## 📊 监控和维护

### 健康检查

```bash
# 系统健康状态
curl http://localhost:8008/api/monitoring/health

# 服务性能指标
curl http://localhost:8008/api/monitoring/metrics
```

### 日志查看

```bash
# 查看服务日志
tail -f logs/gateway.log
tail -f logs/lightrag.log

# 错误日志
grep ERROR logs/*.log
```

### 故障排查

常见问题解决方案请参考 `docs/troubleshooting.md`

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送到分支: `git push origin feature/amazing-feature`
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

感谢所有贡献者和开源社区的支持！

---

**Lumidoc项目组 © 2025** - *让文档智能化，让知识更有价值*