FROM node:20-slim

WORKDIR /app

# 复制依赖文件
COPY package.json package-lock.json ./

# 安装依赖
RUN npm ci

# 复制所有源代码
COPY . .

# 构建生产版本
RUN npm run build

# 用于开发环境
EXPOSE 3000

# 开发模式启动命令
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"] 