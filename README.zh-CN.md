# Lumidoc

[English](./README.md) | 语言: **简体中文**

Lumidoc 是一个模块化的智能文档平台，围绕 RAG、知识图谱与多服务处理构建。平台支持文件接入、语义检索、文档对话、问答流程以及服务级可观测能力。

## 功能特性

- 面向文件、对话、图谱、认证、RAG、监控等模块的微服务架构
- 支持本地存储与 S3/MinIO 对象存储
- 集成 PostgreSQL（`pgvector`）、Redis、Neo4j
- 全部运行时均使用 Docker，包括本地对话模型与嵌入模型
- `src/modules` 下可扩展的模块化目录结构

## 仓库结构

```text
.
├── src/                    # 后端核心模块与共享库
├── frontend/               # 前端应用
├── scripts/                # 安装、诊断与运维脚本
├── docs/                   # 架构与分析文档
├── docker-compose.yml      # 容器化部署入口
├── start_services.sh       # 跨平台一键 Docker 启动
└── stop_services.sh        # 跨平台一键 Docker 关闭
```

## 快速开始

### 1. 环境依赖

- 支持 Docker Compose 的 Docker 环境

### 2. 配置环境变量

```bash
cp .env.example .env
```

按需修改 `.env`。默认模型运行时为 CPU 兼容的 Ollama 容器，不依赖宿主机模型
服务或硬件专用运行时。

### 3. 启动服务

```bash
./start_services.sh
```

该脚本会校验 Compose 配置、构建全部应用模块、启动完整服务、准备所需模型，
并等待健康检查完成。所有支持 Docker 的宿主机均使用同一份脚本。

### 4. 停止服务

```bash
./stop_services.sh
```

关闭会移除容器与 Compose 网络，但保留数据库、对象存储和模型数据卷。

## 模块文档

- 后端模块总览：[src/README.md](./src/README.md)
- 脚本使用说明：[scripts/README.md](./scripts/README.md)
- 前端说明：[frontend/README.md](./frontend/README.md)

## 说明

- 请将敏感配置保存在 `.env`，不要提交私密凭据。
- 不要在宿主机单独启动模块；受支持的运行方式是 Docker Compose。
