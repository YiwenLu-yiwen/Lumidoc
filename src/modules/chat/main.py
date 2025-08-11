#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
启动聊天服务的独立脚本
"""

import uvicorn
import sys
import os
import logging
from src.shared.logger import initialize_logging, get_logger
from fastapi import FastAPI, Depends, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import traceback
import asyncio
from pydantic import BaseModel, Field

# 确保路径正确
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 添加src/modules到系统路径
modules_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if modules_dir not in sys.path:
    sys.path.insert(0, modules_dir)

# 导入原有模块
from src.modules.chat.chat_service import app as chat_app, api_router as chat_api_router
# 更新配置导入
from src.shared.config import ChatServiceSettings
settings = ChatServiceSettings()
from src.shared.database import get_db, close_db_pool
from src.modules.chat.data_migration import migrate_old_messages_to_db

# 导入定期任务功能
from fastapi_utils.tasks import repeat_every

# 导入服务和路由
from src.modules.chat.chat_service import chat_service, migrate_old_chat_messages
from src.modules.chat.models.chat_history import ChatHistory
from src.modules.chat.models.chat_message import ChatMessage

# 导入文档相关模块
from src.shared.docs.version import get_version_info
from src.shared.docs.openapi import setup_openapi
from src.shared.health_check import health_check_router

# 配置日志
initialize_logging("chat_service")
logger = get_logger(__name__)

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"已从 {env_path} 加载环境变量")

# 创建FastAPI实例
app = FastAPI(title="聊天服务", description="提供聊天和消息处理服务")

# 设置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 把聊天服务API路由挂载到主应用
app.include_router(chat_api_router, prefix="/api")

# 添加健康检查路由
app.include_router(health_check_router)

# 设置OpenAPI
setup_openapi(app)

# 健康检查端点已在chat_service.py中通过共享HealthChecker配置

# 添加定期任务：每天自动迁移旧聊天记录
@app.on_event("startup")
@repeat_every(seconds=86400)  # 每24小时执行一次
async def migrate_old_messages_task() -> None:
    """自动迁移30天前的聊天记录到数据库"""
    logger.info("开始执行自动聊天记录迁移任务")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 执行迁移，默认迁移30天前的消息
        result = migrate_old_messages_to_db(db, days=30)
        logger.info(f"自动迁移任务完成: 已迁移 {result['messages_migrated']} 条消息")
    except Exception as e:
        logger.error(f"自动迁移任务失败: {str(e)}")
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    try:
        # 初始化服务
        # 数据库连接由shared.database模块自动管理
        
        # 注册服务
        from src.shared.service_discovery import register_service
        await register_service("chat", port=settings.port, health_check_endpoint="/health")
        
        # 迁移老聊天数据
        asyncio.create_task(migrate_old_chat_messages())
        
        logger.info("聊天服务启动成功")
    except Exception as e:
        logger.error(f"聊天服务启动失败: {str(e)}")
        traceback.print_exc()
        # 不要直接退出，让服务继续运行

@app.on_event("shutdown")
async def shutdown_event():
    try:
        # 关闭数据库连接池
        await close_db_pool()
        
        # 注销服务
        from src.shared.service_discovery import unregister_service
        await unregister_service("chat")
        
        logger.info("聊天服务关闭")
    except Exception as e:
        logger.error(f"聊天服务关闭失败: {str(e)}")

# 获取版本信息
@app.get("/version", tags=["基础信息"])
async def version():
    return get_version_info()

# 请求模型
class ChatRequest(BaseModel):
    """聊天请求"""
    chat_history_id: str
    message: str
    model: Optional[str] = None
    stream: bool = False

class GraphEnhancedChatRequest(ChatRequest):
    """图谱增强聊天请求"""
    use_path_context: bool = Field(default=True, description="是否使用路径上下文")
    use_entity_expansion: bool = Field(default=True, description="是否使用实体扩展")

# API路由
@app.post("/api/chat", tags=["聊天"])
async def chat(request: ChatRequest):
    """标准聊天API"""
    try:
        result = await chat_service.chat(
            chat_history_id=request.chat_history_id,
            message=request.message,
            model=request.model,
            stream=request.stream
        )
        return result
    except Exception as e:
        logger.error(f"聊天处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/graph", tags=["聊天"])
async def chat_with_graph(request: GraphEnhancedChatRequest):
    """图谱增强聊天API"""
    try:
        result = await chat_service.query_with_graph_augmentation(
            chat_history_id=request.chat_history_id,
            query=request.message,
            use_path_context=request.use_path_context,
            use_entity_expansion=request.use_entity_expansion
        )
        return result
    except Exception as e:
        logger.error(f"图谱增强聊天处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 