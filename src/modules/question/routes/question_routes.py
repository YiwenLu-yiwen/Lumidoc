from fastapi import APIRouter, HTTPException, Depends, Body, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from src.shared.auth import get_current_user
import httpx
from src.modules.config import settings
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from src.shared.types.response import ApiResponse
from src.shared.health_check import create_health_checker, register_health_routes
# 健康检查已在main.py中统一注册
import json

# 定义lifespan事件管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    try:
        await health_checker.start()
        logger.info("Question服务启动成功")

        # 注册到服务发现
        from src.shared.service_discovery import register_service
        await register_service("question", port=8002, health_check_endpoint="/healthz")

    except Exception as e:
        logger.error(f"Question服务启动失败: {str(e)}")

    yield

    # 关闭事件
    try:
        await health_checker.stop()
        logger.info("Question服务关闭")

        # 从服务发现注销
        from src.shared.service_discovery import unregister_service
        await unregister_service("question")

    except Exception as e:
        logger.error(f"Question服务关闭失败: {str(e)}")

# 创建FastAPI应用
app = FastAPI(
    title="Question Service",
    description="问题服务",
    lifespan=lifespan
)

# 创建路由
router = APIRouter(prefix="/api/question", tags=["question"])
logger = logging.getLogger(__name__)

# 健康检查器已在main.py中创建

# 添加健康检查（检查数据库连接）
async def check_database_connection():
    """检查数据库连接"""
    try:
        from src.shared.database import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"数据库连接检查失败: {str(e)}")
        return False

# 添加Question服务连接检查
async def check_question_service():
    """检查Question服务基本功能（不调用自身）"""
    try:
        # 检查基本功能而不是调用自身的健康检查
        # 简单检查：验证可以创建httpx客户端
        async with httpx.AsyncClient():
            # 不实际发送请求，只验证客户端创建
            pass
        return True
    except Exception as e:
        logger.error(f"Question服务基本功能检查失败: {str(e)}")
        return False

# 创建健康检查器
health_checker = create_health_checker("question", "question_service_1")

# 配置健康检查项
health_checker.add_check("database", check_database_connection, critical=True)
health_checker.add_check("question_service", check_question_service, critical=True)

# 注册统一健康检查路由
register_health_routes(app, health_checker)

# 添加聊天流API端点 - 直接添加到app而不是router，使路径为/chat/stream
@app.post("/chat/stream")
async def mock_chat_stream(request: Request):
    """
    模拟聊天流接口，用于测试
    非流式版本 - 返回普通JSON
    """
    try:
        # 获取请求数据
        data = await request.json()
        content = data.get("content", "")
        project_id = data.get("project_id", "")
        user_id = data.get("user_id", "")

        # 记录请求信息
        print(f"接收到聊天流请求: project_id={project_id}, user_id={user_id}, content={content[:30]}...")
        logging.info(f"接收到聊天流请求: project_id={project_id}, user_id={user_id}, content={content[:30]}...")

        # 返回JSON字符串格式的响应，而不是Python字典
        response_json = json.dumps({
            "success": True,
            "response": f"这是对'{content}'的回复，来自项目{project_id}，用户{user_id}",
            "message_id": "mock-msg-123456"
        })

        # 使用Response而不是返回dict，确保Content-Type正确
        return Response(
            content=response_json,
            media_type="application/json"
        )
    except Exception as e:
        error_msg = f"模拟聊天流错误: {str(e)}"
        print(error_msg)
        logging.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

# 添加聊天历史API端点 - 直接添加到app而不是router
@app.get("/chat/history/{project_id}")
async def mock_chat_history(project_id: str):
    """
    模拟获取聊天历史接口，用于测试
    """
    print(f"接收到获取聊天历史请求: project_id={project_id}")
    logging.info(f"接收到获取聊天历史请求: project_id={project_id}")
    return []  # 返回空数组表示没有聊天历史

# 添加聊天历史更新API端点
@app.post("/chat/history/update")
async def mock_update_chat_history(request: Request):
    """
    模拟更新聊天历史接口，用于测试
    """
    try:
        data = await request.json()
        project_id = data.get("project_id", "")
        messages = data.get("messages", [])

        print(f"接收到更新聊天历史请求: project_id={project_id}, messages_count={len(messages)}")
        logging.info(f"接收到更新聊天历史请求: project_id={project_id}, messages_count={len(messages)}")

        return {
            "success": True,
            "message": "Chat history updated successfully"
        }
    except Exception as e:
        error_msg = f"模拟更新聊天历史错误: {str(e)}"
        print(error_msg)
        logging.error(error_msg)
        return JSONResponse(
            status_code=500,
            content={"error": error_msg}
        )

# 创建路由
router = APIRouter(prefix="/api/questions", tags=["questions"])
logger = logging.getLogger(__name__)

# 获取问题服务客户端
async def get_question_service():
    """获取问题服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

async def handle_service_response(response: httpx.Response, operation: str) -> Dict[str, Any]:
    """统一处理服务响应"""
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"{operation} failed with status {e.response.status_code}: {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Question service error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"{operation} failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{project_id}/ask", response_model=ApiResponse)
async def ask_question(
    project_id: str,
    question: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client=Depends(get_question_service)
):
    """提问"""
    logger.info(f"Asking question for project {project_id} for user {user.id}")
    try:
        response = await client.post(
            f"{settings.question_service_url}/ask/{project_id}",
            json=question
        )
        return await handle_service_response(response, "Ask question")
    except Exception as e:
        logger.error(f"Failed to ask question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/history", response_model=List[Dict[str, Any]])
async def get_question_history(
    project_id: str,
    limit: Optional[int] = 100,
    user=Depends(get_current_user),
    client=Depends(get_question_service)
):
    """获取问题历史"""
    logger.info(f"Getting question history for project {project_id} for user {user.id}")
    try:
        params = {}
        if limit:
            params["limit"] = limit

        response = await client.get(
            f"{settings.question_service_url}/history/{project_id}",
            params=params
        )
        return await handle_service_response(response, "Get question history")
    except Exception as e:
        logger.error(f"Failed to get question history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}/history/{question_id}", response_model=ApiResponse)
async def delete_question(
    project_id: str,
    question_id: str,
    user=Depends(get_current_user),
    client=Depends(get_question_service)
):
    """删除问题"""
    logger.info(f"Deleting question {question_id} for project {project_id} for user {user.id}")
    try:
        response = await client.delete(
            f"{settings.question_service_url}/history/{project_id}/{question_id}"
        )
        return await handle_service_response(response, "Delete question")
    except Exception as e:
        logger.error(f"Failed to delete question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/feedback", response_model=ApiResponse)
async def submit_feedback(
    project_id: str,
    feedback: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    client=Depends(get_question_service)
):
    """提交反馈"""
    logger.info(f"Submitting feedback for project {project_id} for user {user.id}")
    try:
        response = await client.post(
            f"{settings.question_service_url}/feedback/{project_id}",
            json=feedback
        )
        return await handle_service_response(response, "Submit feedback")
    except Exception as e:
        logger.error(f"Failed to submit feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 注册路由
app.include_router(router)


