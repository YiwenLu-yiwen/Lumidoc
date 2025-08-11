FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制代码
COPY . .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PORT=8000
ENV HOST=0.0.0.0

# 暴露端口
EXPOSE ${PORT}

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/healthz || exit 1

# 启动服务
CMD ["python", "-m", "src.modules.llm.main"] 