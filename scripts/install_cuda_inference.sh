#!/bin/bash

set -e

echo "🔑 Step 1: 获取并安装 NVIDIA keyring..."
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update

echo "📦 Step 2: 安装 CUDA 核心推理组件（含 libcublasLt.so.11）..."
sudo apt-get install -y \
    libcublas-12-2 \
    libcublas-dev-12-2 \
    libcusolver-12-2 \
    libcusparse-12-2 \
    libcurand-12-2 \
    cuda-cudart-12-2 \
    cuda-command-line-tools-12-2

echo "✅ Step 3: 设置环境变量..."
if ! grep -q 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' ~/.bashrc; then
  echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
  echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
fi
source ~/.bashrc

echo "🚀 Step 4: 验证 cuBLAS 安装是否成功..."
ls /usr/local/cuda*/lib64/libcublasLt.so.11

echo "🎉 完成！你现在可以重新启动服务并启用 CUDAExecutionProvider。"
