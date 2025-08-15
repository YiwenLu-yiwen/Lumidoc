# STP 系统维护脚本说明

## 📋 脚本清单

### 🔧 系统初始化脚本
- **`setup_deps.sh`** - 安装系统依赖
- **`setup_minio.sh`** - MinIO对象存储初始化
- **`setup_pgvector_dev.sh`** - PostgreSQL pgvector扩展安装
- **`init_minio.sh`** - MinIO桶初始化

### 📊 系统诊断脚本
- **`diagnose_services.py`** - 全系统服务健康检查
- **`check_redis_keys.py`** - Redis键状态检查
- **`verify_clear.py`** - 数据库清空验证
- **`final_verification.py`** - 最终数据清空验证

### 🗄️ 数据库清理脚本
- **`clear_redis.py`** - Redis缓存清空
- **`clear_neo4j.py`** - Neo4j图数据库清空
- **`clear_postgresql.py`** - PostgreSQL数据清空
- **`drop_all_tables.py`** - PostgreSQL完全清空
- **`force_clear_redis.py`** - Redis强制清空

### 🚀 运行环境脚本
- **`install_cuda_inference.sh`** - CUDA推理环境安装
- **`install_pgvector.py`** - Python pgvector库安装

## 🔍 使用说明

### 系统启动
```bash
# 启动所有服务
./start_services.sh

# 检查服务状态
python scripts/diagnose_services.py
```

### 数据库维护
```bash
# 清空Redis缓存
python scripts/clear_redis.py

# 清空Neo4j数据
python scripts/clear_neo4j.py

# 清空PostgreSQL数据
python scripts/clear_postgresql.py

# 完全清空并验证
python scripts/drop_all_tables.py
python scripts/final_verification.py
```

### 存储维护
```bash
# 初始化MinIO
bash scripts/setup_minio.sh

# 检查MinIO配置
bash scripts/init_minio.sh
```

## ⚠️ 注意事项

1. **数据清理脚本会删除所有数据，请谨慎使用**
2. **生产环境请勿使用清理脚本**
3. **建议在执行前备份重要数据**
4. **脚本执行需要相应的数据库连接权限**

## 🔧 故障排查

如果脚本执行失败，请检查：
1. 数据库连接配置
2. 服务运行状态
3. 权限设置
4. 网络连通性

## 📝 维护记录

- **2025-07-30**: 整理所有维护脚本到scripts目录
- **2025-07-30**: 添加脚本使用说明文档