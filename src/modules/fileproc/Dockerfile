FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY src/modules/fileproc/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建上传和临时目录
RUN mkdir -p /app/uploads /app/temp

# 复制应用代码
COPY src/ /app/src/
COPY .env /app/.env

# 设置环境变量
ENV PYTHONPATH=/app
ENV UPLOAD_DIR=/app/uploads
ENV TEMP_DIR=/app/temp

# 暴露端口
EXPOSE 8005

# 启动服务
CMD ["python", "-m", "src.modules.fileproc.main"] 