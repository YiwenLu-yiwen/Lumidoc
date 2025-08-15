#!/bin/bash

# MinIO初始化脚本 - 确保首次运行时创建必要的目录结构

echo "🔧 MinIO初始化脚本"
echo "=================="

# 检查是否在项目根目录
if [ ! -f ".env" ]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

# 确保本地data目录存在
echo "📁 创建本地data目录结构..."
mkdir -p data/{uploads,content,rag,models}

# 设置目录权限（确保MinIO容器可以访问）
chmod -R 755 ./data

echo "✅ 本地data目录结构创建完成:"
ls -la ./data/

# 如果MinIO容器还没运行，启动它
echo ""
echo "🚀 检查MinIO服务状态..."
if docker ps | grep -q stp_minio; then
    echo "✅ MinIO服务已在运行"
else
    if docker ps -a | grep -q stp_minio; then
        echo "🔄 启动现有MinIO容器..."
        docker start stp_minio
    else
        echo "🆕 创建并启动MinIO容器..."
        docker run -d \
            --name stp_minio \
            --network stp_network \
            -p 9000:9000 \
            -p 9001:9001 \
            -e MINIO_ROOT_USER=minioadmin \
            -e MINIO_ROOT_PASSWORD=minioadmin \
            -v $(pwd)/data:/data \
            minio/minio:latest \
            server /data --console-address ":9001"
    fi
    
    echo "⏳ 等待MinIO启动..."
    sleep 5
    
    # 检查MinIO是否启动成功
    MAX_RETRIES=15
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
fi

# 使用MinIO客户端创建初始目录结构（可选）
echo ""
echo "📂 验证MinIO中的目录结构..."

# 创建一个测试文件来确保目录结构
echo "test" > /tmp/test_init.txt

# 使用mc（MinIO客户端）或直接通过API创建目录结构
# 这里我们通过上传一个临时文件到每个目录来确保目录存在
python3 -c "
import asyncio
import sys
import os
sys.path.insert(0, '.')

async def init_directories():
    try:
        from src.shared.storage.storage_factory import get_storage
        
        directories = ['upload', 'content', 'rag', 'models']
        
        for dir_type in directories:
            try:
                storage = await get_storage(directory_type=dir_type)
                
                # 上传一个初始化文件到每个目录
                init_file = f'.init_{dir_type}'
                await storage.save_file(init_file, b'Directory initialized')
                print(f'✅ {dir_type} 目录初始化完成')
                
                # 立即删除初始化文件
                await storage.delete_file(init_file)
                
            except Exception as e:
                print(f'⚠️  {dir_type} 目录初始化失败: {str(e)}')
        
        print('✅ MinIO目录结构初始化完成')
        return True
        
    except Exception as e:
        print(f'❌ MinIO初始化失败: {str(e)}')
        return False

# 运行初始化
if asyncio.run(init_directories()):
    print('🎉 MinIO初始化成功')
else:
    print('❌ MinIO初始化失败')
    exit(1)
" 2>/dev/null || echo "⚠️  Python初始化脚本执行失败，但目录结构已创建"

# 清理临时文件
rm -f /tmp/test_init.txt

echo ""
echo "📊 MinIO信息:"
echo "  - 控制台: http://localhost:9001"
echo "  - API端点: http://localhost:9000"
echo "  - 用户名: minioadmin"
echo "  - 密码: minioadmin"
echo "  - 本地数据目录: $(pwd)/data/"
echo ""
echo "✅ MinIO初始化完成！"