from .auth_routes import get_current_user
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
import httpx
from src.modules.config import settings
import logging
from typing import Dict, Any, List, Optional
# 使用共享类型库
from src.shared.types.chat import ChatRequest, ChatResponse, ChatSession, ChatMessage
from src.shared.types.response import ApiResponse
from src.shared.types.graph import GraphAnalysisRequest
from src.shared.utils import to_response_model
from .services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user=Depends(get_current_user)
):
    """发送消息"""
    logger.info(f"Sending message for user {user.id}")
    try:
        result = await chat_service.post(
            "/chat/message",
            json_data={
                "content": request.content,
                "user_id": user.id,
                "project_id": request.project_id,
                "use_stream": request.use_stream
            }
        )
        return to_response_model(ChatResponse, result)
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=List[ChatSession])
async def list_sessions(
    user=Depends(get_current_user)
):
    """获取会话列表"""
    logger.info(f"Listing sessions for user {user.id}")
    try:
        result = await chat_service.get(
            "/chat/sessions",
            params={"user_id": user.id}
        )
        return to_response_model(ChatSession, result)
    except Exception as e:
        logger.error(f"Failed to list sessions: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(
    session_id: str,
    user=Depends(get_current_user)
):
    """获取会话详情"""
    logger.info(f"Getting session {session_id} for user {user.id}")
    try:
        result = await chat_service.get(
            f"/chat/sessions/{session_id}",
            params={"user_id": user.id}
        )
        return to_response_model(ChatSession, result)
    except Exception as e:
        logger.error(f"Failed to get session: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: str,
    user=Depends(get_current_user)
):
    """删除会话"""
    logger.info(f"Deleting session {session_id} for user {user.id}")
    try:
        result = await chat_service.delete(
            f"/chat/sessions/{session_id}",
            params={"user_id": user.id}
        )
        return ApiResponse(
            success=True,
            message="Session deleted successfully",
            data=result
        )
    except Exception as e:
        logger.error(f"Failed to delete session: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions", response_model=ApiResponse)
async def clear_sessions(
    user=Depends(get_current_user)
):
    """清空所有会话"""
    logger.info(f"Clearing all sessions for user {user.id}")
    try:
        result = await chat_service.delete(
            "/chat/sessions",
            params={"user_id": user.id}
        )
        return ApiResponse(
            success=True,
            message="All sessions cleared successfully",
            data=result
        )
    except Exception as e:
        logger.error(f"Failed to clear sessions: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/history/{project_id}", response_model=ApiResponse)
async def clear_chat_history(
    project_id: str,
    user=Depends(get_current_user)
):
    """清空聊天历史"""
    logger.info(f"清空项目 {project_id} 的聊天历史，用户：{user.id}")
    try:
        result = await chat_service.delete(
            f"/chat/history/{project_id}",
            params={"user_id": user.id}
        )
        return ApiResponse(
            success=True,
            message="聊天历史已成功清空",
            data=result
        )
    except Exception as e:
        logger.error(f"清空聊天历史失败: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/knowledge_framework", response_model=Dict[str, Any])
async def analyze_knowledge_framework(
    request: GraphAnalysisRequest,
    user=Depends(get_current_user)
):
    """分析知识框架"""
    logger.info(f"Analyzing knowledge framework for user {user.id}")
    try:
        result = await chat_service.post(
            "/chat/knowledge_framework",
            json_data={
                "query": request.query,
                "project_id": request.project_id
            }
        )
        return result
    except Exception as e:
        logger.error(f"Failed to analyze knowledge framework: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(
    user_id: str,
    project_id: str = 'default',
    user=Depends(get_current_user)
):
    """获取聊天历史"""
    logger.info(f"获取用户 {user_id} 在项目 {project_id} 的聊天历史")
    try:
        result = await chat_service.get(
            f"/chat/history/{project_id}",
            params={"user_id": user_id}
        )
        return result
    except Exception as e:
        logger.error(f"获取聊天历史失败: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        # 如果服务返回404，说明没有历史记录，返回空列表
        if "404" in str(e):
            return []
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save")
async def save_chat_message(
    request: Request,
    user=Depends(get_current_user)
):
    """保存聊天消息"""
    try:
        data = await request.json()
        logger.info(f"保存聊天消息: user_id={data.get('user_id')}, project_id={data.get('project_id')}")
        
        result = await chat_service.post(
            "/chat/save",
            json_data=data
        )
        return result
    except Exception as e:
        logger.error(f"保存聊天消息失败: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
async def clear_chat_records(
    user_id: str,
    project_id: str = 'default',
    user=Depends(get_current_user)
):
    """清除聊天历史"""
    logger.info(f"清除用户 {user_id} 在项目 {project_id} 的聊天历史")
    try:
        result = await chat_service.delete(
            f"/chat/history/{project_id}",
            params={"user_id": user_id}
        )
        return ApiResponse(
            success=True,
            message="聊天历史已成功清除",
            data=result
        )
    except Exception as e:
        logger.error(f"清除聊天历史失败: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/migrate", response_model=ApiResponse)
async def migrate_chat_history(
    days: int = 30,
    user=Depends(get_current_user)
):
    """手动触发聊天历史迁移"""
    logger.info(f"用户 {user.id} 手动触发聊天历史迁移，保留最近 {days} 天")
    try:
        result = await chat_service.post(
            "/chat/migrate",
            params={"days": days}
        )
        return ApiResponse(
            success=True,
            message=f"成功迁移 {result.get('data', {}).get('messages_migrated', 0)} 条聊天记录到数据库",
            data=result.get('data', {})
        )
    except Exception as e:
        logger.error(f"触发聊天历史迁移失败: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) 