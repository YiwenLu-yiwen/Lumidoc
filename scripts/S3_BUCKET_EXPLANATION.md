# S3_BUCKET=data 配置说明

## ✅ 这个配置非常重要且有用！

您在 `.env` 文件中看到的 `S3_BUCKET=data` 配置是**必需的**，它统一了整个系统的存储桶命名。

## 🎯 为什么需要S3_BUCKET=data？

### 1. 统一存储桶命名
MinIO是**对象存储**，所有文件都存储在"桶"(bucket)中。`S3_BUCKET=data` 告诉系统：
- 所有文件都存储在名为 `data` 的桶中
- 不同目录通过**对象键前缀**区分，而不是物理目录

### 2. 系统架构映射
```
MinIO桶结构:
data/                    ← S3_BUCKET=data 创建的桶
├── uploads/file1.pdf    ← 对象键: "uploads/file1.pdf"
├── content/hash1.md     ← 对象键: "content/hash1.md"  
├── rag/index.faiss      ← 对象键: "rag/index.faiss"
└── models/model.bin     ← 对象键: "models/model.bin"

本地映射:
./data/                  ← Docker卷映射
├── uploads/
├── content/
├── rag/
└── models/
```

### 3. 代码中的使用

**存储工厂** (`src/shared/storage/storage_factory.py`):
```python
bucket_name = os.getenv('S3_BUCKET', 'data')  # 读取配置
```

**文件处理服务** (`src/modules/fileproc/`):
```python
MINIO_BUCKET = os.getenv("S3_BUCKET", "data")  # 统一配置
```

**服务配置** (`src/shared/config/service_settings.py`):
```python
s3_bucket: str = Field(default_factory=lambda: get_env("S3_BUCKET", "data"))
```

## 🔧 配置一致性

### 修复前的问题
- 主存储系统使用: `S3_BUCKET=data`
- 文件处理服务使用: `MINIO_BUCKET=stp-files`
- **不一致导致文件存储在不同桶中！**

### 修复后的统一配置
- 所有服务统一使用: `S3_BUCKET=data`
- 确保文件存储位置一致
- 简化运维和管理

## 🌟 实际效果

### MinIO控制台中看到的结构
```
桶: data
├── 对象: uploads/123/file1.pdf
├── 对象: uploads/456/file2.docx  
├── 对象: content/abc123.md
├── 对象: rag/index.faiss
└── 对象: models/ocr_model.bin
```

### 本地文件系统中的映射
```
./data/
├── uploads/
│   ├── 123/
│   │   └── file1.pdf
│   └── 456/
│       └── file2.docx
├── content/
│   └── abc123.md
├── rag/
│   └── index.faiss
└── models/
    └── ocr_model.bin
```

## 🚀 如果修改S3_BUCKET会怎样？

### 修改为其他名称
```env
S3_BUCKET=my-custom-bucket
```

**结果**：
- MinIO会创建名为 `my-custom-bucket` 的桶
- 所有文件存储在新桶中
- 本地目录映射不变（仍然是 `./data/`）

### 不设置S3_BUCKET
**默认值**: `data`
- 系统会自动使用 `data` 作为桶名
- 保持向后兼容性

## 🔍 验证配置是否正确

```bash
# 验证S3_BUCKET配置一致性
python3 scripts/verify_s3_bucket_config.py
```

这个脚本会检查：
- ✅ 所有服务是否使用相同的桶配置
- ✅ 存储操作是否正常
- ✅ 配置是否一致

## 📋 总结

**S3_BUCKET=data 的重要性：**

1. ✅ **必需配置** - 定义MinIO存储桶名称
2. ✅ **统一标识** - 确保所有服务使用相同桶
3. ✅ **对象存储** - MinIO的核心概念，不是文件系统目录
4. ✅ **系统一致性** - 避免文件散布在不同桶中
5. ✅ **运维简化** - 所有数据在一个桶中管理

**结论**: `S3_BUCKET=data` 配置不仅有用，而且是系统正常运行的**关键配置**！