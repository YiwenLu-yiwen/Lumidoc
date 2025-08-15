# 共享组件目录 (shared)

## 概述

`shared` 目录包含Lumidoc项目中跨多个微服务复用的共享组件、工具和接口定义。这些组件遵循"一次定义，多处使用"的原则，确保系统各部分保持一致性和互操作性。

## 设计原则

1. **单一数据源**: 每个概念或功能只定义一次，避免重复和不一致
2. **接口稳定性**: 共享接口变更谨慎，确保向后兼容
3. **最小依赖**: 共享组件之间尽量减少相互依赖
4. **轻量设计**: 保持组件轻量，只包含必要功能

## 目录结构

```
shared/
├── config/             # 配置相关工具
├── errors/             # 错误定义和处理
├── llm/                # LLM客户端
├── file/               # 文件处理工具
├── types/              # 通用类型定义
├── utils/              # 通用工具函数
├── docs/               # API文档工具
└── interfaces/         # 服务接口定义
```

## 主要组件

### 1. 客户端库

位于各服务名称目录下，如`shared/llm/client.py`:

- 为微服务提供标准化客户端
- 处理服务发现和连接
- 提供错误处理和重试逻辑

示例:
```python
# 使用LLM客户端
from src.shared.llm.client import LLMClient

client = LLMClient()
response = await client.chat_completion(
    messages=[{"role": "user", "content": "你好"}],
    model="deepseek-chat"
)
```

### 2. 类型定义

位于`shared/types/`目录:

- 定义跨服务使用的数据模型
- 提供序列化和验证功能
- 实现Pydantic模型，支持类型检查

示例:
```python
# 文件类型定义
from src.shared.types.file import FileInfo, FileUploadResponse

# 使用共享类型
file_info = FileInfo(
    file_id="123",
    filename="document.pdf",
    size=1024567,
    mime_type="application/pdf"
)
```

### 3. 错误处理

位于`shared/errors/`目录:

- 统一的错误类型定义
- 标准化错误码和消息
- 错误处理中间件和装饰器

**核心组件**:

- `ErrorCode`: 枚举所有可能的错误类型
- `ServiceError`: 基础服务错误类
- `NotFoundError`, `ValidationError`等: 特定错误类型
- `handle_service_error`: 错误处理装饰器
- `register_error_handlers`: 注册FastAPI错误处理器

示例:
```python
from src.shared.errors import ServiceError, ErrorCode, NotFoundError, handle_service_error

# 使用预定义错误类
if not user:
    raise NotFoundError("User", user_id)

# 使用错误处理装饰器
@handle_service_error
async def get_user(user_id: str):
    # 函数内的异常会被自动包装为标准错误响应
    user = await db.find_user(user_id)
    if not user:
        raise NotFoundError("User", user_id)
    return user

# 注册错误处理器到FastAPI应用
from fastapi import FastAPI
from src.shared.errors import register_error_handlers

app = FastAPI()
register_error_handlers(app)
```

### 4. 配置管理

位于`shared/config/`目录:

- 环境变量加载和验证
- 服务配置管理
- 密钥和敏感信息处理

**核心组件**:

- `config_loader`: 提供配置加载和环境变量处理
- `service_config`: 统一管理服务URL和端口
- `settings`: 基于Pydantic的配置模型基类

示例:
```python
from src.shared.config import get_env, load_config, get_service_url, ServiceSettings

# 获取环境变量
debug = get_env("DEBUG", False, env_type=bool)
port = get_env("API_PORT", 8000, env_type=int)

# 加载配置文件
config = load_config("config.yaml", env_prefix="APP_")

# 获取服务URL
llm_url = get_service_url("llm")

# 定义服务配置
class FileServiceSettings(ServiceSettings):
    storage_path: str = "./data/files"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    
    class Config:
        env_prefix = "FILE_"
```

### 5. API文档工具

位于`shared/docs/`目录:

- OpenAPI规范自定义
- Swagger UI和ReDoc配置
- API版本控制

**核心组件**:

- `openapi`: 定制Swagger UI和OpenAPI规范
- `version`: API版本控制工具

示例:
```python
from fastapi import FastAPI
from src.shared.docs import setup_swagger_ui, add_api_metadata
from src.shared.docs.version import VersionedAPIRouter, create_versioned_app

# 创建支持版本的应用
app = create_versioned_app("文件服务", "处理文件上传和管理")

# 设置Swagger UI
setup_swagger_ui(app, "文件服务API", "1.0.0")

# 添加API元数据
add_api_metadata(
    app=app,
    contact_email="support@example.com",
    license_name="MIT"
)

# 创建版本化API路由
router_v1 = VersionedAPIRouter(version="1", tags=["files"])

@router_v1.get("/files")
async def list_files():
    return {"files": []}

# 包含路由
app.include_router(router_v1)
```

### 6. 通用工具

位于`shared/utils/`目录:

- 日期时间处理
- 字符串操作
- ID生成
- 加密和安全

示例:
```python
from src.shared.utils.time import get_current_timestamp
from src.shared.utils.id_generator import generate_unique_id

# 生成唯一ID
task_id = generate_unique_id()

# 获取当前时间戳
timestamp = get_current_timestamp()
```

## 接口定义

位于`shared/interfaces/`目录:

- 定义服务间协议
- 使用Protocol类实现接口
- 确保服务实现兼容性

示例:
```python
from src.shared.interfaces.rag_interface import RAGServiceInterface

# 实现接口
class CustomRAGService(RAGServiceInterface):
    async def retrieve(self, query: str, **kwargs) -> List[Document]:
        # 实现检索逻辑
        ...
    
    async def query(self, query: str, **kwargs) -> str:
        # 实现问答逻辑
        ...
```

## 微服务集成指南

要在微服务中正确集成共享组件，请遵循以下步骤:

1. **错误处理集成**:
   ```python
   # 在FastAPI应用启动时
   from src.shared.errors import register_error_handlers
   
   app = FastAPI()
   register_error_handlers(app)
   
   # 在业务逻辑中
   from src.shared.errors import ServiceError, handle_service_error
   
   @handle_service_error
   async def my_service_function():
       # 业务逻辑，异常会被自动处理
       pass
   ```

2. **配置管理集成**:
   ```python
   # 创建服务特定配置类
   from src.shared.config import ServiceSettings
   
   class MyServiceSettings(ServiceSettings):
       # 服务特定配置项
       special_feature: bool = False
       
       class Config:
           env_prefix = "MYSERVICE_"
   
   # 使用配置
   settings = MyServiceSettings()
   ```

3. **API文档集成**:
   ```python
   # 在FastAPI应用启动时
   from src.shared.docs import setup_swagger_ui
   
   app = FastAPI()
   setup_swagger_ui(app, "我的服务", "1.0.0")
   ```

## 注意事项

1. **版本兼容性**: 变更共享组件时，确保不破坏现有服务
2. **测试覆盖**: 共享组件需要全面的单元测试
3. **文档完善**: 每个共享组件都需要清晰的文档和示例
4. **循环依赖**: 避免在共享组件间创建循环依赖

## 扩展建议

添加新的共享组件时遵循以下步骤:

1. 确认该功能确实需要在多个服务间共享
2. 设计稳定的接口，考虑未来扩展
3. 实现最小可行功能，避免过度设计
4. 提供完整的文档和使用示例
5. 添加充分的测试用例 