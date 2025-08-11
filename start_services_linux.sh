#!/bin/bash

# 检查是否在Linux上运行
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "此脚本仅支持Linux系统"
    exit 1
fi

# 定义默认值
DEFAULT_CONDA_INIT="source /opt/anaconda3/etc/profile.d/conda.sh"
DEFAULT_CONDA_ENV="Lumidoc_env"
DEFAULT_ENV_FILE=".env"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --conda-init)
            CONDA_INIT_ARG="$2"
            shift 2
            ;;
        --conda-env)
            CONDA_ENV_ARG="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE_ARG="$2"
            shift 2
            ;;
        --help)
            echo "使用方法: $0 [选项]"
            echo "选项:"
            echo "  --conda-init PATH   指定conda初始化脚本路径"
            echo "  --conda-env NAME    指定conda环境名称"
            echo "  --env-file PATH     指定环境配置文件路径"
            echo "  --help              显示此帮助信息"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# 使用参数值或默认值
CONDA_INIT=${CONDA_INIT_ARG:-$DEFAULT_CONDA_INIT}
CONDA_ENV=${CONDA_ENV_ARG:-$DEFAULT_CONDA_ENV}
# 使用命令行参数或环境变量或默认值
ENV_FILE=${ENV_FILE_ARG:-${ENV_FILE:-$DEFAULT_ENV_FILE}}

# 如果指定了环境文件，设置ENV_FILE环境变量
if [ "$ENV_FILE" != "$DEFAULT_ENV_FILE" ]; then
    export ENV_FILE
    echo "将使用环境配置文件: $ENV_FILE"
fi

# 定义颜色代码
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
RESET='\033[0m'

# ASCII艺术标志
echo -e "${BLUE}"
echo "  ██████╗████████╗██████╗     ██████╗ ██╗      █████╗ ████████╗███████╗ ██████╗ ██████╗ ███╗   ███╗"
echo " ██╔════╝╚══██╔══╝██╔══██╗    ██╔══██╗██║     ██╔══██╗╚══██╔══╝██╔════╝██╔═══██╗██╔══██╗████╗ ████║"
echo " ╚█████╗    ██║   ██████╔╝    ██████╔╝██║     ███████║   ██║   █████╗  ██║   ██║██████╔╝██╔████╔██║"
echo "  ╚═══██╗   ██║   ██╔═══╝     ██╔═══╝ ██║     ██╔══██║   ██║   ██╔══╝  ██║   ██║██╔══██╗██║╚██╔╝██║"
echo " ██████╔╝   ██║   ██║         ██║     ███████╗██║  ██║   ██║   ██║     ╚██████╔╝██║  ██║██║ ╚═╝ ██║"
echo " ╚═════╝    ╚═╝   ╚═╝         ╚═╝     ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝"
echo -e "${RESET}"
echo -e "${CYAN}=========================== 智能文本处理平台启动工具 (Linux版) ===========================${RESET}"
echo

# 输出当前配置信息
echo -e "${YELLOW}当前Conda配置:${RESET}"
echo -e "  ${WHITE}Conda初始化:${RESET} $CONDA_INIT"
echo -e "  ${WHITE}Conda环境:${RESET} $CONDA_ENV"
echo

# 获取当前目录
CURRENT_DIR=$(pwd)
LOG_DIR="$CURRENT_DIR/logs"
mkdir -p "$LOG_DIR"

# 加载环境变量
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}✓ ${RESET}从${ENV_FILE}加载配置..."
    # 将环境变量导出到当前shell
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo -e "${RED}✗ ${RESET}未找到环境配置文件: ${ENV_FILE}"
    exit 1
fi

# 输出环境信息
echo -e "${PURPLE}▶ 系统环境:${RESET} Linux $(uname -r)"
echo -e "${PURPLE}▶ 发行版:${RESET} $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')"
echo -e "${PURPLE}▶ Python:${RESET} $(python --version 2>&1)"
echo -e "${PURPLE}▶ Node:${RESET} $(node --version 2>&1)"
echo -e "${PURPLE}▶ 工作目录:${RESET} $CURRENT_DIR"
echo

# 显示启动进度
show_progress() {
    local duration=$1
    local message=$2
    local status=$3
    local i=0
    local progress_bar=""

    echo -ne "${message} ["
    while [ $i -lt 20 ]; do
        echo -ne "▓"
        sleep $(echo "$duration / 20" | bc -l 2>/dev/null || echo "0.1")
        i=$((i+1))
    done
    
    if [ "$status" == "success" ]; then
        echo -e "] ${GREEN}完成${RESET}"
    else
        echo -e "] ${RED}失败${RESET}"
    fi
}

# 检查Docker是否运行
echo -e "${CYAN}检查Docker状态...${RESET}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker未运行，请启动Docker后再试${RESET}"
    echo -e "${YELLOW}提示: 可以运行 'sudo systemctl start docker' 来启动Docker${RESET}"
    exit 1
else
    echo -e "${GREEN}✓ Docker正在运行${RESET}"
fi

# 创建Docker网络（如果不存在）
echo -e "${CYAN}配置Docker网络...${RESET}"
if ! docker network ls | grep -q stp_network; then
    echo -e "创建Docker网络 ${WHITE}stp_network${RESET}..."
    docker network create stp_network
    echo -e "${GREEN}✓ 网络创建成功${RESET}"
else
    echo -e "${GREEN}✓ 网络已存在${RESET}"
fi

echo
echo -e "${CYAN}========== 启动基础设施服务 ==========${RESET}"

# 启动PostgreSQL
echo -e "${CYAN}▶ 启动PostgreSQL数据库...${RESET}"
if [ "$(docker ps -q -f name=stp_postgres)" ]; then
    echo -e "${GREEN}✓ PostgreSQL容器已运行${RESET}"
    
    # 检查是否支持pgvector
    echo -e "${YELLOW}➤ 检查pgvector扩展支持...${RESET}"
    if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'" | grep -q '1'; then
        echo -e "${YELLOW}⚠️ 未检测到pgvector扩展，尝试安装...${RESET}"
        if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1; then
            echo -e "${RED}✗ 现有PostgreSQL容器不支持pgvector扩展${RESET}"
            echo -e "${YELLOW}➤ 停止并移除现有容器，将使用支持pgvector的镜像...${RESET}"
            docker stop stp_postgres > /dev/null
            docker rm stp_postgres > /dev/null
            
            # 创建新容器
            echo -e "${YELLOW}➤ 创建支持pgvector的PostgreSQL容器...${RESET}"
            docker run -d --name stp_postgres \
                --network stp_network \
                -e POSTGRES_USER=stpuser \
                -e POSTGRES_PASSWORD=stppassword \
                -e POSTGRES_DB=stpdb \
                -p 5432:5432 \
                -v postgres_data:/var/lib/postgresql/data \
                -v $CURRENT_DIR/scripts/setup_pgvector.sql:/docker-entrypoint-initdb.d/setup_pgvector.sql \
                ankane/pgvector:latest > /dev/null
            
            show_progress 3 "初始化支持pgvector的PostgreSQL数据库" "success"
            echo -e "${GREEN}✓ 已创建支持pgvector的PostgreSQL容器${RESET}"
        else
            echo -e "${GREEN}✓ pgvector扩展安装成功${RESET}"
            echo -e "${GREEN}✓ 向量存储准备就绪，表和索引将在服务启动时自动创建${RESET}"
        fi
    else
        echo -e "${GREEN}✓ PostgreSQL已支持pgvector扩展${RESET}"
    fi
else
    if [ "$(docker ps -aq -f name=stp_postgres)" ]; then
        # 容器存在但未运行，启动它
        docker start stp_postgres > /dev/null
        show_progress 3 "启动现有PostgreSQL容器" "success"
        
        # 检查是否支持pgvector
        echo -e "${YELLOW}➤ 检查pgvector扩展支持...${RESET}"
        if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'" | grep -q '1'; then
            echo -e "${YELLOW}⚠️ 未检测到pgvector扩展，尝试安装...${RESET}"
            if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1; then
                echo -e "${RED}✗ 现有PostgreSQL容器不支持pgvector扩展${RESET}"
                echo -e "${YELLOW}➤ 停止并移除现有容器，将使用支持pgvector的镜像...${RESET}"
                docker stop stp_postgres > /dev/null
                docker rm stp_postgres > /dev/null
                
                # 创建新容器
                echo -e "${YELLOW}➤ 创建支持pgvector的PostgreSQL容器...${RESET}"
                docker run -d --name stp_postgres \
                    --network stp_network \
                    -e POSTGRES_USER=stpuser \
                    -e POSTGRES_PASSWORD=stppassword \
                    -e POSTGRES_DB=stpdb \
                    -p 5432:5432 \
                    -v postgres_data:/var/lib/postgresql/data \
                    -v $CURRENT_DIR/scripts/setup_pgvector.sql:/docker-entrypoint-initdb.d/setup_pgvector.sql \
                    ankane/pgvector:latest > /dev/null
                
                show_progress 3 "初始化支持pgvector的PostgreSQL数据库" "success"
                echo -e "${GREEN}✓ 已创建支持pgvector的PostgreSQL容器${RESET}"
            else
                echo -e "${GREEN}✓ pgvector扩展安装成功${RESET}"
                echo -e "${GREEN}✓ 向量存储准备就绪，表和索引将在服务启动时自动创建${RESET}"
            fi
        else
            echo -e "${GREEN}✓ PostgreSQL已支持pgvector扩展${RESET}"
        fi
    else
        # 容器不存在，创建并启动
        echo -e "${YELLOW}➤ 创建支持pgvector的PostgreSQL容器...${RESET}"
        
        # 确保setup_pgvector.sql存在
        if [ ! -f "$CURRENT_DIR/scripts/setup_pgvector.sql" ]; then
            echo -e "${YELLOW}⚠️ 未找到setup_pgvector.sql，创建默认文件...${RESET}"
            mkdir -p "$CURRENT_DIR/scripts"
            cat > "$CURRENT_DIR/scripts/setup_pgvector.sql" << 'EOL'
-- 安装pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建RAG向量表（如果不存在）
CREATE TABLE IF NOT EXISTS rag_default_index_vectors (
    id SERIAL PRIMARY KEY,
    content_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    embedding vector(1024),
    metadata JSONB,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为向量创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_vectors_project_id_idx ON rag_default_index_vectors(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_vectors_content_id_idx ON rag_default_index_vectors(content_id);

-- 创建RAG文档状态表
CREATE TABLE IF NOT EXISTS rag_default_index_document_status (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档状态表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_project_id_idx ON rag_default_index_document_status(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_status_document_id_idx ON rag_default_index_document_status(document_id);

-- 创建RAG文档内容表
CREATE TABLE IF NOT EXISTS rag_default_index_document_content (
    id SERIAL PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 为文档内容表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_project_id_idx ON rag_default_index_document_content(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_document_content_document_id_idx ON rag_default_index_document_content(document_id);

-- 创建RAG关系表
CREATE TABLE IF NOT EXISTS rag_default_index_relationships (
    id SERIAL PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    project_id TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relation_type, project_id)
);

-- 为关系表创建索引
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_project_id_idx ON rag_default_index_relationships(project_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_source_id_idx ON rag_default_index_relationships(source_id);
CREATE INDEX IF NOT EXISTS rag_default_index_relationships_target_id_idx ON rag_default_index_relationships(target_id);
EOL
            echo -e "${GREEN}✓ 已创建默认setup_pgvector.sql文件${RESET}"
        fi
        
        docker run -d --name stp_postgres \
            --network stp_network \
            -e POSTGRES_USER=stpuser \
            -e POSTGRES_PASSWORD=stppassword \
            -e POSTGRES_DB=stpdb \
            -p 5432:5432 \
            -v postgres_data:/var/lib/postgresql/data \
            -v $CURRENT_DIR/scripts/setup_pgvector.sql:/docker-entrypoint-initdb.d/setup_pgvector.sql \
            ankane/pgvector:latest > /dev/null
        show_progress 3 "初始化支持pgvector的PostgreSQL数据库" "success"
    fi
    echo -e "${GREEN}✓ PostgreSQL已启动${RESET} [端口: ${WHITE}5432${RESET}]"
fi

# 启动Neo4j
echo -e "${CYAN}▶ 启动Neo4j图数据库...${RESET}"
if [ "$(docker ps -q -f name=stp_neo4j)" ]; then
    echo -e "${GREEN}✓ Neo4j容器已运行${RESET}"
else
    if [ "$(docker ps -aq -f name=stp_neo4j)" ]; then
        # 容器存在但未运行，启动它
        docker start stp_neo4j > /dev/null
        show_progress 2 "启动现有Neo4j容器" "success"
    else
        # 容器不存在，创建并启动
        echo -e "${YELLOW}➤ 创建新Neo4j容器...${RESET}"
        docker run -d --name stp_neo4j \
            --network stp_network \
            -e NEO4J_AUTH=neo4j/123456789 \
            -p 7474:7474 -p 7687:7687 \
            -v neo4j_data:/data \
            neo4j:5 > /dev/null
        show_progress 3 "初始化Neo4j图数据库" "success"
    fi
    echo -e "${GREEN}✓ Neo4j已启动${RESET} [端口: ${WHITE}7474${RESET}(HTTP), ${WHITE}7687${RESET}(Bolt)]"
fi

# 启动Redis
echo -e "${CYAN}▶ 启动Redis缓存服务...${RESET}"
if [ "$(docker ps -q -f name=stp_redis)" ]; then
    echo -e "${GREEN}✓ Redis容器已运行${RESET}"
else
    if [ "$(docker ps -aq -f name=stp_redis)" ]; then
        # 容器存在但未运行，启动它
        docker start stp_redis > /dev/null
        show_progress 1 "启动现有Redis容器" "success"
    else
        # 容器不存在，创建并启动
        echo -e "${YELLOW}➤ 创建新Redis容器...${RESET}"
        docker run -d --name stp_redis \
            --network stp_network \
            -p 6379:6379 \
            -v redis_data:/data \
            redis:7 --requirepass 123456789 > /dev/null
        show_progress 1 "初始化Redis服务" "success"
    fi
    echo -e "${GREEN}✓ Redis已启动${RESET} [端口: ${WHITE}6379${RESET}]"
fi

# 启动RabbitMQ
echo -e "${CYAN}▶ 启动RabbitMQ消息队列...${RESET}"
if [ "$(docker ps -q -f name=stp_rabbitmq)" ]; then
    echo -e "${GREEN}✓ RabbitMQ容器已运行${RESET}"
else
    if [ "$(docker ps -aq -f name=stp_rabbitmq)" ]; then
        # 容器存在但未运行，启动它
        docker start stp_rabbitmq > /dev/null
        show_progress 2 "启动现有RabbitMQ容器" "success"
    else
        # 容器不存在，创建并启动
        echo -e "${YELLOW}➤ 创建新RabbitMQ容器...${RESET}"
        docker run -d --name stp_rabbitmq \
            --network stp_network \
            -e RABBITMQ_DEFAULT_USER=guest \
            -e RABBITMQ_DEFAULT_PASS=guest \
            -p 5672:5672 \
            -p 15672:15672 \
            -v rabbitmq_data:/var/lib/rabbitmq \
            rabbitmq:3-management > /dev/null
        show_progress 3 "初始化RabbitMQ服务" "success"
    fi
    echo -e "${GREEN}✓ RabbitMQ已启动${RESET} [端口: ${WHITE}5672${RESET}(AMQP), ${WHITE}15672${RESET}(管理界面)]"
fi

# 启动MinIO
echo -e "${CYAN}▶ 启动MinIO对象存储...${RESET}"
if [ "$(docker ps -q -f name=stp_minio)" ]; then
    echo -e "${GREEN}✓ MinIO容器已运行${RESET}"
else
    if [ "$(docker ps -aq -f name=stp_minio)" ]; then
        # 容器存在但未运行，启动它
        docker start stp_minio > /dev/null
        show_progress 1 "启动现有MinIO容器" "success"
    else
        # 容器不存在，创建并启动
        echo -e "${YELLOW}➤ 创建新MinIO容器...${RESET}"
        docker run -d --name stp_minio \
            --network stp_network \
            -e MINIO_ROOT_USER=minioadmin \
            -e MINIO_ROOT_PASSWORD=minioadmin \
            -p 9000:9000 -p 9001:9001 \
            -v minio_data:/data \
            minio/minio server /data --console-address ":9001" > /dev/null
        
        show_progress 2 "初始化MinIO服务" "success"
        
        # 创建默认存储桶
        echo -e "${YELLOW}➤ 初始化MinIO存储桶...${RESET}"
        docker run --rm \
            --network stp_network \
            -e MC_HOST_minio=http://minioadmin:minioadmin@stp_minio:9000 \
            minio/mc mb minio/data --ignore-existing > /dev/null 2>&1 || true
    fi
    echo -e "${GREEN}✓ MinIO已启动${RESET} [端口: ${WHITE}9000${RESET}(API), ${WHITE}9001${RESET}(控制台)]"
fi

# 更新环境变量中的数据库连接信息
export POSTGRES_HOST=localhost
export NEO4J_HOST=localhost
export REDIS_HOST=localhost
export RABBITMQ_HOST=localhost
export S3_ENDPOINT=http://localhost:9000
export POSTGRES_URL="postgresql://stpuser:stppassword@localhost:5432/stpdb"

echo -e "${GREEN}✓ 所有基础设施容器已启动${RESET}"
echo

echo -e "${CYAN}========== 启动Lumidoc微服务 ==========${RESET}"

# 检查并释放端口函数
check_and_free_port() {
    local port=$1
    local service_name=$2
    echo -ne "${YELLOW}检查端口 ${WHITE}${port}${YELLOW} (${service_name})... ${RESET}"
    
    if command -v lsof >/dev/null 2>&1; then
        if lsof -i :$port > /dev/null 2>&1; then
            echo -e "${RED}已占用${RESET}"
            # 获取占用端口的进程ID
            local pid=$(lsof -ti :$port)
            if [ ! -z "$pid" ]; then
                echo -ne "${YELLOW}释放端口 ${port} (进程ID: ${pid})... ${RESET}"
                kill -9 $pid > /dev/null 2>&1
                sleep 1
                echo -e "${GREEN}已释放${RESET}"
            fi
        else
            echo -e "${GREEN}可用${RESET}"
        fi
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -tuln | grep ":$port " > /dev/null 2>&1; then
            echo -e "${RED}已占用${RESET}"
            # 使用ss或netstat查找进程
            if command -v ss >/dev/null 2>&1; then
                local pid=$(ss -tlnp | grep ":$port " | sed 's/.*pid=\([0-9]*\).*/\1/' | head -1)
            else
                local pid=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d/ -f1 | head -1)
            fi
            if [ ! -z "$pid" ] && [ "$pid" != "-" ]; then
                echo -ne "${YELLOW}释放端口 ${port} (进程ID: ${pid})... ${RESET}"
                kill -9 $pid > /dev/null 2>&1
                sleep 1
                echo -e "${GREEN}已释放${RESET}"
            else
                echo -e "${YELLOW}无法获取进程ID${RESET}"
            fi
        else
            echo -e "${GREEN}可用${RESET}"
        fi
    else
        echo -e "${YELLOW}跳过检查${RESET}"
    fi
}

# 从URL中提取端口
extract_port() {
    local url=$1
    local default=$2
    if [[ $url =~ :[0-9]+(/|$) ]]; then
        echo $url | sed -E 's/.*:([0-9]+).*/\1/'
    else
        echo $default
    fi
}

# 提取各服务端口
GATEWAY_PORT=$(extract_port "${API_GATEWAY_URL:-http://localhost:8888}" 8888)
PROJECT_PORT=$(extract_port "${PROJECT_SERVICE_URL:-http://localhost:8020}" 8020)
AUTH_PORT=$(extract_port "${AUTH_SERVICE_URL:-http://localhost:8007}" 8007)
FILE_PORT=$(extract_port "${FILE_SERVICE_URL:-http://localhost:8004}" 8004)
CHAT_PORT=$(extract_port "${CHAT_SERVICE_URL:-http://localhost:8001}" 8001)
FILEPROC_PORT=$(extract_port "${FILEPROC_SERVICE_URL:-http://localhost:8005}" 8005)
RAG_PORT=$(extract_port "${RAG_SERVICE_URL:-http://localhost:8006}" 8006)
GRAPH_PORT=$(extract_port "${GRAPH_SERVICE_URL:-http://localhost:8003}" 8003)
QUESTION_PORT=$(extract_port "${QUESTION_SERVICE_URL:-http://localhost:8002}" 8002)
MONITORING_PORT=$(extract_port "${MONITORING_SERVICE_URL:-http://localhost:8008}" 8008)
LLM_PORT=$(extract_port "${LLM_SERVICE_URL:-http://localhost:8080}" 8080)
TASK_SERVICE_PORT=$(extract_port "${TASK_SERVICE_URL:-http://localhost:8085}" 8085)
FRONTEND_PORT=3000
BACKEND_PORT=8000

# 检查并释放端口
echo -e "${CYAN}▶ 检查服务端口状态...${RESET}"
check_and_free_port $GATEWAY_PORT "API网关服务"
check_and_free_port $BACKEND_PORT "主后端服务"
check_and_free_port $AUTH_PORT "认证服务"
check_and_free_port $FILE_PORT "文件服务"
check_and_free_port $CHAT_PORT "聊天服务"
check_and_free_port $FILEPROC_PORT "文件处理服务"
check_and_free_port $RAG_PORT "RAG服务"
check_and_free_port $GRAPH_PORT "图谱服务"
check_and_free_port $QUESTION_PORT "问题服务"
check_and_free_port $MONITORING_PORT "监控服务"
check_and_free_port $LLM_PORT "LLM服务"
check_and_free_port $FRONTEND_PORT "前端服务"
check_and_free_port $PROJECT_PORT "项目服务"
check_and_free_port $TASK_SERVICE_PORT "任务管理服务"

# 服务启动函数
start_service() {
    local name=$1
    local port=$2
    local command=$3
    local log_file=$4
    
    echo -e "${CYAN}▶ 启动${name}${RESET} [端口: ${WHITE}${port}${RESET}]"
    nohup bash -c "$command" > "$log_file" 2>&1 &
    local pid=$!
    echo -ne "  "
    show_progress 1 "服务启动中" "success"
    echo -e "  ${GREEN}✓ 已启动${RESET} [PID: ${WHITE}$pid${RESET}] [日志: ${WHITE}$log_file${RESET}]"
}

# 启动微服务
echo -e "${CYAN}▶ 正在启动Lumidoc微服务...${RESET}"

# 启动API网关服务
start_service "API网关服务" $GATEWAY_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.gateway.main --port $GATEWAY_PORT" \
    "$LOG_DIR/gateway.log"

# 启动主后端服务
start_service "主后端服务" $BACKEND_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR/Lumidoc_webui/backend' && PYTHONPATH=$CURRENT_DIR uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT" \
    "$LOG_DIR/backend.log"

# 启动认证服务
start_service "认证服务" $AUTH_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.auth.main --port $AUTH_PORT" \
    "$LOG_DIR/auth.log"

# 启动文件服务
start_service "文件服务" $FILE_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.file.main --port $FILE_PORT" \
    "$LOG_DIR/file.log"

# 启动聊天服务
start_service "聊天服务" $CHAT_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.chat.main --port $CHAT_PORT" \
    "$LOG_DIR/chat.log"

# 启动文件处理服务
start_service "文件处理服务" $FILEPROC_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.fileproc.main --port $FILEPROC_PORT" \
    "$LOG_DIR/fileproc.log"

# 启动LightRAG服务
echo -e "${CYAN}▶ 配置LightRAG服务...${RESET}"

# 确保.env文件中的FAISS_STORAGE_MODE设置正确
if grep -q "FAISS_STORAGE_MODE" "$ENV_FILE"; then
    current_mode=$(grep "FAISS_STORAGE_MODE" "$ENV_FILE" | cut -d= -f2)
    echo -e "${YELLOW}➤ 当前FAISS存储模式: ${current_mode}${RESET}"
    
    # 如果使用POSTGRES模式，确保pgvector已安装
    if [[ "$current_mode" == "POSTGRES" ]]; then
        echo -e "${YELLOW}➤ 检查PostgreSQL是否支持pgvector...${RESET}"
        if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'" | grep -q '1'; then
            echo -e "${RED}⚠️ PostgreSQL未安装pgvector扩展，但FAISS_STORAGE_MODE设置为POSTGRES${RESET}"
            echo -e "${YELLOW}➤ 尝试安装pgvector扩展...${RESET}"
            
            if ! docker exec stp_postgres psql -U stpuser -d stpdb -c "CREATE EXTENSION IF NOT EXISTS vector;" > /dev/null 2>&1; then
                echo -e "${RED}✗ 无法安装pgvector扩展。将FAISS_STORAGE_MODE修改为LOCAL${RESET}"
                sed -i "s/FAISS_STORAGE_MODE=POSTGRES/FAISS_STORAGE_MODE=LOCAL/" "$ENV_FILE"
                echo -e "${YELLOW}➤ 已将FAISS_STORAGE_MODE修改为LOCAL${RESET}"
            else
                echo -e "${GREEN}✓ pgvector扩展安装成功${RESET}"
                echo -e "${GREEN}✓ 向量存储准备就绪，表和索引将在服务启动时自动创建${RESET}"
            fi
        else
            echo -e "${GREEN}✓ PostgreSQL已支持pgvector扩展${RESET}"
        fi
    fi
else
    # 未找到FAISS_STORAGE_MODE配置，添加默认配置
    echo -e "${YELLOW}➤ 未找到FAISS_STORAGE_MODE配置，添加默认值...${RESET}"
    
    # 检查PostgreSQL是否支持pgvector
    if docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'" | grep -q '1'; then
        echo -e "${GREEN}✓ 检测到PostgreSQL支持pgvector扩展，设置FAISS_STORAGE_MODE=POSTGRES${RESET}"
        echo "FAISS_STORAGE_MODE=POSTGRES" >> "$ENV_FILE"
    else
        echo -e "${YELLOW}➤ PostgreSQL不支持pgvector扩展，设置FAISS_STORAGE_MODE=LOCAL${RESET}"
        echo "FAISS_STORAGE_MODE=LOCAL" >> "$ENV_FILE"
    fi
    
    # 添加其他默认FAISS配置
    if ! grep -q "FAISS_INDEX_TYPE" "$ENV_FILE"; then
        echo "FAISS_INDEX_TYPE=FLAT" >> "$ENV_FILE"
    fi
    if ! grep -q "FAISS_USE_GPU" "$ENV_FILE"; then
        echo "FAISS_USE_GPU=false" >> "$ENV_FILE"
    fi
    if ! grep -q "FAISS_NUM_PARTITIONS" "$ENV_FILE"; then
        echo "FAISS_NUM_PARTITIONS=1" >> "$ENV_FILE"
    fi
    
    echo -e "${GREEN}✓ FAISS配置已添加到${ENV_FILE}文件${RESET}"
fi

# 启动LightRAG服务
start_service "LightRAG服务" $RAG_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.lightraglocal.main --port $RAG_PORT" \
    "$LOG_DIR/lightrag.log"

# 启动图服务
start_service "图谱服务" $GRAPH_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.graph.main --port $GRAPH_PORT" \
    "$LOG_DIR/graph.log"

# 启动问题服务
start_service "问题服务" $QUESTION_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.question.main --port $QUESTION_PORT" \
    "$LOG_DIR/question.log"

# 启动监控服务
start_service "监控服务" $MONITORING_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.monitoring.main --port $MONITORING_PORT" \
    "$LOG_DIR/monitoring.log"

# 启动LLM服务
start_service "LLM服务" $LLM_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.llm.main --port $LLM_PORT" \
    "$LOG_DIR/llm_service.log"

# 启动任务管理服务
start_service "任务管理服务" $TASK_SERVICE_PORT \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.scripts.task_service" \
    "$LOG_DIR/task_service.log"

# 启动任务监控服务
start_service "任务监控服务" "N/A" \
    "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.shared.task_monitor" \
    "$LOG_DIR/task_monitor.log"

# 启动前端服务
echo -e "${CYAN}▶ 启动前端服务${RESET} [端口: ${WHITE}$FRONTEND_PORT${RESET}]"
nohup bash -c "cd '$CURRENT_DIR/Lumidoc_webui/frontend' && npm run dev -- --host 0.0.0.0" > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo -ne "  "
show_progress 2 "前端启动中" "success"
echo -e "  ${GREEN}✓ 前端已启动${RESET} [PID: ${WHITE}$FRONTEND_PID${RESET}] [日志: ${WHITE}$LOG_DIR/frontend.log${RESET}]"

# 启动项目服务
echo -e "${CYAN}▶ 启动项目服务...${RESET}"
if [ "$(pgrep -f 'python.*src.modules.project.main')" ]; then
    echo -e "  ${YELLOW}! 项目服务已在运行${RESET}"
else
    # 根据存储类型决定是否创建本地目录
    if [ "${STORAGE_TYPE:-local}" == "local" ]; then
        # 本地存储模式：创建必要的目录结构
        mkdir -p "$UPLOAD_DIR"
        mkdir -p "$CONTENT_DIR"
        mkdir -p "$RAG_DIR"
        mkdir -p "$MODELS_DIR"
        echo -e "  ${GREEN}✓ 本地存储目录已创建${RESET}"
        echo -e "    - 上传目录: ${UPLOAD_DIR}"
        echo -e "    - 内容目录: ${CONTENT_DIR}"
        echo -e "    - RAG目录: ${RAG_DIR}"
        echo -e "    - 模型目录: ${MODELS_DIR}"
    else
        # S3/MinIO存储模式：不创建本地目录
        echo -e "  ${YELLOW}✓ 使用S3/MinIO存储，跳过本地目录创建${RESET}"
        echo -e "    - 存储类型: ${STORAGE_TYPE}"
        echo -e "    - S3 Bucket: ${S3_BUCKET:-data}"
        echo -e "    - S3 Endpoint: ${S3_ENDPOINT:-http://localhost:9000}"
    fi
    
    # 启动项目服务，确保使用正确的端口
    start_service "项目服务" $PROJECT_PORT \
        "$CONDA_INIT && conda activate $CONDA_ENV && cd '$CURRENT_DIR' && PYTHONPATH=$CURRENT_DIR python -m src.modules.project.main --port $PROJECT_PORT" \
        "$LOG_DIR/project_service.log"
    
    # 等待服务启动
    sleep 2
    if [ "$(pgrep -f 'python.*src.modules.project.main')" ]; then
        echo -e "  ${GREEN}✓ 项目服务启动成功，端口: ${PROJECT_PORT}${RESET}"
    else
        echo -e "  ${RED}✗ 项目服务启动失败，请检查日志${RESET}"
    fi
fi

echo
echo -e "${GREEN}========== Lumidoc平台启动成功 ==========${RESET}"
echo -e "${CYAN}▶ 系统状态:${RESET}"
echo -e "  ${WHITE}基础设施:${RESET} ${GREEN}已启动${RESET} (PostgreSQL, Neo4j, Redis, RabbitMQ, MinIO)"
echo -e "  ${WHITE}微服务:${RESET} ${GREEN}已启动${RESET} (12个微服务)"
echo -e "  ${WHITE}前端:${RESET} ${GREEN}已启动${RESET} (http://localhost:$FRONTEND_PORT)"

# 添加FAISS存储模式信息
current_faiss_mode=$(grep "FAISS_STORAGE_MODE" "$ENV_FILE" | cut -d= -f2)
faiss_index_type=$(grep "FAISS_INDEX_TYPE" "$ENV_FILE" | cut -d= -f2)
echo -e "${YELLOW}▶ RAG向量存储配置:${RESET}"
echo -e "  ${WHITE}存储模式:${RESET} ${GREEN}${current_faiss_mode}${RESET}"
echo -e "  ${WHITE}索引类型:${RESET} ${GREEN}${faiss_index_type}${RESET}"

# 如果使用POSTGRES模式，显示pgvector状态
if [[ "$current_faiss_mode" == "POSTGRES" ]]; then
    if docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'" | grep -q '1'; then
        vector_version=$(docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'" -t | tr -d '[:space:]')
        echo -e "  ${WHITE}pgvector版本:${RESET} ${GREEN}${vector_version}${RESET}"
        
        # 检查是否已创建向量表
        if docker exec stp_postgres psql -U stpuser -d stpdb -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'rag_default_index_vectors'" -t | grep -q '1'; then
            echo -e "  ${WHITE}向量表状态:${RESET} ${GREEN}已创建${RESET}"
        else
            echo -e "  ${WHITE}向量表状态:${RESET} ${YELLOW}未创建${RESET}"
        fi
    else
        echo -e "  ${WHITE}pgvector状态:${RESET} ${RED}未安装${RESET} (将使用本地存储)"
    fi
fi

echo
echo -e "${YELLOW}▶ 访问地址:${RESET}"
echo -e "  ${WHITE}前端:${RESET} ${BLUE}http://localhost:$FRONTEND_PORT${RESET}"
echo -e "  ${WHITE}API:${RESET} ${BLUE}http://localhost:$BACKEND_PORT/docs${RESET}"
echo -e "  ${WHITE}Neo4j浏览器:${RESET} ${BLUE}http://localhost:7474${RESET}"
echo -e "  ${WHITE}MinIO控制台:${RESET} ${BLUE}http://localhost:9001${RESET}"
echo
echo -e "${YELLOW}▶ 操作提示:${RESET}"
echo -e "  ${WHITE}查看日志:${RESET} ${CYAN}tail -f logs/*.log${RESET}"
echo -e "  ${WHITE}停止所有服务:${RESET} ${CYAN}bash stop_services_linux.sh${RESET}"
echo -e "  ${WHITE}检查RAG索引:${RESET} ${CYAN}curl http://localhost:$RAG_PORT/rag/files/42${RESET}"
echo
echo -e "${PURPLE}Lumidoc平台已准备就绪，祝您使用愉快！${RESET}"
echo 