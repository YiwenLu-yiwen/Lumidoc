#!/bin/bash

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
echo -e "${RED}"
echo "  ██████╗████████╗██████╗     ███████╗████████╗ ██████╗ ██████╗ "
echo " ██╔════╝╚══██╔══╝██╔══██╗    ██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗"
echo " ╚█████╗    ██║   ██████╔╝    ███████╗   ██║   ██║   ██║██████╔╝"
echo "  ╚═══██╗   ██║   ██╔═══╝     ╚════██║   ██║   ██║   ██║██╔═══╝ "
echo " ██████╔╝   ██║   ██║         ███████║   ██║   ╚██████╔╝██║     "
echo " ╚═════╝    ╚═╝   ╚═╝         ╚══════╝   ╚═╝    ╚═════╝ ╚═╝     "
echo -e "${RESET}"
echo -e "${CYAN}=========================== 智能文本处理平台停止工具 (Linux版) ===========================${RESET}"
echo

# 停止微服务进程
echo -e "${CYAN}========== 停止Lumidoc微服务 ==========${RESET}"

# 停止微服务函数
stop_service() {
    local name=$1
    local pattern=$2
    
    echo -ne "${YELLOW}▶ 停止${name}... ${RESET}"
    
    local pids=$(ps aux | grep -i "$pattern" | grep -v grep | awk '{print $2}')
    if [ -z "$pids" ]; then
        echo -e "${CYAN}未运行${RESET}"
        return 0
    fi
    
    for pid in $pids; do
        kill -15 $pid 2>/dev/null || kill -9 $pid 2>/dev/null
    done
    
    # 检查是否成功停止
    sleep 1
    local still_running=$(ps aux | grep -i "$pattern" | grep -v grep | awk '{print $2}')
    if [ -z "$still_running" ]; then
        echo -e "${GREEN}已停止${RESET}"
    else
        # 强制终止
        for pid in $still_running; do
            kill -9 $pid 2>/dev/null
        done
        echo -e "${RED}强制终止${RESET}"
    fi
}

# 停止前端服务
stop_service "前端服务" "npm.*run dev"

# 停止后端服务
stop_service "后端API服务" "uvicorn.*main:app"
stop_service "认证服务" "python.*src.modules.auth.main"
stop_service "文件服务" "python.*src.modules.file.main"
stop_service "聊天服务" "python.*src.modules.chat.main"
stop_service "文件处理服务" "python.*src.modules.fileproc.main"
stop_service "RAG服务" "python.*src.modules.lightraglocal.main"
stop_service "图谱服务" "python.*src.modules.graph.main"
stop_service "问题服务" "python.*src.modules.question.main"
stop_service "监控服务" "python.*src.modules.monitoring.main"
stop_service "LLM服务" "python.*src.modules.llm.main"
stop_service "项目服务" "python.*src.modules.project.main"
stop_service "API网关服务" "python.*src.modules.gateway.main"

# 停止任务管理服务
stop_service "任务管理服务" "python.*src.scripts.task_service"

# 停止任务监控服务
stop_service "任务监控服务" "python.*src.shared.task_monitor"

echo -e "${GREEN}✓ 所有微服务进程已停止${RESET}"
echo

# 清理Docker容器
echo -e "${CYAN}========== 停止基础设施服务 ==========${RESET}"

stop_container() {
    local name=$1
    local container_name=$2
    
    echo -ne "${YELLOW}▶ 停止${name}... ${RESET}"
    
    if [ "$(docker ps -q -f name=$container_name)" ]; then
        docker stop $container_name > /dev/null
        echo -e "${GREEN}已停止${RESET}"
    else
        echo -e "${CYAN}未运行${RESET}"
    fi
}

# 停止各个容器
stop_container "MinIO存储服务" "stp_minio"
stop_container "RabbitMQ消息队列" "stp_rabbitmq"
stop_container "Redis缓存服务" "stp_redis"
stop_container "Neo4j图数据库" "stp_neo4j"
stop_container "PostgreSQL数据库" "stp_postgres"

echo -e "${GREEN}✓ 所有基础设施服务已停止${RESET}"
echo

# 选择是否删除容器
echo -e "${YELLOW}是否要删除所有Docker容器？(不会删除数据卷)${RESET}"
echo -e "1) ${GREEN}是${RESET} - 删除所有Lumidoc相关容器"
echo -e "2) ${RED}否${RESET} - 保留容器下次快速启动"
echo
read -p "请选择 [2]: " delete_option
delete_option=${delete_option:-2}

if [ "$delete_option" = "1" ]; then
    echo -e "${CYAN}▶ 正在删除容器...${RESET}"
    
    for container in stp_minio stp_rabbitmq stp_redis stp_neo4j stp_postgres; do
        if [ "$(docker ps -aq -f name=$container)" ]; then
            echo -ne "${YELLOW}删除容器 ${WHITE}$container${YELLOW}... ${RESET}"
            docker rm $container > /dev/null
            echo -e "${GREEN}已删除${RESET}"
        fi
    done
    
    echo -e "${GREEN}✓ 所有容器已删除${RESET}"
fi

echo
echo -e "${GREEN}========== Lumidoc平台已完全停止 ==========${RESET}"
echo -e "${YELLOW}▶ 系统状态:${RESET}"
echo -e "  ${WHITE}微服务:${RESET} ${RED}已停止${RESET}"
echo -e "  ${WHITE}基础设施:${RESET} ${RED}已停止${RESET}"
echo

echo -e "${PURPLE}Lumidoc平台已安全关闭，感谢使用！${RESET}"
echo 