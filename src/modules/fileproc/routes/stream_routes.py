#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件流处理路由 - 提供流式文件处理API
"""

import os
import logging
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from ..services.stream_processor import FileProcessorStreamService

logger = logging.getLogger(__name__)

# 创建路由器，统一API前缀
stream_router = APIRouter(
    prefix="/stream",
    tags=["文件流处理"],
    responses={404: {"description": "Not found"}}
)

# 创建流处理服务实例
upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
stream_processor = FileProcessorStreamService(base_dir=upload_dir)

# 定义需要的依赖模拟类
class MockConverter:
    """文档转换器模拟类"""
    def convert(self, source, image_output_dir=None):
        return {"success": True, "message": "文档转换成功"}

class MockOCRProcessor:
    """OCR处理器模拟类"""
    def process(self, image_path, output_path, model_dir):
        return {"success": True, "message": "OCR处理成功"}

class MockLLMClient:
    """LLM客户端模拟类"""
    async def generate_stream(self, prompt, temperature=0):
        yield "这是模拟的LLM生成内容。"
        yield "基于提供的文本生成的摘要。"

# 路由定义
@stream_router.post("/process")
async def process_file_stream(
    file: UploadFile = File(...),
    project_id: str = Form(...),
):
    """
    流式处理文件，实时返回处理状态
    
    Args:
        file: 上传的文件
        project_id: 项目ID
        
    Returns:
        StreamingResponse: 流式响应，包含处理状态和结果
    """
    logger.info(f"接收到流式处理请求: 文件={file.filename}, 项目={project_id}")
    
    # 创建必要的依赖实例
    converter = MockConverter()
    ocr_processor = MockOCRProcessor()
    llm_client = MockLLMClient()
    
    # 定义提示词
    data_summary_prompt = "请总结以下内容:\n{extracted_text}"
    brand_prompt = "请识别以下内容中的品牌信息:\n{extracted_text}"
    
    # 创建流式响应
    async def event_generator():
        async for event in stream_processor.process_file_stream(
            file=file,
            project_id=project_id,
            document_converter=converter,
            layout_ocr_processor=ocr_processor,
            llm_client=llm_client,
            data_summary_prompt=data_summary_prompt,
            brand_prompt=brand_prompt
        ):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    ) 