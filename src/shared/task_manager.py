"""
任务管理模块
提供基于Redis的任务去重、分布式锁和任务状态追踪功能
"""

import os
import json
import time
import asyncio
import uuid
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Callable, Awaitable, TypeVar, Union
import redis.asyncio as aioredis
# 正确导入Redis异常
from redis.exceptions import AuthenticationError, ConnectionError, TimeoutError as RedisTimeoutError
from datetime import datetime, timedelta
from functools import wraps
import inspect

# 配置日志
logger = logging.getLogger(__name__)

# Redis配置
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")

# 任务配置
TASK_KEY_PREFIX = "stp:tasks:"
TASK_LOCK_PREFIX = "stp:task_lock:"
TASK_RESULT_PREFIX = "stp:task_result:"
TASK_DEFAULT_TTL = int(os.environ.get("TASK_DEFAULT_TTL", "86400"))  # 任务结果保留1天
# 新增任务ID计数器键名
TASK_COUNTER_KEY = "stp:task_counter"
# 新增全局任务索引键，用于检索所有活跃任务
TASK_INDEX_KEY = "stp:task_index"
# 新增任务内容哈希映射，用于快速查找任务
TASK_CONTENT_HASH_KEY = "stp:task_content_hash"
# 任务ID前缀，用于唯一标识任务
TASK_ID_PREFIX = os.environ.get("TASK_ID_PREFIX", "task")
# 服务实例标识，用于区分不同实例生成的任务
SERVICE_INSTANCE_ID = os.environ.get("SERVICE_INSTANCE_ID", "")

# 任务状态
class TaskStatus:
    PENDING = "pending"      # 任务等待执行
    RUNNING = "running"      # 任务正在执行
    COMPLETED = "completed"  # 任务已完成
    FAILED = "failed"        # 任务执行失败
    CANCELLED = "cancelled"  # 任务已取消
    DUPLICATE = "duplicate"  # 重复任务
    TIMEOUT = "timeout"      # 任务执行超时

# 定义返回类型
T = TypeVar('T')

class TaskLock:
    """分布式任务锁"""
    
    def __init__(self, redis_client: aioredis.Redis, lock_name: str, timeout: int = 60):
        """
        初始化任务锁
        
        Args:
            redis_client: Redis客户端
            lock_name: 锁名称
            timeout: 锁超时时间（秒）
        """
        self.redis = redis_client
        self.lock_name = f"{TASK_LOCK_PREFIX}{lock_name}"
        self.lock_id = str(uuid.uuid4())
        self.timeout = timeout
        self._locked = False
        
    async def acquire(self) -> bool:
        """
        获取锁
        
        Returns:
            bool: 是否成功获取锁
        """
        # 使用SET NX实现锁
        acquired = await self.redis.set(self.lock_name, self.lock_id, nx=True, ex=self.timeout)
        self._locked = acquired
        if acquired:
            logger.debug(f"已获取任务锁: {self.lock_name} (ID: {self.lock_id})")
        return acquired
        
    async def release(self) -> bool:
        """
        释放锁
        
        Returns:
            bool: 是否成功释放锁
        """
        if not self._locked:
            return True
            
        # 使用Lua脚本确保只删除自己的锁
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        # 先尝试简单方法：检查值然后删除 (无需脚本)
        try:
            current_value = await self.redis.get(self.lock_name)
            if current_value == self.lock_id:
                success = await self.redis.delete(self.lock_name)
                if success:
                    logger.debug(f"已释放任务锁: {self.lock_name} (ID: {self.lock_id})")
                    self._locked = False
                    return True
                return False
            return False
        except Exception as e:
            logger.warning(f"使用简单方法释放锁失败: {str(e)}，尝试使用脚本方式")
            
            # 使用Redis lua脚本eval方法的适配
            try:
                # Redis 5.0+ 版本API
                result = await self.redis.eval(script, 1, self.lock_name, self.lock_id)
                if result:
                    logger.debug(f"已释放任务锁: {self.lock_name} (ID: {self.lock_id})")
                    self._locked = False
                    return True
                return False
            except Exception as script_err:
                logger.error(f"释放锁时出错: {str(script_err)}")
                return False
        
    async def refresh(self) -> bool:
        """
        刷新锁超时时间
        
        Returns:
            bool: 是否成功刷新锁
        """
        if not self._locked:
            return False
            
        # 先尝试简单方法：检查值然后更新超时时间 (无需脚本)
        try:
            current_value = await self.redis.get(self.lock_name)
            if current_value == self.lock_id:
                success = await self.redis.expire(self.lock_name, self.timeout)
                if success:
                    logger.debug(f"已刷新任务锁: {self.lock_name} (ID: {self.lock_id})")
                    return True
                return False
            return False
        except Exception as e:
            logger.warning(f"使用简单方法刷新锁失败: {str(e)}，尝试使用脚本方式")
            
            # 使用Lua脚本确保只刷新自己的锁
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            
            try:
                # Redis 5.0+ 版本API
                result = await self.redis.eval(script, 1, self.lock_name, self.lock_id, self.timeout)
                if result:
                    logger.debug(f"已刷新任务锁: {self.lock_name} (ID: {self.lock_id})")
                    return True
                return False
            except Exception as script_err:
                logger.error(f"刷新锁时出错: {str(script_err)}")
                return False
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.acquire()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.release()

class TaskManager:
    """任务管理器，处理任务去重和状态追踪"""
    
    def __init__(self):
        """初始化任务管理器"""
        self._redis = None
        self._instance_id = SERVICE_INSTANCE_ID or str(uuid.uuid4())[:8]
        logger.debug(f"TaskManager实例初始化，实例ID: {self._instance_id}")
        # 记录本地任务缓存
        self._local_tasks = {}
    
    async def connect(self):
        """连接到Redis"""
        if self._redis is not None:
            logger.debug("Redis连接已存在，跳过连接")
            return
            
        logger.info(f"连接Redis: {REDIS_HOST}:{REDIS_PORT} DB={REDIS_DB}")
        max_retries = 3
        retry_count = 0
        backoff_time = 1.0
        
        while retry_count < max_retries:
            try:
                # 构建Redis连接URL
                if REDIS_PASSWORD:
                    # 创建带密码的连接
                    redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
                    logger.debug("使用密码连接Redis")
                else:
                    # 创建不带密码的连接
                    redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
                    logger.debug("使用无密码连接Redis")

                # 创建Redis连接
                self._redis = await aioredis.from_url(
                    redis_url, 
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0
                )
                
                # 测试连接
                await self._redis.ping()
                logger.info("Redis连接成功")
                return
            except (ConnectionError, AuthenticationError) as e:
                retry_count += 1
                logger.warning(f"Redis连接失败 (尝试 {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count >= max_retries:
                    logger.error(f"Redis连接失败，达到最大重试次数: {str(e)}")
                    raise
                    
                # 等待一段时间后重试，使用指数退避策略
                await asyncio.sleep(backoff_time)
                backoff_time *= 2
            except Exception as e:
                logger.error(f"Redis连接出现未知错误: {str(e)}")
                raise
                
    def is_connected(self) -> bool:
        """检查是否已连接到Redis"""
        return self._redis is not None

    async def close(self):
        """关闭连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    async def generate_sequential_task_id(self, task_name: str) -> str:
        """
        生成顺序递增的任务ID
        
        Args:
            task_name: 任务名称
            
        Returns:
            str: 格式为 {前缀}-{任务名}-{时间戳}-{计数器}-{实例ID} 的任务ID
        """
        await self.connect()
        
        # 获取当前时间戳
        timestamp = int(time.time())
        
        # 使用Redis的INCR原子操作获取唯一计数器
        counter = await self._redis.incr(TASK_COUNTER_KEY)
        
        # 生成任务ID: 前缀-任务名-时间戳-计数器-实例ID
        task_id = f"{TASK_ID_PREFIX}-{task_name}-{timestamp}-{counter}-{self._instance_id}"
        
        return task_id
            
    def _generate_task_id(self, task_name: str, task_params: Dict[str, Any]) -> str:
        """
        根据任务名和参数生成任务内容哈希ID
        
        Args:
            task_name: 任务名称
            task_params: 任务参数
            
        Returns:
            str: 任务哈希ID
        """
        # 将任务参数转换为JSON字符串，确保可重复的哈希
        params_str = json.dumps(task_params, sort_keys=True)
        # 计算MD5哈希作为ID
        hash_obj = hashlib.md5(f"{task_name}:{params_str}".encode())
        return hash_obj.hexdigest()
        
    async def create_task(self, 
                        task_name: str, 
                        task_params: Dict[str, Any] = None,
                        task_id: str = None,
                        ttl: int = TASK_DEFAULT_TTL,
                        use_sequential_id: bool = False) -> Tuple[str, bool]:
        """
        创建任务
        
        Args:
            task_name: 任务名称
            task_params: 任务参数
            task_id: 可选的任务ID，如果不提供则自动生成
            ttl: 任务结果保留时间（秒）
            use_sequential_id: 是否使用顺序递增ID
            
        Returns:
            Tuple[str, bool]: (任务ID，是否为新任务)
        """
        await self.connect()
        
        # 如果没有提供参数，使用空字典
        task_params = task_params or {}
        
        # 如果提供了task_id，直接使用
        if not task_id:
            if use_sequential_id:
                # 使用顺序递增ID
                task_id = await self.generate_sequential_task_id(task_name)
            else:
                # 使用内容哈希作为任务ID
                task_id = self._generate_task_id(task_name, task_params)
        
        # 检查任务是否已存在
        task_key = f"{TASK_KEY_PREFIX}{task_id}"
        exists = await self._redis.exists(task_key)
        
        if exists:
            # 任务已存在，返回现有任务ID
            logger.debug(f"任务已存在: {task_name} (ID: {task_id})")
            return task_id, False
        
        # 创建任务信息
        task_info = {
            "task_id": task_id,
            "task_name": task_name,
            "params": task_params,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "instance_id": self._instance_id
        }
        
        # 计算内容哈希用于去重
        content_hash = hashlib.md5(f"{task_name}:{json.dumps(task_params, sort_keys=True)}".encode()).hexdigest()
        task_info["content_hash"] = content_hash
        
        # 保存任务信息到Redis
        await self._redis.set(task_key, json.dumps(task_info), ex=ttl)
        
        # 添加到任务索引
        await self._redis.sadd(TASK_INDEX_KEY, task_id)
        
        # 添加内容哈希映射，用于快速查找任务
        await self._redis.hset(TASK_CONTENT_HASH_KEY, content_hash, task_id)
        
        # 添加到本地任务缓存
        self._local_tasks[task_id] = task_info
        
        logger.debug(f"任务已创建: {task_name} (ID: {task_id})")
        return task_id, True
    
    async def find_task_by_content(self, task_name: str, task_params: Dict[str, Any]) -> Optional[str]:
        """
        根据任务内容查找已存在的任务
        
        Args:
            task_name: 任务名称
            task_params: 任务参数
            
        Returns:
            Optional[str]: 任务ID，如不存在则返回None
        """
        await self.connect()
        
        # 计算内容哈希
        content_hash = self._generate_task_id(task_name, task_params)
        
        # 直接从哈希映射表中查找
        task_id = await self._redis.hget(TASK_CONTENT_HASH_KEY, content_hash)
        if task_id:
            # 验证任务是否仍然存在
            if await self._redis.exists(f"{TASK_KEY_PREFIX}{task_id}"):
                logger.debug(f"找到内容匹配的任务: {task_id}")
                return task_id
            else:
                # 任务不存在，从哈希映射表中删除
                await self._redis.hdel(TASK_CONTENT_HASH_KEY, content_hash)
        
        return None
        
    async def update_task_status(self, 
                               task_id: str, 
                               status: str, 
                               result: Any = None,
                               error: str = None,
                               ttl: int = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            result: 任务结果
            error: 错误信息
            ttl: 任务结果保留时间（秒）
            
        Returns:
            bool: 是否成功更新
        """
        await self.connect()
        
        task_key = f"{TASK_KEY_PREFIX}{task_id}"
        
        # 加锁确保原子操作
        lock = await self.get_lock(f"update_task_{task_id}", timeout=10)
        if not await lock.acquire():
            logger.warning(f"无法获取任务更新锁: {task_id}")
            return False
            
        try:
            # 检查任务是否存在
            task_info_json = await self._redis.get(task_key)
            if not task_info_json:
                logger.warning(f"尝试更新不存在的任务: {task_id}")
                return False
                
            try:
                task_info = json.loads(task_info_json)
            except json.JSONDecodeError:
                logger.error(f"任务数据格式错误: {task_id}")
                return False
                
            # 检查任务状态逻辑
            current_status = task_info.get("status")
            if current_status == TaskStatus.COMPLETED and status != TaskStatus.DUPLICATE:
                # 已完成任务不应被更新为其他状态（除了标记为重复）
                logger.debug(f"任务{task_id}已完成，忽略状态更新为{status}")
                return False
                
            # 更新任务状态
            task_info["status"] = status
            task_info["updated_at"] = datetime.now().isoformat()
            
            # 更新任务结果
            if status == TaskStatus.COMPLETED and result is not None:
                # 处理复杂对象，确保可序列化
                if hasattr(result, '__dict__'):
                    # 如果对象有__dict__属性，尝试将其转换为字典
                    try:
                        result_dict = result.__dict__
                        # 检查是否有to_dict或dict方法
                        if hasattr(result, 'to_dict') and callable(getattr(result, 'to_dict')):
                            result_dict = result.to_dict()
                        elif hasattr(result, 'dict') and callable(getattr(result, 'dict')):
                            result_dict = result.dict()
                        task_info["result"] = result_dict
                    except Exception as e:
                        logger.warning(f"无法序列化结果对象: {e}")
                        task_info["result"] = str(result)
                else:
                    # 尝试直接存储结果
                    try:
                        # 测试是否可序列化
                        json.dumps(result)
                        task_info["result"] = result
                    except TypeError:
                        # 如果不可序列化，转换为字符串
                        logger.warning(f"结果对象不可JSON序列化，转换为字符串")
                        task_info["result"] = str(result)
                
                # 存储大型结果到单独的键
                if isinstance(task_info["result"], (dict, list)) and len(json.dumps(task_info["result"])) > 1024:
                    result_key = f"{TASK_RESULT_PREFIX}{task_id}"
                    await self._redis.set(result_key, json.dumps(task_info["result"]), ex=ttl or TASK_DEFAULT_TTL)
                    task_info["result_key"] = result_key
                    task_info["result"] = None  # 不在主任务记录中存储大型结果
            
            # 更新错误信息
            if status == TaskStatus.FAILED and error:
                task_info["error"] = error
                
                # 检查是否需要重试
                retry_count = task_info.get("retry_count", 0)
                max_retries = task_info.get("max_retries", 3)
                
                if retry_count < max_retries:
                    # 增加重试计数
                    task_info["retry_count"] = retry_count + 1
                    task_info["status"] = TaskStatus.PENDING  # 重新设置为待处理状态
                    task_info["retry_at"] = datetime.now().isoformat()
                    logger.info(f"任务{task_id}失败，将重试 ({retry_count+1}/{max_retries})")
                
            # 保存更新后的任务信息
            try:
                await self._redis.set(task_key, json.dumps(task_info), ex=ttl or TASK_DEFAULT_TTL)
                logger.debug(f"任务状态已更新: {task_id} -> {status}")
            except TypeError as e:
                logger.error(f"序列化任务信息失败: {e}")
                # 尝试简化任务信息
                simplified_info = {
                    "task_id": task_info.get("task_id"),
                    "task_name": task_info.get("task_name"),
                    "status": status,
                    "error": error or task_info.get("error"),
                    "updated_at": datetime.now().isoformat()
                }
                await self._redis.set(task_key, json.dumps(simplified_info), ex=ttl or TASK_DEFAULT_TTL)
                logger.debug(f"使用简化信息更新任务状态: {task_id} -> {status}")
            
            return True
        finally:
            # 释放锁
            await lock.release()
        
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态及结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务信息，包含状态和结果
        """
        await self.connect()
        
        task_key = f"{TASK_KEY_PREFIX}{task_id}"
        
        # 获取任务信息
        task_info_json = await self._redis.get(task_key)
        if not task_info_json:
            logger.warning(f"任务不存在或已过期: {task_id}")
            return {
                "task_id": task_id,
                "status": None,
                "error": "任务不存在或已过期"
            }
            
        try:
            task_info = json.loads(task_info_json)
        except json.JSONDecodeError:
            logger.error(f"任务数据格式错误: {task_id}")
            return {
                "task_id": task_id,
                "status": None,
                "error": "任务数据格式错误"
            }
            
        # 如果任务结果存储在单独的键中，则获取完整结果
        if "result_key" in task_info and task_info["result_key"]:
            result_json = await self._redis.get(task_info["result_key"])
            if result_json:
                try:
                    task_info["result"] = json.loads(result_json)
                except json.JSONDecodeError:
                    task_info["result"] = result_json
                    
        return task_info
    
    async def get_active_tasks(self, task_name: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取当前活跃任务列表
        
        Args:
            task_name: 可选的任务名称过滤器
            status: 可选的任务状态过滤器
            
        Returns:
            List[Dict[str, Any]]: 活跃任务列表
        """
        await self.connect()
        
        # 获取任务索引中的所有任务ID，直接转换为列表
        all_task_ids_set = await self._redis.smembers(TASK_INDEX_KEY)
        all_task_ids = list(all_task_ids_set) if all_task_ids_set else []
        
        if not all_task_ids:
            return []
        
        tasks = []
        pipeline = self._redis.pipeline()
        
        # 批量获取任务信息
        for task_id in all_task_ids:
            pipeline.get(f"{TASK_KEY_PREFIX}{task_id}")
        
        results = await pipeline.execute()
        
        for i, result in enumerate(results):
            if not result:
                # 任务不存在，从索引中移除
                await self._redis.srem(TASK_INDEX_KEY, all_task_ids[i])
                continue
                
            try:
                task = json.loads(result)
                
                # 应用过滤
                if task_name and task.get("task_name") != task_name:
                    continue
                    
                if status and task.get("status") != status:
                    continue
                    
                tasks.append(task)
            except json.JSONDecodeError:
                logger.warning(f"任务数据格式错误: {all_task_ids[i]}")
                continue
                
        return tasks
        
    async def get_lock(self, lock_name: str, timeout: int = 60) -> TaskLock:
        """
        获取分布式锁
        
        Args:
            lock_name: 锁名称
            timeout: 锁超时时间（秒）
            
        Returns:
            TaskLock: 分布式锁对象
        """
        await self.connect()
        return TaskLock(self._redis, lock_name, timeout)
    
    async def cleanup_expired_tasks(self, max_age_days: int = 7) -> int:
        """
        清理过期任务
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            int: 清理的任务数量
        """
        await self.connect()
        
        # 获取任务索引中的所有任务ID，直接转换为列表
        all_task_ids_set = await self._redis.smembers(TASK_INDEX_KEY)
        all_task_ids = list(all_task_ids_set) if all_task_ids_set else []
        
        if not all_task_ids:
            return 0
            
        now = datetime.now()
        max_age = timedelta(days=max_age_days)
        cleaned_count = 0
        
        pipeline = self._redis.pipeline()
        
        # 批量获取任务信息
        for task_id in all_task_ids:
            pipeline.get(f"{TASK_KEY_PREFIX}{task_id}")
        
        results = await pipeline.execute()
        
        # 清理管道
        pipeline = self._redis.pipeline()
        has_operations = False  # 标记是否有操作需要执行
        
        for i, result in enumerate(results):
            if not result:
                # 任务不存在，从索引中移除
                pipeline.srem(TASK_INDEX_KEY, all_task_ids[i])
                has_operations = True
                cleaned_count += 1
                continue
                
            try:
                task = json.loads(result)
                created_at = datetime.fromisoformat(task.get("created_at", "2000-01-01T00:00:00"))
                
                # 检查任务是否过期
                if now - created_at > max_age:
                    # 删除任务
                    pipeline.delete(f"{TASK_KEY_PREFIX}{all_task_ids[i]}")
                    # 同时删除任务结果（如果存在）
                    if "result_key" in task:
                        pipeline.delete(task["result_key"])
                    # 从索引中移除
                    pipeline.srem(TASK_INDEX_KEY, all_task_ids[i])
                    # 从内容哈希映射中移除
                    if "content_hash" in task:
                        pipeline.hdel(TASK_CONTENT_HASH_KEY, task["content_hash"])
                    has_operations = True
                    cleaned_count += 1
            except (json.JSONDecodeError, ValueError):
                # 任务数据格式错误，清理
                pipeline.delete(f"{TASK_KEY_PREFIX}{all_task_ids[i]}")
                pipeline.srem(TASK_INDEX_KEY, all_task_ids[i])
                has_operations = True
                cleaned_count += 1
        
        # 执行清理操作
        if has_operations:  # 使用自定义标记检查是否有操作需要执行
            await pipeline.execute()
            
        return cleaned_count
        
    async def run_once(self,
                      task_name: str, 
                      func: Callable[..., Awaitable[T]], 
                      *args, 
                      ttl: int = TASK_DEFAULT_TTL,
                      use_sequential_id: bool = False,
                      task_timeout: int = None,
                      retry_on_failure: bool = True,
                      max_retries: int = 3,
                      **kwargs) -> Tuple[str, T]:
        """
        确保函数只运行一次的包装器
        如果相同参数的任务已存在且已完成，直接返回缓存结果
        否则运行函数并缓存结果
        
        Args:
            task_name: 任务名称
            func: 异步函数
            *args: 函数位置参数
            ttl: 任务结果保留时间（秒）
            use_sequential_id: 是否使用顺序递增ID
            task_timeout: 任务超时时间（秒）
            retry_on_failure: 是否在失败时重试
            max_retries: 最大重试次数
            **kwargs: 函数关键字参数
            
        Returns:
            Tuple[str, T]: (任务ID，函数返回值)
        """
        # 将参数转换为可序列化的格式
        task_params = {
            "args": [str(arg) if not isinstance(arg, (str, int, float, bool, list, dict)) else arg for arg in args],
            "kwargs": {k: str(v) if not isinstance(v, (str, int, float, bool, list, dict)) else v for k, v in kwargs.items()}
        }
        
        # 检查是否有相同内容的任务
        existing_task_id = await self.find_task_by_content(task_name, task_params)
        if existing_task_id:
            # 获取已有任务状态
            existing_task = await self.get_task_status(existing_task_id)
            if existing_task.get('status') == TaskStatus.COMPLETED:
                logger.debug(f"使用已完成任务的结果: {task_name} (ID: {existing_task_id})")
                return existing_task_id, existing_task.get('result')
        
        # 如果要使用顺序ID或没有找到现有任务，创建新任务
        task_id, is_new = await self.create_task(
            task_name=task_name,
            task_params=task_params,
            ttl=ttl,
            use_sequential_id=use_sequential_id
        )
        
        # 更新任务配置
        if is_new and retry_on_failure:
            # 获取任务信息并更新重试配置
            task_key = f"{TASK_KEY_PREFIX}{task_id}"
            task_info_json = await self._redis.get(task_key)
            if task_info_json:
                try:
                    task_info = json.loads(task_info_json)
                    task_info["max_retries"] = max_retries
                    if task_timeout:
                        task_info["timeout"] = task_timeout
                    await self._redis.set(task_key, json.dumps(task_info), ex=ttl)
                except json.JSONDecodeError:
                    pass
        
        # 如果是新任务或任务未完成，执行函数
        if is_new:
            try:
                # 更新状态为运行中
                await self.update_task_status(task_id, TaskStatus.RUNNING)
                
                # 设置任务超时保护
                if task_timeout:
                    # 创建一个带超时的任务
                    try:
                        # 执行函数，带超时控制
                        result = await asyncio.wait_for(func(*args, **kwargs), timeout=task_timeout)
                    except asyncio.TimeoutError:
                        # 任务超时处理
                        await self.update_task_status(task_id, TaskStatus.TIMEOUT, 
                                                   error=f"任务执行超时 ({task_timeout}秒)")
                        raise TimeoutError(f"任务{task_id}执行超时")
                else:
                    # 正常执行函数
                    result = await func(*args, **kwargs)
                
                # 更新状态为已完成
                await self.update_task_status(task_id, TaskStatus.COMPLETED, result=result, ttl=ttl)
                
                return task_id, result
                
            except Exception as e:
                # 更新状态为失败
                await self.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
                raise
        else:
            # 获取现有任务状态
            task_info = await self.get_task_status(task_id)
            task_status = task_info.get("status")
            
            if task_status == TaskStatus.COMPLETED:
                # 如果任务已完成，直接返回结果
                return task_id, task_info.get("result")
                
            elif task_status == TaskStatus.FAILED:
                # 如果任务已失败，抛出异常
                raise Exception(task_info.get("error", "任务执行失败"))
                
            else:
                # 如果任务正在进行中，等待完成
                logger.debug(f"等待任务完成: {task_name} (ID: {task_id})")
                
                # 轮询任务状态
                max_retries = 20
                retry_delay = 1
                
                for _ in range(max_retries):
                    await asyncio.sleep(retry_delay)
                    task_info = await self.get_task_status(task_id)
                    task_status = task_info.get("status")
                    
                    if task_status == TaskStatus.COMPLETED:
                        return task_id, task_info.get("result")
                        
                    elif task_status == TaskStatus.FAILED:
                        raise Exception(task_info.get("error", "任务执行失败"))
                        
                    # 指数退避重试
                    retry_delay = min(retry_delay * 1.5, 10)  # 最大等待10秒
                
                # 如果超过最大重试次数仍未完成，抛出异常
                raise TimeoutError(f"等待任务{task_id}完成超时")

# 任务去重装饰器
def dedupe_task(task_name: str = None, ttl: int = TASK_DEFAULT_TTL, use_sequential_id: bool = False,
               task_timeout: int = None, retry_on_failure: bool = True, max_retries: int = 3):
    """
    任务去重装饰器，确保同一参数的函数只执行一次
    
    Args:
        task_name: 任务名称，默认使用函数名
        ttl: 任务结果保留时间（秒）
        use_sequential_id: 是否使用顺序递增ID，适用于需要按执行顺序排序的任务
        task_timeout: 任务超时时间（秒）
        retry_on_failure: 是否在失败时重试
        max_retries: 最大重试次数
    """
    def decorator(func):
        # 获取原始函数的签名
        sig = inspect.signature(func)
        _task_name = task_name or func.__name__
        
        # 确定函数类型
        is_async = asyncio.iscoroutinefunction(func)
        
        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 使用全局任务管理器实例，避免重复创建连接
                try:
                    # 运行并获取结果
                    task_id, result = await task_manager.run_once(
                        _task_name, func, *args, ttl=ttl, use_sequential_id=use_sequential_id,
                        task_timeout=task_timeout, retry_on_failure=retry_on_failure,
                        max_retries=max_retries, **kwargs
                    )
                    return result
                except Exception as e:
                    logger.error(f"任务执行失败: {str(e)}")
                    raise
            return async_wrapper
        else:
            @wraps(func)
            async def sync_wrapper(*args, **kwargs):
                # 使用全局任务管理器实例，避免重复创建连接
                
                # 将同步函数包装为异步
                async def run_sync():
                    return func(*args, **kwargs)
                
                try:
                    # 运行并获取结果
                    task_id, result = await task_manager.run_once(
                        _task_name, run_sync, ttl=ttl, use_sequential_id=use_sequential_id,
                        task_timeout=task_timeout, retry_on_failure=retry_on_failure,
                        max_retries=max_retries
                    )
                    return result
                except Exception as e:
                    logger.error(f"任务执行失败: {str(e)}")
                    raise
            return sync_wrapper
        
    return decorator

# 全局任务管理器实例
task_manager = TaskManager()

# 单例访问函数
async def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global task_manager
    if task_manager._redis is None:
        try:
            await task_manager.connect()
        except Exception as e:
            logger.error(f"任务管理器连接失败: {str(e)}")
            # 失败时仍然返回实例，但可能无法正常工作
    return task_manager 