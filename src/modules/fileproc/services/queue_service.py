#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件处理队列服务
基于Redis实现的异步消息队列，用于文件处理任务
遵循Lumidoc微服务架构原则，支持分布式环境
"""

import json
import uuid
import time
import asyncio
import traceback
from typing import Dict, Any, Optional, List, Callable, Awaitable
import redis.asyncio as aioredis
from datetime import datetime

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
                        if hasattr(self._redis, "aclose"):
                            await self._redis.aclose()
                        else:
                            await self._redis.close()
                    except Exception:
                        pass
                    self._redis = None
            
            # 尝试连接Redis
            try:
                # 获取Redis连接URL
                redis_url = settings.get_redis_url()
                logger.info(
                    "正在连接到Redis: %s:%s DB=%s",
                    settings.redis_host,
                    settings.redis_port,
                    settings.redis_db,
                )
                
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
                    # redis-py 5+ 使用 aclose；兼容较早版本的异步 close。
                    if hasattr(self._redis, "aclose"):
                        await self._redis.aclose()
                    else:
                        await self._redis.close()
                    logger.info("Redis连接已关闭")
                except AttributeError:
                    # 兼容旧版 aioredis。
                    close_result = self._redis.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
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
    
    async def enqueue(self, payload):
        if not await self._ensure_connection(): raise ConnectionError('Queue unavailable')
        task_id = payload.get('task_id') or str(uuid.uuid4())
        task = {'task_id': task_id, 'created_at': datetime.now().isoformat(), 'status': 'pending', 'progress': 0, 'payload': payload}
        # The intent and the queue entry commit together; repeated submissions are harmless.
        await self._redis.eval("""
            if redis.call('EXISTS', KEYS[1]) == 0 then
                redis.call('SET', KEYS[1], ARGV[1])
                redis.call('LPUSH', KEYS[2], ARGV[2])
            end
            return 1
        """, 2, self._status_prefix+task_id, self._queue_name, json.dumps(task), task_id)
        return task_id

    async def recover_inflight(self):
        from src.shared.operation_journal import journal
        for raw in await self._redis.lrange(self._processing_queue_key, 0, -1):
            try:
                parsed = json.loads(raw)
                identifier = parsed['task_id']
            except (ValueError, TypeError):
                identifier = raw.decode() if isinstance(raw, bytes) else raw
            moved = await self._redis.eval("""
                if redis.call('EXISTS', KEYS[1]) == 0 and redis.call('LREM', KEYS[2], 1, ARGV[1]) == 1 then
                    redis.call('LPUSH', KEYS[3], ARGV[1])
                    return 1
                end
                return 0
            """, 3, 'fileproc:lease:'+identifier, self._processing_queue_key, self._queue_name, raw)
            if moved: journal().event('task.interrupted', 'fileproc', 'recovering', operation_id=identifier)

    async def dequeue(self):
        if not await self._ensure_connection(): return None
        await self.recover_inflight()
        raw = await self._redis.rpoplpush(self._queue_name, self._processing_queue_key)
        if not raw: return None
        try:
            parsed = json.loads(raw)
            task_id = parsed['task_id']
        except (ValueError, TypeError):
            task_id = raw.decode() if isinstance(raw, bytes) else raw
        task = await self.get_task_status(task_id)
        if not task or task.get('status') in ('completed','cancelled','failed'):
            await self._redis.lrem(self._processing_queue_key, 1, raw)
            return None
        lease = 'fileproc:lease:'+task_id
        if not await self._redis.set(lease, self._worker_id, nx=True, ex=60): return None
        attempts = task.get('attempts', 0)
        if attempts >= 5:
            task.update(status='failed', message='Automatic recovery limit reached')
            await self._save_task_status(task_id, task)
            await self._redis.lrem(self._processing_queue_key, 1, raw)
            await self._redis.delete(lease)
            return None
        task.update(status='processing', attempts=attempts+1, started_at=datetime.now().isoformat())
        await self._save_task_status(task_id, task)
        task['_raw'] = raw
        return task

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
            if status == 'failed' and current_status.get('attempts', 0) < 5:
                status, message, progress = 'pending', '正在自动恢复处理', min(current_status.get('progress', 0), 95)
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
    
    async def _process_queue(self, handler):
        from src.shared.operation_journal import journal
        while self._running:
            try:
                task = await self.dequeue()
                if not task:
                    await asyncio.sleep(1)
                    continue
                task_id = task['task_id']
                self._processing_tasks.add(task_id)
                lease = 'fileproc:lease:'+task_id
                async def heartbeat():
                    while True:
                        await self._redis.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('EXPIRE',KEYS[1],60) end return 0", 1, lease, self._worker_id)
                        await asyncio.sleep(15)
                beat = asyncio.create_task(heartbeat())
                started = time.time()
                terminal = False
                try:
                    payload = task.get('payload') or {key:value for key,value in task.items() if key != '_raw'}
                    payload['task_id'] = task_id
                    result = await handler(payload)
                    if not result or not result.get('success'): raise RuntimeError('Processing interrupted')
                    await self.update_task_status(task_id, 'completed', progress=100, result=result, processing_time_seconds=time.time()-started)
                    terminal = True
                    journal().event('task.completed', 'fileproc', 'completed', operation_id=task_id)
                except asyncio.CancelledError:
                    journal().event('task.interrupted', 'fileproc', 'recovering', operation_id=task_id)
                    raise
                except Exception:
                    terminal = task['attempts'] >= 5
                    await self.update_task_status(task_id, 'failed', message='Recovery limit reached' if terminal else '正在自动恢复处理')
                    journal().event('task.retry', 'fileproc', 'needs_attention' if terminal else 'recovering', operation_id=task_id)
                    if not terminal: await asyncio.sleep(min(2**task['attempts'], 30))
                finally:
                    beat.cancel()
                    await asyncio.gather(beat, return_exceptions=True)
                    if terminal: await self._redis.lrem(self._processing_queue_key, 1, task['_raw'])
                    await self._redis.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0", 1, lease, self._worker_id)
                    self._processing_tasks.discard(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(2)

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
                    task_id = data.decode("utf-8") if isinstance(data, bytes) else data
                    try:
                        task_id = json.loads(task_id)['task_id']
                    except (ValueError, TypeError):
                        pass
                    task = await self.get_task_status(task_id)
                    if task: tasks.append(task)
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
            await self._redis.set(status_key, status_json, ex=self._task_ttl if status.get('status') in ('completed','failed','cancelled') else None)
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
                
            task_data['task_id'] = task_id
            await self.enqueue(task_data)
            return True
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
            
            # set_task_data atomically enqueues the task already.
            return bool(await self.get_task_status(task_id))
        except Exception as e:
            logger.error(f"任务入队失败: {str(e)}")
            logger.error(traceback.format_exc())
            return False

# 创建全局队列实例
file_processing_queue = FileProcessingQueue()
