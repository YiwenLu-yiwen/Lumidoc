# Scripts 文件夹使用说明

## 概述

该文件夹包含STP项目的运维、部署和诊断脚本。所有脚本都经过清理，只保留项目运行必需的核心脚本。

## 📁 文件结构

### 🔧 系统诊断脚本
- `diagnose_services.py` - 服务健康检查和状态诊断工具
- `fix_database_structure.py` - 数据库结构修复脚本

### 🚀 环境设置脚本
- `setup_deps.sh` - 项目依赖自动安装脚本
- `setup_minio.sh` - MinIO对象存储设置和测试
- `init_minio.sh` - MinIO服务初始化
- `setup_pgvector_dev.sh` - 开发环境pgvector扩展设置
- `install_cuda_inference.sh` - CUDA推理环境安装

### 🗄️ 数据库相关
- `install_pgvector.py` - PostgreSQL pgvector扩展安装
- `setup_pgvector.sql` - pgvector SQL初始化脚本
- `add_rag_status_fields.sql` - RAG状态字段添加脚本

### 📖 文档说明
- `README_MINIO_MIGRATION.md` - MinIO迁移使用说明
- `S3_BUCKET_EXPLANATION.md` - S3存储桶结构说明

## 🚀 使用指南

### 初次部署

1. **安装项目依赖**
   ```bash
   bash scripts/setup_deps.sh
   ```

2. **设置MinIO对象存储**
   ```bash
   bash scripts/setup_minio.sh
   ```

3. **安装pgvector扩展**
   ```bash
   python scripts/install_pgvector.py
   ```

### 日常运维

1. **诊断服务状态**
   ```bash
   python scripts/diagnose_services.py
   ```

2. **修复数据库结构**
   ```bash
   python scripts/fix_database_structure.py
   ```

### 开发环境设置

1. **设置开发环境pgvector**
   ```bash
   bash scripts/setup_pgvector_dev.sh
   ```

2. **CUDA推理环境**
   ```bash
   bash scripts/install_cuda_inference.sh
   ```

## ⚠️ 注意事项

1. **权限要求**: 某些脚本需要管理员权限，请根据提示执行
2. **环境检查**: 运行脚本前请确保.env文件配置正确
3. **依赖要求**: 确保Docker、Python 3.9+、Node.js 16+已安装
4. **备份建议**: 运行数据库相关脚本前建议先备份数据

## 🔄 脚本执行顺序

推荐的首次部署顺序：
1. `setup_deps.sh` - 安装基础依赖
2. `setup_minio.sh` - 配置对象存储
3. `install_pgvector.py` - 安装向量数据库扩展
4. `diagnose_services.py` - 验证所有服务正常

## 🚫 已清理的脚本

为保持代码库整洁，已删除以下类型的临时脚本：
- 历史调试和测试脚本 (61个文件)
- 临时数据迁移脚本
- 一次性问题修复脚本
- 开发过程中的实验性脚本

这些脚本在解决LightRAG高并发问题过程中发挥了重要作用，但现在已完成使命。

## 📞 支持

如需帮助或发现问题，请：
1. 检查脚本输出的错误信息
2. 确认环境配置是否正确
3. 查看相关服务的日志文件
4. 联系开发团队获取支持