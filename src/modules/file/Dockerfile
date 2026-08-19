FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY src/modules/file/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建存储目录
RUN mkdir -p /app/storage

# 复制应用代码
COPY src/ /app/src/
COPY scripts/docker_healthcheck.py /app/scripts/docker_healthcheck.py

# 设置环境变量
ENV PYTHONPATH=/app
ENV STORAGE_DIR=/app/storage

# 暴露端口
EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "/app/scripts/docker_healthcheck.py", "http://127.0.0.1:8004/healthz"]

# 启动服务
CMD ["python", "-m", "src.modules.file.main"]
