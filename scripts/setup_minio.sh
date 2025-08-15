#!/bin/bash

# MinIO设置和测试脚本

echo "🚀 MinIO集成设置开始..."

# 检查Docker是否运行
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker未运行，请先启动Docker"
    exit 1
fi

echo "✅ Docker运行正常"

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "❌ .env文件不存在，请确保在项目根目录运行此脚本"
    exit 1
fi

echo "✅ 环境配置文件存在"

# 启动MinIO服务
echo "🏃 启动MinIO服务..."
docker-compose up -d minio

# 等待MinIO启动
echo "⏳ 等待MinIO服务启动..."
sleep 10

# 检查MinIO是否启动成功
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1; then
        echo "✅ MinIO服务启动成功"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ 等待MinIO启动... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ MinIO服务启动超时"
    exit 1
fi

# 显示MinIO控制台信息
echo ""
echo "📊 MinIO控制台信息:"
echo "  - 控制台地址: http://localhost:9001"
echo "  - 用户名: minioadmin"
echo "  - 密码: minioadmin"
echo "  - API端点: http://localhost:9000"
echo "  - 数据存储: Docker命名卷 (minio_data)"
echo ""

# 运行集成测试
echo "🧪 运行MinIO集成测试..."
python3 scripts/test_minio_integration.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 MinIO集成设置完成!"
    echo ""
    echo "📋 后续步骤:"
    echo "1. 如需迁移现有文件到MinIO，运行: python3 scripts/migrate_to_minio.py"
    echo "2. 启动完整服务: ./start_services.sh"
    echo "3. 访问MinIO控制台: http://localhost:9001"
    echo ""
    echo "💡 提示: 所有文件存储在Docker命名卷中，通过MinIO进行管理"
else
    echo "❌ MinIO集成测试失败，请检查配置"
    exit 1
fi