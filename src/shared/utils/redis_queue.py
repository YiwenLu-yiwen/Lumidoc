"""
Redis队列工具
提供基于Redis的异步消息队列实现
"""

import json
import uuid
import time
import asyncio
import traceback
import redis.asyncio as aioredis
from typing import Dict, Any, Optional, List, Callable, Awaitable, Union
from datetime import datetime, timedelta

import logging
logger = logging.getLogger(__name__)

class RedisQueue:
    """Redis消息队列客户端"""
    
    def __init__(
        self,
        queue_name: str = "default_queue",
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        db: int = 0,
        namespace: str = "queue",
    ):
        """
        初始化Redis队列
        
        Args:
            queue_name: 队列名称
            host: Redis主机地址，默认使用环境变量REDIS_HOST
            port: Redis端口，默认使用环境变量REDIS_PORT
            password: Redis密码，默认使用环境变量REDIS_PASSWORD
            db: Redis数据库索引
            namespace: 队列命名空间
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.password = password or os.getenv("REDIS_PASSWORD", "")
        self.db = db
        self.namespace = namespace
        self.queue_name = queue_name
        self.redis = None
        self.full_queue_name = f"{namespace}:{queue_name}" if namespace else queue_name
        
    async def connect(self) -> None:
        """连接到Redis服务器"""
        if self.redis is None:
            try:
                connection_string = f"redis://{self.host}:{self.port}/{self.db}"
                if self.password:
                    connection_string = f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
                
                self.redis = await aioredis.from_url(
                    connection_string,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info(f"已连接到Redis: {self.host}:{self.port}, 队列: {self.full_queue_name}")
            except Exception as e:
                logger.error(f"Redis连接失败: {str(e)}")
                raise
    
    async def disconnect(self) -> None:
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
            self.redis = None
            logger.info("已断开Redis连接")
    
    async def ensure_connection(self) -> None:
        """确保Redis连接有效"""
        if self.redis is None:
            await self.connect()
    
    async def enqueue(self, message: Union[Dict[str, Any], str], message_id: Optional[str] = None) -> str:
        """
        将消息加入队列
        
        Args:
            message: 消息内容(字典或字符串)
            message_id: 消息ID，如不提供则自动生成
            
        Returns:
            str: 消息ID
        """
        await self.ensure_connection()
        
        if message_id is None:
            message_id = str(uuid.uuid4())
            
        # 序列化消息
        if isinstance(message, dict):
            message_data = json.dumps(message)
        else:
            message_data = message
            
        # 将消息存入哈希表，便于查询状态
        task_key = f"{self.namespace}:tasks:{message_id}"
        await self.redis.hset(task_key, mapping={
            "id": message_id,
            "data": message_data,
            "status": "pending",
            "queue": self.queue_name,
            "created_at": await self.redis.time()
        })
        
        # 消息ID加入队列
        await self.redis.lpush(self.full_queue_name, message_id)
        logger.debug(f"消息已入队: {message_id}")
        
        return message_id
    
    async def dequeue(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        从队列取出消息
        
        Args:
            timeout: 等待超时(秒)，0表示立即返回，负值表示无限等待
            
        Returns:
            Optional[Dict[str, Any]]: 消息内容，队列为空时返回None
        """
        await self.ensure_connection()
        
        # 从队列右侧取出消息ID(阻塞等待)
        if timeout == 0:
            message_id = await self.redis.rpop(self.full_queue_name)
        else:
            result = await self.redis.brpop(self.full_queue_name, timeout)
            message_id = result[1] if result else None
            
        if not message_id:
            return None
            
        # 从哈希表获取完整消息
        task_key = f"{self.namespace}:tasks:{message_id}"
        task_data = await self.redis.hgetall(task_key)
        
        if not task_data:
            logger.warning(f"找不到消息数据: {message_id}")
            return None
            
        # 更新任务状态
        await self.redis.hset(task_key, "status", "processing")
        await self.redis.hset(task_key, "started_at", await self.redis.time())
        
        # 尝试解析JSON数据
        try:
            message_data = json.loads(task_data.get("data", "{}"))
        except json.JSONDecodeError:
            message_data = task_data.get("data")
            
        return {
            "id": message_id,
            "data": message_data,
            "status": "processing",
            "queue": self.queue_name,
            "created_at": task_data.get("created_at")
        }
    
    async def update_task_status(self, task_id: str, status: str, result: Optional[Any] = None, error: Optional[str] = None) -> bool:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态(completed/failed)
            result: 处理结果
            error: 错误信息
            
        Returns:
            bool: 是否成功更新
        """
        await self.ensure_connection()
        
        task_key = f"{self.namespace}:tasks:{task_id}"
        exists = await self.redis.exists(task_key)
        
        if not exists:
            logger.warning(f"找不到任务: {task_id}")
            return False
            
        update_data = {
            "status": status,
            "updated_at": await self.redis.time()
        }
        
        if status == "completed" and result is not None:
            if isinstance(result, dict):
                update_data["result"] = json.dumps(result)
            else:
                update_data["result"] = str(result)
                
        if status == "failed" and error:
            update_data["error"] = error
            
        await self.redis.hset(task_key, mapping=update_data)
        logger.debug(f"任务状态已更新: {task_id} => {status}")
        
        return True
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 任务状态信息
        """
        await self.ensure_connection()
        
        task_key = f"{self.namespace}:tasks:{task_id}"
        task_data = await self.redis.hgetall(task_key)
        
        if not task_data:
            return None
            
        # 尝试解析结果JSON
        if "result" in task_data:
            try:
                task_data["result"] = json.loads(task_data["result"])
            except (json.JSONDecodeError, TypeError):
                pass
                
        return task_data
    
    async def clear_queue(self) -> int:
        """
        清空队列
        
        Returns:
            int: 清除的消息数量
        """
        await self.ensure_connection()
        
        # 获取队列中所有消息ID
        message_ids = await self.redis.lrange(self.full_queue_name, 0, -1)
        
        # 删除相关任务数据
        pipeline = self.redis.pipeline()
        for message_id in message_ids:
            task_key = f"{self.namespace}:tasks:{message_id}"
            pipeline.delete(task_key)
            
        # 清空队列
        pipeline.delete(self.full_queue_name)
        
        # 执行
        results = await pipeline.execute()
        cleared_count = len(message_ids)
        
        logger.info(f"队列已清空: {self.full_queue_name}, 移除了 {cleared_count} 条消息")
        return cleared_count 