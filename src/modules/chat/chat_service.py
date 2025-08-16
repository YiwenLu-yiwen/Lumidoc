from fastapi import FastAPI, HTTPException, Depends, WebSocket, Request, status, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Dict, Any, Optional
import redis
import os
from src.modules.chat.chat_manager import ChatManager, process_special_format
from src.modules.llm_chat import LLMToolService
from src.shared.clients import default_lightrag_client as lightrag_service
from src.modules.graph.services.graph_service import GraphService
from src.modules.chat.config.config import settings
from src.database import get_db
from sqlalchemy.orm import Session
from src.modules.chat.chat_engine import ChatEngine
import json
from pathlib import Path
import logging
import traceback
from fastapi.responses import StreamingResponse
from src.modules.lightraglocal.config.config import config as rag_config
from fastapi.routing import APIRouter
import uuid
from datetime import datetime
from .models import ChatHistory
from .data_migration import fetch_chat_history, migrate_old_messages_to_db

# 导入共享类型
from src.shared.types.chat import ChatMessage, ChatSession, ChatRequest, ChatResponse, GraphAnalysisRequest
from src.shared.types.response import ApiResponse
from src.shared.health_check import register_health_routes, create_health_checker

# 确保URL总是包含协议
def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

logger = logging.getLogger(__name__)

app = FastAPI(title="Chat Service")

# 创建API路由器 (前缀由main.py中的include_router添加)
api_router = APIRouter()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://115.29.191.36:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建健康检查器
health_checker = create_health_checker("chat", "chat_service_1")

# 添加Chat特定的健康检查
async def check_chat_engine():
    """检查聊天引擎状态"""
    try:
        return chat_engine is not None
    except Exception as e:
        logger.error(f"聊天引擎检查失败: {str(e)}")
        return False

async def check_llm_service():
    """检查LLM服务连接"""
    try:
        return llm_service is not None
    except Exception as e:
        logger.error(f"LLM服务检查失败: {str(e)}")
        return False

async def check_redis_connection():
    """检查Redis连接状态"""
    try:
        redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis连接检查失败: {str(e)}")
        return False

# 初始化服务
llm_service = LLMToolService()
graph_service = GraphService()
chat_engine = ChatEngine(llm_service, graph_service)
chat_manager = ChatManager(llm_service=llm_service, graph_service=graph_service, chat_engine=chat_engine)

# 初始化Redis连接（用于缓存）
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password
)

# 配置健康检查项
health_checker.add_check("chat_engine", check_chat_engine, critical=True)
health_checker.add_check("llm_service", check_llm_service, critical=True)
health_checker.add_check("redis_connection", check_redis_connection, critical=True)

# 注册统一健康检查路由
register_health_routes(app, health_checker)

def get_chat_manager(db: Session = Depends(get_db)) -> ChatManager:
    """获取聊天管理器实例"""
    return chat_manager

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_id: Optional[str] = None,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    处理聊天请求
    
    Args:
        request: 聊天请求，包含消息和项目ID
        session_id: 可选的会话ID
        chat_manager: 聊天管理器实例
        
    Returns:
        ChatResponse: 包含回复和会话ID的响应
    """
    if not session_id:
        session_id = chat_manager.create_session(project_id=request.project_id)
    
    # 从请求中获取搜索模式和是否使用图谱，如果未提供则使用配置中的默认值
    search_mode = getattr(request, "search_mode", None) or rag_config.default_query_mode
    use_graph = getattr(request, "use_graph", None)
    if use_graph is None:
        use_graph = True  # 默认使用图谱增强
    
    response = await chat_manager.process_message(
        session_id=session_id,
        message=request.content,
        project_id=request.project_id,
        use_stream=request.use_stream,
        search_mode=search_mode,
        use_graph=use_graph
    )
    
    return ChatResponse(response=response, session_id=session_id)

@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    session_id: Optional[str] = None,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    处理流式聊天请求
    
    Args:
        request: 聊天请求，包含消息和项目ID
        session_id: 可选的会话ID
        chat_manager: 聊天管理器实例
        
    Returns:
        StreamingResponse: 流式响应
    """
    if not session_id:
        session_id = chat_manager.create_session(project_id=request.project_id)
    
    # 从请求中获取搜索模式和是否使用图谱，如果未提供则使用配置中的默认值
    search_mode = getattr(request, "search_mode", None) or rag_config.default_query_mode
    use_graph = getattr(request, "use_graph", None)
    if use_graph is None:
        use_graph = True  # 默认使用图谱增强
    
    async def stream_generator():
        try:
            # 获取用户ID（从请求中提取或默认值）
            user_id = getattr(request, "user_id", None) or "unknown"
            
            async for chunk in chat_manager.process_message_stream(
                project_id=request.project_id,
                message=request.content,
                user_id=user_id,
                search_mode=search_mode,
                use_graph=use_graph
            ):
                # 发送SSE格式的数据，确保中文正常显示，使用content字段匹配前端期待
                yield f"data: {json.dumps({'content': chunk, 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"流式聊天失败: {str(e)}")
            yield f"data: {json.dumps({'error': str(e), 'session_id': session_id}, ensure_ascii=False)}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    获取指定会话的信息
    
    Args:
        session_id: 会话ID
        chat_manager: 聊天管理器实例
        
    Returns:
        ChatSession: 会话信息
    """
    history = await chat_manager.get_session_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取会话的完整信息
    session = chat_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return ChatSession(
        session_id=session_id,
        project_id=session.project_id,
        messages=[
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['timestamp']
            ) for msg in history
        ],
        created_at=session.created_at,
        updated_at=session.updated_at,
        graph_analysis=session.graph_analysis
    )

@app.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    删除指定会话
    
    Args:
        session_id: 会话ID
        chat_manager: 聊天管理器实例
    """
    await chat_manager.clear_session(session_id)
    return ApiResponse(
        success=True,
        message="Session deleted successfully"
    )

@app.delete("/sessions", response_model=ApiResponse)
async def delete_all_sessions(
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    删除所有会话
    
    Args:
        chat_manager: 聊天管理器实例
    """
    await chat_manager.clear_all_sessions()
    return ApiResponse(
        success=True,
        message="All sessions deleted successfully"
    )

@app.delete("/sessions/project/{project_id}", response_model=ApiResponse)
async def delete_project_sessions(
    project_id: str,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    删除指定项目的所有会话
    
    Args:
        project_id: 项目ID
        chat_manager: 聊天管理器实例
    """
    await chat_manager.clear_sessions_by_project(project_id)
    return ApiResponse(
        success=True,
        message=f"All sessions for project {project_id} deleted successfully"
    )

@app.get("/chat/history", response_model=List[ChatMessage])
async def get_chat_history(project_id: str, db: Session = Depends(get_db)):
    """获取聊天历史"""
    try:
        history = chat_manager.get_chat_history(project_id)
        return [
            ChatMessage(
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['timestamp']
            ) for msg in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/message", response_model=ChatResponse)
async def send_message(
    project_id: str, 
    message: str, 
    db: Session = Depends(get_db)
):
    """发送消息"""
    try:
        response = await chat_manager.process_message(project_id, message)
        return ChatResponse(
            response=response, 
            session_id=chat_manager.get_current_session_id(project_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/chat/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket聊天"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = await chat_manager.process_message(project_id, data)
            await websocket.send_text(response)
    except Exception as e:
        await websocket.close()

@app.delete("/chat/history/{project_id}", response_model=ApiResponse)
async def clear_chat_history(
    project_id: str, 
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """清空聊天历史（同时清除Redis和PostgreSQL中的记录）"""
    try:
        logger.info(f"清空项目 {project_id} 的聊天历史")
        deleted_count = 0
        
        # 1. 清除Redis中的记录
        redis_key = f"chat:history:{project_id}"
        redis_deleted = redis_client.delete(redis_key)
        
        # 2. 清除PostgreSQL中的记录 - 直接执行而不是使用background_tasks
        pg_deleted = _clear_db_chat_history(db, project_id, user_id)
        deleted_count += pg_deleted
            
        deleted_count += redis_deleted
        
        # 返回清除结果
        if deleted_count > 0:
            message = "聊天历史已成功清空"
        else:
            message = "没有聊天历史记录可清空"
            
        return ApiResponse(
            success=True,
            message=message,
            data={"deleted_count": deleted_count}
        )
    except Exception as e:
        logger.error(f"清空聊天历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def _clear_db_chat_history(db: Session, project_id: str, user_id: Optional[str] = None) -> int:
    """从PostgreSQL中清除聊天历史"""
    try:
        query = db.query(ChatHistory).filter(ChatHistory.project_id == project_id)
        
        # 如果指定了user_id，则只删除该用户的记录
        if user_id:
            query = query.filter(ChatHistory.user_id == user_id)
            
        # 执行删除操作
        deleted_count = query.delete()
        db.commit()
        
        logger.info(f"已从PostgreSQL删除 {deleted_count} 条聊天记录")
        return deleted_count
    except Exception as e:
        logger.error(f"从PostgreSQL清除聊天历史失败: {str(e)}")
        db.rollback()
        return 0

@app.post("/chat/migrate", response_model=ApiResponse)
async def trigger_chat_migration(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """手动触发消息迁移任务"""
    try:
        # 执行迁移
        result = migrate_old_messages_to_db(db, days=days)
        
        return ApiResponse(
            success=True,
            message=f"成功迁移 {result['messages_migrated']} 条聊天记录到数据库",
            data=result
        )
    except Exception as e:
        logger.error(f"手动触发迁移失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def stream_chat(
    request: Request,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    流式聊天接口
    支持SSE（Server-Sent Events）格式返回
    """
    try:
        # 解析请求数据
        data = await request.json()
        project_id = data.get("project_id")
        message = data.get("message")  # 修改为使用message字段
        content = data.get("content")  # 保持兼容，同时检查content字段
        user_id = data.get("user_id")
        search_mode = data.get("search_mode", rag_config.default_query_mode)
        use_graph = data.get("use_graph", True)  # 默认使用图谱增强
        
        # 优先使用message字段，然后是content字段
        content_to_use = message or content
        
        if not content_to_use:
            raise HTTPException(status_code=400, detail="Missing content")
        
        # 将用户消息添加到聊天历史
        chat_manager.add_message(project_id, "user", content_to_use)
        
        # 创建SSE流响应
        async def event_generator():
            full_response = ""
            has_sent_content = False
            
            try:
                # 使用ChatManager的process_message_stream方法处理流式响应
                async for chunk in chat_manager.process_message_stream(
                    project_id=project_id,
                    message=content_to_use,
                    user_id=user_id,
                    search_mode=search_mode,
                    use_graph=use_graph
                ):
                    if chunk and chunk.strip():
                        has_sent_content = True
                    
                    full_response += chunk
                    # 处理特殊格式内容
                    processed_chunk = process_special_format(chunk)
                    
                    # 返回SSE格式数据
                    yield f"data: {json.dumps({'content': processed_chunk})}\n\n"
                
                # 检查是否有实际内容返回，如果没有，发送默认回复
                processed_response = process_special_format(full_response)
                if not has_sent_content or not processed_response or processed_response.strip() in ["", "<|COMPLETE|>", "<COMPLETE>"]:
                    # 发送默认回复
                    default_response = "我已收到您的问题，正在处理中。请再详细描述您的需求，以便我能更好地帮助您。"
                    yield f"data: {json.dumps({'content': default_response})}\n\n"
                    # 更新full_response
                    full_response = default_response
                
                # 标记结束
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                
                # 添加处理后的完整回复到聊天历史
                chat_manager.add_message(project_id, "assistant", process_special_format(full_response))
            except Exception as e:
                logger.error(f"Streaming error: {str(e)}")
                error_msg = f"处理消息时发生错误: {str(e)}"
                full_response = error_msg
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
                "Content-Type": "text/event-stream"
            }
        )
        
    except Exception as e:
        logger.error(f"Stream chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/history/update", response_model=ApiResponse)
async def update_chat_history(
    project_id: str,
    messages: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """更新聊天历史"""
    try:
        # 清除旧的聊天历史
        chat_manager.clear_chat_history(project_id)
        
        # 添加新的消息
        for msg in messages:
            chat_manager.add_message_to_history(
                project_id=project_id,
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp")
            )
        
        return ApiResponse(
            success=True,
            message="Chat history updated successfully"
        )
    except Exception as e:
        logger.error(f"Failed to update chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history/{project_id}", response_model=List[ChatMessage])
async def get_project_chat_history(
    project_id: str,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    include_archived: bool = False,
    db: Session = Depends(get_db)
):
    """获取特定项目的聊天历史，支持从Redis和PostgreSQL混合获取"""
    try:
        logger.info(f"获取项目 {project_id} 的聊天历史，用户ID: {user_id}, 包含归档: {include_archived}")
        
        messages = []
        redis_messages = []
        pg_messages = []
        error_occurred = False
        
        # 1. 从Redis获取最近的消息
        redis_key = f"chat:history:{project_id}"
        try:
            raw_messages = redis_client.lrange(redis_key, 0, -1)
            
            if raw_messages:
                logger.info(f"从Redis读取到 {len(raw_messages)} 条消息")
                # 解析Redis中的消息
                for raw_msg in raw_messages:
                    try:
                        msg_data = json.loads(raw_msg)
                        # 用户过滤
                        if user_id and str(msg_data.get('user_id', '')) != str(user_id):
                            continue
                        
                        redis_messages.append({
                            'id': msg_data.get('id', ''),
                            'role': msg_data.get('role', 'unknown'),
                            'content': msg_data.get('content', ''),
                            'timestamp': msg_data.get('timestamp', ''),
                            'user_id': msg_data.get('user_id', ''),
                            'project_id': project_id,
                            'source': 'redis'  # 标记消息来源
                        })
                    except json.JSONDecodeError:
                        logger.error(f"解析Redis消息失败: {raw_msg}")
                        continue
            else:
                logger.info(f"Redis中没有找到项目 {project_id} 的聊天历史")
        except Exception as e:
            logger.error(f"从Redis获取聊天历史失败: {str(e)}")
            error_occurred = True
        
        # 2. 如果需要归档消息，尝试从PostgreSQL获取
        if include_archived:
            try:
                # 尝试从PostgreSQL获取归档消息
                archived_messages = fetch_chat_history(db, project_id, user_id, limit=500, offset=0)
                if archived_messages:
                    logger.info(f"从PostgreSQL获取到 {len(archived_messages)} 条归档消息")
                    # 添加来源标记
                    for msg in archived_messages:
                        msg['source'] = 'postgresql'
                    pg_messages.extend(archived_messages)
                else:
                    logger.info(f"PostgreSQL中没有找到项目 {project_id} 的归档聊天历史")
            except Exception as e:
                logger.error(f"从PostgreSQL获取归档聊天历史失败: {str(e)}")
                logger.error("继续使用仅Redis中的消息")
                error_occurred = True
        
        # 3. 合并消息并按时间戳排序 - 从早到晚排序（不用reverse=True）
        messages = redis_messages + pg_messages
        if messages:
            try:
                # 按时间戳从早到晚排序
                messages.sort(key=lambda x: x.get('timestamp', ''))
            except Exception as e:
                logger.error(f"聊天消息排序失败: {str(e)}")
                # 如果排序失败，保持原始顺序
        
        # 4. 分页处理
        start_idx = min(offset, len(messages))
        end_idx = min(start_idx + limit, len(messages))
        
        # 返回指定范围的消息
        result = messages[start_idx:end_idx]
        
        # 5. 添加调试信息
        if error_occurred:
            logger.warning(f"获取聊天历史过程中发生错误，返回部分结果: Redis={len(redis_messages)}条, PostgreSQL={len(pg_messages)}条")
        else:
            logger.info(f"成功获取聊天历史: Redis={len(redis_messages)}条, PostgreSQL={len(pg_messages)}条, 返回={len(result)}条")
        
        # 6. 转换为API响应格式
        return [
            ChatMessage(
                role=msg.get('role', 'unknown'),
                content=msg.get('content', ''),
                timestamp=msg.get('timestamp', '')
            ) for msg in result
        ]
            
    except Exception as e:
        logger.error(f"获取聊天历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/knowledge_framework", response_model=Dict[str, Any])
async def analyze_knowledge_framework(
    request: GraphAnalysisRequest,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    分析知识图谱的知识框架
    
    Args:
        request: 包含查询和项目ID的请求
        
    Returns:
        Dict[str, Any]: 知识框架分析结果
    """
    try:
        result = await chat_manager.chat_engine.analyze_knowledge_framework(
            query=request.query,
            project_id=request.project_id
        )
        return result
    except Exception as e:
        logger.error(f"知识框架分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 添加带/api前缀的流式聊天接口 - 复用相同的代码处理逻辑
@api_router.post("/chat/stream")
async def api_stream_chat(
    request: Request,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """
    带API前缀的流式聊天接口 
    复用相同的处理逻辑
    """
    logger.info("收到API前缀的流式聊天请求")
    return await stream_chat(request, chat_manager)

# 复制这些关键API到api前缀路由
@api_router.get("/chat/history/{project_id}")
async def api_get_project_chat_history(
    project_id: str,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    include_archived: bool = False,
    db: Session = Depends(get_db)
):
    """带API前缀的获取特定项目的聊天历史接口"""
    logger.info(f"通过API前缀路径获取项目 {project_id} 的聊天历史")
    return await get_project_chat_history(
        project_id=project_id, 
        user_id=user_id, 
        limit=limit, 
        offset=offset, 
        include_archived=include_archived, 
        db=db
    )

@api_router.post("/chat/migrate")
async def api_trigger_chat_migration(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """带API前缀的迁移聊天历史接口"""
    logger.info(f"通过API前缀路径触发聊天历史迁移，days={days}")
    return await trigger_chat_migration(days, db)

@api_router.delete("/chat/history/{project_id}")
async def api_clear_chat_history(
    project_id: str, 
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """带API前缀的清空聊天历史接口"""
    logger.info(f"通过API前缀路径清空项目 {project_id} 的聊天历史")
    return await clear_chat_history(project_id, user_id, db)

@api_router.post("/chat/history/update")
async def api_update_chat_history(
    request: Request,
    db: Session = Depends(get_db)
):
    """带API前缀的更新聊天历史接口"""
    data = await request.json()
    project_id = data.get("project_id")
    messages = data.get("messages", [])
    logger.info(f"通过API前缀路径更新项目 {project_id} 的聊天历史")
    return await update_chat_history(project_id, messages, db)

@api_router.post("/chat/knowledge_framework")
async def api_analyze_knowledge_framework(
    request: Request,
    chat_manager: ChatManager = Depends(get_chat_manager)
):
    """带API前缀的知识框架分析接口"""
    data = await request.json()
    req = GraphAnalysisRequest(**data)
    logger.info(f"通过API前缀路径分析项目 {req.project_id} 的知识框架")
    return await analyze_knowledge_framework(req, chat_manager)

# 添加聊天消息保存接口
@app.post("/chat/save", response_model=ApiResponse)
async def save_chat_message(
    request: Request,
    db: Session = Depends(get_db)
):
    """保存单条聊天消息"""
    try:
        data = await request.json()
        id = data.get("id", str(uuid.uuid4()))
        content = data.get("content", "")
        role = data.get("role", "")
        user_id = data.get("user_id", "")
        project_id = data.get("project_id", "")
        timestamp = data.get("timestamp", datetime.now().isoformat())
        
        logger.info(f"保存聊天消息: project_id={project_id}, role={role}")
        
        # 构建消息对象
        message = {
            "id": id,
            "content": content,
            "role": role,
            "user_id": user_id,
            "project_id": project_id,
            "timestamp": timestamp
        }
        
        # 使用Redis保存消息
        redis_key = f"chat:history:{project_id}"
        redis_client.lpush(redis_key, json.dumps(message))
        
        # 设置过期时间 (30天)
        redis_client.expire(redis_key, 60 * 60 * 24 * 30)
        
        return ApiResponse(
            success=True,
            message="聊天消息保存成功",
            data={"id": id}
        )
    except Exception as e:
        logger.error(f"保存聊天消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 复制保存API到api前缀路由
@api_router.post("/chat/save")
async def api_save_chat_message(
    request: Request,
    db: Session = Depends(get_db)
):
    """带API前缀的保存聊天消息接口"""
    logger.info("通过API前缀路径保存聊天消息")
    return await save_chat_message(request, db)

# 在应用程序最后添加API前缀路由
app.include_router(api_router)

# 注意：定期任务已移动到main.py的lifespan中管理

class ChatService:
    def __init__(self):
        """
        初始化聊天服务
        """
        self._db_initialized = False
        self._message_model = None
        self._history_model = None
        
    async def _get_chat_history_by_id(self, chat_history_id: str):
        """根据聊天历史ID获取聊天历史"""
        try:
            from src.shared.database import get_db
            db_generator = get_db()
            db = next(db_generator)
            
            # 查询聊天历史
            history = db.query(ChatHistory).filter(
                ChatHistory.id == chat_history_id
            ).first()
            
            db.close()
            return history
        except Exception as e:
            logger.error(f"获取聊天历史失败: {str(e)}")
            return None
    
    async def _save_chat_messages(self, chat_history_id: str, messages: List[Dict[str, Any]]):
        """保存聊天消息"""
        try:
            # 使用Redis保存消息
            for message in messages:
                message_data = {
                    "id": str(uuid.uuid4()),
                    "chat_history_id": chat_history_id,
                    "role": message["role"],
                    "content": message["content"],
                    "timestamp": datetime.now().isoformat(),
                    "metadata": message.get("metadata", {})
                }
                
                redis_key = f"chat:messages:{chat_history_id}"
                redis_client.lpush(redis_key, json.dumps(message_data))
                
                # 设置过期时间 (30天)
                redis_client.expire(redis_key, 60 * 60 * 24 * 30)
                
            logger.info(f"已保存 {len(messages)} 条聊天消息")
        except Exception as e:
            logger.error(f"保存聊天消息失败: {str(e)}")
            
    async def query_with_graph_augmentation(
        self, chat_history_id: str, query: str, 
        use_path_context: bool = True, 
        use_entity_expansion: bool = True
    ) -> Dict[str, Any]:
        """
        使用图谱增强RAG进行查询
        
        Args:
            chat_history_id: 聊天历史ID
            query: 用户查询
            use_path_context: 是否使用路径上下文
            use_entity_expansion: 是否使用实体扩展
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        chat_history = await self._get_chat_history_by_id(chat_history_id)
        
        if not chat_history:
            logger.error(f"未找到聊天历史: {chat_history_id}")
            return {
                "success": False,
                "message": f"未找到聊天历史: {chat_history_id}"
            }
            
        try:
            # 获取项目ID
            project_id = chat_history.project_id
            
            # 导入LightRAG客户端
            from src.shared.clients.lightrag_client import default_client as lightrag_client
            
            # 调用图谱增强查询
            result = await lightrag_client.query_with_graph_enhancement(
                project_id=project_id,
                query=query,
                top_k=5,
                use_path_context=use_path_context,
                use_entity_expansion=use_entity_expansion
            )
            
            # 格式化答案
            answer = result.get("answer", "")
            
            # 提取图谱相关信息
            entities = result.get("entities", [])
            related_entities = result.get("related_entities", [])
            paths = result.get("paths", [])
            
            # 保存聊天消息
            metadata = {
                "source": "graph_enhanced_rag",
                "entities": entities,
                "related_entities": related_entities,
                "paths": paths
            }
            
            user_msg = {
                "role": "user",
                "content": query,
                "metadata": {}
            }
            
            assistant_msg = {
                "role": "assistant",
                "content": answer,
                "metadata": metadata
            }
            
            await self._save_chat_messages(chat_history_id, [user_msg, assistant_msg])
            
            return {
                "success": True,
                "answer": answer,
                "entities": entities,
                "related_entities": related_entities,
                "paths": paths,
                "expanded_query": result.get("expanded_query")
            }
        except Exception as e:
            logger.error(f"图谱增强查询失败: {str(e)}")
            return {
                "success": False,
                "message": f"图谱增强查询失败: {str(e)}"
            }

# 定义migrate_old_chat_messages函数
async def migrate_old_chat_messages():
    """迁移旧聊天消息到数据库"""
    try:
        logger.info("开始迁移旧聊天消息")
        from src.shared.database import get_db
        
        # 使用async for正确处理异步生成器
        async for db in get_db():
            try:
                # 执行迁移
                result = migrate_old_messages_to_db(db, days=30)
                logger.info(f"迁移完成: {result}")
                break  # 成功后退出循环
            except Exception as migration_error:
                logger.error(f"迁移执行失败: {str(migration_error)}")
                raise
            finally:
                await db.close()  # 确保连接关闭
                
    except Exception as e:
        logger.error(f"迁移旧聊天消息失败: {str(e)}")

# 创建ChatService实例 - 移动到这里以便导入
chat_service = ChatService()

if __name__ == "__main__":
    uvicorn.run(app, host=settings.service_host, port=settings.service_port) 