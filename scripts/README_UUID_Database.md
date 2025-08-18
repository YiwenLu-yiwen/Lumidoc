# Lumidoc Intelligence UUID 数据库系统

## 概述

Lumidoc Intelligence 使用UUID作为项目主键，提供高安全性的数据库架构。

## 安全优势

- **防止枚举攻击**：UUID无法像连续整数(1,2,3...)那样被预测
- **信息泄露防护**：避免暴露系统项目总数等敏感信息
- **更高安全性**：128位随机标识符，符合现代Web应用安全最佳实践

## 技术特性

- **分布式友好**：UUID在分布式系统中全局唯一
- **无冲突性**：多个服务可以独立生成ID而不冲突
- **标准化**：遵循RFC 4122标准

## 数据库结构

### 核心表结构

```sql
-- 项目表 (UUID主键)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    -- ...其他字段
);

-- 关联表示例
CREATE TABLE project_files (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id),
    -- ...其他字段
);
```

## 自动初始化

系统启动时通过Docker自动初始化UUID数据库结构：

- Docker容器启动时自动执行 `scripts/setup_pgvector.sql`
- 该脚本包含完整的UUID表结构定义
- 无需手动干预，重启服务即可获得正确的数据库结构

## 验证

### 检查表结构
```sql
\d projects
-- 应该看到：id | uuid | not null default uuid_generate_v4()
```

### 测试UUID生成
```sql
INSERT INTO projects (name, user_id) VALUES ('测试项目', 1);
SELECT id, name FROM projects ORDER BY created_at DESC LIMIT 1;
-- 返回类似：04085074-c011-4583-8653-e5768e08f669
```

## 代码集成

### 前端显示
```typescript
// 显示UUID的前8位
const displayId = project.id.slice(0, 8) + '...';
// 例如：04085074...
```

### 后端查询
```python
# 使用UUID查询
project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
```

## 性能优化

UUID查询性能已通过以下方式优化：

1. **B-tree索引**：所有UUID列都有适当的索引
2. **外键优化**：级联删除确保数据一致性
3. **查询优化**：使用prepared statements提高性能

## 安全验证

UUID系统确保：

- ✅ 无法预测项目ID
- ✅ 防止暴力枚举
- ✅ 保护敏感信息
- ✅ 符合安全最佳实践

项目ID示例：`04085074-c011-4583-8653-e5768e08f669`

这种格式确保了系统的安全性和可扩展性。