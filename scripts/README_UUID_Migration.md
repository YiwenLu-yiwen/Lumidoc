# Lumidoc Intelligence UUID 数据库迁移指南

## 概述

本指南介绍如何将 Lumidoc Intelligence 项目的数据库从整数项目ID迁移到UUID系统，或者如何在新部署中直接使用UUID系统。

## 为什么迁移到UUID？

### 安全优势
- **防止枚举攻击**：UUID无法像连续整数(1,2,3...)那样被预测
- **信息泄露防护**：避免暴露系统项目总数等敏感信息
- **更高安全性**：128位随机标识符，符合现代Web应用安全最佳实践

### 技术优势
- **分布式友好**：UUID在分布式系统中全局唯一
- **无冲突性**：多个服务可以独立生成ID而不冲突
- **标准化**：遵循RFC 4122标准

## 迁移选项

### 选项1：新部署（推荐）

如果是全新部署，直接使用UUID初始化脚本：

```bash
# 1. 确保PostgreSQL正在运行
docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT version();"

# 2. 运行UUID初始化脚本
docker exec -i stp_postgres psql -U stpuser -d stpdb < scripts/init_database_uuid.sql

# 3. 验证表结构
docker exec stp_postgres psql -U stpuser -d stpdb -c "\d projects"
```

### 选项2：现有数据迁移

如果已有数据需要迁移：

```bash
# 1. 备份现有数据（重要！）
docker exec stp_postgres pg_dump -U stpuser -d stpdb > backup_before_uuid_migration.sql

# 2. 运行迁移脚本
docker exec -i stp_postgres psql -U stpuser -d stpdb < scripts/migrate_to_uuid.sql

# 3. 验证迁移结果
docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT id, name, user_id FROM projects LIMIT 5;"
```

## 验证步骤

### 1. 检查表结构
```sql
-- 验证projects表使用UUID主键
\d projects

-- 应该看到：
-- id | uuid | not null default uuid_generate_v4()
```

### 2. 测试UUID生成
```sql
-- 测试创建项目
INSERT INTO projects (name, user_id) VALUES ('测试UUID项目', 1);

-- 查看生成的UUID
SELECT id, name FROM projects ORDER BY created_at DESC LIMIT 1;
```

### 3. 验证外键关系
```sql
-- 检查外键约束
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint 
WHERE contype = 'f' 
AND (conrelid::regclass::text LIKE '%project%' OR confrelid::regclass::text LIKE '%project%');
```

## 代码更新

迁移后需要确保以下代码组件已更新：

### 后端代码
- [x] `src/shared/types/project.py` - 项目类型定义
- [x] `src/core/project_orm.py` - ORM模型
- [x] `src/modules/project/models/project.py` - 项目模型
- [x] `src/modules/project/project_service.py` - 项目服务
- [x] `src/modules/file/database/ensure_tables.py` - 表初始化

### 前端代码
- [x] `frontend/src/api/project.ts` - 项目API类型
- [x] `frontend/src/types/api.ts` - API类型定义
- [x] `frontend/src/features/project/ProjectSelect.tsx` - 项目选择组件

## 故障排除

### 常见问题

1. **扩展未安装**
   ```sql
   -- 检查扩展
   SELECT * FROM pg_extension WHERE extname IN ('uuid-ossp', 'vector');
   
   -- 安装扩展
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   ```

2. **外键约束错误**
   ```sql
   -- 检查孤立记录
   SELECT * FROM project_files pf 
   WHERE NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = pf.project_id);
   ```

3. **迁移失败回滚**
   ```bash
   # 恢复备份
   docker exec -i stp_postgres psql -U stpuser -d stpdb < backup_before_uuid_migration.sql
   ```

### 性能优化

UUID相比整数略大，建议：

1. **使用适当的索引**
   ```sql
   -- 为UUID列创建B-tree索引
   CREATE INDEX IF NOT EXISTS idx_projects_id ON projects(id);
   ```

2. **考虑使用UUID v4**
   - 已在脚本中使用 `uuid_generate_v4()`
   - 提供最佳的随机性和安全性

## 测试验证

### 功能测试
1. 创建新项目 - 验证UUID生成
2. 项目列表显示 - 验证ID格式
3. 项目详情页面 - 验证路由参数
4. 文件上传 - 验证项目关联
5. 聊天功能 - 验证消息关联

### 性能测试
1. 大量项目查询响应时间
2. UUID索引查询性能
3. 外键关联查询性能

## 安全验证

迁移后验证安全改进：

```bash
# 1. 验证项目ID不可预测
curl -X GET "http://localhost:8888/api/projects/" \
  -H "Authorization: Bearer $TOKEN"

# 2. 确认无法枚举项目
# 以下请求应该返回404而不是暴露其他项目
curl -X GET "http://localhost:8888/api/projects/00000000-0000-0000-0000-000000000001" \
  -H "Authorization: Bearer $TOKEN"
```

## 结论

UUID迁移显著提升了 Lumidoc Intelligence 的安全性，同时保持了系统功能的完整性。新的UUID系统：

- ✅ 防止项目ID枚举攻击
- ✅ 提高系统安全性
- ✅ 支持分布式架构扩展
- ✅ 兼容现有功能

迁移完成后，系统将更加安全可靠。