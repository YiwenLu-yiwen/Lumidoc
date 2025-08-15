#!/bin/bash

# 杀死占用3000端口的进程
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# 清理缓存
rm -rf node_modules/.vite 2>/dev/null || true

# 设置Node.js内存限制和稳定性选项
export NODE_OPTIONS="--max-old-space-size=4096 --no-warnings"

# 启动开发服务器，使用简化配置
echo "启动STP Intelligence开发服务器..."
npx vite --config vite.config.simple.ts --host 0.0.0.0 --port 3000 --clearScreen false