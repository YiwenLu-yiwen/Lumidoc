# 认证服务 (Auth Service)

## 概述

认证服务是Lumidoc平台的核心安全组件，负责用户身份验证、JWT令牌管理和权限控制。该服务提供统一的身份认证接口，支持用户注册、登录、令牌刷新等功能。

## 服务信息

- **服务名称**: auth
- **默认端口**: 8007
- **数据库**: PostgreSQL
- **认证方式**: JWT (RSA256)

## 核心功能

### 1. 用户管理
- 用户注册和登录
- 密码加密存储（bcrypt）
- 用户信息管理和更新

### 2. JWT令牌管理
- 访问令牌（Access Token）生成和验证
- 刷新令牌（Refresh Token）管理
- 令牌黑名单机制

### 3. 权限控制
- 基于角色的访问控制（RBAC）
- API端点权限验证
- 跨服务认证支持

## 项目结构

```
src/modules/auth/
├── README.md                 # 本文档
├── main.py                   # 服务启动入口
├── auth_service.py           # 核心认证服务
├── auth_api.py              # API路由定义
├── dependencies.py          # FastAPI依赖项
├── user_model.py           # 用户数据模型
├── config/
│   ├── config.py           # 配置管理
│   └── database.py         # 数据库配置
├── models/
│   └── user.py             # 用户实体模型
└── Dockerfile              # 容器构建入口
```

## 核心组件

### 1. 认证服务 (AuthService)

**文件**: `auth_service.py`

**主要功能**:
- 用户注册和登录验证
- JWT令牌生成和验证
- 密码加密和验证

**关键方法**:
```python
class AuthService:
    async def register_user(self, username: str, password: str, email: str) -> dict
    async def authenticate_user(self, username: str, password: str) -> dict
    async def generate_tokens(self, user_id: int) -> dict
    async def refresh_access_token(self, refresh_token: str) -> dict
    async def verify_access_token(self, token: str) -> dict
```

### 2. API路由 (AuthAPI)

**文件**: `auth_api.py`

**端点列表**:
- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录
- `POST /auth/refresh` - 刷新令牌
- `POST /auth/logout` - 用户登出
- `GET /auth/verify` - 令牌验证
- `GET /auth/profile` - 获取用户信息

### 3. 用户模型 (User Model)

**文件**: `models/user.py`

**数据结构**:
```python
class User(BaseModel):
    id: int
    username: str
    email: str
    password_hash: str
    role: str = "user"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

## 数据库设计

### 用户表 (users)

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 刷新令牌表 (refresh_tokens)

```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## JWT配置

### 令牌结构

**访问令牌 (Access Token)**:
- 有效期: 15分钟
- 包含: user_id, username, role
- 默认算法: HS256（密钥仅从环境变量读取）

**刷新令牌 (Refresh Token)**:
- 有效期: 7天
- 存储在数据库中
- 支持撤销机制

### 密钥管理

- `SECRET_KEY` 必须通过未提交的 `.env` 或部署密钥管理器提供。
- 仓库和Docker镜像均不包含签名私钥。
- 如需RS256，应在部署时挂载密钥文件，并设置 `JWT_PRIVATE_KEY_PATH` 与
  `JWT_PUBLIC_KEY_PATH`。

## API使用示例

### 用户注册

```bash
curl -X POST http://localhost:8007/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123",
    "email": "test@example.com"
  }'
```

**响应**:
```json
{
  "success": true,
  "message": "用户注册成功",
  "user_id": 1
}
```

### 用户登录

```bash
curl -X POST http://localhost:8007/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

**响应**:
```json
{
  "success": true,
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "def50200a3b4c5d6e7f8...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 令牌验证

```bash
curl -X GET http://localhost:8007/auth/verify \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**响应**:
```json
{
  "valid": true,
  "user_id": 1,
  "username": "testuser",
  "role": "user"
}
```

## 配置参数

### 环境变量

```bash
# 数据库配置（Compose内部地址）
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=lumidoc
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<从密钥管理器注入>

# JWT配置
JWT_ALGORITHM=HS256
SECRET_KEY=<至少32字符的随机密钥>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 服务配置
AUTH_SERVICE_PORT=8007
AUTH_SERVICE_HOST=0.0.0.0
```

## 安全特性

### 1. 密码安全
- 使用bcrypt进行密码哈希
- 强制密码复杂度要求
- 防止暴力破解攻击

### 2. 令牌安全
- RSA256算法签名
- 短期访问令牌有效期
- 刷新令牌撤销机制

### 3. 防护机制
- 登录失败次数限制
- 账户锁定机制
- CORS跨域请求保护

## 错误处理

### 常见错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| 400 | 请求参数错误 | 检查请求格式和必需字段 |
| 401 | 认证失败 | 检查用户名密码或令牌 |
| 403 | 权限不足 | 检查用户角色和权限 |
| 409 | 用户已存在 | 使用不同的用户名或邮箱 |
| 500 | 服务器内部错误 | 检查服务日志和数据库连接 |

### 错误响应格式

```json
{
  "success": false,
  "error": "INVALID_CREDENTIALS",
  "message": "用户名或密码错误",
  "details": {
    "field": "password",
    "code": "INVALID_PASSWORD"
  }
}
```

## 部署和运维

### 1. 启动服务

```bash
# 开发环境
python -m src.modules.auth.main

# 生产环境
uvicorn src.modules.auth.main:app --host 0.0.0.0 --port 8007
```

### 2. 健康检查

```bash
curl http://localhost:8007/health
```

### 3. 日志监控

日志文件位置: `logs/auth_service.log`

关键监控指标:
- 登录成功/失败率
- 令牌生成/验证频率
- 异常登录尝试

### 4. 数据库维护

```sql
-- 清理过期刷新令牌
DELETE FROM refresh_tokens WHERE expires_at < NOW();

-- 查看活跃用户统计
SELECT COUNT(*) FROM users WHERE is_active = true;

-- 查看最近登录活动
SELECT u.username, rt.created_at 
FROM users u 
JOIN refresh_tokens rt ON u.id = rt.user_id 
WHERE rt.created_at > NOW() - INTERVAL '24 hours';
```

## 与其他服务集成

### 1. API网关集成

认证服务通过API网关提供统一的认证入口，所有需要认证的请求都会经过认证中间件验证。

### 2. 服务间认证

其他微服务可以通过以下方式验证用户身份：

```python
from src.shared.auth import verify_token

async def protected_endpoint(token: str = Depends(verify_token)):
    # 受保护的端点逻辑
    return {"user_id": token.user_id}
```

### 3. 前端集成

前端应用需要：
1. 在登录后存储访问令牌
2. 在每个API请求中携带Authorization头
3. 处理令牌过期和自动刷新

## 性能优化

### 1. 缓存策略
- Redis缓存用户会话信息
- JWT公钥缓存减少文件读取
- 用户权限信息缓存

### 2. 数据库优化
- 用户名和邮箱字段索引
- 刷新令牌表定期清理
- 连接池配置优化

### 3. 并发处理
- 异步数据库操作
- 令牌验证并发优化
- 限流和防护机制

## 故障排除

### 常见问题

1. **JWT验证失败**
   - 检查密钥文件是否存在
   - 验证令牌格式和有效期
   - 确认算法配置正确

2. **数据库连接失败**
   - 检查数据库服务状态
   - 验证连接参数和权限
   - 确认网络连通性

3. **用户无法登录**
   - 检查密码加密方式
   - 验证用户状态（is_active）
   - 查看登录失败日志

### 调试命令

```bash
# 检查服务状态
curl http://localhost:8007/health

# 查看认证服务日志
docker compose logs auth_service
```
