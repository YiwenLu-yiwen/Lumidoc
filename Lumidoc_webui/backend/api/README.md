# API层统一化架构

本文档介绍了STP项目API层统一化的设计和使用方法。

## 架构概述

API层统一化实现了以下目标：

1. **统一请求处理**：所有微服务请求通过通用服务客户端处理
2. **类型安全**：使用Pydantic模型定义请求和响应类型
3. **前后端类型一致**：自动生成与后端一致的TypeScript类型定义
4. **错误处理标准化**：统一的错误处理和响应格式
5. **减少重复代码**：消除各路由文件中的重复代码

## 主要组件

### 1. 类型定义 (`types.py`)

使用Pydantic模型定义API请求和响应类型，包括：

- 通用响应模型 (`ApiResponse`)
- 错误响应模型 (`ErrorResponse`)
- 各领域模型（用户、聊天、项目等）

### 2. 服务客户端 (`services.py`)

提供统一的微服务请求处理，包括：

- 通用服务客户端基类 (`ServiceClient`)
- 各微服务的客户端实现
- 统一的错误处理和日志记录

### 3. 路由模块 (各 `*_routes.py` 文件)

使用服务客户端和类型定义实现API路由，包括：

- 基于Pydantic模型的请求验证
- 响应类型注解
- 简化的服务调用

### 4. 前端类型定义 (`api.ts`)

前端TypeScript类型定义，与后端保持一致，包括：

- 所有API模型的TypeScript接口
- 响应类型定义
- API客户端类型注解

## 如何使用

### 后端开发

1. **定义新的数据模型**：

   在 `types.py` 中添加新的Pydantic模型：

   ```python
   class NewFeatureRequest(BaseModel):
       name: str
       value: int
   
   class NewFeatureResponse(BaseModel):
       id: str
       name: str
       value: int
       created_at: datetime
   ```

2. **添加服务调用**：

   如果需要新的微服务客户端，在 `services.py` 中添加：

   ```python
   class NewFeatureServiceClient(ServiceClient):
       def __init__(self):
           super().__init__(settings.new_feature_service_url)
   
   new_feature_service = NewFeatureServiceClient()
   ```

3. **实现路由处理函数**：

   ```python
   @router.post("/new-feature", response_model=NewFeatureResponse)
   async def create_new_feature(
       request: NewFeatureRequest,
       user=Depends(get_current_user)
   ):
       """创建新功能"""
       result = await new_feature_service.post(
           "/api/features",
           json_data=request.dict()
       )
       return NewFeatureResponse(**result)
   ```

### 前端开发

1. **使用生成的类型定义**：

   ```typescript
   import { NewFeatureRequest, NewFeatureResponse } from '../types/api';
   
   const createFeature = async (feature: NewFeatureRequest): Promise<NewFeatureResponse> => {
     const response = await apiClient.post<NewFeatureResponse>('/new-feature', feature);
     return response.data;
   };
   ```

2. **类型自动补全和检查**：

   TypeScript开发环境会提供自动补全和类型检查功能。

## 自动生成类型定义

使用 `utils/generate_types.py` 脚本可以从FastAPI应用自动生成OpenAPI文档和TypeScript类型：

```bash
python Lumidoc_webui/backend/utils/generate_types.py
```

这将在 `Lumidoc_webui/frontend/src/types` 目录下生成 `openapi.json` 和 `api-schema.ts` 文件。

## 建议和最佳实践

1. **使用响应模型**：始终在路由函数上使用 `response_model` 参数
2. **保持类型同步**：修改后端模型后，更新前端类型定义
3. **使用通用响应格式**：对于成功/失败的操作，使用 `ApiResponse` 
4. **记录API文档**：使用FastAPI的文档字符串功能记录API用途和参数 