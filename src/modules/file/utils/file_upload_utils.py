"""
文件上传工具函数
"""

import hashlib
import logging
from pathlib import Path
from fastapi import UploadFile
from typing import Tuple

from src.shared.storage.storage_factory import get_storage

logger = logging.getLogger(__name__)

async def save_file(file: UploadFile, project_id: str) -> Tuple[str, str]:
    """
    保存上传的文件并计算哈希值
    
    Args:
        file: 上传的文件
        project_id: 项目ID
        
    Returns:
        Tuple[str, str]: 文件保存路径和文件哈希值
    """
    try:
        # 读取文件内容
        content = await file.read()
        
        # 计算文件内容哈希值
        file_hash = generate_file_hash(content)
        logger.info(f"文件哈希值: {file_hash}, 文件名: {file.filename}, 项目ID: {project_id}")
        
        # 获取文件扩展名
        file_extension = Path(file.filename).suffix
        
        # 生成基于哈希的文件名
        file_name = f"{file_hash}{file_extension}"
        
        # 构建项目路径: project_id/file_hash.ext
        file_path = f"{project_id}/{file_name}"
        
        # 获取存储实例
        storage = await get_storage(directory_type="upload")
        
        # 保存文件到存储
        saved_path = await storage.save_file(
            file_id=file_path,
            content=content
        )
        
        logger.info(f"文件已保存到存储: {saved_path}")
        
        # 确保文件指针位置重置，以便后续可能的读取操作
        await file.seek(0)
        
        return saved_path, file_hash
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        raise

def generate_file_hash(content: bytes) -> str:
    """
    生成文件内容的哈希值
    
    Args:
        content: 文件内容
        
    Returns:
        str: 文件哈希值（SHA-256的前16位）
    """
    # 使用SHA-256算法生成文件哈希
    return hashlib.sha256(content).hexdigest()[:16]  # 取前16个字符足够识别 