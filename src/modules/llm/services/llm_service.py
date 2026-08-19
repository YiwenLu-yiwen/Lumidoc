#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一LLM服务
提供各种LLM处理功能，包括摘要、聊天等
"""

import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
from ..config.config import settings

# 导入共享LLM适配器
from src.shared.llm.adapters import create_llm_adapter
from src.shared.llm.langchain import LumidocLangChainLLM

logger = logging.getLogger(__name__)

class LLMService:
    """统一LLM服务类 - 单例模式"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化LLM服务 - 只初始化一次"""
        if LLMService._initialized:
            return
            
        # 创建LLM适配器
        self.adapter = create_llm_adapter(
            model_type=settings.llm_model_type,
            model_name=settings.llm_model_name,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )

        # 嵌入模型与生成模型用途不同，不能复用聊天模型名称。
        self.embedding_adapter = create_llm_adapter(
            model_type=settings.llm_model_type,
            model_name=settings.embedding_model_name,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        
        LLMService._initialized = True
        
        # 创建LangChain LLM
        self.langchain_llm = LumidocLangChainLLM(
            model_type=settings.llm_model_type,
            model_name=settings.llm_model_name,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            api_key=settings.llm_api_key
        )
        
        # LLM参数
        self.default_params = {
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "timeout": settings.request_timeout
        }
        
        logger.info(f"LLM服务初始化完成，使用模型: {settings.llm_model_type}/{settings.llm_model_name}")
    
    async def generate_text(self, prompt: str, **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数，会覆盖默认参数
            
        Returns:
            str: 生成的文本
        """
        try:
            # 合并参数
            params = {**self.default_params, **kwargs}
            
            # 调用适配器
            response = await self.adapter.generate(prompt, **params)
            return response
        except Exception as e:
            logger.error(f"文本生成失败: {str(e)}")
            raise
    
    async def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        生成聊天回复
        
        Args:
            messages: 聊天历史消息列表
            **kwargs: 其他参数，会覆盖默认参数
            
        Returns:
            str: 生成的回复
        """
        try:
            # 合并参数
            params = {**self.default_params, **kwargs}
            
            # 调用适配器 - 修复方法名
            response = await self.adapter.chat(messages, **params)
            return response
        except Exception as e:
            logger.error(f"聊天生成失败: {str(e)}")
            raise
    
    async def create_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        创建文本嵌入向量
        
        Args:
            texts: 文本列表
            **kwargs: 其他参数
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        try:
            selected_model = kwargs.get("model") or settings.embedding_model_name
            adapter = self.embedding_adapter
            if selected_model != settings.embedding_model_name:
                adapter = create_llm_adapter(
                    model_type=settings.llm_model_type,
                    model_name=selected_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )

            embeddings = await adapter.create_embedding(texts)
            return embeddings
        except Exception as e:
            logger.error(f"嵌入向量创建失败: {str(e)}")
            raise
    
    async def stream_generate(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        流式生成文本
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数，会覆盖默认参数
            
        Returns:
            AsyncGenerator: 生成的文本流
        """
        try:
            # 合并参数
            params = {**self.default_params, **kwargs}
            
            # 调用适配器流式生成 - 修复方法名
            async for chunk in self.adapter.generate_stream(prompt, **params):
                yield chunk
        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            yield f"生成错误: {str(e)}"
    
    async def stream_chat(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        流式生成聊天回复
        
        Args:
            messages: 聊天历史消息列表
            **kwargs: 其他参数，会覆盖默认参数
            
        Returns:
            AsyncGenerator: 生成的回复流
        """
        try:
            # 合并参数
            params = {**self.default_params, **kwargs}
            
            # 调用适配器流式生成 - 修复方法名
            async for chunk in self.adapter.chat_stream(messages, **params):
                yield chunk
        except Exception as e:
            logger.error(f"流式聊天生成失败: {str(e)}")
            yield f"生成错误: {str(e)}"
    
    async def generate_summary(self, content: str, **kwargs) -> str:
        """
        生成文本摘要
        
        Args:
            content: 输入文本内容
            **kwargs: 其他参数
            
        Returns:
            str: 生成的摘要
        """
        # 构建摘要提示词
        prompt = f"""请为以下内容生成一个简洁且全面的摘要。摘要应包含主要观点和关键信息，同时保持逻辑连贯性。

内容：
{content}

摘要："""
        
        return await self.generate_text(prompt, **kwargs)
    
    async def generate_question_answer(self, question: str, context: Optional[str] = None, **kwargs) -> str:
        """
        生成问题回答
        
        Args:
            question: 问题文本
            context: 上下文信息（可选）
            **kwargs: 其他参数
            
        Returns:
            str: 生成的回答
        """
        # 构建问答提示词
        if context:
            prompt = f"""基于以下信息回答问题：

背景信息：
{context}

问题：{question}

回答："""
        else:
            prompt = f"""请回答以下问题：

问题：{question}

回答："""
        
        return await self.generate_text(prompt, **kwargs)
    
    async def process_json_task(self, task_prompt: str, **kwargs) -> Dict[str, Any]:
        """
        处理需要JSON输出的任务
        
        Args:
            task_prompt: 任务提示词
            **kwargs: 其他参数
            
        Returns:
            Dict[str, Any]: 解析后的JSON结果
        """
        try:
            # 生成文本
            response = await self.generate_text(task_prompt, **kwargs)
            
            # 解析JSON
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"JSON任务处理失败: {str(e)}")
            return {"error": str(e)}
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析JSON响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            Dict[str, Any]: 解析后的JSON数据
        """
        import re
        import json
        
        # 尝试从Markdown代码块提取JSON
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        
        # 尝试从响应中提取任何JSON对象
        match = re.search(r"(\{.*\})", response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        
        # 如果无法解析，返回空字典
        return {}
        
    async def extract_triples(self, content: str, **kwargs) -> List[Dict[str, str]]:
        """
        从文档内容中提取三元组
        
        Args:
            content: 文档内容
            **kwargs: 其他参数
            
        Returns:
            List[Dict[str, str]]: 三元组列表，每个三元组包含head, relation, tail
        """
        try:
            # 构建提取三元组的提示词
            prompt = f"""请从以下内容中提取实体关系三元组。
            每个三元组由(头实体, 关系, 尾实体)组成。
            提取时需遵循以下规则:
            1. 实体应为名词性短语，表示人物、地点、组织、概念等
            2. 关系应为动词性短语，表示两个实体间的关联
            3. 请输出最多20个最重要的三元组
            4. 只输出标准的JSON格式，结构为数组，每个元素包含"head", "relation", "tail"三个字段

            内容:
            {content}
            
            请输出JSON格式的三元组：
            ```json
            [
              {"head": "头实体1", "relation": "关系1", "tail": "尾实体1"},
              {"head": "头实体2", "relation": "关系2", "tail": "尾实体2"}
            ]
            ```
            只输出JSON，不要有其他解释内容。
            """
            
            # 调用LLM进行提取
            response = await self.generate_text(prompt, **kwargs)
            
            # 尝试从响应中提取JSON数组
            import re
            import json
            
            # 首先尝试从Markdown代码块提取JSON
            match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL)
            if match:
                try:
                    triples = json.loads(match.group(1))
                    return triples
                except Exception as e:
                    logger.error(f"解析三元组JSON失败(代码块): {str(e)}")
            
            # 然后尝试提取任何形式的JSON数组
            match = re.search(r"(\[.*?\])", response, re.DOTALL)
            if match:
                try:
                    triples = json.loads(match.group(1))
                    return triples
                except Exception as e:
                    logger.error(f"解析三元组JSON失败(数组): {str(e)}")
            
            logger.error(f"未能从响应中提取三元组: {response[:200]}...")
            return []
            
        except Exception as e:
            logger.error(f"提取三元组失败: {str(e)}")
            return []
