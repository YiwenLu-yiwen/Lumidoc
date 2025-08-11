import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from src.shared.logger import initialize_logging, get_logger

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(project_root)

# 导入根目录的模块
from src.database import Base, engine, SessionLocal, init_db
from src.modules.lightrag import LightRAGService
from src.modules.graph import GraphService

# 创建FastAPI应用
app = FastAPI(
    title="STP WebUI Backend",
    description="STP WebUI后端服务",
    version="1.0.0"
)

# 配置日志
initialize_logging("webui_backend")
logger = get_logger(__name__)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
@app.on_event("startup")
async def startup():
    await init_db()

# 注册路由
from ..api import router as api_router
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Welcome to STP WebUI Backend"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 