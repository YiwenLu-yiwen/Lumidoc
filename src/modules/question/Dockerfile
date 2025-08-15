FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/modules/question_generator/ /app/
COPY src/core/ /app/core/
COPY src/services/ /app/services/

# 设置环境变量
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8002

# 启动命令
CMD ["python", "question_service.py"] 