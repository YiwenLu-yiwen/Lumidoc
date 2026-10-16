#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! docker info >/dev/null 2>&1; then
    echo "Docker 未运行，请先启动 Docker。" >&2
    exit 1
fi

if [ ! -f .env ]; then
    # Generate per-installation secrets without requiring host Python.
    # Write atomically and keep credentials readable only by the current user.
    umask 077
    trap 'rm -f .env.bootstrap.tmp' EXIT HUP INT TERM
    docker run --rm -i -v "$PROJECT_DIR/.env.example:/template:ro" \
        python:3.11-slim python - > .env.bootstrap.tmp <<'PYTHON'
from pathlib import Path
import secrets
text = Path("/template").read_text()
for placeholder in (
    "change-me-postgres", "change-me-neo4j", "change-me-redis",
    "change-me-minio-user", "change-me-minio",
    "change-me-jwt-secret-at-least-32-characters",
    "change-me-internal-service-token",
):
    text = text.replace(placeholder, secrets.token_hex(24))
print(text, end="")
PYTHON
    mv .env.bootstrap.tmp .env
    trap - EXIT HUP INT TERM
    echo "已创建本地 .env 并生成独立随机凭据；已有配置不会被覆盖。"
fi

# Use the standard Compose builder; Bake can hang on some Docker installations.
export COMPOSE_BAKE=${COMPOSE_BAKE:-false}
docker compose config --quiet
# Reuse existing images on normal starts; pass --build after changing code.
docker compose up -d --wait "$@"
docker compose ps

echo "Lumidoc 已启动：http://localhost:${FRONTEND_PORT:-3000}"
echo "API Gateway：http://localhost:${GATEWAY_PORT:-8888}"
