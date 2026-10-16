"""
文件处理服务，整合文件上传和处理功能
"""

import os
import logging
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiofiles
import traceback
from fastapi import HTTPException, UploadFile
from typing import Union
import hashlib
from src.shared.service_discovery import call_service
from src.shared.storage import get_storage
from src.shared.config import get_settings
from src.shared.models.api_models import ApiResponse
from src.shared.file.schemas import FileUploadResponse, FileProcessingStatusEnum
from src.shared.file_types import is_text_document
from .config.database import FileServiceDatabase
from src.shared.database import get_db

logger = logging.getLogger(__name__)

# 默认工作目录从配置获取
DEFAULT_WORK_DIR = get_settings().storage_dir

class FileProcessorService:
    """文件处理服务，整合文件上传和处理功能"""

    def __init__(self,
                 work_dir: Optional[Union[str, Path]] = None,
                 rapidocr_models_path: Optional[str] = None):
        """
        初始化文件处理服务

        Args:
            work_dir: 工作目录，默认为配置中的存储目录
            rapidocr_models_path: RapidOCR模型路径
        """
        self.work_dir = Path(work_dir) if work_dir else Path(DEFAULT_WORK_DIR)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.rapidocr_models_path = rapidocr_models_path

        # 存储系统将在需要时异步初始化
        self.storage = None
        self.storage_type = os.getenv('STORAGE_TYPE', 'local')
        logger.info(f"文件处理服务已初始化，存储类型: {self.storage_type}")

    async def _get_storage(self, directory_type: str = "upload"):
        """获取存储实例，如果未初始化则异步初始化"""
        if self.storage is None:
            self.storage = await get_storage(self.storage_type, directory_type)
        return self.storage

    def _get_content_type(self, filename: str) -> str:
        """
        根据文件名获取MIME类型

        Args:
            filename: 文件名

        Returns:
            str: MIME类型
        """
        import mimetypes

        # 确保mimetypes已初始化
        mimetypes.init()

        # 获取MIME类型
        content_type, _ = mimetypes.guess_type(filename)

        # 如果无法确定MIME类型，返回通用二进制类型
        return content_type or "application/octet-stream"

    async def upload_file(
        self,
        file: UploadFile,
        project_id: str,
        process: bool = True
    ) -> FileUploadResponse:
        """
        上传文件到存储目录并记录到数据库

        Args:
            file: 上传的文件
            project_id: 项目ID
            process: 是否立即处理文件

        Returns:
            FileUploadResponse: 上传响应
        """
        try:
            # 注意：现在使用存储接口，不需要本地工作目录

            # 读取文件内容
            content = await file.read()

            # 计算文件哈希
            file_hash = self._generate_file_hash(content)

            # 构建文件路径
            file_extension = Path(file.filename).suffix
            file_name = f"{file_hash}{file_extension}"

            # 始终按项目隔离存储，兼容UUID项目ID
            file_path = f"{project_id}/{file_name}"

            # 获取存储实例并保存文件
            from src.shared.storage.storage_factory import get_storage
            storage = await get_storage(directory_type="upload")
            saved_path = await storage.save_file(
                file_id=file_path,
                content=content
            )

            # 获取文件元数据
            file_size = len(content)
            content_type = self._get_content_type(file.filename)

            # 记录到数据库
            file_id = await self._record_file_to_db(
                file_hash=file_hash,
                filename=file.filename,
                content_type=content_type,
                size=file_size,
                file_path=saved_path,
                project_id=project_id
            )

            task_id = None
            if process:
                # 发送处理任务
                task_id = await self._send_processing_task(file_id, saved_path, content_type)

            # 返回上传结果
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                size=file_size,
                content_type=content_type,
                upload_time=datetime.now().isoformat(),
                task_id=task_id,
                status=FileProcessingStatusEnum.PENDING,
                exists=False,
                success=True,
                message="文件上传成功",
                file_hash=file_hash
            )

        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            logger.error(traceback.format_exc())

            # 返回错误响应
            return FileUploadResponse(
                file_id=f"error-{uuid.uuid4().hex[:8]}",
                filename=file.filename,
                size=0,
                content_type=file.content_type or "",
                upload_time=datetime.now().isoformat(),
                task_id=None,
                status=FileProcessingStatusEnum.FAILED,
                exists=False,
                success=False,
                message=f"文件上传失败: {str(e)}",
                file_hash=""
            )

    async def _record_file_to_db(self, file_hash: str, filename: str, content_type: str,
                            size: int, file_path: Path, project_id: str) -> str:
        """
        记录文件信息到数据库

        Args:
            file_hash: 文件哈希
            filename: 文件名
            content_type: 文件类型
            size: 文件大小
            file_path: 文件路径
            project_id: 项目ID

        Returns:
            str: 文件ID
        """
        try:
            # 记录文件到数据库
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 检查文件是否存在
                existing_file = await conn.fetchrow(
                    """
                    SELECT id FROM project_files
                    WHERE file_hash = $1 AND project_id::text = $2::text
                    """,
                    file_hash, project_id
                )

                if existing_file:
                    # 文件已存在，返回已有ID
                    file_id = existing_file['id']
                    logger.info(f"文件已存在: {file_hash}, 项目: {project_id}, ID: {file_id}")
                    return str(file_id)

                # 插入新文件记录
                file_record = await conn.fetchrow(
                    """
                    INSERT INTO project_files
                    (
                        project_id,
                        filename,
                        display_name,
                        content_type,
                        name,
                        path,
                        type,
                        size,
                        file_hash,
                        status,
                        metadata,
                        file_metadata
                    )
                    VALUES (
                        $1::uuid,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6,
                        $7,
                        $8,
                        $9,
                        $10,
                        $11,
                        $12::jsonb
                    )
                    RETURNING id
                    """,
                    project_id,
                    filename,           # filename
                    filename,           # display_name
                    content_type,       # content_type
                    filename,           # name (legacy)
                    str(file_path),     # path (legacy)
                    content_type,       # type (legacy)
                    size,
                    file_hash,
                    'pending',
                    None,
                    "{}"
                )

                file_id = file_record['id']
                logger.info(f"文件已记录到数据库: {file_hash}, 项目: {project_id}, ID: {file_id}")
                return str(file_id)

        except Exception as e:
            logger.error(f"记录文件到数据库失败: {str(e)}")
            logger.error(traceback.format_exc())
            return f"error-{uuid.uuid4().hex[:8]}"

    async def _send_processing_task(self, file_id: str, file_path: Path, content_type: str) -> str:
        """
        发送文件处理任务到处理队列

        Args:
            file_id: 文件ID
            file_path: 文件路径
            content_type: 文件MIME类型

        Returns:
            str: 任务ID
        """
        try:
            # 创建任务ID
            task_id = f"task-{uuid.uuid4().hex}"

            # 从文件路径中提取项目ID
            # 假设格式为：./uploads/项目ID/文件hash
            str_path = str(file_path)
            parts = Path(str_path).parts

            # 提取文件路径中的项目ID
            project_id = None
            if len(parts) > 1:
                # 尝试从路径中提取项目ID
                for part in parts:
                    if part.isdigit():
                        project_id = part
                        break

            if not project_id:
                # 如果路径中没有项目ID，则从数据库中获取
                try:
                    pool = await FileServiceDatabase.get_pool()
                    async with pool.acquire() as conn:
                        record = await conn.fetchrow(
                            """
                            SELECT project_id FROM project_files
                            WHERE id = $1
                            """,
                            int(file_id)
                        )
                        if record:
                            project_id = str(record['project_id'])
                except Exception as db_err:
                    logger.warning(f"从数据库获取项目ID失败: {str(db_err)}")
                    # 使用默认项目ID作为后备
                    project_id = "1"  # 默认项目ID

            logger.info(f"为文件 {file_id} 提取的项目ID: {project_id}")

            # 创建任务数据
            task_data = {
                "task_id": task_id,
                "file_id": file_id,
                "project_id": project_id,
                "file_path": str(file_path),
                "content_type": content_type,
                "created_at": datetime.now().isoformat()
            }

            # 调用fileproc服务处理文件
            try:
                from src.shared.service_discovery import call_service

                # 设置环境变量确保正确的服务标识
                os.environ["SERVICE_NAME"] = "file"

                # 向fileproc服务发送处理任务
                response = await call_service("fileproc", "process", method="POST", json_data=task_data)

                if response.get("success"):
                    logger.info(f"文件处理任务已发送: {task_id}")
                else:
                    logger.warning(f"文件处理任务发送失败: {response.get('message', '未知错误')}")
            except Exception as e:
                logger.error(f"调用文件处理服务失败: {str(e)}")

            return task_id
        except Exception as e:
            logger.error(f"创建处理任务失败: {str(e)}")
            return f"error-{uuid.uuid4().hex[:8]}"

    async def get_processing_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取文件处理状态

        Args:
            task_id: 任务ID

        Returns:
            Dict[str, Any]: 处理状态信息
        """
        try:
            # 尝试从fileproc服务获取任务状态
            try:
                from src.shared.service_discovery import call_service

                # 添加随机参数避免缓存
                import random
                cache_bust = random.randint(10000, 99999)

                # 调用fileproc服务获取任务状态 - 使用正确的API路径
                task_status = await call_service(
                    service_name="fileproc",
                    endpoint=f"api/status/{task_id}",
                    method="GET",
                    params={"_cb": cache_bust},
                    timeout=5.0  # 设置较短的超时以提高响应速度
                )

                if task_status:
                    logger.info(f"从fileproc获取到任务状态: {task_id} -> {task_status}")

                    # 确保返回正确的状态
                    status = task_status.get("status", "pending")
                    progress = task_status.get("progress", 0)
                    message = task_status.get("message", "处理中")
                    file_id = task_status.get("file_id", "")
                    project_id = task_status.get("project_id", "")

                    # 如果任务已完成或失败，更新数据库中的文件状态
                    if status in ["completed", "failed"]:
                        try:
                            # 尝试查找与该任务关联的文件
                            pool = await FileServiceDatabase.get_pool()
                            async with pool.acquire() as conn:
                                # 查询通过processing_task_id关联的文件
                                file_record = await conn.fetchrow(
                                    """
                                    SELECT file_hash, project_id FROM project_files
                                    WHERE processing_task_id = $1
                                    """,
                                    task_id
                                )

                                if file_record:
                                    file_hash = file_record["file_hash"]
                                    project_id = file_record["project_id"]

                                    # 更新文件状态为已完成或失败
                                    await conn.execute(
                                        """
                                        UPDATE project_files
                                        SET status = $3, processed_at = NOW()
                                        WHERE file_hash = $1 AND project_id = $2
                                        """,
                                        file_hash, project_id, status
                                    )

                                    logger.info(f"已更新文件状态为{status}: file_hash={file_hash}, project_id={project_id}")
                                elif file_id or task_status.get("file_hash"):
                                    # 如果通过processing_task_id找不到，尝试通过任务数据中的file_id查找
                                    search_file_id = file_id or task_status.get("file_hash", "")
                                    search_project_id = project_id or task_status.get("project_id", "")

                                    if search_file_id:
                                        # 查找项目中的所有pending或processing状态文件
                                        pending_files_query = """
                                        SELECT file_hash, project_id FROM project_files
                                        WHERE (status = 'pending' OR status = 'processing')
                                        """

                                        # 如果有file_hash，添加筛选条件
                                        params = []
                                        if search_file_id:
                                            pending_files_query += " AND file_hash = $1"
                                            params.append(search_file_id)

                                        # 如果有project_id，添加筛选条件
                                        if search_project_id:
                                            pending_files_query += f" AND project_id = ${len(params) + 1}"
                                            params.append(search_project_id)

                                        # 执行查询
                                        pending_files = await conn.fetch(pending_files_query, *params)

                                        for pending_file in pending_files:
                                            file_hash = pending_file["file_hash"]
                                            project_id = pending_file["project_id"]

                                            # 更新文件状态并关联任务ID
                                            await conn.execute(
                                                """
                                                UPDATE project_files
                                                SET status = $3, processed_at = NOW(),
                                                    processing_task_id = $4
                                                WHERE file_hash = $1 AND project_id = $2
                                                """,
                                                file_hash, project_id, status, task_id
                                            )

                                            logger.info(f"已更新文件状态为{status}并关联任务ID: file_hash={file_hash}, project_id={project_id}")
                        except Exception as db_err:
                            logger.error(f"更新文件状态失败: {str(db_err)}")
                            logger.error(traceback.format_exc())

                    # 返回标准化的状态响应
                    return {
                        "status": status,
                        "progress": progress,
                        "message": message,
                        "task_id": task_id
                    }
            except Exception as e:
                logger.warning(f"获取任务状态失败: {str(e)}")

            # 如果无法从fileproc获取状态，尝试从数据库获取
            try:
                pool = await FileServiceDatabase.get_pool()
                async with pool.acquire() as conn:
                    # 首先查询通过processing_task_id关联的文件
                    file_record = await conn.fetchrow(
                        """
                        SELECT status, file_hash, project_id FROM project_files
                        WHERE processing_task_id = $1
                        """,
                        task_id
                    )

                    if file_record and file_record["status"]:
                        db_status = file_record["status"]
                        logger.info(f"从数据库获取到文件状态: {task_id} -> {db_status}")

                        # 映射数据库状态到前端状态
                        status_mapping = {
                            "pending": "pending",
                            "processing": "processing",
                            "completed": "completed",
                            "failed": "failed"
                        }

                        status = status_mapping.get(db_status, "pending")
                        progress = 100 if status == "completed" else (0 if status == "pending" else 50)
                        message = "处理完成" if status == "completed" else ("处理失败" if status == "failed" else ("处理中" if status == "processing" else "等待处理"))

                        return {
                            "status": status,
                            "progress": progress,
                            "message": message,
                            "task_id": task_id
                        }
            except Exception as db_err:
                logger.warning(f"从数据库获取文件状态失败: {str(db_err)}")

            # 默认返回failed状态，避免永久显示"等待处理"
            return {
                "status": "failed",
                "progress": 100,
                "message": "任务处理失败，请检查文件格式或重新上传",
                "task_id": task_id
            }
        except Exception as e:
            logger.error(f"获取处理状态失败: {str(e)}")
            return {
                "status": "failed",
                "progress": 100,
                "message": f"获取状态失败: {str(e)}",
                "task_id": task_id
            }

    async def get_file_info(self, project_id: str, file_id: str) -> Dict[str, Any]:
        """
        获取文件信息

        Args:
            project_id: 项目ID
            file_id: 文件ID或哈希值

        Returns:
            Dict[str, Any]: 文件信息
        """
        try:
            # 记录原始参数
            logger.info(f"获取文件信息: file_id={file_id}, project_id={project_id}")

            # 查询数据库获取文件信息
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 尝试通过ID查询
                project_file = None

                # 首先尝试通过文件ID查询
                try:
                    file_id_int = int(file_id)
                    project_file = await conn.fetchrow(
                        """
                        SELECT * FROM project_files
                        WHERE id = $1 AND project_id::text = $2::text
                        """,
                        file_id_int, project_id
                    )
                except ValueError:
                    # 如果不是整数，可能是哈希值
                    pass

                # 如果通过ID未找到，则尝试用哈希值查询
                if project_file is None:
                    project_file = await conn.fetchrow(
                        """
                        SELECT * FROM project_files
                        WHERE file_hash::text = $1::text AND project_id::text = $2::text
                        """,
                        file_id, project_id
                    )

                if project_file is None:
                    logger.warning(f"未找到文件信息: {file_id}, 项目: {project_id}")
                    return {
                        "success": False,
                        "message": f"文件不存在: {file_id}"
                    }

                # 构建响应
                # 不使用await storage，因为storage不是异步对象
                file_path = project_file["path"]

                # 封装文件信息
                response = {
                    "success": True,
                    "file_id": str(project_file["id"]),
                    "project_id": str(project_file["project_id"]),
                    "filename": project_file["name"],
                    "file_path": file_path,
                    "size": project_file["size"],
                    "content_type": project_file["type"],
                    "upload_time": str(project_file["created_at"]),
                    "status": project_file["status"],
                    "file_hash": project_file["file_hash"]
                }

                return response

        except Exception as e:
            logger.error(f"获取文件信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取文件信息失败: {str(e)}"
            }

    async def get_file_content(self, file_hash: str) -> str:
        """获取处理后的文件内容（支持MinIO存储）"""
        try:
            # 首先从数据库检查文件是否存在
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                record = await conn.fetchrow(
                    """
                    SELECT markdown_content FROM file_contents
                    WHERE file_hash = $1
                    """,
                    file_hash
                )

                if record and record["markdown_content"]:
                    # 文件内容存在于数据库中，直接返回
                    logger.info(f"从数据库获取到文件内容: {file_hash}")
                    return record["markdown_content"]
                else:
                    # 文件不在数据库中或内容为空，尝试从存储系统获取
                    storage_type = os.environ.get("STORAGE_TYPE", "local")

                    if storage_type == "s3":
                        # 使用MinIO/S3存储
                        file_path = f"content/{file_hash}.txt"
                        if await self.storage.file_exists(file_path):
                            try:
                                content = await self.storage.get_file(file_path)
                                logger.info(f"从MinIO存储系统获取文件内容: {file_path}")
                                # 确保内容是字符串格式
                                if isinstance(content, bytes):
                                    content = content.decode('utf-8')
                                return content
                            except Exception as e:
                                logger.error(f"从MinIO存储系统获取文件内容失败: {str(e)}")

                        # 如果content目录没有，尝试其他可能的路径
                        alt_paths = [
                            f"{file_hash}.txt",
                            f"content/{file_hash}",
                            f"uploads/{file_hash}.txt"
                        ]

                        for alt_path in alt_paths:
                            if await self.storage.file_exists(alt_path):
                                try:
                                    content = await self.storage.get_file(alt_path)
                                    logger.info(f"从MinIO存储系统备用路径获取文件内容: {alt_path}")
                                    if isinstance(content, bytes):
                                        content = content.decode('utf-8')
                                    return content
                                except Exception as e:
                                    logger.error(f"从MinIO存储系统备用路径获取文件内容失败: {str(e)}")
                                    continue

                    else:
                        # 使用本地文件系统（原有逻辑）
                        content_dir = os.environ.get("CONTENT_DIR", "./content")
                        content_file_path = os.path.join(content_dir, f"{file_hash}.txt")

                        if os.path.exists(content_file_path):
                            try:
                                # 从content目录读取
                                async with aiofiles.open(content_file_path, "r", encoding="utf-8") as f:
                                    content = await f.read()
                                    logger.info(f"从本地content目录读取文件内容: {content_file_path}")
                                    return content
                            except Exception as e:
                                logger.error(f"从本地content目录读取文件失败: {str(e)}")

                        # 如果content目录没有，尝试从存储系统获取
                        file_path = f"content/{file_hash}.txt"
                        if await self.storage.file_exists(file_path):
                            try:
                                content = await self.storage.get_file(file_path)
                                logger.info(f"从本地存储系统获取文件内容: {file_path}")
                                return content
                            except Exception as e:
                                logger.error(f"从本地存储系统获取文件内容失败: {str(e)}")

                    # 如果都没有找到，返回空字符串或错误信息
                    logger.warning(f"未找到文件内容: {file_hash}")
                    return f"# 文件内容不可用\n\n无法找到文件 {file_hash} 的处理结果。"
        except Exception as e:
            logger.error(f"获取文件内容失败: {str(e)}")
            logger.error(traceback.format_exc())
            return f"# 获取文件内容出错\n\n错误信息: {str(e)}"

    async def delete_file(self, file_hash: str, project_id: str) -> bool:
        """删除文件"""
        try:
            logger.info(f"开始删除文件，文件哈希: {file_hash}, 项目ID: {project_id}")

            project_id_value = str(project_id)

            # 首先从数据库删除关联记录
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 检查文件是否存在(通过文件哈希或文件名)
                file_exists = await conn.fetchrow(
                    """
                    SELECT 1 FROM project_files
                    WHERE (file_hash = $1 OR name = $1) AND project_id::text = $2::text
                    """,
                    file_hash, project_id_value
                )

                if not file_exists:
                    logger.warning(f"要删除的文件不存在: 文件哈希={file_hash}, 项目ID={project_id}")
                    return False

                try:
                    # 获取文件名用于日志记录
                    file_record = await conn.fetchrow(
                        """
                        SELECT name, file_hash, path FROM project_files
                        WHERE (file_hash = $1 OR name = $1) AND project_id::text = $2::text
                        """,
                        file_hash, project_id_value
                    )

                    if file_record:
                        actual_file_name = file_record["name"]
                        actual_file_hash = file_record["file_hash"]
                        file_path = file_record["path"]
                        logger.info(f"找到要删除的文件: {actual_file_name} (哈希: {actual_file_hash}, 路径: {file_path})")

                        # 更新file_hash为实际哈希值
                        file_hash = actual_file_hash
                    else:
                        logger.warning(f"无法获取文件详情，继续尝试删除: {file_hash}")
                except Exception as e:
                    # 如果无法获取文件名，继续删除过程
                    logger.warning(f"获取文件详情失败: {str(e)}，继续尝试删除: {file_hash}")

                # 删除项目文件关联
                try:
                    # 使用拓展的条件删除记录
                    result = await conn.execute(
                        """
                        DELETE FROM project_files
                        WHERE (file_hash = $1 OR name = $1) AND project_id::text = $2::text
                        RETURNING id
                        """,
                        file_hash, project_id_value
                    )
                    logger.info(f"已从project_files表删除文件关联记录，结果: {result}")
                except Exception as e:
                    logger.error(f"删除project_files记录失败: {str(e)}")
                    raise

                # 检查是否还有其他项目引用此文件
                other_refs = 0
                try:
                    other_refs = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM project_files
                        WHERE file_hash = $1
                        """,
                        file_hash
                    )
                except Exception as e:
                    logger.error(f"检查文件引用失败: {str(e)}")
                    raise

                # 🔧 修改删除逻辑：删除项目记录但保留content内容，避免用户在不同project上传同一文件的问题
                if other_refs == 0:
                    logger.info(f"文件无其他引用，删除file_contents记录但保留content内容, 哈希: {file_hash}")

                    try:
                        await conn.execute(
                            """
                            DELETE FROM file_contents
                            WHERE file_hash = $1
                            """,
                            file_hash
                        )
                        logger.info(f"已从file_contents表删除记录, 哈希: {file_hash}")
                    except Exception as e:
                        logger.error(f"删除file_contents记录失败: {str(e)}")
                        # 继续尝试删除物理文件，不中断流程

                    # 🔧 修改：从存储系统中删除原始文件，但保留content内容
                    try:
                        # 检查存储类型
                        storage_type = os.getenv('STORAGE_TYPE', 'local')
                        logger.info(f"存储类型: {storage_type}")

                        if storage_type == 's3':
                            # S3/MinIO存储删除逻辑（不删除content目录）
                            await self._delete_files_from_s3_storage_keep_content(conn, file_hash, project_id_value)
                        else:
                            # 本地存储删除逻辑（不删除content目录）
                            await self._delete_files_from_local_storage_keep_content(conn, file_hash, project_id_value)

                        logger.info(f"物理文件删除操作完成（保留content内容）, 哈希: {file_hash}")
                    except Exception as e:
                        logger.error(f"删除物理文件过程中出错: {str(e)}")
                        logger.error(traceback.format_exc())
                        # 数据库记录已删除，即使物理文件删除失败也认为删除成功
                else:
                    logger.info(f"文件仍有其他项目引用({other_refs}个)，保留物理文件, 哈希: {file_hash}")

                logger.info(f"文件删除成功完成, 哈希: {file_hash}, 项目ID: {project_id}")
                return True

        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _delete_files_from_s3_storage(self, conn, file_hash: str, project_id_int: int):
        """从S3/MinIO存储删除文件"""
        try:
            # 获取数据库中的文件信息
            file_record = await conn.fetchrow(
                """
                SELECT name, path, id FROM project_files
                WHERE file_hash = $1 AND project_id = $2
                """,
                file_hash, project_id_int
            )

            # 定义可能的文件路径
            file_paths_to_check = [
                # 基于文件哈希的路径
                f"uploads/{file_hash}",
                f"uploads/{project_id_int}/{file_hash}",
                f"content/{file_hash}.txt",
                f"raw/{file_hash}",
                file_hash
            ]

            if file_record:
                file_name = file_record.get('name')
                file_path = file_record.get('path')
                file_id = file_record.get('id')

                # 添加基于文件名的路径
                if file_name:
                    file_paths_to_check.extend([
                        f"uploads/{file_name}",
                        f"uploads/{project_id_int}/{file_name}",
                        file_name
                    ])

                    # 添加带扩展名的变体
                    name_parts = file_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        base_name, ext = name_parts
                        file_paths_to_check.extend([
                            f"uploads/{file_hash}.{ext}",
                            f"uploads/{project_id_int}/{file_hash}.{ext}"
                        ])

                # 添加基于文件ID的路径
                if file_id:
                    file_paths_to_check.extend([
                        f"uploads/{file_id}",
                        f"uploads/{project_id_int}/{file_id}",
                        str(file_id)
                    ])

                # 添加数据库中的路径
                if file_path:
                    file_paths_to_check.append(file_path)

            # 去重并尝试删除所有可能的路径
            unique_paths = list(set(file_paths_to_check))
            deleted_count = 0

            storage = await self._get_storage("upload")
            for file_path in unique_paths:
                try:
                    result = await storage.delete_file(file_path)
                    if result:
                        deleted_count += 1
                        logger.info(f"成功删除S3文件: {file_path}")
                    else:
                        logger.debug(f"S3文件不存在或删除失败: {file_path}")
                except Exception as e:
                    logger.warning(f"删除S3文件路径失败 {file_path}: {str(e)}")

            logger.info(f"S3文件删除完成，删除了 {deleted_count} 个文件，检查了 {len(unique_paths)} 个路径")

        except Exception as e:
            logger.error(f"S3存储删除过程出错: {str(e)}")
            raise

    async def _delete_files_from_local_storage(self, conn, file_hash: str, project_id_int: int):
        """从本地存储删除文件（保留原有逻辑）"""
        try:
            # 从存储系统中删除实际文件
            file_paths_to_check = [
                f"content/{file_hash}.txt",  # 处理后的文本
                f"raw/{file_hash}",         # 原始文件
                f"raw/{file_hash}.pdf",     # PDF版本
                f"raw/{file_hash}.docx",    # DOCX版本
                f"{file_hash}"              # 直接存储的版本
            ]

            # 初始化变量
            real_file_id = None
            file_path_db = None

            # 添加UUID格式文件到检查列表
            try:
                # 查询表获取真实文件ID
                real_file_id = await conn.fetchval(
                    """
                    SELECT id FROM project_files
                    WHERE file_hash = $1 AND project_id = $2
                    """,
                    file_hash, project_id_int
                )
                if real_file_id:
                    logger.info(f"找到对应的文件ID: {real_file_id}")
                    for ext in ['.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '']:
                        file_paths_to_check.append(f"{real_file_id}{ext}")

                # 获取完整文件路径
                file_path_db = await conn.fetchval(
                    """
                    SELECT path FROM project_files
                    WHERE file_hash = $1 AND project_id = $2
                    """,
                    file_hash, project_id_int
                )
                if file_path_db:
                    logger.info(f"数据库中的文件路径: {file_path_db}")
                    file_paths_to_check.append(file_path_db)

                # 获取文件名
                file_name = await conn.fetchval(
                    """
                    SELECT name FROM project_files
                    WHERE file_hash = $1 AND project_id = $2
                    """,
                    file_hash, project_id_int
                )
                if file_name:
                    logger.info(f"数据库中的文件名: {file_name}")
                    file_paths_to_check.append(file_name)

            except Exception as e:
                logger.warning(f"查询文件ID失败，将尝试直接删除哈希文件: {str(e)}")

            # 获取存储实例用于检查类型
            storage_for_info = await self._get_storage("upload")

            # 打印存储类型和路径
            logger.info(f"存储类型: {type(storage_for_info).__name__}")
            logger.info(f"存储基本路径: {getattr(storage_for_info, 'base_dir', 'N/A')}")

            # 检查直接保存在uploads目录下的文件
            try:
                # 使用glob查找可能的文件
                base_dir = str(getattr(storage_for_info, 'base_dir', './uploads'))
                logger.info(f"尝试在目录中查找文件: {base_dir}")

                # 获取可能匹配的UUID文件标识符
                possible_file_identifiers = []
                if real_file_id:
                    possible_file_identifiers.append(str(real_file_id))

                # 从文件路径中提取的文件名
                if file_path_db and '/' in file_path_db:
                    possible_file_identifiers.append(file_path_db.split('/')[-1])

                # 添加文件名作为标识符
                if file_name:
                    possible_file_identifiers.append(file_name)

                logger.info(f"可能的文件标识符: {possible_file_identifiers}")

                # 确保有可以搜索的标识符
                if not possible_file_identifiers:
                    possible_file_identifiers.append(file_hash)

                # 列出目录中的所有文件，但只处理与当前文件相关的文件
                all_files = os.listdir(base_dir)
                for file_name in all_files:
                    # 只处理与当前要删除的文件相关的文件
                    if any(identifier in file_name for identifier in possible_file_identifiers) or file_hash in file_name:
                        logger.info(f"找到与当前文件相关的文件: {file_name}")
                        file_paths_to_check.append(file_name)

                        # 直接删除匹配到的文件
                        full_path = os.path.join(base_dir, file_name)
                        if os.path.isfile(full_path):
                            logger.info(f"尝试直接删除文件: {full_path}")
                            try:
                                os.remove(full_path)
                                logger.info(f"成功删除文件: {full_path}")
                            except Exception as e:
                                logger.error(f"删除文件失败: {str(e)}")

                # 如果没有找到相关文件，尝试直接删除原始文件名
                if file_name and os.path.exists(os.path.join(base_dir, file_name)):
                    full_path = os.path.join(base_dir, file_name)
                    logger.info(f"尝试直接删除原始文件: {full_path}")
                    try:
                        os.remove(full_path)
                        logger.info(f"成功删除原始文件: {full_path}")
                    except Exception as e:
                        logger.error(f"删除原始文件失败: {str(e)}")

            except Exception as e:
                logger.warning(f"直接查找文件失败: {str(e)}")

            # 获取存储实例
            storage = await self._get_storage("upload")

            # 尝试删除所有可能的文件路径
            for file_path in file_paths_to_check:
                try:
                    exists = await storage.file_exists(file_path)
                    logger.info(f"检查文件是否存在: {file_path}, 结果: {exists}")

                    if exists:
                        result = await storage.delete_file(file_path)
                        logger.info(f"删除文件结果: {result}, 路径: {file_path}")
                    else:
                        logger.warning(f"文件不存在，无法删除: {file_path}")
                except Exception as path_error:
                    # 记录错误，但继续处理其他路径
                    logger.warning(f"删除文件路径失败 {file_path}: {str(path_error)}")

            # 检查文件是否真的被删除
            try:
                remaining_files = 0
                base_dir = str(getattr(storage_for_info, 'base_dir', './uploads'))
                all_files = os.listdir(base_dir)
                for file_name in all_files:
                    if any(identifier in file_name for identifier in possible_file_identifiers) or file_hash in file_name:
                        remaining_files += 1
                        logger.warning(f"文件删除后仍存在: {file_name}")

                if remaining_files == 0:
                    logger.info("所有相关文件均已成功删除")
                else:
                    logger.warning(f"删除操作后仍有{remaining_files}个相关文件存在")
            except Exception as e:
                logger.warning(f"检查剩余文件失败: {str(e)}")

        except Exception as e:
            logger.error(f"本地存储删除过程出错: {str(e)}")
            raise

    async def _delete_files_from_s3_storage_keep_content(self, conn, file_hash: str, project_id_int: str):
        """从S3/MinIO存储删除文件但保留content内容"""
        try:
            # 获取数据库中的文件信息
            file_record = await conn.fetchrow(
                """
                SELECT name, path, id FROM project_files
                WHERE file_hash = $1 AND project_id::text = $2::text
                """,
                file_hash, project_id_int
            )

            # 定义要删除的文件路径（不包含content目录）
            file_paths_to_check = [
                # 基于文件哈希的路径，但排除content目录
                f"uploads/{file_hash}",
                f"uploads/{project_id_int}/{file_hash}",
                f"raw/{file_hash}",
                file_hash
            ]

            if file_record:
                file_name = file_record.get('name')
                file_path = file_record.get('path')
                file_id = file_record.get('id')

                # 添加基于文件名的路径
                if file_name:
                    file_paths_to_check.extend([
                        f"uploads/{file_name}",
                        f"uploads/{project_id_int}/{file_name}",
                        file_name
                    ])

                    # 添加带扩展名的变体
                    name_parts = file_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        base_name, ext = name_parts
                        file_paths_to_check.extend([
                            f"uploads/{file_hash}.{ext}",
                            f"uploads/{project_id_int}/{file_hash}.{ext}"
                        ])

                # 添加基于文件ID的路径
                if file_id:
                    file_paths_to_check.extend([
                        f"uploads/{file_id}",
                        f"uploads/{project_id_int}/{file_id}",
                        str(file_id)
                    ])

                # 添加数据库中的路径（但排除content目录）
                if file_path and not file_path.startswith('content/'):
                    file_paths_to_check.append(file_path)

            # 去重并尝试删除所有可能的路径
            unique_paths = list(set(file_paths_to_check))
            deleted_count = 0

            storage = await self._get_storage("upload")
            for file_path in unique_paths:
                try:
                    result = await storage.delete_file(file_path)
                    if result:
                        deleted_count += 1
                        logger.info(f"成功删除S3文件: {file_path}")
                    else:
                        logger.debug(f"S3文件不存在或删除失败: {file_path}")
                except Exception as e:
                    logger.warning(f"删除S3文件路径失败 {file_path}: {str(e)}")

            logger.info(f"S3文件删除完成（保留content内容），删除了 {deleted_count} 个文件，检查了 {len(unique_paths)} 个路径")

        except Exception as e:
            logger.error(f"S3存储删除过程出错: {str(e)}")
            raise

    async def _delete_files_from_local_storage_keep_content(self, conn, file_hash: str, project_id_int: str):
        """从本地存储删除文件但保留content内容"""
        try:
            # 获取数据库中的文件信息
            file_record = await conn.fetchrow(
                """
                SELECT name, path, id FROM project_files
                WHERE file_hash = $1 AND project_id::text = $2::text
                """,
                file_hash, project_id_int
            )

            # 定义要删除的文件路径（不包含content目录）
            file_paths_to_check = [
                f"raw/{file_hash}",
                f"raw/{file_hash}.pdf",
                f"raw/{file_hash}.docx",
                f"{file_hash}"
            ]

            if file_record:
                file_name = file_record.get('name')
                file_path = file_record.get('path')

                # 添加基于文件名的路径
                if file_name:
                    file_paths_to_check.append(file_name)

                # 添加数据库中的路径（但排除content目录）
                if file_path and not file_path.startswith('content/'):
                    file_paths_to_check.append(file_path)

            # 去重
            unique_paths = list(set(file_paths_to_check))
            deleted_count = 0

            # 从各个存储目录删除文件
            storage_dirs = ["upload", "raw"]

            for storage_dir in storage_dirs:
                try:
                    storage = await self._get_storage(storage_dir)
                    for file_path in unique_paths:
                        try:
                            if await storage.file_exists(file_path):
                                result = await storage.delete_file(file_path)
                                if result:
                                    deleted_count += 1
                                    logger.info(f"成功删除本地文件: {storage_dir}/{file_path}")
                        except Exception as e:
                            logger.warning(f"删除本地文件失败 {storage_dir}/{file_path}: {str(e)}")
                            continue
                except Exception as e:
                    logger.warning(f"获取{storage_dir}存储失败: {str(e)}")
                    continue

            logger.info(f"本地文件删除完成（保留content内容），删除了 {deleted_count} 个文件，检查了 {len(unique_paths)} 个路径")

        except Exception as e:
            logger.error(f"本地存储删除过程出错: {str(e)}")
            raise

    def _generate_file_hash(self, content: bytes) -> str:
        """生成文件内容的哈希值"""
        # 使用SHA-256算法生成完整的文件哈希
        return hashlib.sha256(content).hexdigest()  # 使用完整的SHA-256哈希值

    async def list_files(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取项目文件列表

        Args:
            project_id: 项目ID

        Returns:
            List[Dict[str, Any]]: 文件列表
        """
        try:
            # 查询数据库
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 查询项目文件
                records = await conn.fetch(
                    """
                    SELECT * FROM project_files
                    WHERE project_id::text = $1::text
                    ORDER BY created_at DESC
                    """,
                    project_id
                )

                # 转换为列表
                result = []
                for record in records:
                    # 确保文件名不为空
                    filename = record["name"] or ""
                    if not filename or filename == "undefined" or filename == "null":
                        # 尝试从路径中提取文件名
                        path = record["path"]
                        if path:
                            try:
                                # 从路径中提取文件名
                                path_parts = str(path).split("/")
                                if path_parts and len(path_parts) > 0:
                                    filename = path_parts[-1]
                                else:
                                    filename = f"file_{record['id']}"
                            except Exception as e:
                                logger.warning(f"从路径提取文件名失败: {e}")
                                filename = f"file_{record['id']}"
                        else:
                            # 使用ID作为文件名
                            filename = f"file_{record['id']}"

                    # 记录文件名处理过程
                    logger.info(f"文件名处理: 原始={record['name']}, 处理后={filename}, 路径={record['path']}")

                    file_info = {
                        "file_id": str(record["id"]),
                        "filename": filename,
                        "name": record["name"],  # 保留原始name字段
                        "display_name": filename,  # 添加显示名称字段
                        "path": record["path"],
                        "size": record["size"],
                        "file_type": record["type"],
                        "type": record["type"],  # 确保type字段存在
                        "content_type": record["type"],
                        "created_at": record["created_at"].isoformat() if record["created_at"] else datetime.now().isoformat(),
                        "updated_at": record["updated_at"].isoformat() if record["updated_at"] else datetime.now().isoformat(),
                        "status": record["status"] or "pending",
                        "metadata": record.get("metadata", None),  # 使用get方法避免KeyError
                        "file_hash": record["file_hash"]
                    }
                    result.append(file_info)

                logger.info(f"找到{len(result)}个项目文件")
                return result
        except Exception as e:
            logger.error(f"获取项目文件列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    async def get_file_url(self, file_hash: str, expire: int = 3600) -> str:
        """获取文件的可访问URL"""
        try:
            # 获取content存储实例
            from src.shared.storage.storage_factory import get_storage
            content_storage = await get_storage(directory_type="content")

            # 确定文件路径（在content目录中）
            file_path = f"{file_hash}.txt"

            # 检查文件是否存在
            if not await content_storage.file_exists(file_path):
                raise HTTPException(status_code=404, detail=f"文件 {file_hash} 不存在")

            # 获取URL
            url = content_storage.get_file_url(file_path, expire)
            return url

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取文件URL失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取文件URL失败: {str(e)}")

    async def get_document_content(
        self,
        project_id: str,
        file_hash: str
    ) -> Dict[str, Any]:
        """
        获取文档内容

        Args:
            project_id: 项目ID
            file_hash: 文件哈希值

        Returns:
            Dict[str, Any]: 文档内容
        """
        try:
            db_gen = get_db()
            db = await anext(db_gen)
            try:
                # 尝试将project_id转换为整数，如果是数字字符串的话
                try:
                    if project_id != "global":  # 特殊处理global关键字
                        project_id_value = int(project_id)
                    else:
                        # 如果是global，则直接获取内容，不检查项目关联
                        content = await db.fetchrow(
                            """
                            SELECT * FROM file_contents
                            WHERE file_hash = $1
                            """,
                            file_hash
                        )

                        if not content:
                            return {
                                "success": False,
                                "message": "未找到文件内容",
                                "data": None
                            }

                        return {
                            "success": True,
                            "message": "获取内容成功",
                            "data": dict(content)
                        }
                except ValueError:
                    # 如果无法转换为整数，记录错误但继续使用原始值
                    logger.warning(f"无法将project_id '{project_id}'转换为整数，将使用原始值")
                    project_id_value = project_id

                # 首先检查文件是否属于该项目
                project_file = await db.fetchrow(
                    """
                    SELECT file_hash, path, type, name FROM project_files
                    WHERE project_id = $1 AND file_hash = $2
                    """,
                    project_id_value,
                    file_hash
                )

                if not project_file:
                    return {
                        "success": False,
                        "message": "未找到指定文件",
                        "data": None
                    }

                # 获取文件内容
                content = await db.fetchrow(
                    """
                    SELECT * FROM file_contents
                    WHERE file_hash = $1
                    """,
                    project_file["file_hash"]
                )

                if not content:
                    if is_text_document(project_file["type"], project_file["name"]):
                        upload_storage = await self._get_storage("upload")
                        stored_path = str(project_file["path"] or "")
                        candidates = [stored_path]
                        for marker in ("app/uploads/", "uploads/"):
                            if marker in stored_path:
                                candidates.append(stored_path.split(marker, 1)[1])

                        for candidate in dict.fromkeys(filter(None, candidates)):
                            try:
                                raw_content = await upload_storage.get_file(candidate)
                                if isinstance(raw_content, bytes):
                                    raw_content = raw_content.decode("utf-8", errors="replace")
                                return {
                                    "success": True,
                                    "message": "获取原始文本内容成功",
                                    "content": raw_content,
                                    "data": {
                                        "file_hash": file_hash,
                                        "markdown_content": raw_content,
                                        "source": "upload",
                                    },
                                }
                            except FileNotFoundError:
                                continue

                    return {
                        "success": False,
                        "message": "未找到文件内容",
                        "data": None
                    }

                return {
                    "success": True,
                    "message": "获取内容成功",
                    "content": content["markdown_content"],
                    "data": dict(content)
                }
            finally:
                await db.close()

        except Exception as e:
            logger.error(f"获取文档内容失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"获取文档内容失败: {str(e)}",
                "data": None
            }

    async def register_file_content(self, file_hash: str, markdown_content: str,
                                   metadata: Union[str, Dict[str, Any]], file_type: str,
                                   page_count: int = 1) -> Dict[str, Any]:
        """
        注册文件内容

        将文件的Markdown内容和元数据保存到数据库

        Args:
            file_hash: 文件哈希值
            markdown_content: Markdown内容
            metadata: 文件元数据（可以是JSON字符串或字典）
            file_type: 文件类型
            page_count: 页数

        Returns:
            Dict[str, Any]: 注册结果
        """
        try:
            logger.info(f"注册文件内容: 文件哈希={file_hash}, 内容类型={file_type}, 内容长度={len(markdown_content)}")

            # 处理metadata参数 - 支持JSON字符串或字典
            if isinstance(metadata, str):
                try:
                    # 尝试解析JSON字符串
                    metadata_dict = json.loads(metadata)
                    logger.info(f"成功解析metadata JSON字符串，长度: {len(metadata)}")
                except json.JSONDecodeError as e:
                    logger.error(f"metadata JSON解析失败: {str(e)}")
                    raise ValueError(f"无效的metadata JSON格式: {str(e)}")
            else:
                metadata_dict = metadata

            # 保存到数据库
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 检查是否已存在
                existing = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM file_contents
                    WHERE file_hash = $1
                    """,
                    file_hash
                )

                if existing > 0:
                    # 更新现有内容
                    await conn.execute(
                        """
                        UPDATE file_contents
                        SET markdown_content = $1, metadata = $2, file_type = $3, page_count = $4
                        WHERE file_hash = $5
                        """,
                        markdown_content, json.dumps(metadata_dict), file_type, page_count, file_hash
                    )
                    logger.info(f"已更新文件内容: 文件哈希={file_hash}")
                else:
                    # 创建新内容记录
                    await conn.execute(
                        """
                        INSERT INTO file_contents
                        (file_hash, markdown_content, metadata, file_type, page_count, created_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                        """,
                        file_hash, markdown_content, json.dumps(metadata_dict), file_type, page_count
                    )
                    logger.info(f"已保存新文件内容: 文件哈希={file_hash}")

            return {
                "file_hash": file_hash,
                "content_length": len(markdown_content),
                "file_type": file_type,
                "page_count": page_count
            }
        except Exception as e:
            logger.error(f"注册文件内容失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def update_file_status(self, file_hash: str, project_id: str, status: str) -> Dict[str, Any]:
        """
        更新文件状态

        Args:
            file_hash: 文件哈希值
            project_id: 项目ID
            status: 新状态

        Returns:
            Dict[str, Any]: 更新结果
        """
        try:
            logger.info(f"更新文件状态: 项目ID={project_id}, 文件哈希={file_hash}, 状态={status}")

            # 尝试将project_id转换为整数，如果转换失败则保持原样
            try:
                project_id_int = int(project_id)
            except (ValueError, TypeError):
                logger.warning(f"项目ID不是有效整数: {project_id}，将使用原始值")
                project_id_int = project_id

            # 更新数据库
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 先检查文件是否存在
                file_exists = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM project_files
                    WHERE project_id = $1 AND file_hash = $2
                    """,
                    project_id_int, file_hash
                )

                if file_exists:
                    # 文件存在，进行更新
                    await conn.execute(
                        """
                        UPDATE project_files
                        SET status = $1, processed_at = NOW()
                        WHERE project_id = $2 AND file_hash = $3
                        """,
                        status, project_id_int, file_hash
                    )

                    logger.info(f"文件状态已更新: 项目ID={project_id}, 文件哈希={file_hash}, 状态={status}")
                else:
                    logger.warning(f"找不到要更新的文件: 项目ID={project_id}, 文件哈希={file_hash}")

            return {
                "project_id": project_id,
                "file_hash": file_hash,
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"更新文件状态失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def get_document_summary(self, project_id: str, file_hash: str, regenerate: bool = False) -> Dict[str, Any]:
        """
        获取文档摘要，如果不存在或需要重新生成则调用LLM摘要服务

        Args:
            project_id: 项目ID
            file_hash: 文件哈希值
            regenerate: 是否重新生成摘要

        Returns:
            Dict[str, Any]: 包含摘要的响应
        """
        try:
            # 如果不需要重新生成，则先从数据库获取
            if not regenerate:
                pool = await FileServiceDatabase.get_pool()
                async with pool.acquire() as conn:
                    # 查询文件摘要
                    summary = await conn.fetchval(
                        """
                        SELECT c.summary
                        FROM project_files p
                        JOIN file_contents c ON p.file_hash = c.file_hash
                        WHERE p.project_id = $1 AND p.file_hash = $2
                        """,
                        project_id, file_hash
                    )

                    # 如果已有摘要，直接返回
                    if summary:
                        return {
                            "success": True,
                            "file_hash": file_hash,
                            "project_id": project_id,
                            "summary": summary
                        }

            # 需要生成摘要
            # 先获取文档内容
            content_result = await self.get_document_content(project_id, file_hash)
            if not content_result.get("success", False):
                return {
                    "success": False,
                    "message": f"获取文档内容失败: {content_result.get('message', '未知错误')}"
                }

            # 通过服务发现调用fileproc服务生成摘要
            summary_result = await call_service(
                service_name="fileproc",
                endpoint="summary/generate",
                method="POST",
                data={
                    "content": content_result.get("markdown_content", ""),
                    "project_id": project_id,
                    "file_hash": file_hash
                }
            )

            # 检查摘要结果
            if not summary_result or not summary_result.get("success", False):
                return {
                    "success": False,
                    "message": f"生成摘要失败: {summary_result.get('error', '未知错误')}"
                }

            # 获取摘要文本
            summary_text = summary_result.get("summary", "")

            # 更新数据库中的摘要
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE file_contents
                    SET summary = $1
                    WHERE file_hash = $2
                    """,
                    summary_text, file_hash
                )

            return {
                "success": True,
                "file_hash": file_hash,
                "project_id": project_id,
                "summary": summary_text
            }

        except Exception as e:
            logger.error(f"获取文档摘要失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取文档摘要失败: {str(e)}"
            }

    async def list_project_files(self, project_id: str) -> List[Dict[str, Any]]:
        """列出项目文件"""
        try:
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 使用当前数据库实际表结构进行查询
                records = await conn.fetch(
                    """
                    SELECT id, file_hash, name, path, size, type, file_metadata,
                           created_at, updated_at, status
                    FROM project_files
                    WHERE project_id::text = $1::text
                    ORDER BY created_at DESC
                    """,
                    project_id
                )

                # 处理结果
                result = []
                for record in records:
                    file_info = {
                        "file_id": str(record["id"]),  # 确保file_id为字符串类型
                        "filename": record["name"],
                        "path": record["path"],
                        "size": record["size"],
                        "file_type": record["type"],
                        "content_type": record["type"] or "application/octet-stream",  # 添加content_type字段
                        "created_at": str(record["created_at"]),
                        "updated_at": str(record["updated_at"]),
                        "status": record["status"] or "pending",  # 添加状态字段
                        "metadata": record["file_metadata"],
                        "file_hash": record["file_hash"]
                    }
                    result.append(file_info)
                return result
        except Exception as e:
            logger.error(f"列出项目文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    async def batch_delete_files(self, project_id: str, file_hashes: List[str]) -> Dict[str, Any]:
        """
        批量删除文件

        Args:
            project_id: 项目ID
            file_hashes: 文件哈希列表

        Returns:
            Dict[str, Any]: 删除结果
        """
        try:
            # 确保project_id是整数
            try:
                project_id_int = int(project_id)
                logger.info(f"批量删除 - 项目ID转换为整数: {project_id_int}")
            except ValueError:
                logger.error(f"批量删除 - 项目ID格式错误，无法转换为整数: {project_id}")
                return {
                    "success": False,
                    "message": f"项目ID格式错误: {project_id}",
                    "deleted": [],
                    "failed": file_hashes
                }

            # 记录成功和失败的删除操作
            successful = []
            failed = []

            # 逐个删除文件
            for file_hash in file_hashes:
                try:
                    logger.info(f"批量删除 - 开始处理文件: {file_hash}")
                    result = await self.delete_file(file_hash, project_id)

                    if result:
                        successful.append(file_hash)
                        logger.info(f"批量删除 - 成功删除文件: {file_hash}")
                    else:
                        failed.append(file_hash)
                        logger.warning(f"批量删除 - 删除文件失败: {file_hash}")
                except Exception as e:
                    logger.error(f"批量删除 - 处理文件时出错: {file_hash}, 错误: {str(e)}")
                    failed.append(file_hash)

            # 返回结果
            return {
                "success": len(successful) > 0,
                "message": f"成功删除{len(successful)}个文件，{len(failed)}个文件删除失败",
                "deleted": successful,
                "failed": failed
            }

        except Exception as e:
            logger.error(f"批量删除文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"批量删除文件失败: {str(e)}",
                "deleted": [],
                "failed": file_hashes
            }

    async def list_pending_files(self) -> List[Dict[str, Any]]:
        """
        获取所有待处理状态的文件列表

        Returns:
            List[Dict[str, Any]]: 待处理文件列表
        """
        try:
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                # 查询所有待处理状态的文件
                records = await conn.fetch(
                    """
                    SELECT id, file_hash, name, path, size, type, file_metadata,
                           created_at, updated_at, status, project_id
                    FROM project_files
                    WHERE status = 'pending' OR status = 'uploaded'
                    ORDER BY created_at DESC
                    """
                )

                # 处理结果
                result = []
                for record in records:
                    file_info = {
                        "file_id": str(record["id"]),  # 确保file_id为字符串类型
                        "file_hash": record["file_hash"],
                        "filename": record["name"],
                        "path": record["path"],
                        "size": record["size"],
                        "file_type": record["type"],
                        "content_type": record["type"] or "application/octet-stream",
                        "created_at": str(record["created_at"]),
                        "updated_at": str(record["updated_at"]),
                        "status": record["status"],
                        "project_id": str(record["project_id"])  # 确保project_id为字符串类型
                    }
                    result.append(file_info)

                logger.info(f"找到{len(result)}个待处理文件")
                return result
        except Exception as e:
            logger.error(f"获取待处理文件列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    async def register_content(
        self,
        file_hash: str,
        markdown_content: str,
        metadata: Dict[str, Any],
        file_type: str,
        page_count: int = 1
    ) -> ApiResponse:
        """
        注册文件内容

        Args:
            file_hash: 文件哈希值
            markdown_content: Markdown内容
            metadata: 元数据
            file_type: 文件类型
            page_count: 页数

        Returns:
            ApiResponse: API响应
        """
        try:
            db_gen = get_db()
            db = await anext(db_gen)
            try:
                # 检查内容是否已存在
                existing = await db.fetchrow(
                    """
                    SELECT file_hash FROM file_contents
                    WHERE file_hash = $1
                    """,
                    file_hash
                )

                if existing:
                    return ApiResponse(
                        success=True,
                        message="内容已存在",
                        data={"file_hash": file_hash}
                    )

                # 插入新内容
                await db.execute(
                    """
                    INSERT INTO file_contents (
                        file_hash, markdown_content, metadata,
                        file_type, page_count
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    file_hash,
                    markdown_content,
                    metadata,
                    file_type,
                    page_count
                )

                logger.info(f"已注册新的文件内容: {file_hash}")
                return ApiResponse(
                    success=True,
                    message="内容注册成功",
                    data={"file_hash": file_hash}
                )
            finally:
                await db.close()

        except Exception as e:
            logger.error(f"注册文件内容时发生错误: {str(e)}")
            logger.error(traceback.format_exc())
            return ApiResponse(
                success=False,
                message="注册文件内容失败",
                error=str(e)
            )

    async def get_content_by_hash(self, file_hash: str) -> Dict[str, Any]:
        """
        通过哈希值获取文件内容

        Args:
            file_hash: 文件哈希值

        Returns:
            Dict[str, Any]: 文件内容
        """
        try:
            # 首先从数据库检查文件是否存在
            pool = await FileServiceDatabase.get_pool()
            async with pool.acquire() as conn:
                record = await conn.fetchrow(
                    """
                    SELECT markdown_content FROM file_contents
                    WHERE file_hash = $1
                    """,
                    file_hash
                )

                if record and record["markdown_content"]:
                    # 文件内容存在于数据库中，直接返回
                    logger.info(f"从数据库获取到文件内容: {file_hash}")
                    return {
                        "success": True,
                        "content": record["markdown_content"],
                        "file_hash": file_hash
                    }

            # 如果数据库中没有，尝试从content目录获取
            content_dir = os.environ.get("CONTENT_DIR", "./content")
            content_file_path = os.path.join(content_dir, f"{file_hash}.txt")

            if os.path.exists(content_file_path):
                try:
                    # 从content目录读取
                    async with aiofiles.open(content_file_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        logger.info(f"从content目录读取文件内容: {content_file_path}")
                        return {
                            "success": True,
                            "content": content,
                            "file_hash": file_hash
                        }
                except Exception as e:
                    logger.error(f"从content目录读取文件失败: {str(e)}")

            # 如果content目录没有，尝试从存储系统获取
            file_path = f"content/{file_hash}.txt"
            if await self.storage.file_exists(file_path):
                try:
                    content = await self.storage.get_file_content(file_path)
                    logger.info(f"从存储系统获取文件内容: {file_path}")
                    return {
                        "success": True,
                        "content": content,
                        "file_hash": file_hash
                    }
                except Exception as e:
                    logger.error(f"从存储系统获取文件内容失败: {str(e)}")

            # 如果都没有找到，返回友好的错误信息
            logger.warning(f"未找到文件内容: {file_hash}")
            return {
                "success": False,
                "message": f"未找到文件内容: {file_hash}",
                "error": "文件内容不存在或尚未处理完成",
                "file_hash": file_hash
            }
        except Exception as e:
            logger.error(f"获取文件内容失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"获取文件内容失败: {str(e)}",
                "error": str(e),
                "file_hash": file_hash
            }
