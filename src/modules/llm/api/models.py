#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM API模型定义
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class TextGenerationRequest(BaseModel):
    """文本生成请求"""
    prompt: str = Field(..., description="生成提示词")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")
    stop_sequences: Optional[List[str]] = Field(None, description="停止生成的序列")
    stream: Optional[bool] = Field(False, description="是否启用流式生成")

class TextGenerationResponse(BaseModel):
    """文本生成响应"""
    text: str = Field(..., description="生成的文本")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")

class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="消息角色，如'system', 'user', 'assistant'")
    content: str = Field(..., description="消息内容")

class ChatGenerationRequest(BaseModel):
    """聊天生成请求"""
    messages: List[ChatMessage] = Field(..., description="聊天消息历史")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")
    stop_sequences: Optional[List[str]] = Field(None, description="停止生成的序列")
    stream: Optional[bool] = Field(False, description="是否启用流式生成")
    model: Optional[str] = Field(
        None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:/-]+$",
        description="本次请求使用的模型ID",
    )

class ChatGenerationResponse(BaseModel):
    """聊天生成响应"""
    message: ChatMessage = Field(..., description="生成的消息")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")

class SummaryRequest(BaseModel):
    """摘要生成请求"""
    content: str = Field(..., description="需要摘要的内容")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")

class SummaryResponse(BaseModel):
    """摘要生成响应"""
    summary: str = Field(..., description="生成的摘要")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")

class QuestionAnswerRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="问题内容")
    context: Optional[str] = Field(None, description="上下文信息")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")

class QuestionAnswerResponse(BaseModel):
    """问答响应"""
    answer: str = Field(..., description="生成的回答")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")

class JsonTaskRequest(BaseModel):
    """JSON任务请求"""
    task_prompt: str = Field(..., description="任务提示词")
    task_type: Optional[str] = Field(None, description="任务类型")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")

class JsonTaskResponse(BaseModel):
    """JSON任务响应"""
    result: Dict[str, Any] = Field(..., description="任务结果JSON")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")

class Triple(BaseModel):
    """三元组数据模型"""
    head: str = Field(..., description="头实体")
    relation: str = Field(..., description="关系")
    tail: str = Field(..., description="尾实体")

class TripleExtractionRequest(BaseModel):
    """三元组提取请求"""
    content: str = Field(..., description="需要提取三元组的内容")
    file_id: Optional[str] = Field(None, description="文件ID，如果内容来自文件")
    project_id: Optional[str] = Field(None, description="项目ID")
    temperature: Optional[float] = Field(None, description="采样温度，控制随机性")
    max_tokens: Optional[int] = Field(None, description="最大生成令牌数")

class TripleExtractionResponse(BaseModel):
    """三元组提取响应"""
    triples: List[Triple] = Field(..., description="提取的三元组列表")
    usage: Optional[Dict[str, int]] = Field(None, description="token使用情况")
