#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件流处理服务
提供文件流式处理相关功能
"""

import os
import json
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator

# 配置日志
logger = logging.getLogger(__name__)

class FileProcessorStreamService:
    """文件处理流服务"""
    
    def __init__(self, base_dir: str):
        """
        初始化文件处理服务
        
        Args:
            base_dir: 基础目录
        """
        self.base_dir = Path(base_dir)
    
    def get_project_dir(self, project_id: str) -> Path:
        """
        获取项目目录
        
        Args:
            project_id: 项目ID
            
        Returns:
            Path: 项目目录
        """
        project_dir = self.base_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def get_model_dir(self) -> Path:
        """
        获取模型目录
        
        Returns:
            Path: 模型目录
        """
        model_dir = self.base_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir
    
    async def process_file_stream(
        self,
        file,
        project_id: str,
        document_converter,
        layout_ocr_processor,
        llm_client,
        data_summary_prompt,
        brand_prompt,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式处理文件
        
        Args:
            file: 上传的文件
            project_id: 项目ID
            document_converter: 文档转换器
            layout_ocr_processor: 布局OCR处理器
            llm_client: LLM客户端
            data_summary_prompt: 数据摘要提示词
            brand_prompt: 品牌提示词
            **kwargs: 其他参数
            
        Yields:
            str: 处理状态和结果
        """
        try:
            # 获取项目目录
            project_dir = self.get_project_dir(project_id)
            upload_data_dir = project_dir / "upload_data"
            images_data_dir = project_dir / "images_data"
            outputs_dir = project_dir / "outputs"
            stored_model_dir = self.get_model_dir()
            
            # 创建必要的目录
            upload_data_dir.mkdir(parents=True, exist_ok=True)
            images_data_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)

            # 保存上传的文件
            file_path = upload_data_dir / file.filename
            content = await file.read()
            if not content:
                yield json.dumps({"error": f"文件内容为空: {file.filename}"}) + "\n"
                return
            with open(file_path, "wb") as f:
                f.write(content)
            yield json.dumps({"status": "file_saved", "message": f"文件 {file.filename} 已保存"}) + "\n"

            # 创建处理目录
            file_stem = file_path.stem
            images_dir = images_data_dir / file_stem
            output_dir = outputs_dir / file_stem
            deepseek_dir = output_dir / "DeepSeek"
            brand_dir = output_dir / "standardlised"
            txt_dir = output_dir / "standardlised_txt"
            for dir_path in [images_dir, output_dir, deepseek_dir, brand_dir, txt_dir]:
                dir_path.mkdir(parents=True, exist_ok=True)
            yield json.dumps({"status": "directories_created", "message": "处理目录已创建"}) + "\n"

            # 处理PDF文件
            yield json.dumps({"status": "processing", "message": "开始PDF处理"}) + "\n"
            
            # 使用文档转换器处理PDF
            result = document_converter.convert(source=str(file_path), image_output_dir=str(images_dir))
            yield json.dumps({"status": "pdf_converted", "message": "PDF已转换为图片"}) + "\n"

            # 使用布局OCR处理器
            layout_ocr_processor.process(
                image_path=str(images_dir),
                output_path=str(output_dir),
                model_dir=str(stored_model_dir)
            )
            yield json.dumps({"status": "ocr_completed", "message": "OCR处理完成"}) + "\n"

            # 使用LLM生成摘要
            async for chunk in llm_client.generate_stream(
                prompt=data_summary_prompt.format(extracted_text=content.decode('utf-8', errors='ignore')),
                temperature=0
            ):
                yield json.dumps({"status": "llm_processing", "chunk": chunk}) + "\n"
            yield json.dumps({"status": "summary_completed", "message": "摘要生成完成"}) + "\n"

            # 处理品牌信息
            brands = self._collect_brand_fields(str(outputs_dir))
            async for chunk in llm_client.generate_stream(
                prompt=brand_prompt.format(extracted_text=brands),
                temperature=0
            ):
                yield json.dumps({"status": "brand_processing", "chunk": chunk}) + "\n"
                
            # 保存标准化结果
            self._standardize_product_fields(str(outputs_dir), brand_dir)
            yield json.dumps({"status": "brand_alignment_completed", "message": "品牌对齐完成"}) + "\n"
            
            # 转换JSON到TXT
            self._json_to_txt(brand_dir, txt_dir)
            yield json.dumps({"status": "txt_conversion_completed", "message": "TXT转换完成"}) + "\n"
            
            # 完成处理
            yield json.dumps({"status": "success", "message": f"文件 {file.filename} 处理完成"}) + "\n"
        except Exception as e:
            logger.error(f"处理文件流失败: {str(e)}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"
    
    def _collect_brand_fields(self, output_dir: str) -> str:
        """
        收集品牌字段
        
        Args:
            output_dir: 输出目录
            
        Returns:
            str: 品牌字段内容
        """
        # 实现品牌字段收集逻辑
        # 这里简化为读取输出目录中的summary.json文件
        try:
            summary_path = Path(output_dir) / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    return f.read()
            return ""
        except Exception as e:
            logger.error(f"收集品牌字段失败: {str(e)}")
            return ""
    
    def _standardize_product_fields(self, output_dir: str, brand_dir: Path) -> None:
        """
        标准化产品字段
        
        Args:
            output_dir: 输出目录
            brand_dir: 品牌目录
        """
        # 实现产品字段标准化逻辑
        try:
            # 读取normBrand.json
            norm_brand_path = Path(output_dir) / "normBrand.json"
            if not norm_brand_path.exists():
                logger.warning(f"标准化品牌文件不存在: {norm_brand_path}")
                return
                
            with open(norm_brand_path, "r", encoding="utf-8") as f:
                norm_brand = json.load(f)
                
            # 标准化处理
            # 这里简化处理，只是将文件复制到标准化目录
            standardized_path = brand_dir / "standardized.json"
            with open(standardized_path, "w", encoding="utf-8") as f:
                json.dump(norm_brand, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"标准化产品字段失败: {str(e)}")
    
    def _json_to_txt(self, json_dir: Path, txt_dir: Path, keep_structure: bool = True) -> None:
        """
        将JSON转换为TXT格式
        
        Args:
            json_dir: JSON目录
            txt_dir: TXT目录
            keep_structure: 是否保持结构
        """
        try:
            # 获取所有JSON文件
            json_files = list(json_dir.glob("*.json"))
            
            for json_file in json_files:
                try:
                    # 读取JSON文件
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # 创建同名TXT文件
                    txt_file = txt_dir / f"{json_file.stem}.txt"
                    
                    # 转换内容
                    if keep_structure:
                        # 保持JSON结构，美化输出
                        txt_content = json.dumps(data, ensure_ascii=False, indent=2)
                    else:
                        # 扁平化JSON
                        txt_content = self._flatten_json(data)
                    
                    # 写入TXT文件
                    with open(txt_file, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                        
                except Exception as e:
                    logger.error(f"转换JSON文件失败 {json_file}: {str(e)}")
        except Exception as e:
            logger.error(f"JSON到TXT转换失败: {str(e)}")
    
    def _flatten_json(self, data: Dict[str, Any], prefix: str = "") -> str:
        """
        扁平化JSON数据
        
        Args:
            data: JSON数据
            prefix: 前缀
            
        Returns:
            str: 扁平化后的文本
        """
        result = []
        
        for key, value in data.items():
            new_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # 递归处理嵌套字典
                result.append(self._flatten_json(value, new_key))
            elif isinstance(value, list):
                # 处理列表
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result.append(self._flatten_json(item, f"{new_key}[{i}]"))
                    else:
                        result.append(f"{new_key}[{i}] = {item}")
            else:
                # 基本类型直接添加
                result.append(f"{new_key} = {value}")
        
        return "\n".join(result) 