# STP PostgreSQL 数据库分析文档

## 概述

STP（Smart Text Processing）系统使用 PostgreSQL 作为主数据库，通过 Docker 容器管理。数据库包含 pgvector 扩展以支持向量搜索功能。

### 数据库基本信息
- **数据库名称**: `stp` (环境变量: `POSTGRES_DB`)
- **用户名**: `postgres` (环境变量: `POSTGRES_USER`)  
- **密码**: `postgres` (环境变量: `POSTGRES_PASSWORD`)
- **Docker镜像**: `ankane/pgvector:latest`
- **扩展**: pgvector（用于向量搜索）

## 数据库表结构

### 1. 用户管理模块

#### 1.1 users（用户表）
- **功能**: 存储系统用户信息
- **表结构**:
  ```sql
  CREATE TABLE users (
      id INTEGER PRIMARY KEY,
      email TEXT UNIQUE NOT NULL,
      username TEXT UNIQUE NOT NULL,
      hashed_password TEXT NOT NULL,
      nickname TEXT,
      is_active BOOLEAN DEFAULT TRUE,
      is_superuser BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **用途**: 用户认证、权限管理

### 2. 项目管理模块

#### 2.1 projects（项目表）
- **功能**: 存储项目基本信息
- **表结构**:
  ```sql
  CREATE TABLE projects (
      id INTEGER PRIMARY KEY,
      name VARCHAR,
      description TEXT,
      user_id INTEGER,
      status VARCHAR(20) DEFAULT 'active',
      project_metadata JSONB DEFAULT '{}',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
  );
  ```
- **用途**: 项目创建、管理、状态跟踪

#### 2.2 project_collaborators（项目协作者表）
- **功能**: 管理项目协作关系
- **表结构**:
  ```sql
  CREATE TABLE project_collaborators (
      id INTEGER PRIMARY KEY,
      project_id INTEGER REFERENCES projects(id),
      user_id INTEGER NOT NULL,
      role VARCHAR NOT NULL, -- owner, editor, viewer
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP
  );
  ```
- **用途**: 多用户协作权限管理

#### 2.3 project_files（项目文件表）
- **功能**: 管理项目关联文件
- **表结构**:
  ```sql
  CREATE TABLE project_files (
      id INTEGER PRIMARY KEY,
      project_id INTEGER REFERENCES projects(id),
      name VARCHAR(255) NOT NULL,
      path TEXT NOT NULL,
      size INTEGER,
      type VARCHAR(100),
      file_metadata JSON,
      file_hash TEXT,
      content_hash TEXT REFERENCES file_contents(content_hash),
      -- RAG处理状态字段
      rag_status VARCHAR(20) DEFAULT 'pending',
      rag_processed_at TIMESTAMP,
      rag_error_message VARCHAR(500),
      is_in_rag BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **用途**: 文件上传管理、RAG处理状态跟踪

### 3. 文件处理模块

#### 3.1 file_contents（文件内容表）
- **功能**: 存储处理后的文件内容
- **表结构**:
  ```sql
  CREATE TABLE file_contents (
      content_hash TEXT PRIMARY KEY, -- SHA-256哈希值
      markdown_content TEXT NOT NULL,
      metadata JSONB,
      file_type TEXT NOT NULL,
      page_count INTEGER DEFAULT 1,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **用途**: 去重存储文件内容，支持内容共享

### 4. 聊天模块

#### 4.1 chat_history（聊天历史表）
- **功能**: 存储30天以上的归档聊天记录
- **表结构**:
  ```sql
  CREATE TABLE chat_history (
      id VARCHAR PRIMARY KEY,
      project_id VARCHAR,
      user_id VARCHAR,
      role VARCHAR NOT NULL, -- user, assistant
      content VARCHAR NOT NULL,
      timestamp TIMESTAMP NOT NULL,
      meta_data JSON
  );
  ```
- **用途**: 长期聊天记录存储、历史查询

### 5. 问题生成模块

#### 5.1 question_sets（题集表）
- **功能**: 管理题目集合
- **表结构**:
  ```sql
  CREATE TABLE question_sets (
      id VARCHAR(50) PRIMARY KEY,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      meta_info JSON DEFAULT '{}'
  );
  ```

#### 5.2 questions（问题表）
- **功能**: 存储生成的问题
- **表结构**:
  ```sql
  CREATE TABLE questions (
      id VARCHAR(50) PRIMARY KEY,
      set_id VARCHAR(50) REFERENCES question_sets(id),
      type VARCHAR(20), -- 单选题、多选题、判断题
      difficulty INTEGER DEFAULT 1, -- 1-3
      content TEXT,
      options JSON DEFAULT '[]',
      answer TEXT,
      explanation TEXT,
      tags JSON DEFAULT '[]',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

### 6. RAG（检索增强生成）模块

#### 6.1 rag_default_index_vectors（向量索引表）
- **功能**: 存储文档向量嵌入
- **表结构**:
  ```sql
  CREATE TABLE rag_default_index_vectors (
      id SERIAL PRIMARY KEY,
      content_id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      embedding vector(1024), -- pgvector类型
      metadata JSONB,
      content TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **索引**: 
  - `project_id_idx`
  - `content_id_idx`
  - 向量索引（IVFFlat）用于相似度搜索

#### 6.2 rag_default_index_document_status（文档状态表）
- **功能**: 跟踪RAG处理状态
- **表结构**:
  ```sql
  CREATE TABLE rag_default_index_document_status (
      id SERIAL PRIMARY KEY,
      document_id TEXT UNIQUE NOT NULL,
      project_id TEXT NOT NULL,
      status TEXT NOT NULL,
      metadata JSONB,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

#### 6.3 rag_default_index_document_content（文档内容表）
- **功能**: 存储RAG处理的原始文档
- **表结构**:
  ```sql
  CREATE TABLE rag_default_index_document_content (
      id SERIAL PRIMARY KEY,
      document_id TEXT UNIQUE NOT NULL,
      project_id TEXT NOT NULL,
      content TEXT,
      metadata JSONB,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```

#### 6.4 rag_default_index_relationships（关系表）
- **功能**: 存储文档间的关系
- **表结构**:
  ```sql
  CREATE TABLE rag_default_index_relationships (
      id SERIAL PRIMARY KEY,
      source_id TEXT NOT NULL,
      target_id TEXT NOT NULL,
      relation_type TEXT NOT NULL,
      project_id TEXT NOT NULL,
      metadata JSONB,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(source_id, target_id, relation_type, project_id)
  );
  ```

## CRUD 操作示例

### 1. 用户管理

```python
# 创建用户
async def create_user(db, email: str, username: str, password: str):
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password)
    )
    db.add(user)
    await db.commit()
    return user

# 查询用户
async def get_user_by_email(db, email: str):
    return db.query(User).filter(User.email == email).first()

# 更新用户
async def update_user_status(db, user_id: int, is_active: bool):
    user = db.query(User).filter(User.id == user_id).first()
    user.is_active = is_active
    await db.commit()

# 删除用户（软删除）
async def deactivate_user(db, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()
    user.is_active = False
    await db.commit()
```

### 2. 项目管理

```python
# 创建项目
async def create_project(db, name: str, user_id: int):
    project = Project(
        name=name,
        user_id=user_id,
        status=ProjectStatus.ACTIVE.value
    )
    db.add(project)
    await db.commit()
    
    # 添加创建者为项目所有者
    collaborator = ProjectCollaborator(
        project_id=project.id,
        user_id=user_id,
        role="owner"
    )
    db.add(collaborator)
    await db.commit()
    return project

# 查询用户的所有项目
async def get_user_projects(db, user_id: int):
    return db.query(Project).join(ProjectCollaborator).filter(
        ProjectCollaborator.user_id == user_id
    ).all()

# 添加项目文件
async def add_project_file(db, project_id: int, file_info: dict):
    file = ProjectFile(
        project_id=project_id,
        name=file_info["name"],
        path=file_info["path"],
        size=file_info["size"],
        type=file_info["type"],
        file_hash=file_info["hash"]
    )
    db.add(file)
    await db.commit()
    return file
```

### 3. RAG向量操作

```python
# 插入向量
async def insert_vector(db, content_id: str, project_id: str, embedding: list):
    sql = """
    INSERT INTO rag_default_index_vectors 
    (content_id, project_id, embedding, content, metadata)
    VALUES ($1, $2, $3, $4, $5)
    """
    await db.execute(sql, content_id, project_id, embedding, content, metadata)

# 向量相似度搜索
async def vector_search(db, query_embedding: list, project_id: str, limit: int = 5):
    sql = """
    SELECT content_id, content, 
           1 - (embedding <=> $1::vector) as similarity
    FROM rag_default_index_vectors
    WHERE project_id = $2
    ORDER BY embedding <=> $1::vector
    LIMIT $3
    """
    results = await db.fetch(sql, query_embedding, project_id, limit)
    return results
```

## 数据库维护建议

### 1. 定期备份

```bash
# 创建备份脚本 backup_postgres.sh
#!/bin/bash
BACKUP_DIR="/backup/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="stp_postgres"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
docker exec -t $CONTAINER_NAME pg_dump -U postgres stp | gzip > $BACKUP_DIR/stp_backup_$TIMESTAMP.sql.gz

# 保留最近7天的备份
find $BACKUP_DIR -name "stp_backup_*.sql.gz" -mtime +7 -delete

echo "备份完成: stp_backup_$TIMESTAMP.sql.gz"
```

### 2. 定期维护任务

```bash
# 添加到 crontab
# 每天凌晨2点执行备份
0 2 * * * /path/to/backup_postgres.sh

# 每周日凌晨3点执行VACUUM分析
0 3 * * 0 docker exec stp_postgres psql -U postgres -d stp -c "VACUUM ANALYZE;"

# 每月1号凌晨4点重建索引
0 4 1 * * docker exec stp_postgres psql -U postgres -d stp -c "REINDEX DATABASE stp;"
```

### 3. 监控建议

```sql
-- 检查数据库大小
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'stp';

-- 检查表大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 检查慢查询
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY mean_time DESC
LIMIT 10;
```

### 4. 性能优化建议

1. **向量索引优化**
   ```sql
   -- 当向量数据量超过10万时，创建IVFFlat索引
   CREATE INDEX rag_vectors_embedding_idx 
   ON rag_default_index_vectors 
   USING ivfflat (embedding vector_cosine_ops) 
   WITH (lists = 100);
   ```

2. **连接池配置**
   - 使用 SQLAlchemy 连接池
   - 设置合理的 pool_size 和 max_overflow
   ```python
   engine = create_engine(
       DATABASE_URL,
       pool_size=20,
       max_overflow=40,
       pool_pre_ping=True
   )
   ```

3. **定期清理**
   ```sql
   -- 清理30天前的聊天记录
   DELETE FROM chat_history 
   WHERE timestamp < NOW() - INTERVAL '30 days';
   
   -- 清理失败的RAG处理记录
   DELETE FROM project_files 
   WHERE rag_status = 'failed' 
   AND rag_processed_at < NOW() - INTERVAL '7 days';
   ```

### 5. Docker 管理命令

```bash
# 查看PostgreSQL容器状态
docker ps | grep postgres

# 查看容器日志
docker logs stp_postgres --tail 100

# 进入容器执行SQL
docker exec -it stp_postgres psql -U postgres -d stp

# 重启容器
docker restart stp_postgres

# 导出数据
docker exec stp_postgres pg_dump -U postgres stp > backup.sql

# 导入数据
docker exec -i stp_postgres psql -U postgres stp < backup.sql
```

### 6. 灾难恢复

1. **从备份恢复**
   ```bash
   # 停止应用服务
   docker-compose stop
   
   # 恢复数据库
   gunzip < backup.sql.gz | docker exec -i stp_postgres psql -U postgres -d stp
   
   # 重启服务
   docker-compose up -d
   ```

2. **主从复制**（生产环境建议）
   - 配置 PostgreSQL 流复制
   - 使用 pgpool-II 实现负载均衡
   - 定期测试故障转移

## 注意事项

1. **数据安全**
   - 定期更改数据库密码
   - 限制数据库访问IP
   - 使用SSL连接
   - 加密敏感数据

2. **性能监控**
   - 使用 pg_stat_statements 监控查询性能
   - 监控连接数和活动会话
   - 设置慢查询日志

3. **容量规划**
   - 监控磁盘使用率
   - 提前规划扩容
   - 定期清理历史数据

4. **版本管理**
   - 使用数据库迁移工具（如Alembic）
   - 记录所有schema变更
   - 在测试环境验证迁移脚本