#!/bin/bash
# 在开发环境中设置pgvector

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}开始设置pgvector扩展...${NC}"

# 检查是否已安装Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未安装Docker。请先安装Docker。${NC}"
    exit 1
fi

# 检查是否已安装docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: 未安装docker-compose。请先安装docker-compose。${NC}"
    exit 1
fi

# 检查PostgreSQL容器是否正在运行
POSTGRES_CONTAINER=$(docker ps | grep postgres | grep -v pgvector | awk '{print $1}')

if [ -z "$POSTGRES_CONTAINER" ]; then
    echo -e "${YELLOW}未找到运行中的PostgreSQL容器，将使用docker-compose启动新容器...${NC}"
    
    # 检查是否存在ankane/pgvector镜像
    if ! docker images | grep -q "ankane/pgvector"; then
        echo -e "${YELLOW}拉取ankane/pgvector镜像...${NC}"
        docker pull ankane/pgvector:latest
    fi
    
    # 启动PostgreSQL容器
    docker-compose up -d db
    
    echo -e "${GREEN}等待PostgreSQL启动...${NC}"
    sleep 5
else
    echo -e "${YELLOW}发现运行中的PostgreSQL容器: $POSTGRES_CONTAINER${NC}"
    echo -e "${YELLOW}注意: 如果该容器不支持pgvector扩展，安装可能会失败${NC}"
    echo -e "${YELLOW}建议使用ankane/pgvector镜像重新创建容器${NC}"
    
    # 询问是否继续
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}操作已取消${NC}"
        exit 0
    fi
fi

# 安装Python依赖
echo -e "${YELLOW}安装Python依赖...${NC}"
pip install asyncpg python-dotenv

# 运行安装脚本
echo -e "${YELLOW}运行pgvector安装脚本...${NC}"
python scripts/install_pgvector.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}pgvector设置完成!${NC}"
    
    # 运行测试脚本
    echo -e "${YELLOW}运行pgvector测试脚本...${NC}"
    python scripts/test_pgvector.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}pgvector测试通过!${NC}"
        echo -e "${GREEN}现在您可以使用PostgreSQL存储向量数据了。${NC}"
    else
        echo -e "${RED}pgvector测试失败。请检查错误信息。${NC}"
    fi
else
    echo -e "${RED}pgvector设置失败。请检查错误信息。${NC}"
fi 