FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY src/modules/fileproc/requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# 轻量级入口/诊断依赖单独分层，避免变更时重复下载 Docling 模型运行时。
COPY src/modules/fileproc/requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# 创建上传和临时目录
RUN mkdir -p /app/uploads /app/temp

# 复制应用代码
COPY src/ /app/src/
COPY scripts/docker_healthcheck.py /app/scripts/docker_healthcheck.py

# 设置环境变量
ENV PYTHONPATH=/app
ENV UPLOAD_DIR=/app/uploads
ENV TEMP_DIR=/app/temp

# 暴露端口
EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "/app/scripts/docker_healthcheck.py", "http://127.0.0.1:8005/healthz"]

# 启动服务
CMD ["python", "-m", "src.modules.fileproc.main"]
