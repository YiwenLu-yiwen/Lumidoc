FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 公共运行时与 Gateway 模块依赖分层，保持模块边界。
COPY requirements/service-core.txt /tmp/service-core.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r /tmp/service-core.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/modules/gateway/requirements.txt /tmp/module-requirements.txt
RUN pip install --no-cache-dir -r /tmp/module-requirements.txt

# 复制源代码
COPY src/ /app/src/
COPY scripts/docker_healthcheck.py /app/scripts/docker_healthcheck.py

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python", "/app/scripts/docker_healthcheck.py", "http://127.0.0.1:8888/healthz"]

# 启动命令
CMD ["python", "-m", "src.modules.gateway.main", "--host", "0.0.0.0", "--port", "8888"]
