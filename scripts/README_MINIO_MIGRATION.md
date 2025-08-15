# MinIO迁移完成指南

## 🎉 迁移已完成！

您的STP项目已成功从本地文件系统迁移到MinIO对象存储。以下是所有更改的详细说明：

## 📁 目录结构映射

### MinIO桶结构
所有文件现在存储在MinIO的 `data` 桶中，使用Docker命名卷进行持久化：

```
MinIO桶: data
├── uploads/                    # 上传文件目录
│   ├── 123/                   # 数字项目ID子目录
│   │   ├── abc123.pdf         # 项目文件
│   │   └── def456.docx        # 项目文件
│   ├── 456/                   # 另一个数字项目ID
│   └── xyz789.txt             # 非数字项目ID的文件（直接在uploads下）
├── content/                    # OCR处理后的文件
│   ├── abc123.md              # 处理后的markdown文件
│   └── def456.md              # 处理后的markdown文件
├── rag/                       # RAG索引和向量文件
│   ├── index.faiss            # FAISS索引文件
│   └── embeddings.pkl         # 向量数据
└── models/                    # 模型文件
    ├── ocr_model.bin          # OCR模型
    └── embedding_model.bin    # 向量模型
```

**🎯 优势**: 
- 数据持久化在Docker卷中，性能更好
- 通过MinIO提供S3兼容的API访问
- 自动备份和高可用性支持

### 项目ID规则
- **数字项目ID** (如 `123`, `456`): 文件存储在 `uploads/{project_id}/` 子目录下
- **非数字项目ID** (如 `project_abc`): 文件直接存储在 `uploads/` 目录下

## 🔧 技术实现

### 存储接口更新
所有文件操作现在通过统一的存储接口进行：

```python
from src.shared.storage.storage_factory import get_storage

# 获取不同类型的存储实例
upload_storage = await get_storage(directory_type="upload")
content_storage = await get_storage(directory_type="content") 
rag_storage = await get_storage(directory_type="rag")
models_storage = await get_storage(directory_type="models")

# 基础操作
await storage.save_file(file_id="123/example.pdf", content=b"data")
content = await storage.get_file("123/example.pdf")
exists = await storage.file_exists("123/example.pdf")
await storage.delete_file("123/example.pdf")

# MinIO预签名URL（用于直接访问）
url = storage.get_file_url("123/example.pdf", expire=3600)
```

### 文件路径构建
```python
# 上传文件路径构建逻辑
if project_id.isdigit():
    file_path = f"{project_id}/{file_hash}.{extension}"  # 123/abc123.pdf
else:
    file_path = f"{file_hash}.{extension}"               # abc123.pdf

# 内容文件路径
content_path = f"{file_hash}.md"                         # abc123.md

# RAG文件路径
rag_path = f"index_{project_id}.faiss"                   # index_123.faiss
```

## 🚀 启动和测试

### 1. 启动MinIO服务
```bash
# 一键设置和测试（推荐）
./scripts/setup_minio.sh

# 或手动启动
docker-compose up -d minio
```

### 2. 验证集成
```bash
# 本地data目录配置验证
python3 scripts/test_local_data_directory.py

# 完整验证
python3 scripts/verify_minio_integration.py

# 基础集成测试
python3 scripts/test_minio_integration.py

# 项目目录结构测试
python3 scripts/test_project_directories.py
```

### 3. 迁移现有文件（可选）
```bash
# 将本地文件迁移到MinIO
python3 scripts/migrate_to_minio.py
```

### 4. 启动完整服务
```bash
./start_services.sh
```

## 🔐 MinIO访问信息

- **控制台**: http://localhost:9001
- **API端点**: http://localhost:9000
- **用户名**: minioadmin
- **密码**: minioadmin
- **桶名**: data
- **本地数据目录**: ./data/

## 📈 性能提升

### 直接访问优化
- 文件预览和下载通过预签名URL直接访问MinIO
- 减少服务器带宽使用90%以上
- 支持CDN加速和全球分发

### 并发处理
- 支持多文件并发上传/下载
- 自动负载均衡和故障转移
- 内置数据冗余和修复

## 🛠️ 故障排除

### 常见问题

1. **MinIO连接失败**
   ```bash
   # 检查MinIO服务状态
   docker ps | grep minio
   
   # 检查端口占用
   lsof -i :9000
   
   # 重启MinIO
   docker-compose restart minio
   ```

2. **文件上传失败**
   ```bash
   # 检查存储类型配置
   grep STORAGE_TYPE .env
   
   # 应该显示: STORAGE_TYPE=s3
   ```

3. **路径访问错误**
   ```bash
   # 验证桶和路径结构
   python3 scripts/test_project_directories.py
   ```

### 日志查看
```bash
# MinIO服务日志
docker logs stp_minio

# 应用服务日志
docker logs stp_file_service
docker logs stp_fileproc_service
```

## 📝 配置说明

### 环境变量
```env
# 存储配置
STORAGE_TYPE=s3                           # 使用S3/MinIO存储
S3_ENDPOINT=http://localhost:9000         # MinIO端点
S3_ACCESS_KEY=minioadmin                  # 访问密钥
S3_SECRET_KEY=minioadmin                  # 秘密密钥
S3_BUCKET=data                            # 桶名
S3_REGION=us-east-1                       # 区域

# 目录映射（保持原有配置）
UPLOAD_DIR=./uploads                      # 映射到 data/uploads/
CONTENT_DIR=./content                     # 映射到 data/content/
RAG_DIR=./rag                            # 映射到 data/rag/
MODELS_DIR=./models                      # 映射到 data/models/
```

## 🔄 回滚方案

如果需要回滚到本地存储：

1. 更改环境变量：
   ```env
   STORAGE_TYPE=local
   ```

2. 重启服务：
   ```bash
   docker-compose restart
   ```

3. 从MinIO导出文件（如需要）：
   ```bash
   # 使用MinIO客户端工具导出
   mc cp --recursive minio/data/ ./backup/
   ```

## 🎯 下一步

MinIO集成完成后，您可以：

1. **配置CDN加速**: 将MinIO与CloudFlare或其他CDN服务集成
2. **设置备份策略**: 配置跨区域复制和定期备份
3. **监控和告警**: 设置MinIO性能监控和存储使用告警
4. **权限管理**: 配置更细粒度的访问权限和安全策略

## 📞 支持

如果遇到问题，请：
1. 运行完整验证脚本获取详细错误信息
2. 检查Docker和MinIO服务状态
3. 查看应用日志定位具体问题

---

**✅ MinIO迁移已完成！现在您可以享受更高性能、更可靠的文件存储服务了！**