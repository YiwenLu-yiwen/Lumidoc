FROM python:3.11-slim

WORKDIR /app

# 安装公共运行时和 LLM 模块自有依赖。
COPY requirements/service-core.txt /tmp/service-core.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --no-cache-dir -r /tmp/service-core.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/modules/llm/requirements.txt /tmp/module-requirements.txt
RUN pip install --no-cache-dir -r /tmp/module-requirements.txt

# 只复制运行所需源码和公共健康检查，不把整个仓库放入镜像。
COPY src/ /app/src/
COPY scripts/docker_healthcheck.py /app/scripts/docker_healthcheck.py

# 设置环境变量
ENV PYTHONPATH=/app
ENV LLM_SERVICE_PORT=8080
ENV PORT=8080
ENV HOST=0.0.0.0

# 暴露端口
EXPOSE ${PORT}

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "/app/scripts/docker_healthcheck.py", "http://127.0.0.1:8080/healthz"]

# 启动服务
CMD ["python", "-m", "src.modules.llm.main"]
