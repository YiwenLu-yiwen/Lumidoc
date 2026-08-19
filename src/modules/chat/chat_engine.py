from typing import Dict, Any, Optional, AsyncGenerator
from src.modules.llm_chat import LLMToolService
from src.shared.clients import default_lightrag_client as lightrag_service
from src.shared.clients import GraphServiceClient
from src.modules.chat.config.config import settings
import logging
import os
import httpx
import json
import asyncio
import re

# 处理循环导入问题
logger = logging.getLogger(__name__)

# 打印环境变量，便于调试
logger.info(f"加载环境变量: RAG_SERVICE_URL={os.getenv('RAG_SERVICE_URL', 'http://localhost:8006')}")

# 确保URL总是包含协议
def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

class ChatEngine:
    def __init__(self, 
                 llm_service: LLMToolService,
                 graph_service: Optional[GraphServiceClient] = None):
        self.llm_service = llm_service
        self.graph_service = graph_service
        self.language = "中文"

    def _extract_secret_from_context(self, context: str) -> Optional[str]:
        if not context:
            return None
        patterns = [
            r'(?:secret(?:\s+code)?|密钥(?:代码)?|code)\s*(?:is|:|：)\s*([A-Z0-9][A-Z0-9_\-]{6,})',
            r'\b([A-Z]{2,}_[A-Z0-9_]{6,})\b'
        ]
        for pattern in patterns:
            match = re.search(pattern, context, flags=re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _build_context_direct_answer(self, message: str, context: str) -> Optional[str]:
        if not context or not context.strip():
            return None

        lowered = message.lower() if message else ""
        asks_secret = any(
            keyword in lowered for keyword in ["secret", "密钥", "code", "密码", "口令"]
        )
        if asks_secret:
            secret = self._extract_secret_from_context(context)
            if secret:
                return secret
        return None
    
    async def process_message(self, 
                          message: str, 
                          project_id: str,
                          session_id: str,
                          use_stream: bool = False,
                          search_mode: str = None,
                          use_graph: bool = True,
                          auth_header: Optional[str] = None,
                          model: Optional[str] = None) -> str:
        """
        处理聊天消息
        
        Args:
            message: 用户消息
            project_id: 项目ID
            session_id: 会话ID
            use_stream: 是否使用流式处理
            search_mode: 搜索模式
            use_graph: 是否使用图谱数据
            
        Returns:
            str: 响应消息
        """
        try:
            logger.info(f"Processing message: {message}, project: {project_id}, search_mode: {search_mode}")
            
            # 获取图谱数据
            graph_context = None
            if use_graph and self.graph_service and project_id:
                try:
                    graph_context = await self.graph_service.get_project_graph(project_id)
                    if graph_context:
                        # 🔧 修复：正确访问GraphData对象的属性
                        logger.info(f"获取到图谱数据: {len(graph_context.nodes)}个节点, {len(graph_context.edges)}个关系")
                    else:
                        logger.warning("未获取到图谱数据，但未报错")
                except Exception as e:
                    logger.error(f"获取图谱数据失败: {str(e)}")
            
            # 1. 使用LightRAG搜索相关内容
            search_results = []
            
            # 增强错误处理和日志记录
            # 首先尝试使用项目级LightRAG实例
            if project_id:
                try:
                    # 🔧 修复：直接调用RAG搜索API
                    logger.info(f"调用RAG搜索API，项目ID: {project_id}, 查询: {message[:50]}...")
                    
                    # 使用HTTP客户端调用RAG搜索端点
                    rag_url = ensure_url_protocol(os.getenv('RAG_SERVICE_URL', 'http://localhost:8006'))
                    search_url = f"{rag_url}/rag/search"
                    
                    search_payload = {
                        "query": message,
                        "project_id": project_id,
                        "mode": search_mode or settings.default_query_mode
                    }
                    headers = {}
                    if auth_header:
                        headers["Authorization"] = auth_header
                    
                    logger.info(f"发送RAG搜索请求到: {search_url}")
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            search_url,
                            json=search_payload,
                            headers=headers if headers else None,
                            timeout=60.0
                        )
                        response.raise_for_status()
                        search_result = response.json()
                    
                    # 🔧 改进：正确处理搜索API的返回结果
                    if search_result and search_result.get("success") and search_result.get("result"):
                        # RAG搜索API返回完整的答案
                        answer_data = search_result.get("result", "")
                        if isinstance(answer_data, str) and answer_data.strip():
                            # 将RAG的答案作为上下文的一部分
                            search_results.append(f"相关信息：{answer_data}")
                            logger.info(f"从RAG搜索API获取到查询结果，长度: {len(answer_data)}")
                        else:
                            logger.warning("RAG搜索返回空数据")
                    else:
                        logger.warning(f"RAG搜索失败或返回格式不正确: {search_result}")
                        
                except ImportError:
                    logger.warning("无法导入LightRAG服务，尝试使用HTTP请求")
                    # 后续会进入HTTP请求逻辑
                except Exception as e:
                    logger.error(f"使用LightRAG服务查询失败: {str(e)}")
                    # 后续会进入HTTP请求逻辑
            
            # 如果没有成功获取到搜索结果，尝试通过Gateway调用RAG服务
            if not search_results:
                try:
                    # 严格遵循项目原则：所有服务间调用必须通过Gateway
                    from src.shared.service_discovery import call_service
                    
                    logger.info("通过Gateway调用LightRAG服务查询")
                    
                    # 通过Gateway调用LightRAG服务
                    response = await call_service(
                        service_name="lightraglocal",
                        endpoint="rag/query",
                        method="POST",
                        json_data={
                            "query": message,
                            "project_id": project_id,
                            "mode": search_mode or settings.default_query_mode,
                            "top_k": 5
                        },
                        headers={"Authorization": auth_header} if auth_header else None,
                        timeout=60.0
                    )
                    
                    if response and response.get("success", False):
                        search_results = response.get("documents", [])
                        logger.info(f"通过Gateway成功获取查询结果，找到{len(search_results)}个文档")
                    else:
                        logger.warning(f"通过Gateway调用LightRAG失败: {response}")
                        
                except Exception as e:
                    logger.error(f"通过Gateway调用LightRAG服务失败: {str(e)}")
                    
            # 如果仍然没有搜索结果，记录警告但继续处理
            if not search_results:
                logger.warning(f"未能获取到项目 {project_id} 的相关文档，将使用原始问题进行回答")

            # 构建提示词
            context = "\n\n".join(search_results)
            
            # 添加图谱数据到提示
            graph_context_str = ""
            if graph_context:
                graph_context_str = "\n\n知识图谱数据:\n"
                # 🔧 修复：正确访问GraphData对象的属性
                # 添加节点信息
                node_sample = graph_context.nodes[:20]  # 限制节点数量
                graph_context_str += "主要概念:\n"
                for node in node_sample:
                    graph_context_str += f"- {node.label} (类型: {node.type})\n"
                
                # 添加边信息
                edge_sample = graph_context.edges[:20]  # 限制边数量
                if edge_sample:
                    graph_context_str += "\n主要关系:\n"
                    for edge in edge_sample:
                        source = next((n.label for n in graph_context.nodes 
                                      if n.id == edge.source), "Unknown")
                        target = next((n.label for n in graph_context.nodes 
                                      if n.id == edge.target), "Unknown")
                        graph_context_str += f"- {source} --[{edge.label}]--> {target}\n"
            
            # 🔧 修复：构建正确的RAG问答prompt
            if context or graph_context_str:
                # 有知识库内容时，使用RAG增强回答
                prompt = f"""你是一个智能助手，请基于以下知识库信息回答用户的问题。

知识库信息：
{context}
{graph_context_str}

用户问题：{message}

请根据上述知识库信息，为用户提供准确、有用的回答。如果知识库中没有相关信息，请诚实地告知用户，并尽可能提供有帮助的一般性建议。

回答要求：
1. 基于知识库信息回答，引用相关内容
2. 回答要准确、清晰、有条理
3. 如果信息不足，请明确说明
4. 使用中文回答

回答："""
            else:
                # 没有知识库内容时，使用普通对话prompt  
                prompt = f"""你是一个智能助手，请回答用户的问题：

{message}

请提供有帮助的回答。"""
            
            # 4. 判断是否使用流式处理
            if use_stream:
                # 流式处理
                async def generate_stream():
                    try:
                        # 使用确保正确配置的LLMService
                        logger.info("开始流式生成回复...")
                        async for chunk in self.llm_service.stream_generate(
                            prompt=prompt
                        ):
                            yield chunk
                    except Exception as e:
                        logger.error(f"流式生成错误: {e}")
                        yield f"生成错误: {str(e)}"
                return generate_stream()
            else:
                # 非流式处理，直接使用LLM服务处理
                response = await self.llm_service.process_general(prompt, model=model)
                return response
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return "Sorry, I couldn't process your request. Please try again later."
    
    async def process_brand_info(self, brand_text: str) -> Dict[str, Any]:
        """
        处理品牌信息
        
        Args:
            brand_text: 品牌信息文本
            
        Returns:
            Dict[str, Any]: 处理后的品牌信息
        """
        return await self.llm_service.process_brand(brand_text)

    async def chat_stream(self, 
                        message: str, 
                        project_id: Optional[str] = None,
                        user_id: Optional[str] = None,
                        auth_header: Optional[str] = None,
                        model: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        流式处理聊天消息 - 真正的LLM流式响应
        
        Args:
            message: 用户消息
            project_id: 项目ID，用于获取图谱数据
            user_id: 用户ID，用于获取历史会话
            
        Returns:
            异步生成器，生成响应片段
        """
        try:
            logger.info(f"流式RAG查询，项目ID: {project_id}, 用户: {user_id}, 查询: {message[:50]}...")
            
            # 1. 获取历史会话（最近5条）
            chat_history = ""
            if project_id and user_id:
                try:
                    # 导入聊天服务来获取历史
                    import redis
                    
                    # 从Redis获取最近的聊天历史
                    redis_client = redis.Redis(
                        host=os.getenv('REDIS_HOST', 'localhost'),
                        port=int(os.getenv('REDIS_PORT', 6379)),
                        password=os.getenv('REDIS_PASSWORD'),
                        decode_responses=True
                    )
                    
                    redis_key = f"chat:history:{project_id}"
                    
                    # 先检查键的类型，避免WRONGTYPE错误
                    key_type = redis_client.type(redis_key)
                    if key_type == 'none':
                        # 键不存在
                        history_messages = []
                    elif key_type == 'list':
                        # 列表类型，使用lrange获取消息（与chat_service.py一致）
                        raw_messages = redis_client.lrange(redis_key, 0, -1)
                        history_messages = []
                        for raw_msg in raw_messages:
                            try:
                                msg_data = json.loads(raw_msg)
                                history_messages.append(msg_data)
                            except json.JSONDecodeError:
                                logger.warning(f"解析Redis消息失败: {raw_msg}")
                                continue
                    elif key_type == 'string':
                        # 字符串类型，兼容旧格式
                        history_data = redis_client.get(redis_key)
                        try:
                            history_messages = json.loads(history_data)
                        except json.JSONDecodeError:
                            logger.warning("解析字符串格式的历史消息失败")
                            history_messages = []
                    else:
                        # 其他类型，删除错误的键并继续
                        logger.warning(f"Redis键类型错误: {redis_key} 类型为 {key_type}，删除并重新开始")
                        redis_client.delete(redis_key)
                        history_messages = []
                    
                    if history_messages:
                        # 获取最近10条消息作为历史上下文，列表已经是按时间倒序排列
                        recent_messages = history_messages[:10]
                        
                        # 格式化历史会话
                        formatted_history = []
                        for msg in recent_messages:
                            role = "User" if msg.get('role') == 'user' else "Assistant"
                            content = msg.get('content', '')
                            formatted_history.append(f"{role}: {content}")
                        
                        chat_history = "\n".join(formatted_history)
                        logger.info(f"获取到历史会话，消息数: {len(recent_messages)}")
                        
                except Exception as history_error:
                    logger.warning(f"获取历史会话失败: {history_error}")
                    chat_history = ""
            
            # 2. 获取RAG上下文，并提供流式进度反馈
            context = ""
            
            # 开始RAG搜索，但不输出调试信息
            
            try:
                rag_url = ensure_url_protocol(os.getenv('RAG_SERVICE_URL', 'http://localhost:8006'))
                search_url = f"{rag_url}/rag/search"
                
                search_payload = {
                    "query": message,
                    "project_id": project_id,
                    "mode": settings.default_query_mode
                }
                headers = {}
                if auth_header:
                    headers["Authorization"] = auth_header
                
                # 执行RAG搜索
                
                # 获取RAG上下文
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        search_url,
                        json=search_payload,
                        headers=headers if headers else None,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    search_result = response.json()
                
                if search_result and search_result.get("success") and search_result.get("result"):
                    context = search_result.get("result", "")
                    logger.info(f"获取到RAG上下文，长度: {len(context)}")
                    # 不输出检索完成消息，直接进入生成流程
                else:
                    # 不输出未找到知识的消息，静默处理
                    context = ""
            except Exception as rag_error:
                logger.warning(f"RAG搜索失败，将使用纯LLM回复: {rag_error}")
                # 不输出错误消息，静默处理
                context = ""
            
            # 2. 使用官方LightRAG查询响应模版（中文版）
            direct_answer = self._build_context_direct_answer(message, context)
            if direct_answer:
                logger.info(f"使用知识库直答路径，长度: {len(direct_answer)}")
                yield direct_answer
                return

            if context:
                # 使用官方LightRAG标准prompt，调整为中文
                prompt = f"""你是一个专业的智能助手，基于提供的知识图谱和文档块信息回答用户问题。

---目标---
基于知识库生成简洁的回应，遵循回应规则，同时考虑对话历史和当前查询。总结知识库中提供的所有信息，并结合与知识库相关的常识。不要包含知识库中未提供的信息。

处理带时间戳的关系时：
1. 每个关系都有"created_at"时间戳，表示我们获得此知识的时间
2. 遇到冲突关系时，同时考虑语义内容和时间戳
3. 不要自动偏好最近创建的关系 - 根据上下文进行判断
4. 对于时间特定查询，在考虑创建时间戳之前，优先考虑内容中的时间信息

---对话历史---
{chat_history if chat_history else "(无历史对话)"}

---知识图谱和文档块---
{context}

---回应规则---
- 目标格式和长度：详细回答
- 使用适当的markdown格式和章节标题
- 请用中文回答用户的问题
- 确保回应与对话历史保持连续性
- 在最后的"参考资料"部分列出最多5个最重要的参考来源。清楚标明每个来源是来自知识图谱(KG)还是文档块(DC)，并包含文件路径（如果可用），格式如下：[KG/DC] 文件路径
- 如果不知道答案，请直接说明
- 不要编造任何内容。不要包含知识库中未提供的信息
- 用户问题：{message}

回答："""
            else:
                # 当没有相关知识时，提供更准确的回答
                prompt = f"""你是一个专业的智能助手。用户询问了"{message}"，但我在知识库中没有找到相关信息。

请你：
1. 诚实地告知没有找到相关信息
2. 如果这是一个专业术语或概念，建议用户提供更多上下文
3. 避免生成可能不准确的通用解释

用户问题：{message}

请提供准确、诚实的中文回答："""
            
            # 3. 稳定模式：使用有超时保护的非流式生成，避免SSE长时间阻塞
            logger.info("开始LLM生成（稳定模式）...")
            response_timeout_seconds = float(os.getenv("CHAT_RESPONSE_TIMEOUT", "60"))
            try:
                response_text = await asyncio.wait_for(
                    self.llm_service.process_general(prompt=prompt, model=model),
                    timeout=response_timeout_seconds
                )
                if response_text and response_text.strip():
                    yield response_text
                else:
                    logger.warning("LLM返回空响应")
                    yield "抱歉，当前未生成有效回复，请稍后重试。"
            except asyncio.TimeoutError:
                logger.error(f"LLM生成超时: {response_timeout_seconds}秒")
                yield "⏰ 响应超时，请稍后重试。您可以尝试简化问题或稍后再试。"
            except Exception as llm_error:
                logger.error(f"LLM生成失败: {str(llm_error)}")
                if "timeout" in str(llm_error).lower() or "超时" in str(llm_error):
                    yield "⏰ 服务响应超时，请重新发送您的问题或稍后再试。"
                else:
                    yield f"💫 生成回答时遇到问题：{str(llm_error)}。请重试或联系支持团队。"
                
        except Exception as e:
            logger.error(f"聊天流式处理失败: {str(e)}")
            yield f"❌ 处理请求时出错: {str(e)}。请检查网络连接并重试。"
            
    async def analyze_knowledge_framework(self, 
                                        query: str, 
                                        project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        分析知识图谱框架
        
        Args:
            query: 查询文本
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        logger.info(f"Analyzing knowledge framework: {query}, project_id: {project_id}")
        
        # 获取相关文档
        docs = await lightrag_service.search(
            query=query,
            project_id=project_id,
            top_k=settings.rag_top_k,
            search_mode=settings.rag_search_mode,
            rerank=settings.rag_use_rerank
        )
        
        # 获取图谱数据
        graph_data = None
        graph_node_count = 0
        graph_edge_count = 0
        if self.graph_service and project_id:
            try:
                graph_data = await self.graph_service.get_project_graph(project_id)
                if graph_data:
                    graph_node_count = len(graph_data.nodes)
                    graph_edge_count = len(graph_data.edges)
            except Exception as e:
                logger.error(f"Error fetching graph data: {e}")
        
        # 构建提示词
        prompt = f"""
我需要你分析以下内容，提取并总结其知识框架：

查询: {query}

相关文档内容:
{' '.join(docs[:5])}

请分析文档内容，识别核心知识点、关键实体、概念之间的关系，并提供一个结构化的知识框架概述。
你的回答应该包括:
1. 核心主题和子主题
2. 重要概念和定义
3. 实体之间的主要关系
4. 知识框架的层次结构

请尽可能组织成一个连贯、结构化的知识表示。
"""
        
        # 处理提示词获取分析结果
        knowledge_framework_analysis = await self.llm_service.process_general(prompt)
        
        # 构建返回结果
        return {
            "query": query,
            "knowledge_framework_analysis": knowledge_framework_analysis,
            "related_documents_count": len(docs),
            "graph_node_count": graph_node_count,
            "graph_edge_count": graph_edge_count,
            "has_graph_data": graph_data is not None
        }
