#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务服务 - 处理文件处理任务的提交、状态跟踪和结果获取
遵循STP微服务架构原则，使用服务发现和消息队列
"""

import os
import uuid
import logging
import asyncio
import json
import traceback
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from ..config import settings
from src.shared.service_discovery import ServiceClient, call_service
from .queue_service import file_processing_queue
from src.shared.logger import get_logger

# 使用共享日志记录器
logger = get_logger(__name__)

class TaskService:
    """任务服务，负责任务提交、状态查询和结果获取"""
    
    def __init__(self):
        """初始化任务服务"""
        self.redis_client = None
        self.service_client = None
        self._initialized = False
        self.queue = file_processing_queue  # 直接在初始化时设置
        logger.info("任务服务实例已创建")
    
    async def check_redis_health(self) -> bool:
        """
        检查Redis连接健康状态
        
        Returns:
            bool: Redis是否健康
        """
        try:
            redis_client = await self._get_redis_client()
            if redis_client:
                await redis_client.ping()
                return True
            return False
        except Exception as e:
            logger.error(f"Redis健康检查失败: {str(e)}")
            return False
    
    async def check_summary_service_health(self) -> bool:
        """
        检查摘要服务健康状态
        
        Returns:
            bool: 摘要服务是否健康
        """
        try:
            # 通过服务发现调用摘要服务健康检查
            result = await call_service("llm_summary", "/api/health")
            return result.get("status") == "healthy"
        except Exception as e:
            logger.error(f"摘要服务健康检查失败: {str(e)}")
            return False
    
    async def _get_redis_client(self):
        """获取Redis客户端实例"""
        try:
            # 确保队列连接可用
            if not file_processing_queue._redis:
                logger.info("尝试连接Redis...")
                # 添加重试逻辑
                max_retries = 5
                retry_count = 0
                connected = False
                
                while retry_count < max_retries and not connected:
                    try:
                        await file_processing_queue.connect()
                        connected = True
                        logger.info("Redis连接成功")
                    except Exception as e:
                        retry_count += 1
                        wait_time = min(2 ** retry_count, 30)  # 指数退避策略
                        logger.warning(f"连接Redis失败(第{retry_count}次尝试): {str(e)}, {wait_time}秒后重试")
                        await asyncio.sleep(wait_time)
                
                if not connected:
                    logger.error("连接Redis失败，达到最大重试次数")
                    raise Exception("无法连接到Redis服务")
                
            return file_processing_queue._redis
        except Exception as e:
            logger.error(f"获取Redis客户端失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    async def _get_service_client(self) -> ServiceClient:
        """获取服务发现客户端"""
        if not self.service_client:
            try:
                logger.info("初始化服务发现客户端...")
                # 添加重试逻辑
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        self.service_client = await ServiceClient.get_instance()
                        logger.info("服务发现客户端初始化成功")
                        break
                    except Exception as e:
                        retry_count += 1
                        wait_time = min(2 ** retry_count, 20)  # 指数退避策略
                        logger.warning(f"初始化服务发现客户端失败(第{retry_count}次尝试): {str(e)}, {wait_time}秒后重试")
                        await asyncio.sleep(wait_time)
                
                if not self.service_client:
                    logger.error("初始化服务发现客户端失败，达到最大重试次数")
                    raise Exception("无法初始化服务发现客户端")
            except Exception as e:
                logger.error(f"初始化服务发现客户端失败: {str(e)}")
                logger.error(traceback.format_exc())
                raise
        
        return self.service_client
    
    async def submit_task(self, file_id: str, project_id: str) -> Dict[str, Any]:
        """
        提交文件处理任务
        
        Args:
            file_id: 文件ID
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 任务信息
        """
        logger.info(f"提交文件处理任务: file_id={file_id}, project_id={project_id}")
        
        try:
            # 获取文件信息
            file_info = await self._get_file_info(file_id, project_id)
            
            if not file_info or not file_info.get("success", False):
                logger.error(f"获取文件信息失败: {file_info}")
                return {"success": False, "message": "获取文件信息失败"}
                
            file_data = file_info.get("data", {})
            file_hash = file_data.get("file_hash")
            file_path = file_data.get("path")
            
            if not file_hash:
                logger.error(f"文件哈希为空: {file_info}")
                return {"success": False, "message": "文件哈希为空"}
                
            # 创建任务
            task_id = f"task-{uuid.uuid4().hex}"
            task_data = {
                "task_id": task_id,
                "status": "queued",
                "file_id": file_id,
                "project_id": project_id,
                "file_hash": file_hash,
                "file_path": file_path,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # 1. 保存任务到Redis
            status_set = await self.queue.set_task_data(task_id, task_data)
            if not status_set:
                logger.error(f"设置任务数据失败: {task_id}")
                return {"success": False, "message": "设置任务数据失败"}
                
            # 2. 将任务放入处理队列
            enqueue_success = await self.queue.enqueue_task(task_id)
            if not enqueue_success:
                logger.error(f"将任务加入处理队列失败: {task_id}")
                return {"success": False, "message": "将任务加入处理队列失败"}
            
            logger.info(f"任务已成功创建并加入处理队列: {task_id}")
            
            return {
                "success": True,
                "task_id": task_id,
                "status": "queued",
                "file_id": file_id,
                "project_id": project_id,
                "message": "任务已提交"
            }
        except Exception as e:
            logger.error(f"提交任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"提交任务失败: {str(e)}"}
            
    async def _get_file_info(self, file_id: str, project_id: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            file_id: 文件ID
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 文件信息
        """
        try:
            # 通过服务发现调用file服务
            result = await call_service(
                service_name="file", 
                endpoint=f"api/file/info/{project_id}/{file_id}",  # 修正API路径格式
                method="GET",
                timeout=10.0,
                use_service_auth=True  # 添加服务间认证
            )
            
            if not result:
                logger.warning(f"获取文件信息失败: 空响应")
                return {"success": False, "message": "获取文件信息失败: 空响应"}
                
            # 检查结果中是否有file_hash字段
            if "file_hash" not in result:
                logger.warning(f"获取文件信息成功，但缺少file_hash字段: {result}")
                return {"success": False, "message": "获取文件信息成功，但缺少file_hash字段"}
                
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"获取文件信息失败: {str(e)}")
            return {"success": False, "message": f"获取文件信息失败: {str(e)}"}
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态
        """
        try:
            # 确保服务已初始化
            if not self._initialized:
                await self.initialize()
                
            # 从队列服务获取任务状态
            status = await self.queue.get_task_status(task_id)
            
            # 记录获取到的状态
            logger.info(f"从队列获取到任务状态: {task_id} -> {status}")
            
            # 如果没有获取到状态，返回默认状态
            if not status:
                # 尝试从结果中获取
                result = await self.queue.get_task_result(task_id)
                if result:
                    # 如果有结果，表示任务已完成
                    success = result.get("success", False)
                    if success:
                        return {
                            "status": "completed",
                            "progress": 100,
                            "message": "处理完成",
                            "task_id": task_id
                        }
                    else:
                        # 任务失败
                        return {
                            "status": "failed",
                            "progress": 100,
                            "message": result.get("message", "处理失败"),
                            "error": result.get("error", "未知错误"),
                            "task_id": task_id
                        }
                
                # 没有状态也没有结果，可能任务不存在
                return {
                    "status": "failed",
                    "progress": 100,
                    "message": "任务处理失败，请检查文件格式或重新上传",
                    "task_id": task_id
                }
            
            # 确保返回的状态包含必要的字段
            if "status" not in status:
                status["status"] = "unknown"
            if "progress" not in status:
                status["progress"] = 0
            if "message" not in status:
                status["message"] = "未知状态"
                
            # 添加任务ID
            status["task_id"] = task_id
            
            return status
        except Exception as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            return {
                "status": "error",
                "progress": 0,
                "message": f"获取状态失败: {str(e)}",
                "task_id": task_id
            }
    
    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务结果，包含处理时间信息
        """
        try:
            # 从队列服务获取任务结果
            # 添加重试逻辑
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries and result is None:
                try:
                    result = await file_processing_queue.get_task_result(task_id)
                except Exception as e:
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 10)  # 指数退避策略
                    logger.warning(f"获取任务结果失败(第{retry_count}次尝试): {str(e)}, {wait_time}秒后重试")
                    if retry_count < max_retries:
                        await asyncio.sleep(wait_time)
            
            if result is None:
                logger.error(f"获取任务结果失败，达到最大重试次数: {task_id}")
                return {
                    "success": False,
                    "message": "获取任务结果失败，请稍后重试"
                }
            
            return {
                "success": True,
                "task_id": task_id,
                "result": result
            }
        except Exception as e:
            logger.error(f"获取任务结果失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"获取任务结果失败: {str(e)}"
            }
    
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 取消结果
        """
        try:
            # 尝试取消任务
            # 添加重试逻辑
            max_retries = 2
            retry_count = 0
            cancelled = False
            
            while retry_count < max_retries and not cancelled:
                try:
                    cancelled = await file_processing_queue.cancel_task(task_id)
                    if cancelled:
                        break
                except Exception as e:
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 10)  # 指数退避策略
                    logger.warning(f"取消任务失败(第{retry_count}次尝试): {str(e)}, {wait_time}秒后重试")
                    if retry_count < max_retries:
                        await asyncio.sleep(wait_time)
            
            if cancelled:
                return {
                    "success": True,
                    "task_id": task_id,
                    "message": "任务已取消"
                }
            else:
                return {
                    "success": False,
                    "task_id": task_id,
                    "message": "无法取消任务，可能任务已完成或不存在"
                }
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "task_id": task_id,
                "message": f"取消任务失败: {str(e)}"
            }
    
    async def initialize(self) -> bool:
        """
        初始化任务服务
        
        Returns:
            bool: 是否初始化成功
        """
        logger.info("初始化任务服务")
        try:
            if self._initialized:
                logger.info("任务服务已初始化")
                return True
            
            # 初始化服务客户端
            try:
                from src.shared.service_discovery import ServiceClient
                self.service_client = await ServiceClient.get_instance()
                logger.info("服务客户端初始化成功")
            except Exception as e:
                logger.error(f"初始化服务客户端失败: {str(e)}")
                return False
            
            # 初始化Redis队列连接
            try:
                from .queue_service import file_processing_queue
                self.queue = file_processing_queue
                
                # 确保队列初始化
                queue_initialized = await self.queue.initialize()
                if not queue_initialized:
                    logger.error("无法初始化队列")
                    return False
                    
                logger.info("任务队列已连接")
                
                # 启动队列工作器，处理文件任务
                from .file_processor import file_processor
                
                # 确保处理器已初始化
                processor_initialized = await file_processor.initialize()
                if not processor_initialized:
                    logger.error("无法初始化文件处理器")
                    return False
                
                # 设置环境变量标识服务名称
                import os
                os.environ["SERVICE_NAME"] = "fileproc"
                
                # 启动队列工作器
                await self.queue.start_worker(file_processor.process_file)
                logger.info("任务队列工作者已启动")
                
            except Exception as e:
                logger.error(f"初始化Redis队列失败: {str(e)}")
                logger.error(traceback.format_exc())
                return False
            
            # 处理待处理文件
            try:
                pending_files_processed = await self._process_pending_files()
                logger.info(f"已处理{pending_files_processed}个待处理文件")
            except Exception as e:
                logger.error(f"处理待处理文件失败: {str(e)}")
            
            self._initialized = True
            logger.info("任务服务初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化任务服务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def _process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理任务的回调函数
        
        Args:
            task_data: 任务数据
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        task_id = task_data.get("task_id")
        logger.info(f"开始处理任务: {task_id}")
        
        try:
            # 更新任务状态为处理中
            await self.queue.update_task_status(
                task_id=task_id,
                status="processing",
                progress=10,
                message="正在处理"
            )
            
            # 获取任务数据
            file_id = task_data.get("file_id")
            project_id = task_data.get("project_id")
            file_hash = task_data.get("file_hash")
            file_path = task_data.get("file_path")
            
            if not all([file_id, project_id]):
                raise ValueError("任务数据不完整")
            
            # 调用文件处理服务
            result = await call_service(
                service_name="fileproc",
                endpoint=f"api/process/{file_id}",
                method="POST",
                json_data={
                    "file_id": file_id,
                    "project_id": project_id,
                    "file_hash": file_hash,
                    "file_path": file_path
                },
                use_service_auth=True
            )
            
            if not result or not result.get("success", False):
                raise Exception(f"文件处理失败: {result.get('message', '未知错误')}")
            
            # 更新任务状态为完成
            await self.queue.update_task_status(
                task_id=task_id,
                status="completed",
                progress=100,
                message="处理完成",
                result=result
            )
            
            logger.info(f"任务处理完成: {task_id}")
            return {
                "success": True,
                "task_id": task_id,
                "message": "处理完成",
                "result": result
            }
        except Exception as e:
            logger.error(f"任务处理失败: {str(e)}")
            logger.error(traceback.format_exc())
            
            # 更新任务状态为失败
            await self.queue.update_task_status(
                task_id=task_id,
                status="failed",
                progress=0,
                message=f"处理失败: {str(e)}"
            )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }
    
    async def _process_pending_files(self) -> int:
        """
        处理所有待处理的文件
        
        Returns:
            int: 处理的文件数量
        """
        try:
            # 获取DB连接池
            db_pool = await self._get_db_pool()
            if not db_pool:
                logger.error("无法获取数据库连接池")
                return 0
            
            # 获取队列统计信息
            queue_stats = await self.queue.get_queue_stats()
            pending_count = queue_stats.get("pending_count", 0)
            
            # 获取待处理任务列表
            pending_tasks = await self.queue.get_pending_tasks()
            
            processed_count = 0
            if pending_tasks:
                logger.info(f"发现{len(pending_tasks)}个待处理任务，开始处理")
                
                for task in pending_tasks:
                    task_id = task.get("task_id")
                    if not task_id:
                        logger.warning(f"任务缺少task_id字段: {task}")
                        continue
                    
                    # 将任务放入处理队列
                    await self.queue.enqueue_task(task_id)
                    processed_count += 1
                    
                logger.info(f"成功将{processed_count}个待处理任务加入处理队列")
            else:
                logger.info("没有待处理任务")
                
            return processed_count
        except Exception as e:
            logger.error(f"处理待处理文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return 0
            
    async def _get_db_pool(self):
        """获取数据库连接池"""
        try:
            from src.shared.database import get_db_pool
            return await get_db_pool()
        except Exception as e:
            logger.error(f"获取数据库连接池失败: {str(e)}")
            return None
    
    async def shutdown(self) -> bool:
        """关闭任务服务"""
        try:
            logger.info("正在关闭任务服务")
            if self.queue:
                # 停止队列工作者
                await self.queue.stop_worker()
                logger.info("任务队列工作者已停止")
                
                # 关闭队列连接
                await self.queue.close()
                logger.info("任务队列连接已关闭")
            
            self._initialized = False
            logger.info("任务服务已关闭")
            return True
        except Exception as e:
            logger.error(f"关闭任务服务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def submit_task_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交文件处理任务数据
        
        Args:
            task_data: 任务数据，包含任务ID、文件ID、文件路径等
        
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            if not self._initialized:
                await self.initialize()
                
            task_id = task_data.get("task_id")
            if not task_id:
                task_id = f"task-{str(uuid.uuid4()).replace('-', '')}"
                task_data["task_id"] = task_id
                
            logger.info(f"提交文件处理任务: {task_id}")
            
            # 1. 使用队列的set_task_data方法设置任务数据
            status_set = await self.queue.set_task_data(task_id, task_data)
            if not status_set:
                logger.error(f"设置任务数据失败: {task_id}")
                return {"success": False, "message": "设置任务数据失败"}
                
            # 2. 必须显式将任务ID加入处理队列
            enqueue_success = await self.queue.enqueue_task(task_id)
            if not enqueue_success:
                logger.error(f"将任务加入处理队列失败: {task_id}")
                return {"success": False, "message": "将任务加入处理队列失败"}
            
            logger.info(f"任务已成功加入处理队列: {task_id}")
            
            # 3. 更新任务数据，确保包含必要字段
            file_id = task_data.get("file_id")
            project_id = task_data.get("project_id")
            
            # 记录任务已提交
            return {
                "success": True,
                "message": "文件处理任务已提交", 
                "task_id": task_id,
                "status": "pending",
                "file_id": file_id,
                "project_id": project_id
            }
        except Exception as e:
            logger.error(f"处理任务数据失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"处理任务数据失败: {str(e)}"}

# 创建全局实例供其他模块使用
task_service = TaskService() 