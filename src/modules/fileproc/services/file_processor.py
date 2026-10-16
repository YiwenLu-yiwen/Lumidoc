#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理器 - 负责处理上传的文件
遵循Lumidoc微服务架构原则，通过异步任务队列处理文件
所有IO操作严格使用异步方式
"""

import os
import logging
import asyncio
import time
import json
import boto3
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import aiofiles
import traceback
import hashlib

from ..config import settings
from src.shared.service_discovery import ServiceClient, call_service
from ..processors.docling_processor import DoclingProcessor
from src.shared.storage import get_storage
from src.shared.file_types import is_text_document
from src.shared.config import get_settings

logger = logging.getLogger(__name__)

# WebSocket连接管理器的延迟导入
def get_connection_manager():
    """延迟导入WebSocket连接管理器以避免循环导入"""
    try:
        from ..routes.websocket_routes import connection_manager
        return connection_manager
    except ImportError:
        logger.warning("无法导入WebSocket连接管理器，进度推送功能不可用")
        return None

class FileProcessor:
    """
    文件处理器 - 处理通过队列接收的文件任务
    所有IO操作严格使用异步方式
    """

    def __init__(self):
        """初始化文件处理器"""
        self.storage = None
        self.content_storage = None  # 用于存储处理后的内容
        self.s3_client = None
        self.clients = {}  # 服务客户端
        self.queue = None  # 文件处理队列
        self.is_initialized = False  # 初始化状态
        # 初始化content目录路径（兼容性，仍保留但优先使用存储接口）
        self.content_dir = settings.content_dir
        # 确保使用绝对路径
        if not os.path.isabs(self.content_dir):
            self.content_dir = os.path.abspath(self.content_dir)

        logger.info("文件处理器初始化，处理后的markdown文件将保存到统一存储")
        # 确保content目录存在（兼容性）
        try:
            os.makedirs(self.content_dir, exist_ok=True)
            logger.info(f"已确保content目录存在: {self.content_dir}")
        except Exception as e:
            logger.error(f"创建content目录失败: {str(e)}")

        # 初始化S3客户端（MinIO）
        try:
            if settings.minio_endpoint:
                # 解析endpoint
                endpoint = settings.minio_endpoint
                if "://" in endpoint:
                    endpoint = endpoint.split("://", 1)[1]

                logger.info(f"初始化S3客户端连接: {endpoint}")

                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=f"http://{endpoint}",
                    aws_access_key_id=settings.minio_access_key,
                    aws_secret_access_key=settings.minio_secret_key,
                    region_name='us-east-1',  # MinIO不需要特定区域
                    config=boto3.session.Config(signature_version='s3v4')
                )
                logger.info("S3客户端初始化成功")
            else:
                self.s3_client = None
                logger.info("未配置MinIO，跳过S3客户端初始化")
        except Exception as e:
            logger.error(f"S3客户端初始化失败: {str(e)}")
            self.s3_client = None

        # 设置存储桶名称 - 使用统一的S3_BUCKET配置
        self.bucket_name = os.getenv("S3_BUCKET", "data")
        logger.info(f"使用存储桶: {self.bucket_name}")

        # 初始化docling处理器
        try:
            self.docling_processor = DoclingProcessor()
            logger.info("DoclingProcessor初始化成功")
        except Exception as e:
            logger.error(f"DoclingProcessor初始化失败: {str(e)}")
            self.docling_processor = None

        self.settings = get_settings()
        self.service_client = ServiceClient()
        logger.info("文件处理器实例已创建")

    async def initialize(self) -> bool:
        """
        初始化文件处理器

        Returns:
            bool: 初始化是否成功
        """
        if self.is_initialized:
            logger.info("文件处理器已经初始化")
            return True

        try:
            logger.info("开始初始化文件处理器")

            # 初始化存储服务
            try:
                from src.shared.storage.storage_factory import get_storage
                self.storage = await get_storage(directory_type="upload")
                if not self.storage:
                    logger.error("上传存储服务初始化失败: get_storage()返回了None")
                    return False
                logger.info("上传存储服务初始化成功")

                # 初始化content存储服务
                self.content_storage = await get_storage(directory_type="content")
                if not self.content_storage:
                    logger.error("内容存储服务初始化失败: get_storage()返回了None")
                    return False
                logger.info("内容存储服务初始化成功")
            except Exception as e:
                logger.error(f"初始化存储服务失败: {str(e)}")
                logger.error(traceback.format_exc())
                return False

            # 检查存储健康状态
            storage_healthy = await self._check_storage_health()
            if not storage_healthy:
                logger.error("存储服务健康检查失败")
                return False

            # 初始化服务客户端
            try:
                from src.shared.service_discovery import ServiceClient
                self.service_client = await ServiceClient.get_instance()
                logger.info("服务客户端初始化成功")
            except Exception as e:
                logger.error(f"初始化服务客户端失败: {str(e)}")
                return False

            # 初始化文件处理队列
            try:
                from .queue_service import file_processing_queue
                self.queue = file_processing_queue
                if not self.queue.is_connected():
                    await self.queue.connect()
                logger.info("文件处理队列初始化成功")
            except Exception as e:
                logger.error(f"初始化文件处理队列失败: {str(e)}")
                return False

            # 初始化完成
            self.is_initialized = True
            logger.info("文件处理器初始化完成")
            return True

        except Exception as e:
            logger.error(f"文件处理器初始化失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _check_storage_health(self) -> bool:
        """
        检查存储服务的健康状态

        Returns:
            bool: 存储服务是否健康
        """
        try:
            # 如果存储服务未初始化，先尝试初始化
            if self.storage is None:
                logger.info("存储服务未初始化，尝试初始化")
                from src.shared.storage.storage_factory import get_storage
                self.storage = get_storage()

            # 检查存储服务
            if self.storage is None:
                logger.error("存储服务未初始化")
                return False

            # 简单检查存储服务连接
            if hasattr(self.storage, "is_connected") and callable(getattr(self.storage, "is_connected")):
                connected = await self.storage.is_connected()
                if connected:
                    logger.info("存储服务连接正常")
                else:
                    logger.error("存储服务连接失败")
                return connected

            # 备用检查方法
            return True
        except Exception as e:
            logger.error(f"存储健康检查失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def shutdown(self) -> None:
        """关闭文件处理器"""
        try:
            logger.info("开始关闭文件处理器")

            # 关闭存储服务
            if self.storage:
                try:
                    await self.storage.close()
                    logger.info("存储服务已关闭")
                except Exception as e:
                    logger.error(f"关闭存储服务失败: {str(e)}")

            # 关闭队列连接
            if hasattr(self, 'queue') and self.queue:
                try:
                    await self.queue.close()
                    logger.info("队列连接已关闭")
                except Exception as e:
                    logger.error(f"关闭队列连接失败: {str(e)}")

            self.is_initialized = False
            logger.info("文件处理器已关闭")
        except Exception as e:
            logger.error(f"关闭文件处理器时发生错误: {str(e)}")
            logger.error(traceback.format_exc())

    async def _calculate_content_hash(self, file_path: str) -> str:
        """
        计算文件内容的SHA-256哈希值

        Args:
            file_path: 文件的物理路径

        Returns:
            str: 内容哈希值
        """
        try:
            # 尝试读取文件内容
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()

            # 使用SHA-256算法计算哈希值
            content_hash = hashlib.sha256(content).hexdigest()
            logger.info(f"计算文件内容哈希: {file_path} -> {content_hash}")
            return content_hash
        except Exception as e:
            logger.error(f"计算文件内容哈希失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _check_content_exists(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """
        检查内容是否已存在于数据库中

        Args:
            content_hash: 文件内容的哈希值

        Returns:
            Optional[Dict[str, Any]]: 如果内容存在，返回内容信息；否则返回None
        """
        try:
            # 首先检查content目录是否已有该文件
            content_file_path = os.path.join(self.content_dir, f"{content_hash}.txt")
            if os.path.exists(content_file_path):
                logger.info(f"内容文件已存在于本地: {content_file_path}")

                # 尝试获取内容
                try:
                    with open(content_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 构造数据结构返回
                    return {
                        "content": content,
                        "hash": content_hash,
                        "exists": True,
                        "file_path": content_file_path
                    }
                except Exception as e:
                    logger.warning(f"无法读取已存在的内容文件: {content_file_path}, 错误: {str(e)}")

            # 调用文件服务API检查内容是否存在
            from src.shared.service_discovery import call_service

            response = await call_service(
                service_name="file",
                endpoint=f"api/file/content/global/{content_hash}",
                method="GET",
                use_service_auth=True  # 添加服务间认证
            )

            if response and response.get("success"):
                logger.info(f"发现内容哈希已存在于数据库: {content_hash}")
                return response.get("data")

            logger.info(f"内容哈希在数据库和本地都不存在: {content_hash}")
            return None
        except Exception as e:
            logger.error(f"检查内容是否存在时发生错误: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    async def _register_content(self, content_hash: str, markdown_content: str,
                              metadata: Dict[str, Any], file_type: str,
                              page_count: int = 1) -> bool:
        """
        注册新的文件内容到数据库

        Args:
            content_hash: 文件内容的哈希值
            markdown_content: 处理后的Markdown内容
            metadata: 文件元数据
            file_type: 文件类型
            page_count: 页数

        Returns:
            bool: 注册是否成功
        """
        try:
            # 导入服务调用函数
            from src.shared.service_discovery import call_service

            # 调用文件服务API注册内容
            response = await call_service(
                service_name="file",
                endpoint="api/file/register/content",
                method="POST",
                json_data={
                    "file_hash": content_hash,
                    "markdown_content": markdown_content,
                    "metadata": metadata,
                    "file_type": file_type,
                    "page_count": page_count
                },
                use_service_auth=True  # 添加服务间认证
            )
            return response and response.get("success", False)
        except Exception as e:
            logger.error(f"注册文件内容时发生错误: {str(e)}")
            return False

    async def process_file(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理文件任务

        Args:
            task_data: 任务数据，包含文件信息

        Returns:
            Dict[str, Any]: 处理结果
        """
        logger.info(f"处理文件任务: {task_data}")

        # 确保服务已初始化
        if not self.is_initialized:
            await self.initialize()

        # 从任务数据中提取信息
        task_id = task_data.get("task_id")

        # 适配不同的数据结构
        if "payload" in task_data:
            payload = task_data.get("payload", {})
        else:
            # 如果没有payload字段，可能整个task_data就是payload
            payload = task_data

        # 如果payload为空，尝试从直接字段中获取
        file_id = payload.get("file_id") or task_data.get("file_id")
        project_id = payload.get("project_id") or task_data.get("project_id")
        file_path = payload.get("file_path") or task_data.get("file_path")
        file_hash = payload.get("file_hash") or task_data.get("file_hash")
        content_type = payload.get("content_type") or task_data.get("content_type")

        if not task_id:
            task_id = f"task-{uuid.uuid4().hex}"
            logger.info(f"任务ID为空，生成新任务ID: {task_id}")

        start_time = time.time()

        logger.info(f"开始处理文件: ID={file_id}, 项目ID={project_id}, 任务ID={task_id}")

        # 获取WebSocket连接管理器并注册任务
        connection_manager = get_connection_manager()
        if connection_manager and project_id:
            connection_manager.register_task_project(task_id, project_id)

            # 发送任务开始通知
            await self._send_progress_update(
                connection_manager, project_id, task_id,
                {
                    "status": "started",
                    "progress": 0,
                    "stage": "initialization",
                    "message": "开始处理文件",
                    "file_id": file_id,
                    "timestamp": datetime.now().isoformat()
                }
            )

        try:
            # 初始化客户端
            if self.queue is None:
                from .queue_service import file_processing_queue
                self.queue = file_processing_queue

            # 初始化服务发现客户端
            if not self.service_client or not hasattr(self.service_client, 'call'):
                from src.shared.service_discovery import ServiceClient
                self.service_client = await ServiceClient.get_instance()

            # 如果未提供文件路径，从file服务获取文件信息
            if not file_path or not file_hash:
                if not file_id or not project_id:
                    logger.error("任务数据不完整，缺少file_id或project_id")
                    return {
                        "success": False,
                        "error": "任务数据不完整，缺少file_id或project_id",
                        "task_id": task_id
                    }

                # 获取文件信息
                file_info = await call_service(
                    service_name="file",
                    endpoint=f"api/file/info/{project_id}/{file_id}",
                    method="GET",
                    use_service_auth=True  # 添加服务间认证
                )

                if not file_info or not file_info.get("success", False):
                    logger.error(f"获取文件信息失败: {file_info}")

                    # 更新任务状态为失败
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        progress=100,
                        message="获取文件信息失败"
                    )

                    return {
                        "success": False,
                        "task_id": task_id,
                        "message": "获取文件信息失败",
                        "details": file_info
                    }

                file_path = file_info.get("file_path") or file_info.get("path")
                file_hash = file_info.get("file_hash")
                content_type = file_info.get("content_type") or file_info.get("type")

                logger.info(f"从文件服务获取的信息: path={file_path}, hash={file_hash}, type={content_type}")

            # 检查必要的字段
            if not file_id or not project_id:
                logger.error("缺少必要的任务字段: file_id或project_id")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message="缺少必要的任务字段: file_id或project_id"
                )

                return {
                    "success": False,
                    "task_id": task_id,
                    "message": "缺少必要的任务字段: file_id或project_id"
                }

            if not file_path:
                logger.error("无法获取文件路径")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message="无法获取文件路径"
                )

                return {
                    "success": False,
                    "task_id": task_id,
                    "message": "无法获取文件路径"
                }

            # 使用统一存储接口检查文件是否存在
            try:
                # 获取上传文件的存储实例
                upload_storage = await get_storage(directory_type="upload")

                # 检查文件是否存在于存储中
                file_exists = await upload_storage.file_exists(file_path)

                if file_exists:
                    logger.info(f"确认文件存在于存储中: {file_path}")
                else:
                    logger.error(f"文件不存在于存储中: {file_path}")

                    # 更新任务状态为失败
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        progress=100,
                        message=f"文件不存在于存储中: {file_path}"
                    )

                    return {
                        "success": False,
                        "task_id": task_id,
                        "message": f"文件不存在于存储中: {file_path}"
                    }

            except Exception as e:
                logger.error(f"检查文件存在性时发生错误: {str(e)}")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"检查文件存在性时发生错误: {str(e)}"
                )

                return {
                    "success": False,
                    "task_id": task_id,
                    "message": f"检查文件存在性时发生错误: {str(e)}"
                }

            # 更新任务状态为处理中
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=20,
                message=f"分析文件类型: {content_type} -> {content_type}"
            )

            # 检查文件是否已经处理过，避免重复处理
            existing_content = await self._check_content_exists(file_hash)
            if existing_content:
                logger.info(f"文件内容已存在，哈希值: {file_hash}，检查是否需要同步到MinIO")

                # 检查MinIO中是否存在对应的文件
                content_file_name = f"{file_hash}.txt"
                minio_file_exists = False

                if self.content_storage:
                    try:
                        minio_file_exists = await self.content_storage.file_exists(content_file_name)
                        logger.info(f"MinIO中文件存在状态: {minio_file_exists}")
                    except Exception as e:
                        logger.warning(f"检查MinIO文件存在性失败: {str(e)}")

                # 如果MinIO中没有文件，则从数据库内容创建文件
                if not minio_file_exists and self.content_storage:
                    try:
                        markdown_content = existing_content.get("markdown_content", "")
                        if markdown_content:
                            logger.info(f"从数据库内容创建MinIO文件: {content_file_name}")
                            saved_path = await self.content_storage.save_file(
                                file_id=file_hash,
                                content=markdown_content.encode('utf-8'),
                                file_extension=".txt"
                            )
                            logger.info(f"成功创建MinIO文件: {saved_path}")
                        else:
                            logger.warning("数据库中的markdown内容为空，无法创建MinIO文件")
                    except Exception as e:
                        logger.error(f"创建MinIO文件失败: {str(e)}")

                # 更新文件状态为已处理
                status_update = await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_hash,
                        "project_id": project_id,
                        "status": "completed"
                    },
                    use_service_auth=True
                )

                logger.info(f"更新文件状态结果: {status_update}")

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="completed",
                    progress=100,
                    message=f"文件内容已存在，已确保MinIO同步: {file_hash}"
                )

                # 构造正确的文件路径
                if self.content_storage and hasattr(self.content_storage, 'base_prefix'):
                    # 如果有content存储，使用正确的路径格式
                    content_path = f"{self.content_storage.base_prefix}/{file_hash}.txt" if self.content_storage.base_prefix else f"{file_hash}.txt"
                else:
                    # 兼容性：默认路径
                    content_path = f"content/{file_hash}.txt"

                # 构造结果
                result = {
                    "success": True,
                    "task_id": task_id,
                    "file_id": file_id,
                    "message": "文件内容已存在，已确保MinIO文件同步",
                    "content_hash": file_hash,
                    "reused": True,
                    "file_path": content_path,
                    "content_type": "text/plain"
                }

                logger.info(f"复用现有内容完成: {result}")
                return result

            # 文件存在性已经在前面检查过了，这里直接继续处理

            # 更新任务状态为处理中
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=30,
                message=f"分析文件类型: {content_type} -> {content_type}"
            )

            # 从存储中读取文件并计算哈希值
            try:
                file_content = await upload_storage.get_file(file_path)
                content_hash = hashlib.sha256(file_content).hexdigest()
                file_size = len(file_content)
                logger.info(f"文件内容哈希值: {content_hash}, 文件大小: {file_size} bytes, 文件ID: {file_id}")
            except Exception as e:
                logger.error(f"读取文件或计算哈希值失败: {str(e)}")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"读取文件失败: {str(e)}"
                )

                return {
                    "success": False,
                    "task_id": task_id,
                    "message": f"读取文件失败: {str(e)}"
                }

            # 检查该哈希值是否已存在，如果存在则可以直接复用内容
            existing_content = await self._check_content_exists(content_hash)

            if existing_content:
                logger.info(f"发现相同内容的已处理文件，将复用处理结果: {content_hash}")

                # 检查MinIO中是否存在对应的文件，如果不存在则创建
                content_file_name = f"{content_hash}.txt"
                if self.content_storage:
                    try:
                        minio_file_exists = await self.content_storage.file_exists(content_file_name)
                        logger.info(f"复用内容时，MinIO中文件存在状态: {minio_file_exists}")

                        # 如果MinIO中没有文件，则从数据库内容创建文件
                        if not minio_file_exists:
                            markdown_content = existing_content.get("markdown_content", "")
                            if markdown_content:
                                logger.info(f"从数据库内容创建MinIO文件: {content_file_name}")
                                saved_path = await self.content_storage.save_file(
                                    file_id=content_hash,
                                    content=markdown_content.encode('utf-8'),
                                    file_extension=".txt"
                                )
                                logger.info(f"成功创建MinIO文件: {saved_path}")
                            else:
                                logger.warning("数据库中的markdown内容为空，无法创建MinIO文件")
                    except Exception as e:
                        logger.error(f"同步MinIO文件失败: {str(e)}")

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="processing",
                    progress=50,
                    message=f"发现相同内容文件，复用处理结果并同步MinIO: {content_hash}"
                )

                # 异步获取文件大小
                try:
                    file_size = await self._async_get_file_size(file_path)
                except Exception as e:
                    logger.error(f"获取文件大小失败: {str(e)}")
                    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

                if not content_type and file_path:
                    file_extension = Path(file_path).suffix.lower()
                    ext_to_mime = {
                        ".pdf": "application/pdf",
                        ".txt": "text/plain",
                        ".md": "text/markdown",
                        ".csv": "text/csv",
                        ".json": "application/json",
                        ".html": "text/html",
                        ".xml": "text/xml",
                        ".doc": "application/msword",
                        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                    content_type = ext_to_mime.get(file_extension, "application/octet-stream")

                if not content_type:
                    content_type = "application/octet-stream"

                # 创建新的project_files记录，但使用已存在的内容哈希
                try:
                    create_file_record = await call_service(
                        service_name="file",
                        endpoint="api/file/create_record",
                        method="POST",
                        json_data={
                            "file_hash": content_hash,  # 使用内容哈希而不是file_id
                            "project_id": project_id,
                            "name": file_path,
                            "path": f"{project_id}/{content_hash}",
                            "size": file_size,
                            "type": content_type,
                            "status": "completed"  # 直接标记为完成
                        },
                        use_service_auth=True
                    )

                    logger.info(f"为相同内容文件创建project_files记录结果: {create_file_record}")

                    # 更新任务状态为已完成
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="completed",
                        progress=100,
                        message=f"文件处理完成(复用): {file_path}"
                    )

                    total_time = time.time() - start_time
                    logger.info(f"文件处理成功(复用): {file_path}, 总处理用时: {total_time:.2f}秒")

                    # 返回处理结果
                    return {
                        "success": True,
                        "message": "文件处理成功(复用已有内容)",
                        "task_id": task_id,
                        "content_hash": content_hash,
                        "file_id": file_id,
                        "project_id": project_id,
                        "processing_time_seconds": total_time,
                        "markdown_content": existing_content.get("content", ""),
                        "reused_content": True
                    }
                except Exception as e:
                    logger.error(f"复用处理结果时出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    # 如果复用失败，继续进行正常处理流程

            # 不存在相同内容或复用失败，继续正常处理流程
            # 但使用计算出的内容哈希替代原始file_id作为文件标识符
            file_id = content_hash

            # 如果文件类型为空，尝试从文件名推断
            if not content_type and file_path:
                file_extension = Path(file_path).suffix.lower()

                # 扩展名映射到MIME类型
                ext_to_mime = {
                    ".pdf": "application/pdf",
                    ".txt": "text/plain",
                    ".md": "text/markdown",
                    ".csv": "text/csv",
                    ".json": "application/json",
                    ".html": "text/html",
                    ".xml": "text/xml",
                    ".doc": "application/msword",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".xls": "application/vnd.ms-excel",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".ppt": "application/vnd.ms-powerpoint",
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                }

                content_type = ext_to_mime.get(file_extension, "application/octet-stream")
                logger.info(f"从文件名推断文件类型: {file_path} -> {content_type}")

            # 如果仍然为空，使用通用类型
            if not content_type:
                content_type = "application/octet-stream"
                logger.warning(f"无法确定文件类型，使用默认类型: {content_type}")

            logger.info(f"开始处理文件: {file_path} (ID: {file_id}, 项目: {project_id}, 路径: {file_path}, 类型: {content_type}")

            try:
                # 更新任务状态为处理中
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="processing",
                    progress=30,
                    message=f"分析文件类型: {content_type} -> {content_type}"
                )

                # 文件元数据
                metadata = {
                    "file_id": file_id,
                    "file_name": file_path,
                    "file_size": file_size,
                    "file_type": content_type,
                    "normalized_type": content_type,
                    "upload_time": datetime.now().isoformat(),
                    "project_id": project_id,
                    "processed": True
                }

                # 根据标准化的文件类型获取处理结果，使用物理路径处理文件
                processing_start_time = time.time()

                # 确保处理方法存在
                if not hasattr(self, '_get_processor_for_file_type'):
                    logger.error("处理方法不存在: _get_processor_for_file_type")

                    # 更新任务状态为失败
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        progress=100,
                        message="处理方法不存在: _get_processor_for_file_type"
                    )

                    return {
                        "success": False,
                        "task_id": task_id,
                        "message": "处理方法不存在: _get_processor_for_file_type"
                    }

                # 创建临时文件用于处理
                temp_file_path = None
                try:
                    # 创建临时文件
                    temp_file_fd, temp_file_path = tempfile.mkstemp(suffix=Path(file_path).suffix)
                    os.close(temp_file_fd)  # 关闭文件描述符

                    # 将文件内容写入临时文件
                    with open(temp_file_path, 'wb') as temp_file:
                        temp_file.write(file_content)

                    logger.info(f"创建临时文件用于处理: {temp_file_path}")

                    # 使用临时文件路径进行处理
                    result = await self._get_processor_for_file_type(content_type, temp_file_path, metadata, task_id)

                finally:
                    # 清理临时文件
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.unlink(temp_file_path)
                            logger.debug(f"已删除临时文件: {temp_file_path}")
                        except Exception as e:
                            logger.warning(f"删除临时文件失败: {temp_file_path}, 错误: {str(e)}")
                processing_end_time = time.time()
                processing_duration = processing_end_time - processing_start_time
                logger.info(f"文件内容处理耗时: {processing_duration:.2f}秒 ({file_path})")

                # 更新任务状态
                if result.get("success", False):
                    # 处理成功
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="completed",
                        progress=100,
                        message=f"文件处理完成: {file_path}"
                    )

                    # 计算总处理时间
                    total_time = time.time() - start_time
                    metadata["processing_time_seconds"] = total_time
                    logger.info(f"文件处理成功: {file_path}, 总处理用时: {total_time:.2f}秒")
                else:
                    # 处理失败 - 此处直接返回处理结果，不再尝试注册文件
                    error_message = result.get('error', '未知错误')
                    logger.error(f"文件处理失败: {file_path}, 错误: {error_message}")

                    # 更新任务状态
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        progress=100,
                        message=f"文件处理失败: {error_message}"
                    )

                    # 更新文件状态
                    await call_service(
                        service_name="file",
                        endpoint="api/file/update/status",
                        method="POST",
                        json_data={
                            "file_hash": file_id,
                            "project_id": project_id,
                            "status": "failed"
                        },
                        use_service_auth=True
                    )

                    # 计算总处理时间
                    total_time = time.time() - start_time

                    # 返回处理失败结果
                    return {
                        "success": False,
                        "error": error_message,
                        "task_id": task_id,
                        "file_id": file_id,
                        "file_name": file_path,
                        "processing_time_seconds": total_time
                    }

                # 只有在处理成功时才注册文件
                register_start_time = time.time()

                # 注册文件到文件服务
                register_result = await self._register_file_to_service(metadata, result, task_id)

                # 记录注册时间
                register_time = time.time() - register_start_time
                logger.info(f"文件注册耗时: {register_time:.2f}秒 ({file_path})")

                # 如果注册失败，更新任务状态
                if not register_result:
                    logger.error(f"文件注册失败: {file_path}")

                    # 更新任务状态
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        progress=100,
                        message=f"文件注册失败: {file_path}"
                    )

                    # 更新文件状态
                    await call_service(
                        service_name="file",
                        endpoint="api/file/update/status",
                        method="POST",
                        json_data={
                            "file_hash": file_id,
                            "project_id": project_id,
                            "status": "failed"
                        },
                        use_service_auth=True
                    )

                    # 计算总处理时间
                    total_time = time.time() - start_time

                    # 返回处理失败结果
                    return {
                        "success": False,
                        "error": "文件注册失败",
                        "task_id": task_id,
                        "file_id": file_id,
                        "file_name": file_path,
                        "processing_time_seconds": total_time
                    }

                # 记录完整处理时间明细
                final_time = time.time() - start_time
                logger.info(f"文件处理完成明细 - {file_path}: 总时间={final_time:.2f}秒, 内容处理={processing_duration:.2f}秒, 文件注册={register_time:.2f}秒")

                # 发送任务完成通知
                if connection_manager and project_id:
                    await self._send_task_completion(
                        connection_manager, project_id, task_id,
                        {
                            "status": "completed",
                            "progress": 100,
                            "stage": "finished",
                            "message": "文件处理完成",
                            "file_id": file_id,
                            "processing_time": final_time,
                            "timestamp": datetime.now().isoformat(),
                            "result": result
                        }
                    )

                return result

            except Exception as e:
                # 计算错误处理总时间
                error_time = time.time() - start_time
                error_message = str(e)
                logger.error(f"处理文件失败: {file_path}, 错误: {error_message}, 耗时: {error_time:.2f}秒")

                # 更新任务状态
                if hasattr(self, 'queue') and self.queue:
                    await self.queue.update_task_status(
                        task_id=task_id,
                        status="failed",
                        message=f"处理文件时出错: {error_message}"
                    )

                # 更新文件状态
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )

                # 发送错误通知
                if connection_manager and project_id:
                    await self._send_error_notification(
                        connection_manager, project_id, task_id,
                        {
                            "status": "failed",
                            "progress": 100,
                            "stage": "error",
                            "message": f"文件处理失败: {error_message}",
                            "file_id": file_id,
                            "error": error_message,
                            "processing_time": error_time,
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                return {
                    "success": False,
                    "error": f"处理文件时出错: {error_message}",
                    "task_id": task_id,
                    "file_id": file_id,
                    "file_name": file_path,
                    "processing_time_seconds": error_time
                }

        except Exception as e:
            error_message = str(e)
            logger.error(f"处理文件失败: {error_message}")
            logger.error(traceback.format_exc())

            # 更新任务状态
            if hasattr(self, 'queue') and self.queue:
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"处理文件失败: {error_message}"
                )

            # 计算处理时间
            end_time = time.time()
            processing_time = end_time - start_time if 'start_time' in locals() else 0

            # 发送错误通知
            if connection_manager and project_id:
                await self._send_error_notification(
                    connection_manager, project_id, task_id,
                    {
                        "status": "failed",
                        "progress": 100,
                        "stage": "error",
                        "message": f"文件处理失败: {error_message}",
                        "file_id": file_id,
                        "error": error_message,
                        "processing_time": processing_time,
                        "timestamp": datetime.now().isoformat()
                    }
                )

            return {
                "success": False,
                "error": f"处理文件失败: {error_message}",
                "task_id": task_id,
                "file_id": file_id,
                "file_name": file_path,
                "processing_time_seconds": processing_time
            }

    async def _async_path_exists(self, path: str) -> bool:
        """异步检查路径是否存在"""
        try:
            # 先检查是否使用本地存储
            storage_type = os.environ.get("STORAGE_TYPE", "").lower()

            # 尝试多种可能的本地路径
            local_storage_path = os.environ.get("UPLOAD_DIR", "./uploads")
            possible_paths = []

            # 1. 首先尝试直接使用原始路径
            possible_paths.append(path)

            # 2. 如果文件路径不以local_storage_path开头，添加前缀
            if not path.startswith(local_storage_path):
                possible_paths.append(os.path.join(local_storage_path, path))

            # 3. 如果文件路径已经包含项目ID/文件名，移除重复路径部分
            if '/uploads/' in path:
                clean_path = path.split('/uploads/', 1)[1]
                possible_paths.append(os.path.join(local_storage_path, clean_path))

            # 4. 尝试直接使用文件名
            if '/' in path:
                _, file_name = path.rsplit('/', 1)
                possible_paths.append(os.path.join(local_storage_path, file_name))

            # 尝试所有可能的路径
            for test_path in possible_paths:
                logger.info(f"检查本地文件是否存在: {test_path}")
                if os.path.exists(test_path):
                    logger.info(f"文件存在于本地存储: {test_path}")
                    return True

            if storage_type == "local":
                logger.warning(f"文件不存在于所有可能的本地路径: {possible_paths}")
                return False  # 如果是本地存储模式且本地文件不存在，则直接返回

            # 如果文件不存在于本地，检查MinIO
            # 从路径中提取对象键
            object_key = path
            if object_key.startswith('data/'):
                object_key = object_key[5:]  # 移除前缀

            # 检查对象是否存在
            loop = asyncio.get_event_loop()
            try:
                if self.s3_client is None:
                    logger.error("S3客户端未初始化")
                    return False

                await loop.run_in_executor(
                    None,
                    lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
                )
                logger.debug(f"文件存在于MinIO: {object_key}")
                return True
            except Exception as e:
                logger.warning(f"文件不存在于MinIO: {object_key}, 错误: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"检查文件路径时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _async_get_file_size(self, path: str) -> int:
        """异步获取文件大小"""
        try:
            # 先检查是否使用本地存储
            storage_type = os.environ.get("STORAGE_TYPE", "").lower()
            if storage_type == "local":
                # 本地存储模式
                local_storage_path = os.environ.get("UPLOAD_DIR", "./uploads")

                # 尝试多种可能的本地路径
                possible_paths = []

                # 1. 首先尝试直接使用原始路径
                possible_paths.append(path)

                # 2. 如果文件路径不以local_storage_path开头，添加前缀
                if not path.startswith(local_storage_path):
                    possible_paths.append(os.path.join(local_storage_path, path))

                # 3. 如果文件路径已经包含项目ID/文件名，移除重复路径部分
                if '/uploads/' in path:
                    clean_path = path.split('/uploads/', 1)[1]
                    possible_paths.append(os.path.join(local_storage_path, clean_path))

                # 4. 尝试直接使用文件名
                if '/' in path:
                    _, file_name = path.rsplit('/', 1)
                    possible_paths.append(os.path.join(local_storage_path, file_name))

                # 尝试所有可能的路径
                for test_path in possible_paths:
                    if os.path.exists(test_path):
                        logger.info(f"从本地存储获取文件大小: {test_path}")
                        return os.path.getsize(test_path)

                logger.warning(f"文件在所有可能的本地路径中都不存在: {possible_paths}")

            # 从路径中提取对象键
            object_key = path
            if object_key.startswith('data/'):
                object_key = object_key[5:]  # 移除前缀

            # 获取对象信息
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
                )
                # 返回文件大小
                return response.get('ContentLength', 0)
            except Exception as e:
                logger.warning(f"从MinIO获取文件大小失败: {str(e)}")

                # 如果MinIO检查失败，检查本地存储
                local_storage_path = os.environ.get("UPLOAD_DIR", "./uploads")
                full_path = os.path.join(local_storage_path, object_key)
                if os.path.exists(full_path):
                    logger.info(f"从本地存储获取文件大小(备选路径): {full_path}")
                    return os.path.getsize(full_path)

                # 如果都失败，返回默认大小
                return 0
        except Exception as e:
            logger.error(f"获取文件大小失败: {str(e)}")
            return 0

    async def _process_text_file(self, file_path: str, metadata: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """处理文本文件，提取内容"""
        file_id = metadata.get("file_id", "unknown")

        try:
            logger.info(f"处理文本文件: {file_path}")

            # 首先尝试从本地存储读取文件
            content = None
            storage_type = os.environ.get("STORAGE_TYPE", "").lower()

            if storage_type == "local" or os.path.isfile(file_path):
                # 本地存储模式
                local_storage_path = os.environ.get("UPLOAD_DIR", "./uploads")

                # 尝试多种可能的路径
                possible_paths = []

                # 1. 首先尝试直接使用原始路径
                possible_paths.append(file_path)

                # 2. 如果文件路径不以local_storage_path开头，添加前缀
                if not file_path.startswith(local_storage_path):
                    possible_paths.append(os.path.join(local_storage_path, file_path))

                # 3. 如果文件路径已经包含项目ID/文件名，移除重复路径部分
                if '/uploads/' in file_path:
                    clean_path = file_path.split('/uploads/', 1)[1]
                    possible_paths.append(os.path.join(local_storage_path, clean_path))

                # 4. 尝试直接使用文件名
                if '/' in file_path:
                    _, file_name = file_path.rsplit('/', 1)
                    possible_paths.append(os.path.join(local_storage_path, file_name))

                # 尝试所有可能的路径
                content = None
                for path in possible_paths:
                    logger.info(f"尝试从本地存储读取文件: {path}")
                    if os.path.exists(path):
                        try:
                            # 异步读取文件内容
                            async with aiofiles.open(path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = await f.read()
                            logger.info(f"成功从本地存储读取文件内容: {path}")
                            break
                        except Exception as e:
                            logger.error(f"从本地存储读取文件失败: {path}, 错误: {str(e)}")
                    else:
                        logger.warning(f"本地文件不存在: {path}")

            # 如果本地存储未成功，尝试从MinIO获取
            if content is None:
                # 从路径中提取对象键
                object_key = file_path
                if object_key.startswith('data/'):
                    object_key = object_key[5:]  # 移除前缀

                # 从MinIO获取文件内容
                loop = asyncio.get_event_loop()
                try:
                    # 创建临时文件
                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_path = temp_file.name
                    temp_file.close()

                    # 下载文件到临时文件
                    await loop.run_in_executor(
                        None,
                        lambda: self.s3_client.download_file(self.bucket_name, object_key, temp_path)
                    )

                    # 异步读取文件内容
                    async with aiofiles.open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = await f.read()

                    # 删除临时文件
                    os.unlink(temp_path)
                    logger.info(f"成功从MinIO读取文件内容: {object_key}")
                except Exception as e:
                    logger.error(f"从MinIO获取文件失败: {object_key}, 错误: {str(e)}")

                    # 尝试备用路径
                    local_storage_path = os.environ.get("UPLOAD_DIR", "./uploads")
                    full_path = os.path.join(local_storage_path, object_key)
                    if os.path.exists(full_path):
                        try:
                            # 异步读取文件内容
                            async with aiofiles.open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = await f.read()
                            logger.info(f"成功从备用本地路径读取文件内容: {full_path}")
                        except Exception as e2:
                            logger.error(f"从备用本地路径读取文件失败: {full_path}, 错误: {str(e2)}")

            if content is None:
                return {
                    "success": False,
                    "error": "无法读取文件内容",
                    "metadata": metadata
                }

            # 获取文件行数和字符数
            lines = content.count('\n') + 1
            chars = len(content)

            # 将文本内容转换为Markdown格式
            # 简单文本转Markdown：添加标题和原始内容
            file_name = metadata.get("file_name", "unknown")

            logger.info(f"文本处理成功: 行数={lines}, 字符数={chars}")

            # 将文本内容转换为TXT格式而不是Markdown
            txt_content = content  # 直接使用原始文本内容

            # 将处理后的TXT内容保存到存储系统
            try:
                # 获取content存储实例
                content_storage = await get_storage(directory_type="content")

                # 构建文件路径，使用.txt扩展名
                txt_filename = f"{file_id}.txt"

                # 直接保存到存储（本地或S3）
                saved_path = await content_storage.save_file(
                    file_id=txt_filename,
                    content=txt_content.encode('utf-8'),
                    file_extension=""
                )

                logger.info(f"处理后的txt文件已保存到存储: {saved_path}")

            except Exception as e:
                logger.error(f"保存txt到存储系统失败: {str(e)}")
                logger.error(traceback.format_exc())
                return {
                    "success": False,
                    "message": f"保存处理结果失败: {str(e)}",
                    "metadata": metadata
                }

            # 更新元数据
            metadata.update({
                "lines": lines,
                "chars": chars,
                "content_preview": content[:500] if len(content) > 500 else content
            })

            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=80,
                message="文本文件处理完成，准备返回结果"
            )

            # 保留提取内容，由统一登记步骤保存内容并更新项目文件状态。
            return {
                "success": True,
                "content": txt_content,
                "metadata": metadata,
                "file_path": saved_path,
                "content_type": "text/plain"
            }

        except Exception as e:
            logger.error(f"处理文本文件失败: {file_path}, 错误: {str(e)}")
            return {
                "success": False,
                "error": f"处理文本文件失败: {str(e)}",
                "metadata": metadata
            }

    async def _process_office_file(self, file_path: str, metadata: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        处理Office文档

        Args:
            file_path: 文件路径
            metadata: 文件元数据
            task_id: 任务ID

        Returns:
            Dict[str, Any]: 处理结果
        """
        file_id = metadata.get("file_id", "unknown")
        project_id = metadata.get("project_id", "unknown")

        try:
            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=40,
                message="处理Office文档"
            )

            # 同步更新文件状态为processing，确保前端能够看到正在处理的状态
            try:
                from src.shared.service_discovery import call_service
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "processing"
                    },
                    use_service_auth=True,
                    timeout=5.0  # 较短的超时时间，避免影响主流程
                )
            except Exception as e:
                logger.warning(f"更新文件状态为processing时发生异常: {str(e)}")
                # 不影响主流程继续

            # 这里可以添加更复杂的Office文档处理逻辑
            # 使用异步方式处理，例如通过run_in_executor包装同步库
            # 但为了简单起见，我们只记录基本信息

            # 更新元数据（异步处理）
            loop = asyncio.get_event_loop()
            file_info = await loop.run_in_executor(None, lambda: {"content_type": "office", "preview_available": False})
            metadata.update(file_info)

            # 生成一个简单的Markdown内容
            content = f"# {os.path.basename(file_path)}\n\n此Office文档已被处理，但内容提取功能尚未完全实现。\n\n文件路径: {file_path}"

            # 将处理后的内容保存到content目录，使用file_id作为文件名，保存为txt格式
            saved_path = await self._save_txt_to_content_dir(content, file_id)
            logger.info(f"已保存Office文档处理结果到content目录: {saved_path}")

            # 注册到文件服务
            register_result = await call_service(
                service_name="file",
                endpoint="api/file/register/content",
                method="POST",
                json_data={
                    "file_hash": file_id,
                    "markdown_content": content,  # 内容保持不变，但实际存储为txt
                    "metadata": {"processed": True, "source": "office_processor", "format": "txt"},
                    "file_type": "text/plain",  # 修改为txt类型
                    "page_count": 1
                },
                use_service_auth=True
            )

            if not register_result or not register_result.get("success", False):
                logger.warning(f"Office文档内容注册失败: {register_result}")
            else:
                logger.info(f"Office文档内容注册成功: {file_id}")

            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=80,
                message="Office文档处理完成，准备返回结果"
            )

            # 更新文件状态为已完成
            try:
                status_response = await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "completed"
                    },
                    use_service_auth=True
                )
                if not status_response or not status_response.get("success", False):
                    logger.warning(f"更新文件状态失败: {status_response}")
            except Exception as e:
                logger.error(f"更新文件状态为已完成时发生异常: {str(e)}")

            return {
                "success": True,
                "content": content,
                "metadata": metadata,
                "file_type": "office",
                "stats": {
                    "processed": True
                }
            }

        except Exception as e:
            logger.error(f"处理Office文档失败: {file_path}, 错误: {str(e)}")

            # 更新文件状态为失败
            try:
                from src.shared.service_discovery import call_service
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )
            except Exception as update_err:
                logger.error(f"更新文件状态为失败时发生异常: {str(update_err)}")

            return {
                "success": False,
                "error": f"处理Office文档失败: {str(e)}",
                "metadata": metadata
            }

    async def _process_pdf_file(self, file_path: str, metadata: Dict[str, Any], task_id: str, enable_ocr: bool) -> Dict[str, Any]:
        """
        处理PDF文件，提取文本内容

        Args:
            file_path: 文件路径
            metadata: 文件元数据
            task_id: 任务ID

        Returns:
            Dict[str, Any]: 处理结果
        """
        file_id = metadata.get("file_id", "unknown")
        project_id = metadata.get("project_id", "unknown")

        try:
            logger.info(f"处理PDF文件: {file_path}")

            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=40,
                message="处理PDF文件"
            )

            # 同步更新文件状态为processing，确保前端能够看到正在处理的状态
            try:
                from src.shared.service_discovery import call_service
                update_status_response = await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "processing"
                    },
                    use_service_auth=True,
                    timeout=5.0  # 较短的超时时间，避免影响主流程
                )
                if update_status_response and update_status_response.get("success", False):
                    logger.info(f"已更新文件处理状态为processing: file_id={file_id}, project_id={project_id}")
                else:
                    logger.warning(f"更新文件状态为processing失败: {update_status_response}")
            except Exception as e:
                logger.warning(f"更新文件状态为processing时发生异常: {str(e)}")
                # 不影响主流程继续

            # 使用DoclingProcessor处理PDF
            processor = DoclingProcessor()
            result = await processor.process_pdf(file_path, enable_ocr=enable_ocr)

            if not result.get("success", False):
                error_message = result.get("error", "处理PDF失败")
                logger.error(f"PDF处理失败: {error_message}")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"PDF处理失败: {error_message}"
                )

                # 同步更新文件状态为failed
                try:
                    await call_service(
                        service_name="file",
                        endpoint="api/file/update/status",
                        method="POST",
                        json_data={
                            "file_hash": file_id,
                            "project_id": project_id,
                            "status": "failed"
                        },
                        use_service_auth=True
                    )
                    logger.info(f"已更新文件状态为失败: file_id={file_id}, project_id={project_id}")
                except Exception as e:
                    logger.error(f"更新文件状态为失败时发生异常: {str(e)}")

                return {
                    "success": False,
                    "error": error_message,
                    "message": "PDF处理失败"
                }

            # 获取处理后的内容
            content = result.get("content", "")

            # 如果内容太少，可能处理失败
            if not content or len(content.strip()) < 50:
                logger.warning(f"PDF处理结果内容太少: {len(content) if content else 0} 字符")

                # 更新任务状态为失败
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message="PDF处理结果内容太少"
                )

                # 更新文件状态为失败
                try:
                    await call_service(
                        service_name="file",
                        endpoint="api/file/update/status",
                        method="POST",
                        json_data={
                            "file_hash": file_id,
                            "project_id": project_id,
                            "status": "failed"
                        },
                        use_service_auth=True
                    )
                except Exception as e:
                    logger.error(f"更新文件状态为失败时发生异常: {str(e)}")

                return {
                    "success": False,
                    "error": "PDF处理结果内容太少",
                    "message": "PDF处理结果内容太少"
                }

            # 处理成功，返回结果
            logger.info(f"PDF处理成功: {file_path}, 内容长度: {len(content)} 字符")

            # 将处理后的内容保存到content目录，使用file_id作为文件名，保存为txt格式
            saved_path = await self._save_txt_to_content_dir(content, file_id)
            logger.info(f"已保存PDF处理结果到content目录: {saved_path}")

            # 更新任务状态为完成
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",  # 保持为processing，文件内容注册后再更新为completed
                progress=80,
                message="PDF处理成功，准备注册文件内容"
            )

            # 返回处理结果
            return {
                "success": True,
                "content": content,
                "metadata": result.get("metadata", {}),
                "page_count": result.get("page_count", 1),
                "file_path": file_path,
                "file_id": file_id,
                "project_id": project_id
            }
        except Exception as e:
            logger.error(f"处理PDF文件异常: {str(e)}")
            logger.error(traceback.format_exc())

            # 更新任务状态为失败
            await self.queue.update_task_status(
                task_id=task_id,
                status="failed",
                progress=100,
                message=f"处理PDF文件异常: {str(e)}"
            )

            # 更新文件状态为失败
            try:
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )
            except Exception as update_err:
                logger.error(f"更新文件状态为失败时发生异常: {str(update_err)}")

            return {
                "success": False,
                "error": str(e),
                "message": "处理PDF文件异常"
            }

    async def _register_file_to_service(self, metadata: Dict[str, Any], result: Dict[str, Any], task_id: str) -> bool:
        """
        将文件注册到文件服务

        Args:
            metadata: 文件元数据
            result: 处理结果
            task_id: 任务ID

        Returns:
            bool: 是否成功注册
        """
        try:
            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=90,
                message="注册文件到文件服务"
            )

            # 如果处理结果失败，不注册文件，更新文件状态为失败
            if not result.get("success", False):
                logger.warning("处理结果失败，更新文件状态为失败")

                # 获取文件ID和项目ID
                file_id = metadata.get("file_id", "unknown")
                project_id = metadata.get("project_id", "unknown")
                error_message = result.get("error", "未知错误")

                # 更新文件状态为失败
                from src.shared.service_discovery import call_service
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"处理失败: {error_message}"
                )

                return False

            # 构建注册数据 - 使用正确的字段格式
            file_id = metadata.get("file_id")
            project_id = metadata.get("project_id")
            content = result.get("content", "")

            # 如果内容为空，不注册
            if not content or content.strip() == "":
                logger.warning("处理结果内容为空，不注册文件")

                # 更新文件状态为失败
                from src.shared.service_discovery import call_service
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message="处理结果内容为空"
                )

                return False

            # 注册文件内容
            from src.shared.service_discovery import call_service

            # 构建注册数据
            register_data = {
                "file_hash": file_id,
                "markdown_content": content,
                "metadata": json.dumps({**metadata, "format": "txt"}),  # 添加格式标识
                "file_type": "text/plain",  # 修改为txt类型
                "page_count": metadata.get("page_count", 1)
            }

            # 调用文件服务注册内容
            response = await call_service(
                service_name="file",
                endpoint="api/file/register/content",
                method="POST",
                json_data=register_data,
                use_service_auth=True
            )

            if not response or not response.get("success", False):
                logger.error(f"注册文件内容失败: {response}")

                # 更新文件状态为失败
                await call_service(
                    service_name="file",
                    endpoint="api/file/update/status",
                    method="POST",
                    json_data={
                        "file_hash": file_id,
                        "project_id": project_id,
                        "status": "failed"
                    },
                    use_service_auth=True
                )

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=100,
                    message=f"注册文件内容失败: {response.get('error', '未知错误')}"
                )

                return False

            # 更新文件状态为已完成
            status_response = await call_service(
                service_name="file",
                endpoint="api/file/update/status",
                method="POST",
                json_data={
                    "file_hash": file_id,
                    "project_id": project_id,
                    "status": "completed"
                },
                use_service_auth=True
            )

            if not status_response or not status_response.get("success", False):
                logger.warning(f"更新文件状态失败: {status_response}")

                # 更新任务状态
                await self.queue.update_task_status(
                    task_id=task_id,
                    status="completed",
                    progress=100,
                    message="文件处理完成，但状态更新失败"
                )

                return True

            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="completed",
                progress=100,
                message="文件处理完成"
            )

            logger.info(f"文件处理完成并已注册: {file_id}")
            return True

        except Exception as e:
            logger.error(f"注册文件到文件服务失败: {str(e)}")
            logger.error(traceback.format_exc())

            # 更新任务状态
            await self.queue.update_task_status(
                task_id=task_id,
                status="failed",
                progress=100,
                message=f"注册文件失败: {str(e)}"
            )

            return False

    async def _save_txt_to_content_dir(self, content: str, file_hash: str) -> str:
        """
        保存TXT内容到content存储

        Args:
            content: TXT内容
            file_hash: 文件哈希

        Returns:
            str: TXT文件存储路径
        """
        try:
            # 如果内容为空，则不保存文件
            if not content or content.strip() == "":
                logger.warning(f"内容为空，不保存TXT文件: {file_hash}")
                return ""

            # 使用统一存储接口保存文件
            if self.content_storage:
                # 保存到统一存储（本地或S3）
                saved_path = await self.content_storage.save_file(
                    file_id=file_hash,
                    content=content.encode('utf-8'),
                    file_extension=".txt"
                )
                logger.info(f"已保存TXT文件到统一存储: {saved_path}")
                return saved_path
            else:
                # 兼容性：如果存储接口未初始化，使用本地保存
                logger.warning("内容存储接口未初始化，使用本地文件系统")

                # 确保content目录存在
                os.makedirs(self.content_dir, exist_ok=True)

                # 生成文件路径
                txt_path = os.path.join(self.content_dir, f"{file_hash}.txt")

                # 保存文件
                async with aiofiles.open(txt_path, "w", encoding="utf-8") as f:
                    await f.write(content)

                logger.info(f"已保存TXT文件到本地: {txt_path}")
                return txt_path
        except Exception as e:
            logger.error(f"保存TXT文件失败: {str(e)}")
            return ""

    async def _save_markdown_to_content_dir(self, content: str, file_hash: str) -> str:
        """
        保存Markdown内容到content存储（保留用于兼容性）

        Args:
            content: Markdown内容
            file_hash: 文件哈希

        Returns:
            str: Markdown文件存储路径
        """
        try:
            # 如果内容为空，则不保存文件
            if not content or content.strip() == "":
                logger.warning(f"内容为空，不保存Markdown文件: {file_hash}")
                return ""

            # 使用统一存储接口保存文件
            if self.content_storage:
                # 保存到统一存储（本地或S3）
                saved_path = await self.content_storage.save_file(
                    file_id=file_hash,
                    content=content.encode('utf-8'),
                    file_extension=".txt"
                )
                logger.info(f"已保存Markdown文件到统一存储: {saved_path}")
                return saved_path
            else:
                # 兼容性：如果存储接口未初始化，使用本地保存
                logger.warning("内容存储接口未初始化，使用本地文件系统")

                # 确保content目录存在
                os.makedirs(self.content_dir, exist_ok=True)

                # 生成文件路径
                markdown_path = os.path.join(self.content_dir, f"{file_hash}.txt")

                # 保存文件
                async with aiofiles.open(markdown_path, "w", encoding="utf-8") as f:
                    await f.write(content)

                logger.info(f"已保存Markdown文件到本地: {markdown_path}")
                return markdown_path
        except Exception as e:
            logger.error(f"保存Markdown文件失败: {str(e)}")
            return ""

    async def process_text_file(self, file_id: str, project_id: str) -> Dict[str, Any]:
        """
        处理文本文件 - 供服务间调用

        Args:
            file_id: 文件ID或哈希值
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            logger.info(f"处理文本文件: file_id={file_id}, project_id={project_id}")

            # 获取文件信息
            file_info = await call_service(
                service_name="file",
                endpoint=f"file/info/{project_id}/{file_id}",
                method="GET",
                use_service_auth=True
            )

            if not file_info or not file_info.get("success", False):
                error_msg = "获取文件信息失败"
                if file_info and "message" in file_info:
                    error_msg = file_info["message"]
                logger.error(f"{error_msg}: file_id={file_id}, project_id={project_id}")
                return {"success": False, "message": error_msg}

            # 获取文件内容
            file_content = await call_service(
                service_name="file",
                endpoint=f"file/content/{project_id}/{file_id}",
                method="GET",
                use_service_auth=True
            )

            if not file_content or "content" not in file_content:
                error_msg = "获取文件内容失败"
                logger.error(f"{error_msg}: file_id={file_id}, project_id={project_id}")
                return {"success": False, "message": error_msg}

            # 提取文本内容并处理
            text_content = file_content["content"]
            file_hash = file_info.get("file_hash", file_id)

            # 保存到content目录，使用txt格式
            saved_path = await self._save_txt_to_content_dir(text_content, file_hash)

            # 注册到文件服务
            register_result = await call_service(
                service_name="file",
                endpoint="api/file/register/content",
                method="POST",
                json_data={
                    "file_hash": file_hash,
                    "markdown_content": text_content,  # 使用纯文本内容
                    "metadata": {"processed": True, "source": "text_processor", "format": "txt"},
                    "file_type": "text/plain",  # 修改为txt类型
                    "page_count": 1
                },
                use_service_auth=True
            )

            if register_result and register_result.get("success", False):
                logger.info(f"处理完成并注册: file_id={file_id}, 保存路径={saved_path}")
                return {
                    "success": True,
                    "message": "文件处理成功",
                    "file_path": saved_path,
                    "content_type": "text/plain"
                }
            else:
                logger.warning(f"文件处理成功但注册失败: file_id={file_id}, 保存路径={saved_path}")
                return {
                    "success": True,
                    "message": "文件处理成功但注册失败",
                    "file_path": saved_path,
                    "content_type": "text/plain"
                }

        except Exception as e:
            error_msg = f"处理文本文件异常: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {"success": False, "message": error_msg}

    async def process_image_file(self, file_id: str, project_id: str) -> Dict[str, Any]:
        """
        处理图片文件 - 供服务间调用

        Args:
            file_id: 文件ID或哈希值
            project_id: 项目ID

        Returns:
            Dict[str, Any]: 处理结果
        """
        # 目前仅返回一个简单的成功响应
        # 真实实现可以添加OCR处理等
        return {
            "success": True,
            "message": "图片处理功能尚未实现",
            "file_id": file_id,
            "project_id": project_id
        }

    async def check_storage_health(self) -> bool:
        """
        检查存储服务的健康状态

        Returns:
            bool: 存储服务是否健康
        """
        try:
            # 如果存储服务未初始化，先尝试初始化
            if self.storage is None and not self.is_initialized:
                logger.info("存储服务未初始化，尝试初始化")
                await self.initialize()

            # 检查存储服务
            if self.storage is None:
                logger.error("存储服务未初始化")
                return False

            # 简单检查存储服务连接
            if hasattr(self.storage, "is_connected") and callable(getattr(self.storage, "is_connected")):
                connected = await self.storage.is_connected()
                if connected:
                    logger.info("存储服务连接正常")
                else:
                    logger.error("存储服务连接失败")
                return connected

            # 备用检查方法
            return True
        except Exception as e:
            logger.error(f"存储健康检查失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _get_processor_for_file_type(self, content_type: str, file_path: str, metadata: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """根据文件类型选择合适的处理器"""
        logger.info(f"选择处理器: 文件类型={content_type}, 文件路径={file_path}")

        # 更新任务状态
        await self.queue.update_task_status(
            task_id=task_id,
            status="processing",
            progress=30,
            message=f"分析文件内容: {content_type}"
        )

        # 根据文件类型分发到不同的处理器
        if is_text_document(content_type, file_path):
            return await self._process_text_file(file_path, metadata, task_id)
        elif content_type in ["application/pdf"]:
            return await self._process_pdf_file(file_path, metadata, task_id, enable_ocr=False)
        elif content_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                             "application/msword",
                             "application/vnd.ms-excel",
                             "application/vnd.ms-powerpoint"]:
            return await self._process_pdf_file(file_path, metadata, task_id, enable_ocr=False)
        else:
            # 默认作为文本处理
            logger.warning(f"未知文件类型: {content_type}，尝试作为文本处理")
            return await self._process_pdf_file(file_path, metadata, task_id, enable_ocr=False)

    async def _send_progress_update(self, connection_manager, project_id: str, task_id: str, progress_data: dict):
        """发送进度更新到WebSocket客户端"""
        try:
            if connection_manager:
                await connection_manager.send_progress_update(project_id, task_id, progress_data)
        except Exception as e:
            logger.warning(f"发送进度更新失败: {str(e)}")

    async def _send_task_completion(self, connection_manager, project_id: str, task_id: str, result_data: dict):
        """发送任务完成通知到WebSocket客户端"""
        try:
            if connection_manager:
                await connection_manager.send_task_completion(project_id, task_id, result_data)
        except Exception as e:
            logger.warning(f"发送任务完成通知失败: {str(e)}")

    async def _send_error_notification(self, connection_manager, project_id: str, task_id: str, error_data: dict):
        """发送错误通知到WebSocket客户端"""
        try:
            if connection_manager:
                await connection_manager.send_error_notification(project_id, task_id, error_data)
        except Exception as e:
            logger.warning(f"发送错误通知失败: {str(e)}")

# 创建全局实例，供其他模块导入
file_processor = FileProcessor()
