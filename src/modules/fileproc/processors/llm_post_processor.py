#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM后处理器 - 对docling处理后的内容进行深度总结和格式化
解决OCR扫描质量低导致的大量空白文本问题
"""

import os
import re
import asyncio
from typing import Dict, Any, Optional, List, Tuple

from src.shared.logger import get_logger
from src.shared.service_discovery import call_service

logger = get_logger(__name__)

class LLMPostProcessor:
    """LLM后处理器，对docling处理结果进行智能优化"""
    
    def __init__(self):
        """初始化LLM后处理器"""
        # 从环境变量获取配置
        self.enable_llm_processing = os.environ.get('ENABLE_LLM_POST_PROCESSING', 'false').lower() == 'true'
        self.processing_mode = os.environ.get('LLM_PROCESSING_MODE', 'both')  # summary/format/both
        self.min_content_length = int(os.environ.get('MIN_CONTENT_LENGTH_FOR_LLM', '1000'))
        self.max_empty_lines_ratio = float(os.environ.get('MAX_EMPTY_LINES_RATIO', '0.3'))
        self.llm_model = os.environ.get('LLM_POST_PROCESSING_MODEL', 'deepseek-chat')
        
        # 长文本处理配置
        self.max_chunk_size = int(os.environ.get('LLM_MAX_CHUNK_SIZE', '6000'))  # 单个分段最大字符数
        self.concurrent_limit = int(os.environ.get('LLM_CONCURRENT_LIMIT', '5'))  # 最大并发数
        self.enable_semantic_split = os.environ.get('LLM_SEMANTIC_SPLIT', 'true').lower() == 'true'  # 语义分段
        self.chunk_overlap = int(os.environ.get('LLM_CHUNK_OVERLAP', '200'))  # 分段重叠字符数
        
        logger.info("LLM后处理器初始化:")
        logger.info(f"  启用状态: {'启用' if self.enable_llm_processing else '禁用'}")
        logger.info(f"  处理模式: {self.processing_mode}")
        logger.info(f"  最小内容长度: {self.min_content_length}")
        logger.info(f"  最大空行比例: {self.max_empty_lines_ratio}")
        logger.info(f"  使用模型: {self.llm_model}")
        logger.info(f"  分段大小: {self.max_chunk_size}")
        logger.info(f"  并发限制: {self.concurrent_limit}")
        logger.info(f"  语义分段: {'启用' if self.enable_semantic_split else '禁用'}")
    
    async def process_content(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理docling输出的内容
        
        Args:
            content: docling处理后的markdown内容
            metadata: 文件元数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 检查是否启用LLM后处理
            if not self.enable_llm_processing:
                logger.info("LLM后处理未启用，直接返回原内容")
                return {
                    "success": True,
                    "content": content,
                    "metadata": metadata,
                    "processed": False,
                    "reason": "LLM后处理未启用"
                }
            
            # A PDF text layer is already source text, not OCR output. Rewriting it
            # adds model latency and can change facts because headers repeat.
            if (metadata.get("processor") == "local_pdf"
                    and metadata.get("ocr_enabled") is False
                    and os.getenv("LLM_POST_PROCESS_TEXT_PDF", "false").lower() != "true"):
                return {"success": True, "content": content, "metadata": metadata,
                        "processed": False, "reason": "PDF text layer requires no OCR cleanup"}

            # 检查内容质量
            quality_assessment = self._assess_content_quality(content)
            
            logger.info(f"内容质量评估: {quality_assessment}")
            
            # 如果内容质量良好，不需要处理
            if quality_assessment["needs_processing"] is False:
                logger.info("内容质量良好，无需LLM后处理")
                return {
                    "success": True,
                    "content": content,
                    "metadata": metadata,
                    "processed": False,
                    "reason": "内容质量良好",
                    "quality_assessment": quality_assessment
                }
            
            # 执行LLM后处理
            logger.info(f"内容需要LLM后处理，原因: {quality_assessment['reason']}")
            processed_content = await self._llm_process_content(content, quality_assessment, metadata)
            
            if processed_content:
                # 更新元数据
                processed_metadata = metadata.copy()
                processed_metadata["llm_processed"] = True
                processed_metadata["llm_processing_mode"] = self.processing_mode
                processed_metadata["llm_model"] = self.llm_model
                processed_metadata["original_length"] = len(content)
                processed_metadata["processed_length"] = len(processed_content)
                processed_metadata["quality_assessment"] = quality_assessment
                
                logger.info(f"LLM后处理完成: {len(content)} -> {len(processed_content)} 字符")
                
                return {
                    "success": True,
                    "content": processed_content,
                    "metadata": processed_metadata,
                    "processed": True,
                    "quality_assessment": quality_assessment
                }
            else:
                logger.warning("LLM后处理失败，返回原内容")
                return {
                    "success": True,
                    "content": content,
                    "metadata": metadata,
                    "processed": False,
                    "reason": "LLM后处理失败"
                }
                
        except Exception as e:
            logger.error(f"LLM后处理异常: {str(e)}")
            # 出现异常时返回原内容，确保处理流程不中断
            return {
                "success": True,
                "content": content,
                "metadata": metadata,
                "processed": False,
                "reason": f"处理异常: {str(e)}"
            }
    
    def _assess_content_quality(self, content: str) -> Dict[str, Any]:
        """
        评估内容质量，判断是否需要LLM后处理
        
        Args:
            content: 待评估的内容
            
        Returns:
            Dict[str, Any]: 质量评估结果
        """
        try:
            # 基本统计
            total_length = len(content)
            lines = content.split('\n')
            total_lines = len(lines)
            
            # 统计空行和只有空格的行
            empty_lines = sum(1 for line in lines if not line.strip())
            
            # 统计只有少量字符的行（可能是OCR噪音）
            short_lines = sum(1 for line in lines if 0 < len(line.strip()) < 3)
            
            # 统计重复内容
            unique_lines = set(line.strip() for line in lines if line.strip())
            duplicate_ratio = 1 - (len(unique_lines) / max(total_lines - empty_lines, 1))
            
            # 计算比例
            empty_lines_ratio = empty_lines / max(total_lines, 1)
            short_lines_ratio = short_lines / max(total_lines, 1)
            
            # 统计特殊字符和噪音
            special_char_count = len(re.findall(r'[^\w\s\u4e00-\u9fff.,!?;:()[\]{}"`\'"\'-]', content))
            special_char_ratio = special_char_count / max(total_length, 1)
            
            # 计算有效内容密度
            # 移除空行、短行和特殊字符后的内容长度
            cleaned_content = re.sub(r'\n\s*\n', '\n', content)  # 合并多个空行
            cleaned_content = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()[\]{}"`\'"\'-]', '', cleaned_content)
            effective_content_ratio = len(cleaned_content.strip()) / max(total_length, 1)
            
            # 判断是否需要处理
            needs_processing = False
            reasons = []
            
            # 判断条件
            if total_length < self.min_content_length:
                reasons.append(f"内容过短({total_length}字符)")
            
            if empty_lines_ratio > self.max_empty_lines_ratio:
                needs_processing = True
                reasons.append(f"空行比例过高({empty_lines_ratio:.2%})")
            
            if short_lines_ratio > 0.4:
                needs_processing = True
                reasons.append(f"短行比例过高({short_lines_ratio:.2%})")
            
            if duplicate_ratio > 0.3:
                needs_processing = True
                reasons.append(f"重复内容比例过高({duplicate_ratio:.2%})")
            
            if special_char_ratio > 0.1:
                needs_processing = True
                reasons.append(f"特殊字符比例过高({special_char_ratio:.2%})")
                
            if effective_content_ratio < 0.6:
                needs_processing = True
                reasons.append(f"有效内容密度过低({effective_content_ratio:.2%})")
            
            # 检查是否包含明显的OCR错误模式
            ocr_error_patterns = [
                r'\b[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\b',  # 单字母间有空格
                r'\d\s+\d\s+\d',  # 数字间有不合理空格
                r'[^\s]\s{5,}[^\s]',  # 过多连续空格
                r'[\u4e00-\u9fff]\s+[\u4e00-\u9fff]',  # 中文字符间有空格
            ]
            
            ocr_errors = 0
            for pattern in ocr_error_patterns:
                ocr_errors += len(re.findall(pattern, content))
            
            if ocr_errors > 10:
                needs_processing = True
                reasons.append(f"检测到OCR错误模式({ocr_errors}个)")
            
            return {
                "needs_processing": needs_processing,
                "reason": "; ".join(reasons) if reasons else "内容质量良好",
                "stats": {
                    "total_length": total_length,
                    "total_lines": total_lines,
                    "empty_lines": empty_lines,
                    "empty_lines_ratio": empty_lines_ratio,
                    "short_lines": short_lines,
                    "short_lines_ratio": short_lines_ratio,
                    "duplicate_ratio": duplicate_ratio,
                    "special_char_ratio": special_char_ratio,
                    "effective_content_ratio": effective_content_ratio,
                    "ocr_errors": ocr_errors
                }
            }
            
        except Exception as e:
            logger.error(f"质量评估失败: {str(e)}")
            return {
                "needs_processing": False,
                "reason": f"评估失败: {str(e)}",
                "stats": {}
            }
    
    async def _llm_process_content(self, content: str, quality_assessment: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        """
        使用LLM处理内容（支持长文本并发处理）
        
        Args:
            content: 原始内容
            quality_assessment: 质量评估结果
            metadata: 文件元数据
            
        Returns:
            Optional[str]: 处理后的内容
        """
        try:
            # 检查内容长度，决定是否需要分段处理
            if len(content) > self.max_chunk_size:
                logger.info(f"内容过长({len(content)}字符)，启用分段并发处理")
                return await self._process_long_content_concurrent(content, quality_assessment, metadata)
            else:
                # 短内容直接处理
                return await self._process_single_chunk(content, quality_assessment, metadata, chunk_index=0, total_chunks=1)
                
        except Exception as e:
            logger.error(f"LLM处理失败: {str(e)}")
            return None
    
    async def _process_long_content_concurrent(self, content: str, quality_assessment: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        """
        并发处理长文本
        
        Args:
            content: 长文本内容
            quality_assessment: 质量评估结果
            metadata: 文件元数据
            
        Returns:
            Optional[str]: 处理后的完整内容
        """
        try:
            # 1. 智能分段
            chunks_with_offset = self._split_content_by_semantics(content)
            chunks = [chunk for chunk, _ in chunks_with_offset]
            total_chunks = len(chunks)
            
            logger.info(f"文本分为{total_chunks}个分段，准备并发处理")
            
            # 2. 创建并发任务（限制并发数）
            semaphore = asyncio.Semaphore(self.concurrent_limit)
            
            async def process_with_semaphore(chunk: str, index: int):
                async with semaphore:
                    return await self._process_single_chunk(
                        chunk, quality_assessment, metadata, 
                        chunk_index=index, total_chunks=total_chunks
                    )
            
            # 3. 创建所有任务
            tasks = [
                process_with_semaphore(chunk, i) 
                for i, chunk in enumerate(chunks)
            ]
            
            # 4. 并发执行，保持顺序
            processed_chunks = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 5. 处理结果，包括异常处理
            final_chunks = []
            for i, result in enumerate(processed_chunks):
                if isinstance(result, Exception):
                    logger.warning(f"分段{i+1}/{total_chunks}处理失败: {result}")
                    # 降级策略：使用原始分段
                    final_chunks.append(chunks[i])
                elif result is None:
                    logger.warning(f"分段{i+1}/{total_chunks}处理返回空结果")
                    final_chunks.append(chunks[i])
                else:
                    final_chunks.append(result)
            
            # 6. 拼接结果
            processed_content = "\n\n".join(final_chunks)
            
            # 7. 验证最终结果
            if self._validate_processed_content(processed_content, content):
                logger.info(f"并发处理完成: {len(content)} -> {len(processed_content)} 字符")
                return processed_content
            else:
                logger.warning("并发处理结果验证失败，返回原内容")
                return content
                
        except Exception as e:
            logger.error(f"并发处理长文本失败: {str(e)}")
            return None
    
    async def _process_single_chunk(self, chunk: str, quality_assessment: Dict[str, Any], 
                                   metadata: Dict[str, Any], chunk_index: int, total_chunks: int) -> Optional[str]:
        """
        处理单个文本分段
        
        Args:
            chunk: 文本分段
            quality_assessment: 质量评估结果
            metadata: 文件元数据
            chunk_index: 当前分段索引
            total_chunks: 总分段数
            
        Returns:
            Optional[str]: 处理后的分段内容
        """
        try:
            # 构建分段处理提示词
            processing_prompt = self._build_chunk_processing_prompt(
                chunk, quality_assessment, metadata, chunk_index, total_chunks
            )
            
            # 调用LLM服务
            logger.info(f"处理分段 {chunk_index + 1}/{total_chunks}，长度: {len(chunk)} 字符")
            
            # 重试逻辑
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    response = await call_service(
                        service_name="llm",
                        endpoint="/api/v1/llm/chat",
                        method="POST",
                        json_data={
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "你是一个专业的文档处理专家，擅长清理、格式化和总结文档内容。"
                                },
                                {
                                    "role": "user", 
                                    "content": processing_prompt
                                }
                            ],
                            "model": self.llm_model,
                            "temperature": 0.1,  # 低温度确保输出稳定
                            "max_tokens": min(len(chunk) * 2, 8000),  # 限制输出长度
                        },
                        timeout=120.0,  # 设置请求超时为120秒
                        use_service_auth=True  # 启用服务间认证
                    )
                    # 如果成功，跳出重试循环
                    break
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"分段{chunk_index + 1} LLM服务调用失败 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}")
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    else:
                        # 最后一次尝试也失败了，抛出异常
                        logger.error(f"分段{chunk_index + 1} LLM服务调用失败 (所有重试都失败): {str(e)}")
                        raise
            
            # 解析响应
            processed_content = self._parse_llm_response(response)
            
            if processed_content:
                logger.info(f"分段 {chunk_index + 1}/{total_chunks} 处理完成")
                return processed_content
            else:
                logger.warning(f"分段 {chunk_index + 1}/{total_chunks} 处理失败")
                return None
                
        except Exception as e:
            logger.error(f"处理分段 {chunk_index + 1} 失败: {str(e)}")
            return None
    
    def _parse_llm_response(self, response: Any) -> Optional[str]:
        """解析LLM响应，兼容不同格式"""
        try:
            if not response:
                return None
            
            # 检查错误响应
            if isinstance(response, dict) and response.get("success") is False:
                error_msg = response.get("error", "未知错误")
                logger.error(f"LLM服务返回错误: {error_msg}")
                return None
            
            # 尝试不同的响应格式
            if isinstance(response, str):
                return response
            elif isinstance(response, dict):
                # Lumidoc格式
                if "message" in response and "content" in response["message"]:
                    return response["message"]["content"]
                # OpenAI格式
                elif "choices" in response and len(response["choices"]) > 0:
                    return response["choices"][0]["message"]["content"]
                # 简单格式
                elif "content" in response:
                    return response["content"]
            
            logger.error(f"无法解析LLM响应格式: {type(response)}")
            return None
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
            return None
    
    def _build_processing_prompt(self, content: str, quality_assessment: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        构建LLM处理提示词
        
        Args:
            content: 原始内容
            quality_assessment: 质量评估结果
            metadata: 文件元数据
            
        Returns:
            str: 处理提示词
        """
        file_type = metadata.get("file_type", "unknown")
        ocr_enabled = metadata.get("ocr_enabled", False)
        quality_stats = quality_assessment.get("stats", {})
        
        prompt = f"""请处理以下文档内容，这是通过docling{'(启用OCR)' if ocr_enabled else ''}从{file_type}文件提取的内容。

**内容质量问题:**
{quality_assessment.get('reason', '未知')}

**质量统计:**
- 总长度: {quality_stats.get('total_length', 0)} 字符
- 空行比例: {quality_stats.get('empty_lines_ratio', 0):.2%}
- 有效内容密度: {quality_stats.get('effective_content_ratio', 0):.2%}
- OCR错误: {quality_stats.get('ocr_errors', 0)} 个

**处理要求:**
"""

        if self.processing_mode in ['summary', 'both']:
            prompt += """
1. **内容保留**: 保留文档的完整信息和所有要点，不进行总结压缩
2. **质量清理**: 仅去除明显的OCR噪音和重复的空行，保持内容完整性
"""

        if self.processing_mode in ['format', 'both']:
            prompt += """
3. **格式优化**: 
   - 修正因OCR导致的格式问题（如不合理的空格、断行）
   - 重新组织段落结构，提高可读性
   - 统一标题层级和列表格式
   - 修复表格和引用格式
"""

        prompt += """
4. **内容完整性优先**: 
   - 保留原文的所有信息和完整内容结构
   - 保持原始的标题、段落、列表、表格等格式层次
   - 不要删除、总结或压缩任何内容，优先保持完整性
   - 仅修正明显的OCR错误，不改变原意和结构

5. **格式修复原则**:
   - 修正因OCR导致的错误空格和断行（如"J B HI-FI" → "JB HI-FI"）
   - 恢复表格和列表的正确对齐格式
   - 修复被误识别的特殊字符和符号
   - 保持原有的信息层次和排版逻辑

6. **严格输出要求**: 
   - 直接输出修复后的txt格式原始文档

**请注意**: 处理后的内容必须保持原始文档的完整性和信息量，避免任何形式的内容压缩或总结。只进行必要的格式修复和清理，不改变原意和结构。
禁止输出任何指导语或注释，直接输出处理后的内容。
**原始内容:**
---
"""

        # 限制输入内容长度，避免超过模型限制
        max_content_length = 8000
        if len(content) > max_content_length:
            prompt += content[:max_content_length] + "\n\n[内容因长度限制被截断...]"
        else:
            prompt += content

        return prompt
    
    def _build_chunk_processing_prompt(self, chunk: str, quality_assessment: Dict[str, Any], 
                                     metadata: Dict[str, Any], chunk_index: int, total_chunks: int) -> str:
        """
        构建分段处理提示词
        
        Args:
            chunk: 文本分段
            quality_assessment: 质量评估结果
            metadata: 文件元数据
            chunk_index: 当前分段索引
            total_chunks: 总分段数
            
        Returns:
            str: 分段处理提示词
        """
        file_type = metadata.get("file_type", "unknown")
        ocr_enabled = metadata.get("ocr_enabled", False)
        
        prompt = f"""请处理以下文档分段内容（第{chunk_index + 1}部分，共{total_chunks}部分）。
这是通过docling{'(启用OCR)' if ocr_enabled else ''}从{file_type}文件提取的内容。

**注意事项:**
1. 这是文档的一个分段，请保持内容的连续性
2. 不要添加开头或结尾的总结性语句
3. 保持原有的格式和结构
4. 仅清理明显的OCR错误和格式问题

**处理要求:**
"""

        if self.processing_mode in ['format', 'both']:
            prompt += """
- 修正OCR导致的格式问题（如不合理的空格、断行）
- 保持段落结构和层次关系
- 修复明显的识别错误
"""

        prompt += """
**严格要求:**
- 保留所有原始信息，不进行总结或压缩
- 仅输出处理后的内容，不要任何额外说明
- 保持与其他分段的连贯性

**分段内容:**
---
"""
        
        prompt += chunk
        
        return prompt
    
    def _validate_processed_content(self, processed_content: str, original_content: str) -> bool:
        """
        验证处理后的内容是否合理
        
        Args:
            processed_content: 处理后的内容
            original_content: 原始内容
            
        Returns:
            bool: 是否通过验证
        """
        try:
            # 基本检查
            if not processed_content or not processed_content.strip():
                logger.warning("处理后内容为空")
                return False
            
            # 长度检查 - 处理后的内容不应该比原内容长太多
            # if len(processed_content) > len(original_content) * 2:
            #     logger.warning(f"处理后内容过长: {len(processed_content)} vs {len(original_content)}")
            #     return False
            
            # 最小长度检查 - 处理后的内容不应该太短（除非原内容确实很短）
            # if len(processed_content) < min(len(original_content) * 0.1, 100):
            #     logger.warning(f"处理后内容过短: {len(processed_content)} vs {len(original_content)}")
            #     return False
            
            # 检查是否包含明显的AI生成标识（应该避免）
            # ai_indicators = [
            #     "作为AI助手", "我来帮您", "根据文档内容", "以下是总结",
            #     "很抱歉", "无法处理", "请注意", "建议您", "我帮您优化了",
            #     "根据要求进行了", "此markdown格式", "已根据处理要求",
            #     "处理后的文档", "注:", "**注:**", "此内容已", "已经优化",
            #     "以上是", "总结如下", "整理如下", "优化后的内容"
            # ]
            
            # for indicator in ai_indicators:
            #     if indicator in processed_content:
            #         logger.warning(f"检测到AI生成标识: {indicator}")
            #         return False
            
            return True
            
        except Exception as e:
            logger.error(f"内容验证失败: {str(e)}")
            return False
    
    def _split_content_by_semantics(self, content: str) -> List[Tuple[str, int]]:
        """
        按语义边界智能分段
        
        Args:
            content: 待分段的内容
            
        Returns:
            List[Tuple[str, int]]: 分段列表，每个元素为(分段内容, 起始位置)
        """
        if not self.enable_semantic_split:
            # 简单分段
            return self._simple_split(content)
        
        chunks = []
        
        # 1. 首先尝试按标题分段（# ## ### 等）
        title_pattern = r'^#{1,6}\s+.+$'
        title_positions = [(m.start(), m.end()) for m in re.finditer(title_pattern, content, re.MULTILINE)]
        
        if title_positions:
            # 按标题分段
            for i in range(len(title_positions)):
                start = title_positions[i][0]
                end = title_positions[i + 1][0] if i + 1 < len(title_positions) else len(content)
                chunk = content[start:end].strip()
                
                # 检查分段大小
                if len(chunk) > self.max_chunk_size:
                    # 分段过大，需要进一步分割
                    sub_chunks = self._split_large_section(chunk, start)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append((chunk, start))
        else:
            # 2. 没有标题，按段落分段
            chunks = self._split_by_paragraphs(content)
        
        # 3. 合并过小的分段
        chunks = self._merge_small_chunks(chunks)
        
        return chunks
    
    def _simple_split(self, content: str) -> List[Tuple[str, int]]:
        """简单分段（按固定大小）"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + self.max_chunk_size, len(content))
            
            # 尝试在句子边界断开
            if end < len(content):
                # 查找最近的句子结束符
                sentence_ends = ['. ', '。', '！', '？', '! ', '? ', '\n\n']
                best_end = end
                
                for sep in sentence_ends:
                    pos = content.rfind(sep, start + self.max_chunk_size // 2, end)
                    if pos != -1:
                        best_end = pos + len(sep)
                        break
                
                end = best_end
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append((chunk, start))
            
            # 添加重叠
            start = end - self.chunk_overlap if end < len(content) else end
        
        return chunks
    
    def _split_large_section(self, section: str, base_offset: int) -> List[Tuple[str, int]]:
        """分割过大的章节"""
        # 首先尝试按段落分割
        paragraphs = re.split(r'\n\s*\n', section)
        chunks = []
        current_chunk = ""
        current_offset = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 > self.max_chunk_size and current_chunk:
                chunks.append((current_chunk.strip(), base_offset + current_offset))
                current_offset += len(current_chunk) + 2
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append((current_chunk.strip(), base_offset + current_offset))
        
        # 如果仍有过大的段落，使用简单分割
        final_chunks = []
        for chunk, offset in chunks:
            if len(chunk) > self.max_chunk_size:
                sub_chunks = self._simple_split(chunk)
                for sub_chunk, sub_offset in sub_chunks:
                    final_chunks.append((sub_chunk, offset + sub_offset))
            else:
                final_chunks.append((chunk, offset))
        
        return final_chunks
    
    def _split_by_paragraphs(self, content: str) -> List[Tuple[str, int]]:
        """按段落分段"""
        paragraphs = re.split(r'\n\s*\n', content)
        chunks = []
        current_chunk = ""
        current_offset = 0
        chunk_start = 0
        
        for para in paragraphs:
            para_len = len(para) + 2  # 包括段落分隔符
            
            if len(current_chunk) + para_len > self.max_chunk_size and current_chunk:
                chunks.append((current_chunk.strip(), chunk_start))
                current_chunk = para
                chunk_start = current_offset
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            
            current_offset += para_len
        
        if current_chunk:
            chunks.append((current_chunk.strip(), chunk_start))
        
        return chunks
    
    def _merge_small_chunks(self, chunks: List[Tuple[str, int]]) -> List[Tuple[str, int]]:
        """合并过小的分段"""
        if not chunks:
            return chunks
        
        merged_chunks = []
        current_chunk = chunks[0][0]
        current_offset = chunks[0][1]
        
        for i in range(1, len(chunks)):
            chunk, offset = chunks[i]
            
            # 如果当前分段过小，尝试与下一个合并
            if len(current_chunk) < self.max_chunk_size // 3:
                if len(current_chunk) + len(chunk) + 2 <= self.max_chunk_size:
                    current_chunk += "\n\n" + chunk
                    continue
            
            merged_chunks.append((current_chunk, current_offset))
            current_chunk = chunk
            current_offset = offset
        
        merged_chunks.append((current_chunk, current_offset))
        
        return merged_chunks
