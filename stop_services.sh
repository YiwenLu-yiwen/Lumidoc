#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

MODEL_MODE=$(cat .lumidoc-model-mode 2>/dev/null || echo cpu)
case "${1:-}" in
    --native) MODEL_MODE=native ;;
    --gpu) MODEL_MODE=gpu ;;
    --cpu) MODEL_MODE=cpu ;;
esac
export COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
case "$MODEL_MODE" in
    native) COMPOSE_FILE="$COMPOSE_FILE:$PROJECT_DIR/docker-compose.native.yml" ;;
    gpu) COMPOSE_FILE="$COMPOSE_FILE:$PROJECT_DIR/docker-compose.gpu.yml" ;;
esac

docker compose down --remove-orphans
echo "Lumidoc 已关闭；数据库、文件和模型卷均已保留。"
