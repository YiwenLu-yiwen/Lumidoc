# Lumidoc Web界面

Lumidoc Web界面是Lumidoc项目的前端和API网关部分，提供了友好的用户界面和统一的API访问入口。

## 项目结构

```
Lumidoc_webui/
├── frontend/             # 前端应用（React + TypeScript + Vite）
│   ├── src/              # 源代码
│   │   ├── api/          # API客户端和请求处理
│   │   │   ├── client.ts      # 通用API客户端
│   │   │   ├── auth.ts        # 认证API
│   │   │   ├── file.ts        # 文件处理API
│   │   │   ├── rag.ts         # RAG查询API
│   │   │   └── ...
│   │   ├── components/   # 可复用UI组件
│   │   ├── features/     # 功能模块组件
│   │   │   ├── auth/     # 用户认证相关组件
│   │   │   ├── files/    # 文件管理相关组件
│   │   │   ├── rag/      # RAG功能相关组件
│   │   │   └── ...
│   │   ├── context/      # React上下文
│   │   ├── types/        # TypeScript类型定义
│   │   └── lib/          # 实用工具函数
│   └── public/           # 静态资源文件
│
└── backend/              # 后端API网关
    ├── api/              # API路由定义
    │   ├── auth_routes.py    # 用户认证路由
    │   ├── file_routes.py    # 文件处理路由
    │   ├── rag_routes.py     # RAG查询路由
    │   ├── services.py       # 服务客户端
    │   └── ...
    ├── utils/            # 工具函数
    └── main.py           # 应用入口点
```

## 技术栈

### 前端
- React 18
- TypeScript
- Vite
- React Router
- TailwindCSS
- React Query

### 后端
- FastAPI
- Pydantic
- Python 3.10+
- OAuth2 认证

## 开发指南

### 前端开发

1. 安装依赖

```bash
cd Lumidoc_webui/frontend
npm install
```

2. 启动开发服务器

```bash
npm run dev
```

3. 构建生产版本

```bash
npm run build
```

### API开发

1. 在 `backend/api` 目录中创建新的路由文件

2. 使用 `services.py` 中的服务客户端转发请求到微服务

3. 在 `main.py` 中注册新的路由

4. 使用 `types.py` 定义请求和响应模型

## API层统一化架构

Lumidoc Web界面采用统一的API架构，使前后端保持一致的类型定义和请求处理逻辑。详细信息请参考：
[API统一化架构文档](./backend/api/README.md)

## 本地开发

1. 启动所有微服务（或使用Docker Compose）

```bash
docker-compose up -d
```

2. 启动后端API网关

```bash
cd Lumidoc_webui/backend
uvicorn main:app --reload --port 8000
```

3. 启动前端开发服务器

```bash
cd Lumidoc_webui/frontend
npm run dev
```

4. 访问应用

打开浏览器访问 `http://localhost:3000` 