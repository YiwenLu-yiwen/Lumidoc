#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! docker info >/dev/null 2>&1; then
    echo "Docker 未运行，请先启动 Docker。" >&2
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "已从 .env.example 创建本地 .env；公开部署前请替换 change-me 凭据。"
fi

docker compose config --quiet
docker compose up -d --build --wait
docker compose ps

echo "Lumidoc 已启动：http://localhost:${FRONTEND_PORT:-3000}"
echo "API Gateway：http://localhost:${GATEWAY_PORT:-8888}"
