#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

docker compose down --remove-orphans
echo "Lumidoc 已关闭；数据库、文件和模型卷均已保留。"
