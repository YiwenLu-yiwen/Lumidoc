import datetime
import uuid
import re
from typing import Dict, Any, List, Optional, AsyncGenerator

# 导入第三方库

# 导入内部模块
from src.modules.llm_chat import LLMToolService
from src.modules.chat.chat_engine import ChatEngine
from src.modules.chat.config.config import settings

from src.shared.clients import GraphServiceClient
from src.shared.types.chat import GraphAnalysisRequest

def process_special_format(content: str) -> str:
    """处理特殊格式的消息内容"""
    if not isinstance(content, str):
        return content
    
    # 首先移除连接建立前缀（支持各种变体）
    processed_content = re.sub(r'^:?\s*connection\s+established[\s\n]*', '', content, flags=re.IGNORECASE)
    processed_content = re.sub(r'^:?\s*connected[\s\n]*', '', processed_content, flags=re.IGNORECASE)
    processed_content = re.sub(r'^:?\s*已连接[\s\n]*', '', processed_content, flags=re.IGNORECASE)
    processed_content = re.sub(r'^:?\s*连接已建立[\s\n]*', '', processed_content, flags=re.IGNORECASE)
        
    if "<|>" not in processed_content and "<COMPLETE>" not in processed_content:
        return processed_content
        
    # 移除特殊格式标记
    processed_content = processed_content.replace("<COMPLETE>", "")
    processed_content = processed_content.replace("<|>", "")
    
    # 移除实体标记格式，例如 ("entity"<|><knowledge_graph><|><类别><|>"知识图谱是一种...")
    processed_content = re.sub(r'\("([^"]+)"<\|>[^"]+<\|>[^"]+<\|>"([^"]+)"\)', r'\2', processed_content)
    
    # 清理多余的井号分隔符
    processed_content = re.sub(r'##+', '', processed_content)
    
    return processed_content

class ChatSession:
    """聊天会话类"""
    def __init__(self, session_id: str, project_id: str):
        self.session_id = session_id
        self.project_id = project_id
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()
        self.messages = []
        self.graph_analysis = None

    def add_message(self, role: str, content: str):
        """添加消息到会话历史"""
        # 处理内容中可能存在的特殊格式
        processed_content = process_special_format(content)
        
        self.messages.append({
            "role": role,
            "content": processed_content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        self.updated_at = datetime.datetime.now()

class ChatManager:
    """聊天管理器类，负责管理聊天会话和处理消息"""
    
    def __init__(self, llm_service: LLMToolService, 
                 graph_service: GraphServiceClient,
                 chat_engine: ChatEngine):
        self.sessions: Dict[str, ChatSession] = {}
        self.llm_service = llm_service
        self.graph_service = graph_service
        self.chat_engine = chat_engine
        
    def create_session(self, project_id: str) -> str:
        """创建新的聊天会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatSession(session_id, project_id)
        return session_id
        
    async def process_message(self, 
                          session_id: str, 
                          message: str, 
                          project_id: str,
                          use_stream: bool = False,
                          search_mode: str = None,
                          use_graph: bool = True,
                          auth_header: Optional[str] = None,
                          model: Optional[str] = None) -> str:
        """处理用户消息并返回回复"""
        # 检查会话是否存在，不存在则创建
        if session_id not in self.sessions:
            session_id = self.create_session(project_id)
            
        session = self.sessions[session_id]
        
        # 将用户消息添加到会话历史
        session.add_message("user", message)
        
        # 使用聊天引擎处理消息
        response = await self.chat_engine.process_message(
            message, 
            project_id, 
            session_id,
            use_stream=use_stream,
            search_mode=search_mode or settings.default_query_mode,
            use_graph=use_graph,
            auth_header=auth_header,
            model=model,
        )
        
        # 将AI回复添加到会话历史
        session.add_message("assistant", response)
        
        return response
    
    async def process_message_stream(self, 
                                  project_id: str,
                                  message: str,
                                  user_id: Optional[str] = None,
                                  search_mode: Optional[str] = None,
                                  use_graph: Optional[bool] = None,
                                  auth_header: Optional[str] = None,
                                  model: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        流式处理用户消息
        
        Args:
            project_id: 项目ID
            message: 用户消息
            user_id: 用户ID (可选)
            search_mode: 搜索模式 (可选)
            use_graph: 是否使用图谱增强 (可选)
            
        Returns:
            异步生成器，生成响应片段
        """
        # 确保项目有关联的会话
        session_id = self.get_current_session_id(project_id)
        if not session_id:
            session_id = self.create_session(project_id=project_id)
        
        session = self.sessions[session_id]
        
        # 将用户消息添加到会话历史
        session.add_message("user", message)
        
        full_response = ""
        
        # 使用聊天引擎处理消息（流式）
        try:
            # 使用新的chat_stream方法，支持历史会话
            streaming_response = self.chat_engine.chat_stream(
                message=message, 
                project_id=project_id,
                user_id=user_id,
                auth_header=auth_header,
                model=model,
            )
            
            # chat_stream总是返回异步生成器，逐块生成
            async for chunk in streaming_response:
                # 处理特殊格式内容
                processed_chunk = chunk
                if isinstance(chunk, str) and ("<|>" in chunk or "<COMPLETE>" in chunk):
                    processed_chunk = process_special_format(chunk)
                
                # 累积完整响应并yield处理后的chunk
                full_response += processed_chunk
                yield processed_chunk
            
            # 保存完整响应到会话
            session.add_message('assistant', full_response)
            
        except Exception as e:
            import logging
            logging.error(f"Error in stream processing: {e}")
            error_msg = f"处理消息时发生错误: {str(e)}"
            yield error_msg
            session.add_message('assistant', error_msg)
    
    def add_message(self, project_id: str, role: str, content: str):
        """添加消息到项目的聊天历史"""
        session_id = self.get_current_session_id(project_id)
        if not session_id:
            session_id = self.create_session(project_id=project_id)
        
        session = self.sessions[session_id]
        # 处理特殊格式内容
        processed_content = process_special_format(content)
        
        session.add_message(role, processed_content)
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话历史"""
        if session_id in self.sessions:
            return self.sessions[session_id].messages
        return []
    
    async def clear_session(self, session_id: str) -> bool:
        """清空指定会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    async def clear_all_sessions(self) -> bool:
        """清空所有会话"""
        self.sessions = {}
        return True
    
    async def clear_sessions_by_project(self, project_id: str) -> bool:
        """清空指定项目的所有会话"""
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if session.project_id == project_id:
                sessions_to_remove.append(session_id)
                
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            
        return True
    
    def get_chat_history(self, project_id: str) -> List[Dict[str, Any]]:
        """获取项目的聊天历史"""
        history = []
        for session in self.sessions.values():
            if session.project_id == project_id:
                history.extend(session.messages)
        return history
    
    def clear_chat_history(self, project_id: str) -> bool:
        """清空项目的聊天历史，确保真正删除所有聊天记录"""
        # 查找属于该项目的所有会话
        sessions_to_clear = []
        for session_id, session in self.sessions.items():
            if session.project_id == project_id:
                sessions_to_clear.append(session_id)
        
        # 从会话字典中删除所有匹配的会话
        for session_id in sessions_to_clear:
            del self.sessions[session_id]
        
        # 记录操作日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"已清除项目{project_id}的所有聊天历史，共{len(sessions_to_clear)}个会话")
        
        return True
    
    def get_current_session_id(self, project_id: str) -> Optional[str]:
        """获取项目当前会话ID"""
        for session_id, session in self.sessions.items():
            if session.project_id == project_id:
                return session_id
        return None
        
    async def analyze_knowledge_framework(self, request: GraphAnalysisRequest) -> Dict[str, Any]:
        """分析知识框架"""
        try:
            # 假设有关联的会话
            session_id = self.get_current_session_id(request.project_id)
            if session_id and session_id in self.sessions:
                session = self.sessions[session_id]
                
                # 调用图服务分析
                result = await self.graph_service.analyze_text(request)
                
                # 保存分析结果到会话中
                session.graph_analysis = result
                return result
            else:
                # 没有会话，直接调用
                return await self.graph_service.analyze_text(request)
        except Exception as e:
            print(f"Error analyzing knowledge framework: {str(e)}")
            return {"error": str(e)}
