"""
LLM工具服务模块
提供聊天服务使用的LLM工具功能
"""

import logging
from typing import Dict, Any, List, Optional, AsyncGenerator, Union

# 导入共享LLM客户端
from src.shared.clients.llm_service_client import LLMServiceClient
from src.shared.clients.lightrag_client import LightRAGServiceClient
from src.modules.lightraglocal.config.config import config

# 配置日志
logger = logging.getLogger(__name__)

class LLMToolService:
    """LLM工具服务类，为聊天服务提供LLM功能"""
    
    def __init__(self):
        """初始化LLM工具服务"""
        # 创建LLM服务客户端
        self.llm_client = None
        self.lightrag_client = LightRAGServiceClient()
        logger.info("LLM工具服务初始化完成")
    
    async def _get_llm_client(self):
        """获取LLM客户端实例（单例模式）"""
        if self.llm_client is None:
            self.llm_client = await LLMServiceClient.get_instance()
        return self.llm_client
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 2000,
        stream: bool = False,
        **kwargs
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        聊天完成
        
        Args:
            messages: 聊天消息列表
            temperature: 温度参数
            max_tokens: 最大生成token数
            stream: 是否使用流式生成
            **kwargs: 其他参数
            
        Returns:
            聊天回复文本或文本流
        """
        try:
            llm_client = await self._get_llm_client()
            if stream:
                # 流式生成 - 构造提示词
                prompt = self._messages_to_prompt(messages)
                return llm_client.stream_generate(
                    prompt=prompt,
                    temperature=temperature,
                    **kwargs
                )
            else:
                # 普通生成
                return await llm_client.chat_generate(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
        except Exception as e:
            logger.error(f"聊天完成失败: {str(e)}")
            error_message = f"生成错误: {str(e)}"
            if stream:
                async def error_stream():
                    yield error_message
                return error_stream()
            return error_message
    
    async def rag_chat(
        self,
        query: str,
        project_id: str,
        history: Optional[List[Dict[str, str]]] = None,
        search_mode: str = None,
        stream: bool = False,
        **kwargs
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        RAG增强聊天
        
        Args:
            query: 用户查询
            project_id: 项目ID
            history: 聊天历史
            search_mode: 搜索模式
            stream: 是否使用流式生成
            **kwargs: 其他参数
            
        Returns:
            聊天回复文本或文本流
        """
        try:
            # 使用配置中的默认查询模式
            if search_mode is None:
                search_mode = config.default_query_mode
            
            # 调用LightRAG服务
            if stream:
                # 使用query_knowledge方法的流式版本
                options = {
                    "mode": search_mode,
                    "stream": True
                }
                return await self.lightrag_client.query_knowledge(
                    project_id=project_id,
                    question=query,
                    chat_history=history or [],
                    options=options,
                    **kwargs
                )
            else:
                # 使用query_knowledge方法
                options = {
                    "mode": search_mode,
                    "stream": False
                }
                result = await self.lightrag_client.query_knowledge(
                    project_id=project_id,
                    question=query,
                    chat_history=history or [],
                    options=options,
                    **kwargs
                )
                return result.get("answer", "无法获取回答")
        except Exception as e:
            logger.error(f"RAG聊天失败: {str(e)}")
            error_message = f"RAG聊天生成错误: {str(e)}"
            if stream:
                async def error_stream():
                    yield error_message
                return error_stream()
            return error_message
    
    async def generate_summary(self, content: str, **kwargs) -> str:
        """
        生成文本摘要
        
        Args:
            content: 输入文本内容
            **kwargs: 其他参数
            
        Returns:
            str: 生成的摘要
        """
        try:
            llm_client = await self._get_llm_client()
            return await llm_client.generate_summary(content, **kwargs)
        except Exception as e:
            logger.error(f"摘要生成失败: {str(e)}")
            return f"摘要生成错误: {str(e)}"
    
    async def extract_knowledge_graph(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        从文本提取知识图谱
        
        Args:
            content: 文本内容
            **kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 知识图谱数据
        """
        try:
            llm_client = await self._get_llm_client()
            return await llm_client.extract_knowledge_graph(content, **kwargs)
        except Exception as e:
            logger.error(f"知识图谱提取失败: {str(e)}")
            return {"nodes": [], "edges": [], "error": str(e)}

    async def stream_generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回复，支持思考模型
        
        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本片段
        """
        try:
            # 构造标准的聊天消息格式
            messages = [{"role": "user", "content": prompt}]
            
            # 使用chat_completion的流式功能
            stream_generator = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )
            
            # 迭代流式输出
            async for chunk in stream_generator:
                # 处理思考模型的输出
                yield self._process_thinking_model_output(chunk)
        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            yield f"生成错误: {str(e)}"

    async def process_general(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        **kwargs
    ) -> str:
        """
        处理一般文本生成请求，支持思考模型
        
        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的回复
        """
        try:
            # 构造标准的聊天消息格式
            messages = [{"role": "user", "content": prompt}]
            
            # 使用chat_completion的非流式功能
            response = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                **kwargs
            )
            
            # 处理思考模型的输出
            return self._process_thinking_model_output(response)
        except Exception as e:
            logger.error(f"一般文本生成失败: {str(e)}")
            return f"生成错误: {str(e)}"

    def _process_thinking_model_output(self, content: str) -> str:
        """
        处理思考模型的输出，提取思考内容和正文
        
        Args:
            content: 原始输出内容
            
        Returns:
            str: 处理后的内容，包含思考标记
        """
        import re
        
        # 检测思考标签模式（如deepseek-r1的<think>...</think>）
        think_pattern = r'<think>(.*?)</think>'
        matches = re.findall(think_pattern, content, re.DOTALL)
        
        if matches:
            # 提取思考内容和正文
            thinking_content = matches[0].strip()
            # 移除思考标签，获取正文
            main_content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()
            
            # 格式化输出：思考内容 + 正文
            if thinking_content and main_content:
                return f"🤔 **思考过程：**\n{thinking_content}\n\n**回答：**\n{main_content}"
            elif thinking_content:
                return f"🤔 **思考过程：**\n{thinking_content}"
            else:
                return main_content
        else:
            # 没有思考标签，直接返回原内容
            return content

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        将消息列表转换为提示词格式
        
        Args:
            messages: 消息列表
            
        Returns:
            str: 格式化的提示词
        """
        prompt_parts = []
        
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"{role}: {content}")
        
        return "\n\n".join(prompt_parts)

# 创建全局LLM工具服务实例
llm_tool_service = LLMToolService() 