#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG存储适配器

为LightRAG提供统一的存储接口，支持本地文件系统和S3/MinIO存储
"""

import os
import json
import asyncio
import logging
import tempfile
import shutil
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class RAGStorageAdapter:
    """
    RAG存储适配器
    
    提供给LightRAG使用的统一存储接口，内部根据STORAGE_TYPE选择本地或S3存储
    """
    
    def __init__(self, project_id: str, storage_type: Optional[str] = None):
        """
        初始化RAG存储适配器
        
        Args:
            project_id: 项目ID
            storage_type: 存储类型，可选值: 'local', 's3'。如果为None，则从环境变量获取
        """
        self.project_id = project_id
        self.storage_type = storage_type or os.getenv('STORAGE_TYPE', 'local').lower()
        self.storage = None
        self._temp_dir = None
        
        # 根据存储类型设置工作目录
        if self.storage_type == 's3':
            # S3模式：使用项目目录下的cache目录作为本地缓存
            cache_base_dir = os.getenv('RAG_CACHE_DIR', './rag_cache')
            self._temp_dir = os.path.join(cache_base_dir, f"project_{project_id}")
            
            # 确保目录存在
            os.makedirs(self._temp_dir, exist_ok=True)
            
            self.working_dir = self._temp_dir
            logger.info(f"🗄️ 项目 {project_id} 使用S3存储模式，本地缓存目录: {self.working_dir}")
        else:
            # 本地模式：使用本地RAG目录
            rag_base_dir = os.getenv('RAG_DIR', './rag_storage')
            self.working_dir = os.path.join(rag_base_dir, f"project_{project_id}")
            os.makedirs(self.working_dir, exist_ok=True)
            logger.info(f"📁 项目 {project_id} 使用本地存储模式，目录: {self.working_dir}")
    
    async def initialize_storage(self):
        """初始化存储实例"""
        if self.storage_type == 's3':
            # 初始化S3存储
            from src.shared.storage.storage_factory import get_storage
            self.storage = await get_storage(storage_type='s3', directory_type='rag')
            
            # 从S3同步现有项目数据到本地临时目录
            await self.sync_from_s3()
            
        logger.info(f"✅ 项目 {self.project_id} RAG存储适配器初始化完成")
    
    async def sync_from_s3(self):
        """从S3同步项目数据到本地临时目录"""
        try:
            project_prefix = f"rag_storage/project_{self.project_id}/project_{self.project_id}/"
            
            # 获取项目目录下的所有文件
            files = await self._list_s3_files(project_prefix)
            
            # 如果没有找到任何文件，说明项目还没有数据，静默返回
            if not files:
                logger.debug(f"📭 项目 {self.project_id} 暂无S3数据，跳过同步")
                return
            
            for file_key in files:
                # 构建本地路径，需要保持 project_XX 子目录结构
                relative_path = file_key[len(project_prefix):]
                # LightRAG期望的路径结构: working_dir/project_XX/filename
                local_path = os.path.join(self.working_dir, f"project_{self.project_id}", relative_path)
                
                # 确保目录存在
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # 下载文件
                try:
                    content = await self.storage.get_file(file_key)
                    
                    if isinstance(content, bytes):
                        # 二进制文件
                        with open(local_path, 'wb') as f:
                            f.write(content)
                    else:
                        # 文本文件
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    
                    logger.debug(f"同步文件: {file_key} -> {local_path}")
                    
                except Exception as e:
                    logger.warning(f"同步文件失败: {file_key} - {e}")
            
            logger.info(f"📥 从S3同步了 {len(files)} 个文件到本地缓存")
            
        except Exception as e:
            # 对于新项目，同步失败是正常的，不应该记录为错误
            logger.debug(f"从S3同步数据失败: {e} (项目 {self.project_id} 可能是新项目)")
    
    async def _list_s3_files(self, prefix: str) -> list:
        """列出S3中指定前缀的所有文件"""
        try:
            # 由于StorageInterface没有list_files方法，我们尝试获取已知的LightRAG文件
            logger.debug(f"列出S3文件，前缀: {prefix}")
            
            # LightRAG生成的标准文件列表
            known_files = [
                'vdb_chunks.json',
                'vdb_entities.json', 
                'vdb_relationships.json',
                'kv_store_doc_status.json',
                'kv_store_full_docs.json',
                'kv_store_llm_response_cache.json',
                'kv_store_text_chunks.json',
                'graph_chunk_entity_relation.graphml'
            ]
            
            existing_files = []
            for filename in known_files:
                file_key = prefix + filename
                try:
                    # 直接使用文件路径（storage已经包含rag_storage前缀）
                    await self.storage.get_file(file_key)
                    existing_files.append(file_key)
                    logger.debug(f"找到文件: {file_key}")
                except Exception as e:
                    # 文件不存在，静默跳过（不记录日志，避免对新项目产生大量错误日志）
                    logger.debug(f"S3文件不存在: {file_key} - {e}")
                    pass
            
            # 只有找到文件时才记录日志
            if existing_files:
                logger.info(f"找到 {len(existing_files)} 个S3文件")
            else:
                logger.debug(f"项目 {self.project_id} 暂无S3文件")
            return existing_files
            
        except Exception as e:
            # 对于新项目，文件查找失败是正常的，使用debug级别日志
            logger.debug(f"列出S3文件失败: {e} (项目可能是新项目)")
            return []
    
    async def sync_to_s3(self):
        """将本地更改同步到S3"""
        if self.storage_type != 's3' or not self.storage:
            return
        
        try:
            # 遍历工作目录，上传所有文件
            for root, dirs, files in os.walk(self.working_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    
                    # 计算相对路径
                    relative_path = os.path.relpath(local_path, self.working_dir)
                    s3_key = f"project_{self.project_id}/{relative_path.replace(os.sep, '/')}"
                    
                    try:
                        # 读取文件内容
                        with open(local_path, 'rb') as f:
                            content = f.read()
                        
                        # 上传到S3
                        await self.storage.save_file(s3_key, content)
                        logger.debug(f"上传文件: {local_path} -> {s3_key}")
                        
                    except Exception as e:
                        logger.warning(f"上传文件失败: {local_path} - {e}")
            
            logger.info(f"📤 项目 {self.project_id} 数据已同步到S3")
            
        except Exception as e:
            logger.error(f"同步到S3失败: {e}")
    
    def get_working_dir(self) -> str:
        """获取LightRAG的工作目录"""
        return self.working_dir
    
    async def cleanup(self):
        """清理临时资源"""
        try:
            # 如果是S3模式，先同步数据，然后清理临时目录
            if self.storage_type == 's3':
                await self.sync_to_s3()
                
                if self._temp_dir and os.path.exists(self._temp_dir):
                    shutil.rmtree(self._temp_dir)
                    logger.info(f"🗑️ 清理临时目录: {self._temp_dir}")
                    
        except Exception as e:
            logger.error(f"清理RAG存储适配器失败: {e}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        # 注意：这里不能使用async，所以只做基本清理
        if hasattr(self, '_temp_dir') and self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
            except:
                pass


class RAGStorageManager:
    """RAG存储管理器 - 管理多个项目的存储适配器"""
    
    def __init__(self):
        self._adapters: Dict[str, RAGStorageAdapter] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
    
    async def get_adapter(self, project_id: str) -> RAGStorageAdapter:
        """获取项目的存储适配器"""
        async with self._global_lock:
            if project_id not in self._adapters:
                self._adapters[project_id] = RAGStorageAdapter(project_id)
                self._locks[project_id] = asyncio.Lock()
                await self._adapters[project_id].initialize_storage()
            
            return self._adapters[project_id]
    
    async def cleanup_adapter(self, project_id: str):
        """清理项目的存储适配器"""
        async with self._global_lock:
            if project_id in self._adapters:
                await self._adapters[project_id].cleanup()
                del self._adapters[project_id]
                del self._locks[project_id]
    
    async def cleanup_all(self):
        """清理所有存储适配器"""
        for project_id in list(self._adapters.keys()):
            await self.cleanup_adapter(project_id)


# 全局存储管理器实例
_rag_storage_manager = RAGStorageManager()

async def get_rag_storage_adapter(project_id: str) -> RAGStorageAdapter:
    """获取RAG存储适配器"""
    return await _rag_storage_manager.get_adapter(project_id)

async def cleanup_rag_storage(project_id: str):
    """清理项目的RAG存储"""
    await _rag_storage_manager.cleanup_adapter(project_id)