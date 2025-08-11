#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理队列服务
基于Redis实现的异步消息队列，用于文件处理任务
遵循STP微服务架构原则，支持分布式环境
"""

import json
import uuid
import time
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Callable, Awaitable
import redis.asyncio as aioredis
from datetime import datetime, timedelta

from ..config import settings
from src.shared.logger import get_logger

# 使用共享日志记录器
logger = get_logger(__name__)

class FileProcessingQueue:
    """
    基于Redis的文件处理队列
    支持任务发布、订阅、状态更新等功能
    适用于分布式环境的多实例部署
    """
    
    def __init__(self):
        """初始化队列服务"""
        self._redis = None
        self._queue_name = "file_processing_queue"
        self._pending_queue_key = f"{self._queue_name}:pending"
        self._processing_queue_key = f"{self._queue_name}:processing"
        self._completed_queue_key = f"{self._queue_name}:completed"
        self._failed_queue_key = f"{self._queue_name}:failed"
        self._status_prefix = "file_processing_status:"
        self._result_prefix = "file_processing_result:"
        self._task_ttl = 86400  # 默认任务状态保留一天
        self._worker_id = str(uuid.uuid4())[:8]
        self._running = False
        self._processing_tasks = set()
        self._connection_retries = 0
        self._max_connection_retries = 5
        self._connection_lock = asyncio.Lock()  # 添加锁以防止并发连接
        # 创建事件循环用于连接初始化
        self._initialized = False
        self._init_task = None
        logger.info(f"文件处理队列实例已创建，工作器ID: {self._worker_id}")
    
    def is_connected(self) -> bool:
        """
        检查Redis连接是否已建立
        
        Returns:
            bool: 连接是否已建立
        """
        return self._redis is not None
    
    async def connect(self) -> bool:
        """
        连接到Redis服务器
        
        Returns:
            bool: 是否连接成功
        """
        # 使用锁防止并发连接
        async with self._connection_lock:
            # 如果已连接，直接返回
            if self._redis:
                try:
                    # 检查连接是否有效
                    await self._redis.ping()
                    return True
                except Exception:
                    # 连接可能已断开，关闭并重新连接
                    logger.warning("Redis连接可能已断开，尝试重新连接")
                    try:
                        self._redis.close()
                        await self._redis.wait_closed()
                    except Exception:
                        pass
                    self._redis = None
            
            # 尝试连接Redis
            try:
                # 获取Redis连接URL
                redis_url = settings.get_redis_url()
                logger.info(f"正在连接到Redis: {redis_url}")
                
                # 连接Redis - 增加连接选项以提高可靠性
                self._redis = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=10,  # 增加连接超时时间
                    socket_keepalive=True,
                    retry_on_timeout=True,
                    health_check_interval=30  # 启用健康检查
                )
                
                # 测试连接
                await self._redis.ping()
                logger.info("已成功连接到Redis服务器")
                
                # 重置重试计数
                self._connection_retries = 0
                return True
            except Exception as e:
                # 如果连接失败，增加重试计数
                self._connection_retries += 1
                retry_delay = min(2 ** self._connection_retries, 30)  # 指数退避策略，最长30秒
                
                if self._connection_retries < self._max_connection_retries:
                    logger.warning(f"连接到Redis失败(第{self._connection_retries}次尝试): {str(e)}, {retry_delay}秒后重试")
                    await asyncio.sleep(retry_delay)
                    return await self.connect()  # 递归重试
                else:
                    logger.error(f"连接到Redis失败，已达到最大重试次数: {str(e)}")
                    logger.error(traceback.format_exc())
                    self._redis = None
                    return False
    
    async def close(self):
        """关闭Redis连接"""
        if self._redis:
            try:
                # 停止工作器
                if self._running:
                    await self.stop_worker()
                
                # 关闭Redis连接 - 正确处理异步关闭
                try:
                    # 对于新版aioredis (redis-py)，需要使用await close()
                    await self._redis.close()
                    logger.info("Redis连接已关闭")
                except AttributeError:
                    # 对于旧版aioredis，使用close()并等待
                    self._redis.close()
                    if hasattr(self._redis, 'wait_closed'):
                        await self._redis.wait_closed()
                    logger.info("Redis连接已关闭（旧版API）")
                except Exception as e:
                    logger.warning(f"关闭Redis连接时的非严重错误: {str(e)}")
                
                self._redis = None
            except Exception as e:
                logger.error(f"关闭Redis连接时出错: {str(e)}")
                logger.error(traceback.format_exc())
    
    async def _ensure_connection(self) -> bool:
        """
        确保Redis连接可用
        
        Returns:
            bool: 连接是否可用
        """
        if not self._redis:
            return await self.connect()
        
        # 检查连接是否仍然有效
        try:
            await self._redis.ping()
            return True
        except Exception:
            logger.warning("Redis连接已断开，尝试重新连接")
            self._redis = None
            return await self.connect()
    
    async def enqueue(self, payload: Dict[str, Any]) -> Optional[str]:
        """
        将任务添加到队列
        
        Args:
            payload: 任务数据载荷
            
        Returns:
            str: 任务ID，失败则返回None
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，任务入队失败")
                return None
            
            # 生成任务ID
            task_id = payload.get("task_id", str(uuid.uuid4()))
            
            # 创建任务数据
            task = {
                "task_id": task_id,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
                "progress": 0,
                "payload": payload
            }
            
            # 将任务添加到队列
            task_json = json.dumps(task)
            await self._redis.lpush(self._queue_name, task_json)
            
            # 保存任务状态
            await self._save_task_status(task_id, task)
            
            logger.info(f"任务已添加到队列: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"添加任务到队列失败: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        从队列获取待处理任务（带分布式锁）
        
        Returns:
            Dict[str, Any]: 任务数据，队列为空则返回None
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，任务出队失败")
                return None
            
            # 从队列右侧获取任务（先进先出）
            task_data = await self._redis.rpop(self._queue_name)
            if not task_data:
                return None
            
            # 尝试解析任务数据
            try:
                # 先尝试解析为JSON
                try:
                    task = json.loads(task_data)
                    task_id = task.get("task_id")
                    logger.info(f"从队列获取到任务数据: {task_id}")
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON，可能只是任务ID字符串
                    task_id = task_data.decode("utf-8") if isinstance(task_data, bytes) else task_data
                    logger.info(f"从队列获取到任务ID: {task_id}")
                    
                    # 根据任务ID获取任务详情
                    task = await self.get_task_status(task_id)
                
                # 如果没有获取到任务详情，则返回基本任务信息
                if not task:
                    task = {
                        "task_id": task_id,
                        "status": "unknown"
                    }
                
                # 尝试获取任务锁，防止重复处理
                lock_key = f"lock:{task_id}"
                lock_acquired = await self._redis.set(
                    lock_key, 
                    self._worker_id, 
                    nx=True,  # 只有key不存在时才设置
                    ex=3600   # 1小时过期时间
                )
                
                if not lock_acquired:
                    # 锁获取失败，说明任务正在被其他工作器处理
                    logger.warning(f"任务 {task_id} 正在被其他工作器处理，跳过")
                    return None
                
                # 将任务标记为处理中
                await self.update_task_status(
                    task_id=task_id,
                    status="processing",
                    message="处理中"
                )
                
                return task
            except Exception as e:
                logger.error(f"解析任务数据失败: {str(e)}")
                logger.error(traceback.format_exc())
                return None
        except Exception as e:
            logger.error(f"从队列获取任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    async def update_task_status(self, task_id: str, status: str, progress: int = None, message: str = None, 
                                processing_time_seconds: float = None, processing_time_display: str = None, 
                                result: dict = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 处理进度（可选）
            message: 状态消息（可选）
            processing_time_seconds: 处理时间（秒）
            processing_time_display: 处理时间显示
            result: 任务结果（可选）
            
        Returns:
            bool: 是否成功更新
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，更新任务状态失败")
                return False
                
            # 获取当前任务状态
            current_status = await self.get_task_status(task_id)
            if not current_status:
                logger.warning(f"无法更新不存在的任务状态: {task_id}")
                return False
                
            # 更新任务状态
            current_status["status"] = status
            current_status["updated_at"] = datetime.now().isoformat()
            
            if progress is not None:
                current_status["progress"] = progress
                
            if message is not None:
                current_status["message"] = message
                
            # 添加处理时间信息
            if processing_time_seconds is not None:
                current_status["processing_time_seconds"] = processing_time_seconds
                
            if processing_time_display is not None:
                current_status["processing_time_display"] = processing_time_display
                
            # 添加任务结果
            if result is not None:
                current_status["result"] = result
                
            # 如果任务完成或失败，记录结束时间
            if status in ["completed", "failed"]:
                current_status["finished_at"] = datetime.now().isoformat()
                
                # 计算处理时间（如果没有传入处理时间参数）
                if "started_at" in current_status and processing_time_seconds is None:
                    try:
                        started = datetime.fromisoformat(current_status["started_at"])
                        finished = datetime.fromisoformat(current_status["finished_at"])
                        processing_time = (finished - started).total_seconds()
                        current_status["processing_time_seconds"] = processing_time
                        current_status["processing_time_display"] = f"{processing_time:.2f}秒"
                    except Exception as e:
                        logger.warning(f"计算处理时间失败: {str(e)}")
                
            # 保存更新后的任务状态
            await self._save_task_status(task_id, current_status)
            
            logger.info(f"已更新任务状态: {task_id} -> {status}")
            return True
        except Exception as e:
            logger.error(f"更新任务状态失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态信息，不存在则返回None
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，获取任务状态失败")
                return None
                
            # 从Redis获取任务状态
            status_key = f"{self._status_prefix}{task_id}"
            status_json = await self._redis.get(status_key)
            
            if not status_json:
                # 检查任务是否在结果中
                result_key = f"{self._result_prefix}{task_id}"
                result_exists = await self._redis.exists(result_key)
                
                if result_exists:
                    # 如果有结果但没有状态，可能是任务已完成但状态已过期
                    # 尝试获取结果判断成功或失败
                    result_data = await self._redis.get(result_key)
                    if result_data:
                        try:
                            result = json.loads(result_data)
                            success = result.get("success", False)
                            
                            if success:
                                return {
                                    "status": "completed",
                                    "progress": 100,
                                    "message": "处理完成",
                                    "updated_at": datetime.now().isoformat()
                                }
                            else:
                                return {
                                    "status": "failed",
                                    "progress": 100,
                                    "message": result.get("message", "处理失败"),
                                    "error": result.get("error", "未知错误"),
                                    "updated_at": datetime.now().isoformat()
                                }
                        except Exception as e:
                            logger.error(f"解析任务结果失败: {str(e)}")
                
                return None
                
            # 解析任务状态
            try:
                # 如果是字符串，尝试解析为JSON
                if isinstance(status_json, str):
                    return json.loads(status_json)
                # 如果不是字符串，可能已经是字典
                elif isinstance(status_json, dict):
                    return status_json
                else:
                    logger.error(f"任务状态数据格式错误: {type(status_json)}")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"解析任务状态数据失败: {str(e)}")
                logger.error(f"原始数据: {status_json}")
                return None
                
        except Exception as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            return {
                "status": "error",
                "progress": 0,
                "message": f"获取状态失败: {str(e)}"
            }
    
    async def start_worker(self, handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        启动队列工作者
        
        Args:
            handler: 处理任务的异步回调函数
        """
        # 如果已经在运行，先停止
        if self._running:
            logger.warning("工作器已在运行，将先停止")
            await self.stop_worker()
        
        # 标记为运行中
        self._running = True
        
        logger.info(f"启动队列工作者 (ID: {self._worker_id})")
        
        # 启动处理循环的异步任务
        asyncio.create_task(self._process_queue(handler))
    
    async def _process_queue(self, handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]) -> None:
        """
        队列处理循环
        
        Args:
            handler: 处理任务的异步回调函数
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，工作器启动失败")
                self._running = False
                return
            
            # 处理循环
            while self._running:
                try:
                    # 获取任务
                    task = await self.dequeue()
                    
                    if not task:
                        # 队列为空，等待后重试
                        await asyncio.sleep(1)
                        continue
                    
                    # 记录正在处理的任务
                    task_id = task.get("task_id")
                    if not task_id:
                        logger.error("任务缺少task_id字段")
                        continue
                        
                    self._processing_tasks.add(task_id)
                    
                    try:
                        # 记录任务开始处理的时间
                        start_time = time.time()
                        logger.info(f"开始处理任务: {task_id}")
                        
                        # 获取任务负载数据
                        payload = task.get("payload", {})
                        if not payload and "status" in task and task["status"] != "unknown":
                            # 如果没有找到payload但有其他字段，可能是任务数据本身
                            payload = task
                            
                        # 添加详细日志
                        logger.info(f"处理任务数据: task_id={task_id}, payload={payload}")
                        
                        # 确保payload中有必要的信息
                        if not payload.get("file_id") and task.get("file_id"):
                            payload["file_id"] = task.get("file_id")
                            
                        if not payload.get("project_id") and task.get("project_id"):
                            payload["project_id"] = task.get("project_id")
                            
                        # 确保有任务ID
                        if not payload.get("task_id") and task_id:
                            payload["task_id"] = task_id
                            
                        # 处理任务
                        try:
                            result = await handler(payload)
                            logger.info(f"任务处理结果: {result}")
                        except Exception as handler_err:
                            logger.error(f"处理器异常: {str(handler_err)}")
                            logger.error(traceback.format_exc())
                            result = {
                                "success": False,
                                "error": f"处理器异常: {str(handler_err)}"
                            }
                        
                        # 计算处理时间
                        end_time = time.time()
                        processing_time = end_time - start_time
                        
                        # 任务处理完成 - 一次性更新所有状态信息
                        if result and result.get("success", False):
                            logger.info(f"任务处理成功: {task_id}, 处理用时: {processing_time:.2f}秒")
                            # 一次性更新任务状态为完成，包含所有信息
                            await self.update_task_status(
                                task_id=task_id,
                                status="completed",
                                message="处理成功",
                                processing_time_seconds=processing_time,
                                processing_time_display=f"{processing_time:.2f}秒",
                                result=result
                            )
                        else:
                            error_msg = result.get('error', '未知错误') if result else '处理返回空结果'
                            logger.warning(f"任务处理失败: {task_id}, 错误: {error_msg}, 处理用时: {processing_time:.2f}秒")
                            # 一次性更新任务状态为失败，包含所有信息
                            await self.update_task_status(
                                task_id=task_id,
                                status="failed",
                                message=f"处理失败: {error_msg}",
                                processing_time_seconds=processing_time,
                                processing_time_display=f"{processing_time:.2f}秒",
                                result=result
                            )
                        
                        # 释放任务锁
                        lock_key = f"lock:{task_id}"
                        try:
                            await self._redis.delete(lock_key)
                            logger.debug(f"已释放任务锁: {task_id}")
                        except Exception as lock_err:
                            logger.warning(f"释放任务锁失败: {task_id}, 错误: {str(lock_err)}")
                            
                    except Exception as e:
                        # 任务处理过程发生异常
                        end_time = time.time()
                        processing_time = end_time - start_time
                        logger.error(f"处理任务时出错: {task_id}, 错误: {str(e)}, 处理用时: {processing_time:.2f}秒")
                        logger.error(traceback.format_exc())
                        
                        # 更新任务状态为失败
                        await self.update_task_status(
                            task_id=task_id,
                            status="failed",
                            message=f"处理任务时出错: {str(e)}"
                        )
                        
                        # 添加处理时间到任务状态
                        current_status = await self.get_task_status(task_id)
                        if current_status:
                            current_status["processing_time_seconds"] = processing_time
                            current_status["processing_time_display"] = f"{processing_time:.2f}秒"
                            current_status["error"] = str(e)
                            await self._save_task_status(task_id, current_status)
                    finally:
                        # 从处理集合中移除任务
                        if task_id in self._processing_tasks:
                            self._processing_tasks.remove(task_id)
                
                except asyncio.CancelledError:
                    # 任务被取消
                    logger.info("工作者任务被取消")
                    break
                except Exception as e:
                    # 循环处理过程中发生异常，忽略并继续
                    logger.error(f"工作者循环中发生错误: {str(e)}")
                    logger.error(traceback.format_exc())
                    await asyncio.sleep(1)
                    
                    # 检查Redis连接
                    if not await self._ensure_connection():
                        logger.error("Redis连接已断开，尝试重新连接")
                        await asyncio.sleep(5)  # 等待5秒后重试
            
        except Exception as e:
            logger.error(f"队列工作者异常退出: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            self._running = False
            logger.info(f"队列工作者已停止 (ID: {self._worker_id})")
    
    async def stop_worker(self) -> None:
        """停止队列工作者"""
        if not self._running:
            logger.info("工作器已经停止，无需再次停止")
            return
            
        self._running = False
        logger.info("正在停止队列工作者...")
        
        # 等待所有正在处理的任务完成
        if self._processing_tasks:
            logger.info(f"等待 {len(self._processing_tasks)} 个正在处理的任务完成...")
            for _ in range(10):  # 最多等待10秒
                if not self._processing_tasks:
                    break
                await asyncio.sleep(1)
            
            # 如果仍有任务未完成，记录日志
            if self._processing_tasks:
                logger.warning(f"有 {len(self._processing_tasks)} 个任务未完成就被强制停止")
        
        logger.info("队列工作者已停止")
    
    async def get_queue_stats(self) -> Dict[str, int]:
        """
        获取队列统计信息
        
        Returns:
            Dict[str, int]: 队列统计信息，包括待处理任务数等
        """
        try:
            async with self._redis.pipeline() as pipe:
                # 获取待处理队列长度
                await pipe.llen(self._queue_name)
                # 获取处理中队列长度
                await pipe.llen(self._queue_name)
                # 获取已完成队列长度(如果需要)
                await pipe.llen(self._queue_name)
                # 获取失败队列长度
                await pipe.llen(self._queue_name)
                
                results = await pipe.execute()
                
            return {
                "pending_count": results[0],
                "processing_count": results[1], 
                "completed_count": results[2],
                "failed_count": results[3],
                "total_count": sum(results)
            }
        except Exception as e:
            logger.error(f"获取队列统计失败: {str(e)}")
            return {
                "pending_count": 0,
                "processing_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "total_count": 0,
                "error": str(e)
            }
    
    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有待处理任务
        
        Returns:
            List[Dict[str, Any]]: 待处理任务列表
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，获取待处理任务失败")
                return []
            
            # 获取队列中所有任务但不移除它们
            tasks = []
            task_data = await self._redis.lrange(self._queue_name, 0, -1)
            
            for data in task_data:
                try:
                    task_json = data.decode("utf-8")
                    task = json.loads(task_json)
                    tasks.append(task)
                except Exception as e:
                    logger.warning(f"解析任务数据失败: {str(e)}")
            
            return tasks
        except Exception as e:
            logger.error(f"获取待处理任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    async def _save_task_status(self, task_id: str, status: Dict[str, Any]) -> bool:
        """
        保存任务状态到Redis
        
        Args:
            task_id: 任务ID
            status: 任务状态数据
            
        Returns:
            bool: 是否成功保存
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，保存任务状态失败")
                return False
                    
            status_key = f"{self._status_prefix}{task_id}"
            status_json = json.dumps(status)
            
            # 设置带过期时间的数据
            await self._redis.set(status_key, status_json, ex=self._task_ttl)
            return True
        except Exception as e:
            logger.error(f"保存任务状态失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    async def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果，本质上与get_task_status相同，但语义上表示获取最终结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务结果信息，不存在则返回None
        """
        return await self.get_task_status(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，取消任务失败")
                return False
                
            # 获取当前任务状态
            current_status = await self.get_task_status(task_id)
            if not current_status:
                logger.warning(f"无法取消不存在的任务: {task_id}")
                return False
                
            # 只有pending和processing状态的任务可以取消
            status = current_status.get("status")
            if status not in ["pending", "processing"]:
                logger.warning(f"无法取消已完成或失败的任务: {task_id}, 状态: {status}")
                return False
                
            # 更新任务状态为取消
            current_status["status"] = "cancelled"
            current_status["updated_at"] = datetime.now().isoformat()
            current_status["cancelled_at"] = datetime.now().isoformat()
            
            # 保存更新后的任务状态
            await self._save_task_status(task_id, current_status)
            
            logger.info(f"任务已取消: {task_id}")
            return True
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def initialize(self) -> bool:
        """
        初始化队列服务，连接Redis
        
        Returns:
            bool: 是否成功初始化
        """
        if not self._initialized:
            try:
                # 连接Redis
                connected = await self.connect()
                if connected:
                    self._initialized = True
                    logger.info("队列服务初始化成功")
                else:
                    logger.error("队列服务初始化失败 - 无法连接Redis")
                return connected
            except Exception as e:
                logger.error(f"初始化队列服务失败: {str(e)}")
                return False
        return True
        
    def schedule_init(self):
        """创建初始化任务，在事件循环中执行"""
        loop = asyncio.get_event_loop()
        if not self._init_task or self._init_task.done():
            self._init_task = loop.create_task(self.initialize())
        return self._init_task

    async def set_task_data(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        设置任务数据，用于初始化或更新任务状态
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            bool: 设置是否成功
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，设置任务数据失败")
                return False
                
            # 初始化任务状态
            task = {
                "task_id": task_id,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
                "progress": 0,
                "message": "准备处理",
                "payload": task_data
            }
            
            # 保存任务状态
            success = await self._save_task_status(task_id, task)
            if success:
                logger.info(f"任务数据已设置: {task_id}")
                # 添加到待处理队列
                await self._redis.lpush(self._pending_queue_key, task_id)
            
            return success
        except Exception as e:
            logger.error(f"设置任务数据失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def enqueue_task(self, task_id: str) -> bool:
        """
        将任务ID放入处理队列
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功添加到队列
        """
        try:
            # 确保连接可用
            if not await self._ensure_connection():
                logger.error("无法连接到Redis，任务入队失败")
                return False
            
            # 将任务ID添加到队列
            await self._redis.lpush(self._queue_name, task_id)
            
            logger.info(f"任务ID已添加到处理队列: {task_id}")
            return True
        except Exception as e:
            logger.error(f"任务入队失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

# 创建全局队列实例
file_processing_queue = FileProcessingQueue() 