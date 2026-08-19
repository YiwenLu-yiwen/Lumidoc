#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM API路由定义
"""

import logging
import re
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from ..api.models import (
    TextGenerationRequest, TextGenerationResponse,
    ChatMessage, ChatGenerationRequest, ChatGenerationResponse,
    SummaryRequest, SummaryResponse,
    QuestionAnswerRequest, QuestionAnswerResponse,
    JsonTaskRequest, JsonTaskResponse,
    TripleExtractionRequest, TripleExtractionResponse,
    Triple
)
from ..services.llm_service import LLMService

# 创建路由器
router = APIRouter(prefix="/api/v1/llm", tags=["LLM"])
logger = logging.getLogger(__name__)

# 依赖注入：获取LLM服务实例
async def get_llm_service():
    """获取LLM服务实例"""
    return LLMService()

def detect_model_type_intelligent(model_name: str) -> str:
    """
    智能检测模型类型（思考模型或快速模型）
    基于模型架构、参数规模、官方定位等多维度分析
    """
    lower_name = model_name.lower()
    
    # 1. 明确的推理/思考模型
    explicit_thinking_models = [
        'deepseek-r1',     # DeepSeek 推理模型
        'o1',              # OpenAI o1 系列
        'o3',              # OpenAI o3 系列  
        'reasoning',       # 明确标注推理
        'think',           # 明确标注思考
        'cot',             # Chain of Thought
        'chain-of-thought',
        'step-by-step',
        'reflection',
        'analysis'
    ]
    
    for keyword in explicit_thinking_models:
        if keyword in lower_name:
            return 'thinking'
    
    # 2. 基于模型系列和参数规模的智能判断
    model_analysis = analyze_model_characteristics(lower_name)
    
    # 3. 大语言模型系列分析
    if model_analysis['is_large_parameter_model']:
        return 'thinking'
    
    # 4. 专业模型判断
    if model_analysis['is_professional_model']:
        return 'thinking'
    
    # 5. 默认为快速模型
    return 'fast'

def analyze_model_characteristics(model_name: str) -> Dict[str, Any]:
    """分析模型特征"""
    analysis = {
        'is_large_parameter_model': False,
        'is_professional_model': False,
        'model_family': '',
        'parameter_size': 0
    }
    
    # 参数规模提取和分析
    parameter_patterns = [
        r'(\d+)b',           # 如 7b, 13b
        r'(\d+)\.(\d+)b'     # 如 3.5b, 2.7b
    ]
    
    for pattern in parameter_patterns:
        match = re.search(pattern, model_name, re.IGNORECASE)
        if match:
            if '.' in match.group(0):
                size = float(match.group(1) + '.' + match.group(2))
            else:
                size = float(match.group(1))
            analysis['parameter_size'] = size
            break
    
    # 模型系列分析
    if 'qwen' in model_name:
        analysis['model_family'] = 'qwen'
        # Qwen 系列：14B+ 为思考模型，小于14B为快速模型
        analysis['is_large_parameter_model'] = analysis['parameter_size'] >= 14
    elif 'llama' in model_name:
        analysis['model_family'] = 'llama'
        # Llama 系列：13B+ 为思考模型
        analysis['is_large_parameter_model'] = analysis['parameter_size'] >= 13
    elif 'mistral' in model_name or 'mixtral' in model_name:
        analysis['model_family'] = 'mistral'
        # Mistral 系列：7B+ 通常为思考模型（架构优化）
        analysis['is_large_parameter_model'] = analysis['parameter_size'] >= 7
    elif 'gemma' in model_name:
        analysis['model_family'] = 'gemma'
        # Gemma 系列：9B+ 为思考模型
        analysis['is_large_parameter_model'] = analysis['parameter_size'] >= 9
    elif 'claude' in model_name:
        analysis['model_family'] = 'claude'
        # Claude 系列默认为思考模型
        analysis['is_professional_model'] = True
    elif 'gpt' in model_name:
        analysis['model_family'] = 'gpt'
        # GPT 系列默认为思考模型
        analysis['is_professional_model'] = True
    
    # 专业/代码模型判断
    professional_keywords = [
        'codestral',       # 代码专用
        'codeqwen',        # 代码专用
        'wizard',          # 专业模型
        'nous',            # 专业调优
        'solar',           # 专业模型
        'yi-34b',          # 大参数专业模型
    ]
    
    for keyword in professional_keywords:
        if keyword in model_name:
            analysis['is_professional_model'] = True
            break
    
    return analysis

# 文本生成接口
@router.post("/generate", response_model=TextGenerationResponse)
async def generate_text(
    request: TextGenerationRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """生成文本接口"""
    try:
        # 检查是否为流式请求
        if request.stream:
            # 创建流式响应
            async def generate_stream():
                async for chunk in llm_service.stream_generate(
                    request.prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stop_sequences=request.stop_sequences
                ):
                    # 返回JSON格式的流式数据，确保与LLMServiceClient期待的格式匹配
                    import json
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )
        
        # 非流式请求
        response = await llm_service.generate_text(
            request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences
        )
        
        return TextGenerationResponse(
            text=response,
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"文本生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文本生成失败: {str(e)}")

# 聊天生成接口
@router.post("/chat", response_model=ChatGenerationResponse)
async def generate_chat(
    request: ChatGenerationRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """生成聊天回复接口"""
    try:
        # 将Pydantic模型转换为字典列表
        messages = [msg.model_dump() for msg in request.messages]
        
        # 检查是否为流式请求
        if request.stream:
            # 创建流式响应
            async def generate_stream():
                async for chunk in llm_service.stream_chat(
                    messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stop_sequences=request.stop_sequences,
                    model=request.model,
                ):
                    # 返回JSON格式的流式数据，确保与LLMServiceClient期待的格式匹配
                    import json
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )
        
        # 非流式请求
        response = await llm_service.generate_chat(
            messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            model=request.model,
        )
        
        return ChatGenerationResponse(
            message=ChatMessage(role="assistant", content=response),
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"聊天生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"聊天生成失败: {str(e)}")

# 摘要生成接口
@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(
    request: SummaryRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """生成摘要接口"""
    try:
        # 调用摘要服务
        summary = await llm_service.generate_summary(
            request.content,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return SummaryResponse(
            summary=summary,
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"摘要生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {str(e)}")

# 问答接口
@router.post("/question", response_model=QuestionAnswerResponse)
async def answer_question(
    request: QuestionAnswerRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """回答问题接口"""
    try:
        # 调用问答服务
        answer = await llm_service.generate_question_answer(
            request.question,
            context=request.context,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return QuestionAnswerResponse(
            answer=answer,
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"问答生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"问答生成失败: {str(e)}")

# JSON任务接口
@router.post("/json-task", response_model=JsonTaskResponse)
async def process_json_task(
    request: JsonTaskRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """处理JSON任务接口"""
    try:
        # 调用JSON任务处理
        result = await llm_service.process_json_task(
            request.task_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return JsonTaskResponse(
            result=result,
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"JSON任务处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"JSON任务处理失败: {str(e)}")

# 兼容旧版摘要服务的接口
@router.post("/legacy/summary", response_model=Dict[str, Any])
async def legacy_summary(
    request: Dict[str, Any],
    llm_service: LLMService = Depends(get_llm_service)
):
    """兼容旧版摘要服务的接口"""
    try:
        # 从请求中提取内容
        content = request.get("content", "")
        if not content:
            raise HTTPException(status_code=400, detail="请提供要摘要的内容")
        
        # 调用摘要服务
        summary = await llm_service.generate_summary(content)
        
        # 返回与旧接口兼容的格式
        return {
            "summary": summary,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"旧版摘要生成失败: {str(e)}")
        return {
            "summary": "",
            "status": "error",
            "message": str(e)
        }

# 嵌入向量生成接口
class EmbeddingRequest(BaseModel):
    """嵌入向量请求"""
    texts: List[str] = Field(..., description="要生成嵌入的文本列表")
    model: Optional[str] = Field(None, description="模型名称")

class EmbeddingResponse(BaseModel):
    """嵌入向量响应"""
    embeddings: List[List[float]] = Field(..., description="嵌入向量列表")
    usage: Dict[str, Any] = Field(..., description="使用情况统计")

@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """生成文本嵌入向量"""
    try:
        # 调用嵌入服务
        embeddings = await llm_service.create_embeddings(
            request.texts,
            model=request.model,
        )
        
        return EmbeddingResponse(
            embeddings=embeddings,
            usage={"total_tokens": sum(len(text.split()) for text in request.texts)}
        )
    except Exception as e:
        logger.error(f"嵌入向量生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"嵌入向量生成失败: {str(e)}")

# 三元组提取接口
@router.post("/triples", response_model=TripleExtractionResponse)
async def extract_triples(
    request: TripleExtractionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """从文档内容中提取三元组"""
    try:
        # 调用三元组提取服务
        triples = await llm_service.extract_triples(
            request.content,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # 将提取的三元组转换为响应格式
        result_triples = []
        for triple in triples:
            if all(k in triple for k in ["head", "relation", "tail"]):
                result_triples.append(Triple(**triple))
        
        return TripleExtractionResponse(
            triples=result_triples,
            usage={"total_tokens": 0}  # 实际使用中应获取真实token使用量
        )
    except Exception as e:
        logger.error(f"三元组提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"三元组提取失败: {str(e)}")

# 实体提取请求模型
class EntityExtractionRequest(BaseModel):
    query: str
    options: Optional[Dict[str, Any]] = None

# 实体提取响应
class EntityExtractionResponse(BaseModel):
    entities: List[str]

@router.post("/entities", response_model=EntityExtractionResponse)
async def extract_entities(request: EntityExtractionRequest,
    llm_service: LLMService = Depends(get_llm_service)):
    """
    从查询文本中提取实体
    """
    try:
        # 调用LLM提取实体
        prompt = f"""从以下文本中提取关键实体。返回实体列表，不要加任何解释。
        
文本: {request.query}

实体: """
        
        # 获取LLM回答
        response = await llm_service.generate_text(
            prompt=prompt, 
            max_tokens=100,
            temperature=0.1,
            model=request.options.get("model", "default") if request.options else "default"
        )
        
        # 解析实体
        entities = []
        if response:
            # 处理不同格式的响应
            lines = response.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # 处理列表形式 (- Entity)
                    if line.startswith('- '):
                        entities.append(line[2:].strip())
                    # 处理数字列表形式 (1. Entity)
                    elif line[0].isdigit() and '. ' in line:
                        entities.append(line.split('. ', 1)[1].strip())
                    # 处理单行多实体 (Entity1, Entity2)
                    elif ',' in line:
                        for entity in line.split(','):
                            if entity.strip():
                                entities.append(entity.strip())
                    # 单个实体
                    else:
                        entities.append(line)
        
        return EntityExtractionResponse(entities=entities)
    except Exception as e:
        logger.error(f"实体提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =============== Ollama 模型管理 API ===============

# Ollama 模型信息
class OllamaModelInfo(BaseModel):
    name: str = Field(..., description="模型名称")
    size: Optional[int] = Field(None, description="模型大小（字节）")
    digest: Optional[str] = Field(None, description="模型摘要")
    modified: Optional[str] = Field(None, description="修改时间")
    details: Optional[Dict[str, Any]] = Field(None, description="模型详情")

# Ollama 库模型信息
class OllamaLibraryModel(BaseModel):
    name: str = Field(..., description="模型名称")
    description: Optional[str] = Field(None, description="模型描述")
    tags: List[str] = Field(default_factory=list, description="模型标签")
    updated: Optional[str] = Field(None, description="更新时间")
    size: Optional[str] = Field(None, description="模型大小")
    pulls: Optional[int] = Field(None, description="下载次数")

# 模型拉取请求
class ModelPullRequest(BaseModel):
    name: str = Field(..., description="要下载的模型名称")
    insecure: Optional[bool] = Field(False, description="是否允许不安全连接")

# 模型拉取状态
class ModelPullStatus(BaseModel):
    status: str = Field(..., description="下载状态")
    digest: Optional[str] = Field(None, description="当前层摘要")
    total: Optional[int] = Field(None, description="总大小")
    completed: Optional[int] = Field(None, description="已完成大小")
    percentage: Optional[float] = Field(None, description="完成百分比")

# 获取 Ollama 已安装模型列表
@router.get("/models")
async def get_models():
    """获取可用模型列表（增强版，包含Ollama模型识别）"""
    try:
        # 调用现有的模型服务逻辑
        # 这里我们需要访问Ollama API来获取模型列表
        import httpx
        from ..config.config import settings
        
        models = []
        
        # 尝试从Ollama获取模型列表
        try:
            ollama_url = getattr(settings, 'llm_base_url', 'http://localhost:11434')
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model in data.get('models', []):
                        # 检查是否是embedding模型
                        model_name = model.get('name', '').lower()
                        embedding_keywords = ['embed', 'embedding', 'nomic-embed', 'bge-', 'e5-', 'sentence-transformer', 'all-minilm', 'text-embedding']
                        if any(embed_keyword in model_name for embed_keyword in embedding_keywords):
                            continue  # 过滤掉embedding模型
                        
                        # 智能识别模型类型
                        model_type = detect_model_type_intelligent(model_name)
                        
                        models.append({
                            'id': model.get('name'),
                            'name': model.get('name'),
                            'display_name': model.get('name', '').replace(':', ' '),
                            'provider': 'ollama',
                            'type': model_type,
                            'available': True,
                            'size': model.get('size'),
                            'modified': model.get('modified_at')
                        })
        except Exception as e:
            logger.warning(f"无法连接到Ollama: {str(e)}")
        
        return {
            'models': models,
            'total': len(models)
        }
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

# 获取 Ollama 已安装模型
@router.get("/ollama/models")
async def get_ollama_models():
    """获取Ollama已安装的模型列表"""
    try:
        import httpx
        from ..config.config import settings
        
        ollama_url = getattr(settings, 'llm_base_url', 'http://localhost:11434')
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get('models', []):
                # 过滤embedding模型
                model_name = model.get('name', '').lower()
                embedding_keywords = ['embed', 'embedding', 'nomic-embed', 'bge-', 'e5-', 'sentence-transformer', 'all-minilm', 'text-embedding']
                if any(embed_keyword in model_name for embed_keyword in embedding_keywords):
                    continue
                
                models.append(OllamaModelInfo(
                    name=model.get('name'),
                    size=model.get('size'),
                    digest=model.get('digest'),
                    modified=model.get('modified_at'),
                    details=model.get('details', {})
                ))
            
            return {
                'models': models,
                'total': len(models)
            }
    except Exception as e:
        logger.error(f"获取Ollama模型列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Ollama模型列表失败: {str(e)}")

# 下载模型
@router.post("/ollama/pull")
async def pull_model(request: ModelPullRequest, background_tasks: BackgroundTasks):
    """下载Ollama模型"""
    try:
        import httpx
        from ..config.config import settings
        
        # 验证模型名称
        model_name = request.name.strip()
        if not model_name:
            raise HTTPException(status_code=400, detail="模型名称不能为空")
        
        # 检查模型是否已存在
        ollama_url = getattr(settings, 'llm_base_url', 'http://localhost:11434')
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f"{ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    existing_models = [m['name'] for m in data.get('models', [])]
                    if model_name in existing_models:
                        return {
                            'status': 'success',
                            'message': f'模型 {model_name} 已存在',
                            'model': model_name
                        }
            except Exception:
                pass  # 忽略检查错误，继续下载
        
        # 启动后台下载任务
        background_tasks.add_task(download_model_task, model_name, ollama_url)
        
        return {
            'status': 'started',
            'message': f'开始下载模型 {model_name}',
            'model': model_name
        }
    except Exception as e:
        logger.error(f"拉取模型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"拉取模型失败: {str(e)}")

# 获取模型下载状态
@router.get("/ollama/pull/{model_name}/status")
async def get_pull_status(model_name: str):
    """获取模型下载状态"""
    # 这里我们可以检查模型是否已安装
    try:
        import httpx
        from ..config.config import settings
        
        ollama_url = getattr(settings, 'llm_base_url', 'http://localhost:11434')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                existing_models = [m['name'] for m in data.get('models', [])]
                if model_name in existing_models:
                    return {
                        'status': 'completed',
                        'percentage': 100.0,
                        'message': f'模型 {model_name} 已安装完成'
                    }
        
        # 如果模型不存在，返回未找到状态
        return {
            'status': 'not_found',
            'percentage': 0.0,
            'message': f'模型 {model_name} 未找到或下载中'
        }
    except Exception as e:
        logger.error(f"获取下载状态失败: {str(e)}")
        return {
            'status': 'error',
            'percentage': 0.0,
            'message': f'获取状态失败: {str(e)}'
        }

# 后台下载任务
async def download_model_task(model_name: str, ollama_url: str):
    """后台下载模型任务"""
    try:
        import httpx
        import json
        
        logger.info(f"开始下载模型: {model_name}")
        
        async with httpx.AsyncClient(timeout=3600.0) as client:  # 1小时超时
            params = {
                'name': model_name,
                'stream': True
            }
            
            async with client.stream(
                'POST',
                f"{ollama_url}/api/pull",
                json=params,
                headers={'Content-Type': 'application/json'}
            ) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            status = data.get('status', '')
                            logger.info(f"下载进度 [{model_name}]: {status}")
                            
                            if 'error' in data:
                                logger.error(f"下载模型失败 [{model_name}]: {data['error']}")
                                break
                                
                        except json.JSONDecodeError:
                            continue
        
        logger.info(f"模型下载完成: {model_name}")
    except Exception as e:
        logger.error(f"下载模型任务失败 [{model_name}]: {str(e)}")
