#!/usr/bin/env python3
"""
任务管理微服务
独立运行，为其他服务提供任务管理和去重功能
"""

import sys
import os
import asyncio
import signal
from pathlib import Path
import uvicorn
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# 添加项目根目录到PATH
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

# 加载项目根目录.env文件
from dotenv import load_dotenv
env_file = root_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"已从 {env_file} 加载环境变量")

# FastAPI相关导入
from fastapi import FastAPI, Request, Response, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 导入任务管理相关模块
from src.shared.task_manager import TaskManager, TaskStatus, get_task_manager
from src.shared.task_monitor import get_task_monitor, TaskMonitor
from src.shared.health_check import register_health_service
from src.shared.service_discovery import get_service_client

# 服务配置
SERVICE_NAME = os.environ.get("SERVICE_NAME", "task-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8085"))
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# 定义lifespan事件管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global task_manager, task_monitor
    
    # 启动事件
    # 初始化任务管理器
    task_manager = await get_task_manager()
    
    # 初始化任务监控器
    task_monitor = await get_task_monitor()
    
    # 注册健康检查服务
    await register_health_service(app, SERVICE_NAME)
    
    print(f"任务管理服务已启动，端口: {SERVICE_PORT}")
    
    yield
    
    # 关闭事件
    # 任务监控器关闭
    if task_monitor:
        await task_monitor.stop()
    
    print("任务管理服务已关闭")

# 创建FastAPI应用
app = FastAPI(
    title="STP Task Service",
    description="STP 任务管理服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
task_manager = None
task_monitor = None

# 依赖注入
async def get_tm():
    return await get_task_manager()

async def get_tm_monitor():
    return await get_task_monitor()


@app.get("/")
async def root():
    """根路径"""
    return {"message": "STP任务管理服务", "version": "1.0.0"}

@app.get("/healthz")
async def healthz():
    """健康检查端点 - 兼容Kubernetes标准健康检查路径"""
    return {"status": "ok"}

@app.post("/tasks/create")
async def create_task(
    request: Request,
    background_tasks: BackgroundTasks,
    tm: TaskManager = Depends(get_tm)
):
    """创建任务"""
    try:
        data = await request.json()
        task_name = data.get("task_name")
        task_params = data.get("task_params", {})
        use_sequential_id = data.get("use_sequential_id", False)
        ttl = data.get("ttl")
        task_id = data.get("task_id")
        
        if not task_name:
            raise HTTPException(status_code=400, detail="必须提供任务名称")
            
        # 创建任务
        task_id, is_new = await tm.create_task(
            task_name=task_name,
            task_params=task_params,
            task_id=task_id,
            ttl=ttl,
            use_sequential_id=use_sequential_id
        )
        
        return {
            "task_id": task_id,
            "is_new": is_new
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}")
async def get_task(task_id: str, tm: TaskManager = Depends(get_tm)):
    """获取任务状态"""
    try:
        task_info = await tm.get_task_status(task_id)
        if task_info.get("status") is None:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或已过期")
        return task_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    request: Request,
    tm: TaskManager = Depends(get_tm)
):
    """更新任务状态"""
    try:
        data = await request.json()
        status = data.get("status")
        result = data.get("result")
        error = data.get("error")
        ttl = data.get("ttl")
        
        if not status:
            raise HTTPException(status_code=400, detail="必须提供状态")
            
        # 更新状态
        success = await tm.update_task_status(
            task_id=task_id,
            status=status,
            result=result,
            error=error,
            ttl=ttl
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或无法更新")
            
        return {"message": "任务状态已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    task_name: Optional[str] = None,
    tm: TaskManager = Depends(get_tm)
):
    """获取任务列表"""
    try:
        tasks = await tm.get_active_tasks(task_name=task_name, status=status)
        return {"count": len(tasks), "tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tasks/find_by_content")
async def find_task_by_content(request: Request, tm: TaskManager = Depends(get_tm)):
    """根据任务内容查找任务"""
    try:
        data = await request.json()
        task_name = data.get("task_name")
        task_params = data.get("task_params", {})
        
        if not task_name:
            raise HTTPException(status_code=400, detail="必须提供任务名称")
            
        # 查找任务
        task_id = await tm.find_task_by_content(task_name, task_params)
        
        if not task_id:
            return {"exists": False}
            
        # 获取任务详情
        task_info = await tm.get_task_status(task_id)
        
        return {
            "exists": True,
            "task_id": task_id,
            "task_info": task_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitor/stats")
async def monitor_stats(monitor: TaskMonitor = Depends(get_tm_monitor)):
    """获取任务监控统计数据"""
    return monitor.get_stats()

@app.post("/maintenance/cleanup")
async def cleanup_tasks(tm: TaskManager = Depends(get_tm)):
    """清理过期任务"""
    try:
        max_age_days = 7  # 默认7天
        cleaned = await tm.cleanup_expired_tasks(max_age_days=max_age_days)
        return {"message": f"已清理 {cleaned} 个过期任务"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/generate_id")
async def generate_task_id(
    task_name: str,
    tm: TaskManager = Depends(get_tm)
):
    """生成唯一的任务ID"""
    try:
        task_id = await tm.generate_sequential_task_id(task_name)
        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 启动服务
def run_service():
    """启动任务管理服务"""
    uvicorn.run(
        "src.scripts.task_service:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=DEBUG_MODE,
        workers=1,
    )

if __name__ == "__main__":
    run_service() 