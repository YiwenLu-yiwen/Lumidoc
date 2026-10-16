#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Docling处理器 - 使用docling处理PDF文件并转换为Markdown
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
import traceback
import shutil
import aiofiles

from src.shared.logger import get_logger
from .llm_post_processor import LLMPostProcessor

# 设置huggingface镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
# 使用共享日志记录器
logger = get_logger(__name__)

class DoclingProcessor:
    """Docling处理器，用于处理PDF文件并转换为Markdown"""
    
    def __init__(self, rapidocr_models_path: Optional[str] = None):
        """
        初始化Docling处理器
        
        Args:
            rapidocr_models_path: RapidOCR模型路径，如不指定则使用默认路径
        """
        # 从环境变量获取OCR配置
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        self.enable_ocr = os.environ.get('ENABLE_OCR', 'false').lower() == 'true'
        default_models_path = os.path.abspath(os.path.join(project_root, "src/models/RapidOCR"))
        
        # 获取环境变量中的模型路径，如果是相对路径则转换为绝对路径
        env_models_path = os.environ.get('RAPIDOCR_MODELS_PATH', default_models_path)
        if not os.path.isabs(env_models_path):
            env_models_path = os.path.abspath(os.path.join(project_root, env_models_path))
        
        self.rapidocr_models_path = rapidocr_models_path or env_models_path
        logger.info(f"DoclingProcessor初始化: OCR识别状态: {'启用' if self.enable_ocr else '禁用'}")
        logger.info(f"RapidOCR模型路径: {self.rapidocr_models_path}")
        logger.info(f"模型路径是否存在: {os.path.exists(self.rapidocr_models_path)}")
        
        # 检查docling可用性
        self.docling_available = self._check_docling_available()
        
        # 初始化LLM后处理器
        self.llm_post_processor = LLMPostProcessor()
        
    def _check_docling_available(self) -> bool:
        """检查Docling是否可用"""
        try:
            import docling
            version = getattr(docling, "__version__", "未知版本")
            logger.info(f"成功导入docling库，版本: {version}")
            return True
        except ImportError as e:
            logger.error(f"导入docling库失败: {e}")
            # 尝试安装docling
            try:
                logger.info("尝试自动安装docling...")
                import subprocess
                subprocess.check_call(["pip", "install", "docling", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])
                import docling
                version = getattr(docling, "__version__", "未知版本")
                logger.info(f"成功安装并导入docling库，版本: {version}")
                return True
            except Exception as install_err:
                logger.error(f"自动安装docling失败: {install_err}")
                return False
        
    async def process_pdf(self, file_path: str, enable_ocr: bool = None) -> Dict[str, Any]:
        """
        处理PDF文件，提取文本内容
        
        Args:
            file_path: PDF文件路径
            enable_ocr: 是否启用OCR识别
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        temp_file = None
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return {
                    "success": False,
                    "error": f"文件不存在: {file_path}",
                    "message": "文件不存在"
                }
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"文件大小: {file_size_mb:.2f} MB")
            
            # 创建临时文件副本，避免直接操作原文件
            temp_dir = os.path.join(os.path.dirname(file_path), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_file = os.path.join(temp_dir, f"temp_{os.path.basename(file_path)}")
            shutil.copy2(file_path, temp_file)
            logger.info(f"已创建临时文件副本: {temp_file}")
            
            # 根据OCR设置选择处理方式
            if os.environ.get('PDF_PROCESSOR', 'docling') == 'local':
                from .local_pdf import extract_pdf_locally
                result = await asyncio.to_thread(
                    extract_pdf_locally, temp_file, self.rapidocr_models_path
                )
            elif enable_ocr or self.enable_ocr:
                logger.info(f"使用OCR方式处理PDF: {temp_file}")
                result = await self._process_pdf_with_ocr(temp_file)
            else:
                logger.info(f"使用标准方式处理PDF: {temp_file}")
                result = await self._process_pdf_standard(temp_file)
            
            # 检查处理结果
            if not result or not result.get("success", False):
                error_message = result.get("error", "处理PDF失败，未知错误") if result else "处理PDF失败，未返回结果"
                logger.error(f"处理PDF失败: {error_message}")
                return {
                    "success": False,
                    "error": error_message,
                    "message": "处理PDF失败"
                }
            
            # 处理成功，获取初步结果
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            page_count = result.get("page_count", 0)
            
            # 计算文件哈希值
            file_hash = self._calculate_file_hash(file_path)
            metadata["file_hash"] = file_hash
            
            # 执行LLM后处理
            logger.info("开始LLM后处理...")
            llm_result = await self.llm_post_processor.process_content(content, metadata)
            
            if llm_result.get("success", False):
                # LLM后处理成功，使用处理后的内容
                final_content = llm_result.get("content", content)
                final_metadata = llm_result.get("metadata", metadata)
                
                logger.info(f"LLM后处理完成: 处理状态={llm_result.get('processed', False)}")
                if llm_result.get("processed", False):
                    logger.info(f"内容长度变化: {len(content)} -> {len(final_content)}")
                else:
                    logger.info(f"跳过LLM处理原因: {llm_result.get('reason', '未知')}")
                
                # 返回最终处理结果
                return {
                    "success": True,
                    "content": final_content,
                    "metadata": final_metadata,
                    "page_count": page_count,
                    "file_path": file_path,
                    "llm_processing": {
                        "processed": llm_result.get("processed", False),
                        "reason": llm_result.get("reason", ""),
                        "quality_assessment": llm_result.get("quality_assessment", {})
                    }
                }
            else:
                # LLM后处理失败，使用原始内容
                logger.warning("LLM后处理失败，使用原始内容")
                return {
                    "success": True,
                    "content": content,
                    "metadata": metadata,
                    "page_count": page_count,
                    "file_path": file_path,
                    "llm_processing": {
                        "processed": False,
                        "reason": "LLM后处理失败"
                    }
                }
            
        except Exception as e:
            logger.error(f"处理PDF异常: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "message": "处理PDF时发生异常"
            }
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"已删除临时文件: {temp_file}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {str(e)}")
                    # 不影响主流程，继续执行
                    
            # 清理临时目录
            temp_dir = os.path.join(os.path.dirname(file_path), "temp")
            if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
                try:
                    # 检查目录是否为空
                    if not os.listdir(temp_dir):
                        shutil.rmtree(temp_dir)
                        logger.info(f"已删除空的临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"删除临时目录失败: {str(e)}")
                    # 不影响主流程，继续执行
    
    async def _process_standard(self, file_path: str) -> str:
        """
        使用标准方式处理PDF文件（不使用OCR）
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: Markdown内容
        """
        try:
            logger.info(f"使用标准方式处理PDF: {file_path}")
            # 异步执行docling处理
            loop = asyncio.get_event_loop()
            
            # 使用超时机制防止处理过久
            try:
                markdown_content = await asyncio.wait_for(
                    loop.run_in_executor(None, self._run_standard_process, file_path),
                    timeout=15*60  # 10分钟超时
                )
                logger.info(f"标准处理完成，生成Markdown内容: {len(markdown_content)} 字符")
                return markdown_content
            except asyncio.TimeoutError:
                logger.error(f"标准处理超时: {file_path}")
                return f"# 处理错误\n\n处理超时，文件可能过大或过于复杂: {file_path}"
        except Exception as e:
            logger.error(f"标准处理失败: {str(e)}")
            logger.error(traceback.format_exc())
            return f"# 处理错误\n\n标准处理失败: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
    
    def _run_standard_process(self, file_path: str) -> str:
        """
        运行标准docling处理（同步方法）- 基于docling.ipynb中的基本示例
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: Markdown内容
        """
        try:
            from docling.document_converter import DocumentConverter
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.exceptions import ConversionError
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import PdfFormatOption

            # 先检查文件是否存在且可读
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return f"# 处理错误\n\n文件不存在: {file_path}"
            
            # 检查文件是否为有效的PDF
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'%PDF':
                        logger.error(f"无效的PDF文件: {file_path}")
                        return f"# 处理错误\n\n无效的PDF文件: {file_path}"
            except Exception as e:
                logger.error(f"读取文件失败: {str(e)}")
                return f"# 处理错误\n\n读取文件失败: {str(e)}"
            
            # 配置加速选项
            accelerator_options = AcceleratorOptions(
                num_threads=8, device=AcceleratorDevice.AUTO
            )
            pipeline_options = PdfPipelineOptions(accelerator_options=accelerator_options)
            # 基本转换 - 参照ipynb第一个代码块
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                    )
                }
            )
            try:
                result = converter.convert(file_path)
                doc = result.document
                markdown_content = doc.export_to_markdown(
                                                          include_annotations=True,
                                                          page_break_placeholder="--- PAGE BREAK ---"
                                                          )
            except ConversionError as ce:
                logger.error(f"文档转换失败: {str(ce)}")
                return f"# 处理错误\n\n文档转换失败: {str(ce)}\n\n可能是PDF文件格式不受支持或已损坏。"
            except Exception as e:
                logger.error(f"标准处理过程中出错: {str(e)}")
                logger.error(traceback.format_exc())
                return f"# 处理错误\n\n标准处理过程中出错: {str(e)}"
            
            # 如果markdown内容为空，尝试使用更多选项
            if not markdown_content or len(markdown_content.strip()) < 100:
                logger.warning(f"生成的Markdown内容太少，尝试使用高级选项: {file_path}")
                
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
                from docling.datamodel.base_models import InputFormat
                from docling.document_converter import PdfFormatOption
                
                # 使用高级选项重新处理
                pipeline_options = PdfPipelineOptions(
                    generate_parsed_pages=True,
                    force_backend_text=False
                )
                
                converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=pipeline_options,
                        ),
                    },
                )
                
                try:
                    result = converter.convert(file_path)
                    doc = result.document
                    markdown_content = doc.export_to_markdown(
                                                          include_annotations=True,
                                                          page_break_placeholder="--- PAGE BREAK ---"
                                                          )
                except ConversionError as ce:
                    logger.error(f"高级选项文档转换失败: {str(ce)}")
                    return f"# 处理错误\n\n高级选项文档转换失败: {str(ce)}\n\n可能是PDF文件格式不受支持或已损坏。"
                except Exception as e:
                    logger.error(f"高级选项处理过程中出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    return f"# 处理错误\n\n高级选项处理过程中出错: {str(e)}"
            
            return markdown_content
        except Exception as e:
            logger.error(f"标准处理过程中出错: {str(e)}")
            logger.error(traceback.format_exc())
            return f"# 处理错误\n\n标准处理过程中出错: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
    
    async def _process_with_ocr(self, file_path: str) -> str:
        """
        使用OCR增强方式处理PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: Markdown内容
        """
        try:
            logger.info(f"使用OCR增强方式处理PDF: {file_path}")
            # 异步执行docling处理
            loop = asyncio.get_event_loop()
            
            # 使用超时机制防止处理过久
            try:
                markdown_content = await asyncio.wait_for(
                    loop.run_in_executor(None, self._run_ocr_process, file_path),
                    timeout=20*60  # 10分钟超时（OCR处理通常需要更多时间）
                )
                logger.info(f"OCR处理完成，生成Markdown内容: {len(markdown_content)} 字符")
                return markdown_content
            except asyncio.TimeoutError:
                logger.error(f"OCR处理超时: {file_path}")
                logger.info("OCR处理超时，尝试使用标准处理")
                return await self._process_standard(file_path)
        except Exception as e:
            logger.error(f"OCR处理失败: {str(e)}")
            logger.error(traceback.format_exc())
            # OCR失败后，尝试标准处理
            logger.info("OCR处理失败，尝试使用标准处理")
            return await self._process_standard(file_path)
    
    def _run_ocr_process(self, file_path: str) -> str:
        """
        运行OCR增强的docling处理（同步方法）- 基于docling.ipynb中的高级示例
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: Markdown内容
        """
        try:
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            
            # 设置OCR模型路径 - 参照ipynb第二个代码块
            models_path = self.rapidocr_models_path
            
            # 设置模型文件路径
            det_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_det_infer.onnx")
            rec_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx")
            cls_model_path = os.path.join(models_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx")
            
            # 服务器设置， 需手动更改配置
            # det_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_det_infer")
            # rec_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_rec_infer")
            # cls_model_path = os.path.join(models_path, "PP-OCRv4", "ch_ppocr_mobile_v2_cls_infer")

            # 检查模型文件是否存在
            det_exists = os.path.exists(det_model_path)
            rec_exists = os.path.exists(rec_model_path)
            cls_exists = os.path.exists(cls_model_path)
            
            logger.info("OCR模型检测结果:")
            logger.info(f"  检测模型: {det_model_path} - {'存在' if det_exists else '不存在'}")
            logger.info(f"  识别模型: {rec_model_path} - {'存在' if rec_exists else '不存在'}")
            logger.info(f"  分类模型: {cls_model_path} - {'存在' if cls_exists else '不存在'}")
            
            models_exist = det_exists and rec_exists and cls_exists
            if not models_exist:
                logger.warning("OCR模型文件不完整，尝试从HuggingFace下载")
                try:
                    from huggingface_hub import snapshot_download
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
                    models_dir = os.path.join(project_root, "src/models/RapidOCR")
                    models_path = snapshot_download(repo_id="SWHL/RapidOCR", 
                                                    cache_dir=models_dir,
                                                    local_dir=models_dir)
                    logger.info(f"模型下载成功，路径: {models_path}")
                    
                    # 更新模型文件路径
                    det_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_det_infer.onnx")
                    rec_model_path = os.path.join(models_path, "PP-OCRv4", "ch_PP-OCRv4_rec_server_infer.onnx")
                    cls_model_path = os.path.join(models_path, "PP-OCRv3", "ch_ppocr_mobile_v2.0_cls_train.onnx")
                    
                    # 再次检查模型文件是否存在
                    if not os.path.exists(det_model_path) or not os.path.exists(rec_model_path) or not os.path.exists(cls_model_path):
                        logger.error("模型下载成功，但找不到所需的模型文件")
                        raise FileNotFoundError("找不到必要的OCR模型文件")
                except Exception as download_err:
                    logger.error(f"下载OCR模型失败: {download_err}")
                    logger.error(traceback.format_exc())
                    raise
            
            # 配置OCR选项
            ocr_options = RapidOcrOptions(
                det_model_path=det_model_path,
                rec_model_path=rec_model_path,
                cls_model_path=cls_model_path
            )
            
            # cuda加速选项
            accelerator_options = AcceleratorOptions(
                num_threads=8, device=AcceleratorDevice.AUTO
            )

            # 设置管道选项  
            pipeline_options = PdfPipelineOptions(
                ocr_options=ocr_options,
                # generate_parsed_pages=True,
                force_backend_text = False,
                generate_picture_images=True,
                min_picture_page_surface_ratio=0,
                accelerator_options = accelerator_options,
                do_ocr = True,
                do_table_structure = True,
            )
            
            # 转换文档
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                    ),
                },
            )
            
            # 执行转换
            logger.info(f"使用OCR开始转换文档: {file_path}")
            try:
                conversion_result = converter.convert(source=file_path)
                doc = conversion_result.document
                
                # 导出Markdown
                markdown_content = doc.export_to_markdown(
                                                          include_annotations=True,
                                                          page_break_placeholder="--- PAGE BREAK ---"
                                                          )
                return markdown_content
            except Exception as e:
                logger.error(f"使用OCR转换文档失败: {str(e)}")
                # 尝试使用更简单的配置重试
                logger.info("尝试使用更简单的OCR配置重试...")
                
                # 使用更简单的配置
                simple_pipeline_options = PdfPipelineOptions(
                    accelerator_options=accelerator_options,
                    ocr_options=ocr_options,
                    generate_parsed_pages=True,
                    force_backend_text=True  # 强制使用后端文本，避免OCR
                )
                
                simple_converter = DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=simple_pipeline_options,
                        ),
                    },
                )
                
                conversion_result = simple_converter.convert(source=file_path)
                doc = conversion_result.document
                markdown_content = doc.export_to_markdown(
                                                          include_annotations=True,
                                                          page_break_placeholder="--- PAGE BREAK ---"
                                                          )
                return markdown_content
            
        except Exception as e:
            logger.error(f"OCR处理过程中出错: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        处理文档，提取文本内容并转换为Markdown格式
        
        Args:
            file_path: 文档路径
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"处理文档: {file_path}")
        
        # 获取文件扩展名
        file_extension = Path(file_path).suffix.lower()
        
        # 根据文件类型选择处理方式
        if file_extension == '.pdf':
            # 使用新的process_pdf方法处理PDF文件
            result = await self.process_pdf(file_path)
            
            if not result.get("success", False):
                # 处理失败，返回错误信息
                return result
            
            # 处理成功，构建返回结果
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            
            return {
                "success": True,
                "markdown": content,  # 保持兼容性，使用markdown字段
                "content": content,
                "metadata": metadata,
                "page_count": result.get("page_count", 1)
            }
        elif file_extension in ['.txt', '.md']:
            # 处理文本文件
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    
                return {
                    "success": True,
                    "markdown": content,
                    "content": content,
                    "metadata": {
                        "file_hash": self._calculate_file_hash(file_path),
                        "file_type": "text/plain" if file_extension == '.txt' else "text/markdown",
                        "page_count": 1
                    },
                    "page_count": 1
                }
            except Exception as e:
                logger.error(f"处理文本文件失败: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": "处理文本文件失败"
                }
        else:
            # 不支持的文件类型
            error_message = f"不支持的文件类型: {file_extension}"
            logger.error(error_message)
            return {
                "success": False,
                "error": error_message,
                "message": "不支持的文件类型"
            }

    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件的哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        try:
            import hashlib
            
            # 使用SHA-256算法计算文件哈希值
            sha256_hash = hashlib.sha256()
            
            with open(file_path, "rb") as f:
                # 分块读取文件内容，避免一次性读取大文件
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                    
            # 返回十六进制表示的哈希值
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希值失败: {str(e)}")
            # 如果计算失败，使用文件名作为哈希值
            return os.path.basename(file_path)

    async def _process_pdf_standard(self, file_path: str) -> Dict[str, Any]:
        """
        使用标准方式处理PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 检查docling库是否可用
            if not self.docling_available:
                return {
                    "success": False,
                    "error": "Docling库不可用，无法处理PDF文件",
                    "message": "文档处理组件不可用"
                }
            
            # 使用docling库处理PDF
            result = await self._process_standard(file_path)
            
            # 如果结果是错误信息字符串，表示处理失败
            if isinstance(result, str) and result.startswith("# 处理错误"):
                error_message = result.split("\n\n", 1)[1] if "\n\n" in result else "处理PDF失败"
                return {
                    "success": False,
                    "error": error_message,
                    "message": "处理PDF失败"
                }
            
            # 处理成功，返回结果
            return {
                "success": True,
                "content": result,
                "metadata": {
                    "file_type": "application/pdf",
                    "page_count": self._count_pages(file_path)
                }
            }
            
        except Exception as e:
            logger.error(f"标准处理PDF失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "message": "标准处理PDF失败"
            }
    
    async def _process_pdf_with_ocr(self, file_path: str) -> Dict[str, Any]:
        """
        使用OCR方式处理PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 检查docling库是否可用
            if not self.docling_available:
                return {
                    "success": False,
                    "error": "Docling库不可用，无法处理PDF文件",
                    "message": "文档处理组件不可用"
                }
            
            # 使用docling库处理PDF，启用OCR
            result = await self._process_with_ocr(file_path)
            
            # 如果结果是错误信息字符串，表示处理失败
            if isinstance(result, str) and result.startswith("# 处理错误"):
                error_message = result.split("\n\n", 1)[1] if "\n\n" in result else "OCR处理PDF失败"
                return {
                    "success": False,
                    "error": error_message,
                    "message": "OCR处理PDF失败"
                }
            
            # 处理成功，返回结果
            return {
                "success": True,
                "content": result,
                "metadata": {
                    "file_type": "application/pdf",
                    "page_count": self._count_pages(file_path),
                    "ocr_enabled": True
                }
            }
            
        except Exception as e:
            logger.error(f"OCR处理PDF失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "message": "OCR处理PDF失败"
            }
    
    def _count_pages(self, pdf_path: str) -> int:
        """
        计算PDF文件的页数
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            int: 页数
        """
        try:
            import PyPDF2
            
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                return len(pdf_reader.pages)
        except Exception as e:
            logger.warning(f"计算PDF页数失败: {str(e)}")
            return 1  # 默认页数 