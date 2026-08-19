"""
任务监控服务
用于实时监控任务执行状态，检测异常并处理任务失败
"""

import asyncio
import logging
from typing import Dict, Any, List
import os
from datetime import datetime
import signal

from src.shared.task_manager import TaskStatus, get_task_manager

# 配置日志
logger = logging.getLogger(__name__)

# 监控配置
MONITOR_INTERVAL = int(os.environ.get("TASK_MONITOR_INTERVAL", "60"))  # 监控间隔(秒)
MAX_TASK_AGE = int(os.environ.get("MAX_TASK_AGE", "86400"))  # 最大任务保留时间(秒)
STALL_THRESHOLD = int(os.environ.get("TASK_STALL_THRESHOLD", "3600"))  # 任务卡住阈值(秒)
AUTO_RESET_STALLED = os.environ.get("AUTO_RESET_STALLED", "true").lower() == "true"  # 是否自动重置卡住任务

class TaskMonitor:
    """任务监控服务，监控任务执行状态"""
    
    def __init__(self):
        """初始化任务监控器"""
        self._task_manager = None
        self._monitor_task = None
        self._cleanup_task = None
        self._is_running = False
        self._stats = {
            "start_time": datetime.now().isoformat(),
            "monitored_cycles": 0,
            "cleanup_cycles": 0,
            "detected_issues": 0,
            "auto_fixed_issues": 0,
            "reported_issues": 0,
            "last_cycle": None
        }
        
    async def connect(self):
        """连接到任务管理器"""
        self._task_manager = await get_task_manager()
        
    async def start(self):
        """启动监控服务"""
        if not self._task_manager:
            await self.connect()
            
        self._is_running = True
        
        # 启动监控循环
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # 启动清理循环
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("任务监控服务已启动")
        
    async def stop(self):
        """停止监控服务"""
        self._is_running = False
        
        # 取消监控任务
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            
        logger.info("任务监控服务已停止")
        
    async def _monitor_loop(self):
        """监控循环，定期检查任务状态"""
        while self._is_running:
            try:
                self._stats["monitored_cycles"] += 1
                self._stats["last_cycle"] = datetime.now().isoformat()
                
                # 执行监控检查
                try:
                    issues = await self._check_tasks()
                    self._stats["detected_issues"] += len(issues)
                    
                    # 处理发现的问题
                    fixed = await self._handle_issues(issues)
                    self._stats["auto_fixed_issues"] += fixed
                    self._stats["reported_issues"] += len(issues) - fixed
                except Exception as e:
                    logger.error(f"任务监控检查失败: {str(e)}")
                
                # 等待下一个监控周期
                await asyncio.sleep(MONITOR_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务监控出错: {str(e)}")
                await asyncio.sleep(MONITOR_INTERVAL)
                
    async def _cleanup_loop(self):
        """清理循环，定期清理过期任务"""
        # 清理间隔比监控间隔长一点
        cleanup_interval = MONITOR_INTERVAL * 4
        while self._is_running:
            try:
                self._stats["cleanup_cycles"] += 1
                
                # 执行清理
                try:
                    cleaned = await self._task_manager.cleanup_expired_tasks(max_age_days=MAX_TASK_AGE//86400)
                    logger.info(f"清理了 {cleaned} 个过期任务")
                except Exception as inner_e:
                    logger.error(f"任务清理操作失败: {str(inner_e)}")
                    cleaned = 0
                
                # 等待下一个清理周期
                await asyncio.sleep(cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务清理出错: {str(e)}")
                await asyncio.sleep(cleanup_interval)
    
    async def _check_tasks(self) -> List[Dict[str, Any]]:
        """
        检查任务状态，发现问题
        
        Returns:
            List[Dict[str, Any]]: 问题列表
        """
        issues = []
        now = datetime.now()
        
        try:
            # 获取所有运行中的任务
            running_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.RUNNING)
            
            # 确保运行中任务是一个列表
            if not isinstance(running_tasks, list):
                logger.warning(f"运行中任务返回类型错误，预期列表但获得: {type(running_tasks)}")
                running_tasks = list(running_tasks) if hasattr(running_tasks, '__iter__') else []
            
            # 处理运行中任务
            for task in running_tasks:
                if not isinstance(task, dict):
                    continue
                    
                task_id = task.get("task_id")
                created_at = task.get("created_at")
                updated_at = task.get("updated_at", created_at)
                
                if not updated_at:
                    continue
                    
                try:
                    # 计算任务运行时间
                    last_update = datetime.fromisoformat(updated_at)
                    time_since_update = (now - last_update).total_seconds()
                    
                    # 检查任务是否卡住
                    if time_since_update > STALL_THRESHOLD:
                        issues.append({
                            "type": "stalled_task",
                            "task_id": task_id,
                            "task_name": task.get("task_name"),
                            "time_since_update": time_since_update,
                            "threshold": STALL_THRESHOLD
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"处理运行中任务 {task_id} 时出错: {str(e)}")
                    
            # 检查失败的任务是否需要重试
            failed_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.FAILED)
            
            # 确保失败任务是一个列表
            if not isinstance(failed_tasks, list):
                logger.warning(f"失败任务返回类型错误，预期列表但获得: {type(failed_tasks)}")
                failed_tasks = list(failed_tasks) if hasattr(failed_tasks, '__iter__') else []
            
            # 处理失败任务
            for task in failed_tasks:
                if not isinstance(task, dict):
                    continue
                    
                task_id = task.get("task_id")
                retry_count = task.get("retry_count", 0)
                max_retries = task.get("max_retries", 3)
                
                # 如果任务可以重试
                if retry_count < max_retries:
                    issues.append({
                        "type": "retriable_failure",
                        "task_id": task_id,
                        "task_name": task.get("task_name"),
                        "retry_count": retry_count,
                        "max_retries": max_retries,
                        "error": task.get("error")
                    })
            
            # 检查超时任务
            timeout_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.TIMEOUT)
            
            # 确保超时任务是一个列表
            if not isinstance(timeout_tasks, list):
                logger.warning(f"超时任务返回类型错误，预期列表但获得: {type(timeout_tasks)}")
                timeout_tasks = list(timeout_tasks) if hasattr(timeout_tasks, '__iter__') else []
            
            # 处理超时任务
            for task in timeout_tasks:
                if not isinstance(task, dict):
                    continue
                    
                task_id = task.get("task_id")
                retry_count = task.get("retry_count", 0)
                max_retries = task.get("max_retries", 3)
                
                # 如果任务可以重试
                if retry_count < max_retries:
                    issues.append({
                        "type": "timeout_task",
                        "task_id": task_id,
                        "task_name": task.get("task_name"),
                        "retry_count": retry_count,
                        "max_retries": max_retries
                    })
        except Exception as e:
            logger.error(f"检查任务状态时出错: {str(e)}")
            
        return issues
        
    async def _handle_issues(self, issues: List[Dict[str, Any]]) -> int:
        """
        处理发现的问题
        
        Args:
            issues: 问题列表
            
        Returns:
            int: 修复的问题数量
        """
        fixed_count = 0
        
        for issue in issues:
            issue_type = issue.get("type")
            task_id = issue.get("task_id")
            
            if issue_type == "stalled_task" and AUTO_RESET_STALLED:
                # 处理卡住的任务
                try:
                    time_since_update = issue.get("time_since_update", 0)
                    # 根据卡住时间长短决定处理方式
                    if time_since_update > STALL_THRESHOLD * 3:
                        # 卡住时间过长，直接标记为失败
                        await self._task_manager.update_task_status(
                            task_id,
                            TaskStatus.FAILED,
                            error=f"任务执行卡住，超过 {time_since_update//60} 分钟无响应"
                        )
                        logger.warning(f"已将卡住的任务 {task_id} 标记为失败")
                    else:
                        # 重置为待处理状态
                        await self._task_manager.update_task_status(
                            task_id,
                            TaskStatus.PENDING,
                            error="任务执行卡住，已重置为待处理状态"
                        )
                        logger.info(f"已重置卡住的任务 {task_id}")
                    fixed_count += 1
                except Exception as e:
                    logger.error(f"处理卡住任务 {task_id} 时出错: {str(e)}")
            
            elif issue_type in ("retriable_failure", "timeout_task"):
                # 处理可重试的失败或超时任务
                try:
                    # 将任务重置为待处理状态
                    await self._task_manager.update_task_status(
                        task_id,
                        TaskStatus.PENDING,
                        error=f"自动重试 (第{issue.get('retry_count', 0)+1}/{issue.get('max_retries', 3)}次)"
                    )
                    logger.info(f"已将任务 {task_id} 重置为待处理状态，等待重试")
                    fixed_count += 1
                except Exception as e:
                    logger.error(f"处理失败任务 {task_id} 时出错: {str(e)}")
                    
        return fixed_count
        
    def get_stats(self) -> Dict[str, Any]:
        """
        获取监控统计数据
        
        Returns:
            Dict[str, Any]: 监控统计
        """
        return {
            **self._stats,
            "uptime_seconds": (datetime.now() - datetime.fromisoformat(self._stats["start_time"])).total_seconds(),
            "is_running": self._is_running
        }
        
# 全局任务监控器实例
_task_monitor = None

async def get_task_monitor() -> TaskMonitor:
    """
    获取全局任务监控器实例
    
    Returns:
        TaskMonitor: 任务监控器
    """
    global _task_monitor
    if _task_monitor is None:
        _task_monitor = TaskMonitor()
        await _task_monitor.start()
    return _task_monitor

async def run_monitor_service():
    """
    运行任务监控服务
    """
    # 设置信号处理
    loop = asyncio.get_running_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    monitor = await get_task_monitor()
    
    print(f"任务监控服务已启动，间隔 {MONITOR_INTERVAL} 秒")
    print("按 Ctrl+C 停止服务")
    
    try:
        # 保持运行，直到收到终止信号
        while True:
            await asyncio.sleep(10)
            stats = monitor.get_stats()
            print(f"监控周期: {stats['monitored_cycles']}, "
                  f"检测问题: {stats['detected_issues']}, "
                  f"自动修复: {stats['auto_fixed_issues']}")
    except asyncio.CancelledError:
        pass
        
async def shutdown():
    """
    优雅关闭服务
    """
    print("\n正在关闭任务监控服务...")
    global _task_monitor
    if _task_monitor:
        await _task_monitor.stop()
        _task_monitor = None
        
    # 退出程序
    loop = asyncio.get_running_loop()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    # 取消所有任务
    for task in tasks:
        task.cancel()
    
    # 等待所有任务完成
    if tasks:
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
    
    # 停止事件循环
    loop.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run_monitor_service())
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在关闭服务...")
    except RuntimeError as e:
        if "Event loop stopped before Future completed" in str(e):
            # 这是预期的行为，可以忽略
            pass
        else:
            print(f"运行时错误: {e}") 