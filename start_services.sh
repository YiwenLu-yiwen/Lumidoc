#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

MODEL_MODE=auto
case "${1:-}" in
    --native) MODEL_MODE=native; shift ;;
    --cpu) MODEL_MODE=cpu; shift ;;
    --gpu) MODEL_MODE=gpu; shift ;;
esac

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

# Probe from Docker so a host-only endpoint cannot be selected accidentally.
if [ "$MODEL_MODE" = auto ]; then
    APPLE_SILICON=0
    if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ]; then
        APPLE_SILICON=1
    fi
    if docker run --rm --env-file .env \
        --add-host host.docker.internal:host-gateway \
        -e APPLE_SILICON="$APPLE_SILICON" \
        ${NATIVE_OLLAMA_URL:+-e NATIVE_OLLAMA_URL} \
        -v "$PROJECT_DIR/scripts/detect_native_gpu.py:/probe.py:ro" \
        python:3.11-slim python /probe.py >/dev/null 2>&1; then
        MODEL_MODE=native
    elif docker run --rm --gpus all --entrypoint nvidia-smi \
        ollama/ollama:latest -L >/dev/null 2>&1; then
        MODEL_MODE=gpu
    else
        MODEL_MODE=cpu
    fi
fi

export COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
case "$MODEL_MODE" in
    native) COMPOSE_FILE="$COMPOSE_FILE:$PROJECT_DIR/docker-compose.native.yml"
        echo "模型模式：原生 Ollama（GPU 优先）" ;;
    gpu) COMPOSE_FILE="$COMPOSE_FILE:$PROJECT_DIR/docker-compose.gpu.yml"
        echo "模型模式：Docker NVIDIA GPU" ;;
    cpu) echo "模型模式：Docker CPU（未检测到可用 GPU，或已指定 --cpu）" ;;
esac

# Use the standard Compose builder; Bake can hang on some Docker installations.
export COMPOSE_BAKE=${COMPOSE_BAKE:-false}
docker compose config --quiet
# Reuse existing images on normal starts; pass --build after changing code.
docker compose up -d --wait "$@"
printf '%s\n' "$MODEL_MODE" > .lumidoc-model-mode
docker compose ps

echo "Lumidoc 已启动：http://localhost:${FRONTEND_PORT:-3000}"
echo "API Gateway：http://localhost:${GATEWAY_PORT:-8888}"
