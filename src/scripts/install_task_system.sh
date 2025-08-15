#!/bin/bash

# STP 任务系统安装和部署脚本
# 此脚本用于部署任务管理系统修复和监控工具

# 输出颜色配置
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 恢复默认颜色

# 检查脚本是否在项目根目录下运行
if [ ! -d "src" ] || [ ! -f ".env" ]; then
  echo -e "${RED}错误: 请在项目根目录下运行此脚本${NC}"
  exit 1
fi

echo -e "${BLUE}========== STP任务系统安装与部署 ==========${NC}"
echo -e "${BLUE}当前工作目录: $(pwd)${NC}"

# 确保python环境可用
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}错误: 未找到 python3 命令${NC}"
  exit 1
fi

# 验证Redis可用性
echo -e "${YELLOW}验证Redis可用性...${NC}"
REDIS_HOST=$(grep "REDIS_HOST" .env | cut -d '=' -f2)
REDIS_PORT=$(grep "REDIS_PORT" .env | cut -d '=' -f2)
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

if ! command -v redis-cli &>/dev/null; then
  echo -e "${YELLOW}警告: 未找到redis-cli工具，无法验证Redis连接${NC}"
else
  if echo PING | redis-cli -h $REDIS_HOST -p $REDIS_PORT | grep -q PONG; then
    echo -e "${GREEN}Redis连接正常${NC}"
  else
    echo -e "${RED}无法连接到Redis服务器 $REDIS_HOST:$REDIS_PORT${NC}"
    echo -e "${YELLOW}请确保Redis服务已启动并配置正确${NC}"
    read -p "是否继续安装? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      exit 1
    fi
  fi
fi

# 安装任务系统依赖
echo -e "${YELLOW}安装任务系统依赖...${NC}"
pip3 install redis aioredis httpx psutil fastapi uvicorn

# 检查脚本是否可执行
echo -e "${YELLOW}设置脚本可执行权限...${NC}"
chmod +x src/scripts/task_repair.py
chmod +x src/scripts/task_service.py
chmod +x src/scripts/install_task_system.sh

# 创建任务监控服务文件
echo -e "${YELLOW}创建任务监控服务文件...${NC}"
cat > task_monitor.service << EOF
[Unit]
Description=STP Task Monitor Service
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(which python3) -m src.shared.task_monitor
Restart=on-failure
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=stp-task-monitor
Environment="PYTHONPATH=$(pwd)"

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}任务监控服务文件已创建: $(pwd)/task_monitor.service${NC}"

# 创建任务服务文件
echo -e "${YELLOW}创建任务服务文件...${NC}"
cat > task_service.service << EOF
[Unit]
Description=STP Task Management Service
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(which python3) -m src.scripts.task_service
Restart=on-failure
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=stp-task-service
Environment="PYTHONPATH=$(pwd)"
Environment="SERVICE_PORT=8085"

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}任务服务文件已创建: $(pwd)/task_service.service${NC}"

# 注意：任务系统已集成到主启动脚本，不再需要单独创建启动脚本
echo -e "${YELLOW}注意: 任务系统已集成到主启动脚本 (start_services.sh/start_servicesLocal.sh)${NC}"
echo -e "${GREEN}无需单独启动任务系统，将在启动平台时自动启动${NC}"

# 以下为参考，但不再实际创建独立启动脚本
: <<'COMMENT'
# 创建启动脚本
echo -e "${YELLOW}创建快捷启动脚本...${NC}"
cat > start_task_system.sh << EOF
#!/bin/bash

# 启动任务管理系统
echo "正在启动任务管理系统..."

# 启动任务服务
echo "启动任务管理服务..."
nohup python3 -m src.scripts.task_service > logs/task_service.log 2>&1 &
echo \$! > task_service.pid
echo "任务管理服务已启动，PID: \$(cat task_service.pid)"

# 启动任务监控
echo "启动任务监控服务..."
nohup python3 -m src.shared.task_monitor > logs/task_monitor.log 2>&1 &
echo \$! > task_monitor.pid
echo "任务监控服务已启动，PID: \$(cat task_monitor.pid)"

echo "任务管理系统已启动"
EOF

chmod +x start_task_system.sh
echo -e "${GREEN}快捷启动脚本已创建: $(pwd)/start_task_system.sh${NC}"

# 创建停止脚本
echo -e "${YELLOW}创建停止脚本...${NC}"
cat > stop_task_system.sh << EOF
#!/bin/bash

# 停止任务管理系统
echo "正在停止任务管理系统..."

# 停止任务服务
if [ -f task_service.pid ]; then
  pid=\$(cat task_service.pid)
  if ps -p \$pid > /dev/null; then
    echo "停止任务管理服务 (PID: \$pid)..."
    kill \$pid
    sleep 2
    if ps -p \$pid > /dev/null; then
      echo "强制停止任务管理服务..."
      kill -9 \$pid
    fi
  else
    echo "任务管理服务不在运行状态"
  fi
  rm task_service.pid
else
  echo "找不到任务管理服务PID文件"
fi

# 停止任务监控
if [ -f task_monitor.pid ]; then
  pid=\$(cat task_monitor.pid)
  if ps -p \$pid > /dev/null; then
    echo "停止任务监控服务 (PID: \$pid)..."
    kill \$pid
    sleep 2
    if ps -p \$pid > /dev/null; then
      echo "强制停止任务监控服务..."
      kill -9 \$pid
    fi
  else
    echo "任务监控服务不在运行状态"
  fi
  rm task_monitor.pid
else
  echo "找不到任务监控服务PID文件"
fi

echo "任务管理系统已停止"
EOF

chmod +x stop_task_system.sh
echo -e "${GREEN}停止脚本已创建: $(pwd)/stop_task_system.sh${NC}"
COMMENT

# 确保日志目录存在
echo -e "${YELLOW}创建日志目录...${NC}"
mkdir -p logs
chmod 755 logs

# 注册环境变量
echo -e "${YELLOW}更新环境变量...${NC}"
if ! grep -q "TASK_MONITOR_INTERVAL" .env; then
  echo "" >> .env
  echo "# 任务管理系统配置" >> .env
  echo "TASK_MONITOR_INTERVAL=60" >> .env
  echo "MAX_TASK_AGE=86400" >> .env
  echo "TASK_STALL_THRESHOLD=3600" >> .env
  echo "AUTO_RESET_STALLED=true" >> .env
  echo "AUTO_REPAIR_TASKS=false" >> .env
  echo "TASK_SERVICE_URL=http://localhost:8085" >> .env
  echo -e "${GREEN}已添加任务管理系统环境变量到.env文件${NC}"
fi

# 运行诊断脚本
echo -e "${YELLOW}运行任务系统诊断...${NC}"
python3 -m src.scripts.task_repair analyze --output logs/task_analysis.json

# 安装完成
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}任务管理系统安装完成!${NC}"
echo -e "${BLUE}任务系统已集成到STP平台:${NC}"
echo -e "${YELLOW}  bash start_services.sh${NC} - 启动STP平台（包含任务系统）"
echo -e "${YELLOW}  bash stop_services.sh${NC} - 停止STP平台（包含任务系统）"
echo -e "${YELLOW}  python3 -m src.scripts.task_repair analyze${NC} - 分析任务系统"
echo -e "${YELLOW}  python3 -m src.scripts.task_repair repair${NC} - 修复任务系统问题"
echo -e "${YELLOW}  python3 -m src.scripts.task_repair show <任务ID>${NC} - 查看任务详情"
echo -e "${GREEN}========================================${NC}" 