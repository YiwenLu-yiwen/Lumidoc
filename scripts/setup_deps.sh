#!/bin/bash

# 显示彩色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color
YELLOW='\033[1;33m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}STP 项目依赖安装脚本${NC}"
echo -e "${BLUE}=========================================${NC}"

# 检查Python版本
echo -e "\n${YELLOW}正在检查Python版本...${NC}"
if command -v python3 &>/dev/null; then
    python_version=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}Python版本: ${python_version}${NC}"
else
    echo -e "${RED}未找到Python3，请先安装Python 3.10或以上版本${NC}"
    exit 1
fi

# 检查Node.js版本
echo -e "\n${YELLOW}正在检查Node.js版本...${NC}"
if command -v node &>/dev/null; then
    node_version=$(node --version)
    echo -e "${GREEN}Node.js版本: ${node_version}${NC}"
else
    echo -e "${RED}未找到Node.js，请先安装Node.js 18或以上版本${NC}"
    exit 1
fi

# 检查npm版本
echo -e "\n${YELLOW}正在检查npm版本...${NC}"
if command -v npm &>/dev/null; then
    npm_version=$(npm --version)
    echo -e "${GREEN}npm版本: ${npm_version}${NC}"
else
    echo -e "${RED}未找到npm，请先安装npm${NC}"
    exit 1
fi

# 创建Python虚拟环境
echo -e "\n${YELLOW}正在创建Python虚拟环境...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}虚拟环境创建成功${NC}"
else
    echo -e "${GREEN}虚拟环境已存在${NC}"
fi

# 激活虚拟环境
echo -e "\n${YELLOW}正在激活虚拟环境...${NC}"
source venv/bin/activate || { echo -e "${RED}无法激活虚拟环境${NC}"; exit 1; }
echo -e "${GREEN}虚拟环境已激活${NC}"

# 安装后端依赖
echo -e "\n${YELLOW}正在安装后端依赖...${NC}"
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip install -U pip
pip install -r requirements.txt || { echo -e "${RED}后端依赖安装失败${NC}"; exit 1; }
echo -e "${GREEN}后端依赖安装成功${NC}"

# 安装前端依赖
echo -e "\n${YELLOW}正在安装前端依赖...${NC}"
cd STP_webui/frontend || { echo -e "${RED}无法找到前端目录${NC}"; exit 1; }

# 设置npm国内镜像
echo -e "${YELLOW}设置npm国内镜像源...${NC}"
npm config set registry https://registry.npmmirror.com/
echo -e "${GREEN}npm镜像源设置成功${NC}"

# 安装前端依赖
echo -e "${YELLOW}安装前端npm依赖...${NC}"
npm install || { echo -e "${RED}前端依赖安装失败${NC}"; exit 1; }
echo -e "${GREEN}前端依赖安装成功${NC}"

# 返回项目根目录
cd ../../

echo -e "\n${BLUE}=========================================${NC}"
echo -e "${GREEN}STP 项目依赖安装完成!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "\n${YELLOW}使用说明:${NC}"
echo -e "1. 启动后端服务: ${GREEN}bash start_services.sh${NC}"
echo -e "2. 启动前端开发服务器: ${GREEN}cd STP_webui/frontend && npm run dev${NC}"
echo -e "3. 构建前端生产版本: ${GREEN}cd STP_webui/frontend && npm run build${NC}"
echo -e "\n${GREEN}开发愉快!${NC}" 