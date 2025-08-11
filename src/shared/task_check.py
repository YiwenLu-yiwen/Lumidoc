"""
任务系统诊断工具
提供任务执行状态检查和故障排除功能
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import os
import time
from datetime import datetime, timedelta

from src.shared.task_manager import TaskManager, TaskStatus, get_task_manager
from src.shared.service_discovery import get_service_client

# 配置日志
logger = logging.getLogger(__name__)

class TaskDiagnostics:
    """任务诊断工具，用于排查任务执行问题"""
    
    def __init__(self):
        """初始化任务诊断工具"""
        self._task_manager = None
        
    async def connect(self):
        """连接到任务管理器"""
        self._task_manager = await get_task_manager()
        
    async def close(self):
        """关闭连接"""
        # 全局任务管理器由服务管理，不需要在这里关闭
        self._task_manager = None
        
    async def get_task_summary(self) -> Dict[str, Any]:
        """
        获取任务系统摘要信息
        
        Returns:
            Dict[str, Any]: 任务摘要数据
        """
        if not self._task_manager:
            await self.connect()
            
        # 获取所有任务
        all_tasks = await self._task_manager.get_active_tasks()
        
        # 按状态分组
        status_counts = {
            TaskStatus.PENDING: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
            TaskStatus.CANCELLED: 0,
            TaskStatus.DUPLICATE: 0,
            TaskStatus.TIMEOUT: 0,
            "unknown": 0
        }
        
        # 收集任务类型
        task_types = {}
        
        # 查找最近失败的任务
        recent_failures = []
        
        # 分析任务
        for task in all_tasks:
            # 统计状态
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # 统计任务类型
            task_name = task.get("task_name", "unknown")
            if task_name not in task_types:
                task_types[task_name] = 0
            task_types[task_name] += 1
            
            # 收集最近失败的任务
            if status == TaskStatus.FAILED:
                # 获取更新时间或创建时间
                updated_at = task.get("updated_at", task.get("created_at"))
                if updated_at:
                    try:
                        update_time = datetime.fromisoformat(updated_at)
                        # 如果是一天内失败的任务
                        if datetime.now() - update_time < timedelta(days=1):
                            recent_failures.append({
                                "task_id": task.get("task_id"),
                                "task_name": task_name,
                                "error": task.get("error", "未知错误"),
                                "time": updated_at
                            })
                    except (ValueError, TypeError):
                        pass
        
        # 对最近失败的任务按时间排序，最近的在前
        recent_failures.sort(key=lambda x: x.get("time", ""), reverse=True)
        # 只保留最近的10个
        recent_failures = recent_failures[:10]
        
        return {
            "total_tasks": len(all_tasks),
            "status_counts": status_counts,
            "task_types": task_types,
            "recent_failures": recent_failures,
            "timestamp": datetime.now().isoformat()
        }
    
    async def find_task_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        查找任务系统中的瓶颈
        
        Returns:
            List[Dict[str, Any]]: 瓶颈信息列表
        """
        if not self._task_manager:
            await self.connect()
            
        bottlenecks = []
        
        # 检查长时间处于RUNNING状态的任务
        running_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.RUNNING)
        now = datetime.now()
        
        for task in running_tasks:
            # 获取任务开始时间
            created_at = task.get("created_at")
            if not created_at:
                continue
                
            try:
                start_time = datetime.fromisoformat(created_at)
                running_duration = now - start_time
                
                # 如果任务运行超过30分钟，可能是卡住了
                if running_duration > timedelta(minutes=30):
                    bottlenecks.append({
                        "type": "long_running_task",
                        "task_id": task.get("task_id"),
                        "task_name": task.get("task_name"),
                        "running_time": str(running_duration),
                        "severity": "high" if running_duration > timedelta(hours=2) else "medium"
                    })
            except (ValueError, TypeError):
                pass
        
        # 检查任务积压情况
        pending_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.PENDING)
        
        # 按任务类型分组
        task_types = {}
        for task in pending_tasks:
            task_name = task.get("task_name", "unknown")
            if task_name not in task_types:
                task_types[task_name] = []
            task_types[task_name].append(task)
            
        # 检查每种任务类型的积压
        for task_name, tasks in task_types.items():
            if len(tasks) > 10:  # 如果某种任务积压超过10个
                bottlenecks.append({
                    "type": "task_backlog",
                    "task_name": task_name,
                    "count": len(tasks),
                    "oldest_task": min([t.get("created_at", "9999") for t in tasks]),
                    "severity": "high" if len(tasks) > 50 else "medium"
                })
                
        # 检查失败任务的模式
        failed_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.FAILED)
        
        # 分析错误模式
        error_patterns = {}
        for task in failed_tasks:
            error = task.get("error", "")
            # 简化错误消息，只取前50个字符作为模式
            pattern = error[:50]
            if pattern not in error_patterns:
                error_patterns[pattern] = []
            error_patterns[pattern].append(task.get("task_id"))
            
        # 检查重复出现的错误模式
        for pattern, task_ids in error_patterns.items():
            if len(task_ids) > 3:  # 如果同一错误模式出现超过3次
                bottlenecks.append({
                    "type": "recurring_error",
                    "error_pattern": pattern,
                    "count": len(task_ids),
                    "task_ids": task_ids[:5],  # 只包含前5个任务ID
                    "severity": "high" if len(task_ids) > 10 else "medium"
                })
                
        return bottlenecks
    
    async def detect_duplicate_tasks(self) -> List[Dict[str, Any]]:
        """
        检测重复的任务
        
        Returns:
            List[Dict[str, Any]]: 重复任务组列表
        """
        if not self._task_manager:
            await self.connect()
            
        all_tasks = await self._task_manager.get_active_tasks()
        
        # 按内容哈希分组
        content_hash_groups = {}
        
        for task in all_tasks:
            content_hash = task.get("content_hash")
            if not content_hash:
                continue
                
            if content_hash not in content_hash_groups:
                content_hash_groups[content_hash] = []
                
            content_hash_groups[content_hash].append({
                "task_id": task.get("task_id"),
                "task_name": task.get("task_name"),
                "status": task.get("status"),
                "created_at": task.get("created_at"),
                "created_by": task.get("created_by")
            })
            
        # 找出有重复的任务组
        duplicates = []
        
        for content_hash, tasks in content_hash_groups.items():
            if len(tasks) > 1:  # 有重复
                # 按创建时间排序
                tasks.sort(key=lambda x: x.get("created_at", ""))
                
                # 只记录非DUPLICATE状态的重复任务
                non_duplicate_tasks = [t for t in tasks if t.get("status") != TaskStatus.DUPLICATE]
                if len(non_duplicate_tasks) > 1:
                    duplicates.append({
                        "content_hash": content_hash,
                        "task_name": tasks[0].get("task_name"),
                        "duplicate_count": len(tasks),
                        "tasks": tasks
                    })
                    
        # 按重复数量排序
        duplicates.sort(key=lambda x: x["duplicate_count"], reverse=True)
        
        return duplicates
    
    async def repair_tasks(self) -> Dict[str, Any]:
        """
        尝试修复常见的任务问题
        
        Returns:
            Dict[str, Any]: 修复结果
        """
        if not self._task_manager:
            await self.connect()
            
        results = {
            "cleaned_expired": 0,
            "marked_duplicates": 0,
            "reset_stalled": 0,
            "failed_attempts": 0
        }
        
        try:
            # 1. 清理过期任务
            cleaned = await self._task_manager.cleanup_expired_tasks()
            results["cleaned_expired"] = cleaned
            
            # 2. 标记重复任务
            duplicates = await self.detect_duplicate_tasks()
            for duplicate_group in duplicates:
                tasks = duplicate_group["tasks"]
                if len(tasks) <= 1:
                    continue
                    
                # 第一个任务为原始任务，其他为副本
                original_task_id = tasks[0]["task_id"]
                
                for i in range(1, len(tasks)):
                    duplicate_task_id = tasks[i]["task_id"]
                    # 将副本标记为重复
                    try:
                        await self._task_manager.update_task_status(
                            duplicate_task_id,
                            TaskStatus.DUPLICATE,
                            result={"original_task_id": original_task_id}
                        )
                        results["marked_duplicates"] += 1
                    except Exception:
                        results["failed_attempts"] += 1
                        
            # 3. 重置卡住的任务
            running_tasks = await self._task_manager.get_active_tasks(status=TaskStatus.RUNNING)
            now = datetime.now()
            
            for task in running_tasks:
                created_at = task.get("created_at")
                if not created_at:
                    continue
                    
                try:
                    start_time = datetime.fromisoformat(created_at)
                    running_duration = now - start_time
                    
                    # 如果任务运行超过2小时，可能已经卡住
                    if running_duration > timedelta(hours=2):
                        # 重置为待处理状态
                        await self._task_manager.update_task_status(
                            task.get("task_id"),
                            TaskStatus.PENDING,
                            error="任务处理时间过长，已重置"
                        )
                        results["reset_stalled"] += 1
                except (ValueError, TypeError, Exception):
                    results["failed_attempts"] += 1
                    
            return results
        except Exception as e:
            logger.error(f"修复任务时出错: {str(e)}")
            results["error"] = str(e)
            return results

async def check_task_system():
    """
    执行任务系统检查并打印报告
    """
    diagnostics = TaskDiagnostics()
    
    try:
        await diagnostics.connect()
        
        # 获取任务摘要
        print("\n======== 任务系统状态报告 ========")
        summary = await diagnostics.get_task_summary()
        print(f"任务总数: {summary['total_tasks']}")
        print("\n状态分布:")
        for status, count in summary['status_counts'].items():
            if count > 0:
                print(f"  {status}: {count}")
        
        print("\n任务类型:")
        for task_type, count in summary['task_types'].items():
            print(f"  {task_type}: {count}")
            
        print("\n最近失败的任务:")
        for failure in summary['recent_failures']:
            print(f"  {failure['task_name']} ({failure['task_id']}): {failure['error']}")
            
        # 检查瓶颈
        print("\n======== 系统瓶颈分析 ========")
        bottlenecks = await diagnostics.find_task_bottlenecks()
        if bottlenecks:
            for bottleneck in bottlenecks:
                if bottleneck['type'] == 'long_running_task':
                    print(f"长时间运行的任务: {bottleneck['task_name']} ({bottleneck['task_id']})")
                    print(f"  运行时间: {bottleneck['running_time']}")
                    print(f"  严重程度: {bottleneck['severity']}")
                elif bottleneck['type'] == 'task_backlog':
                    print(f"任务积压: {bottleneck['task_name']} - {bottleneck['count']}个待处理")
                    print(f"  最早任务: {bottleneck['oldest_task']}")
                    print(f"  严重程度: {bottleneck['severity']}")
                elif bottleneck['type'] == 'recurring_error':
                    print(f"重复错误模式: {bottleneck['error_pattern']}")
                    print(f"  影响任务数: {bottleneck['count']}")
                    print(f"  严重程度: {bottleneck['severity']}")
        else:
            print("未发现明显的系统瓶颈")
            
        # 检查重复任务
        print("\n======== 重复任务分析 ========")
        duplicates = await diagnostics.detect_duplicate_tasks()
        if duplicates:
            print(f"发现{len(duplicates)}组重复任务:")
            for i, group in enumerate(duplicates[:5]):  # 只显示前5组
                print(f"组 {i+1}: {group['task_name']} - {group['duplicate_count']}个实例")
                for task in group['tasks'][:3]:  # 只显示每组前3个
                    print(f"  {task['task_id']} ({task['status']}) - {task['created_at']}")
                if len(group['tasks']) > 3:
                    print(f"  ... 等{len(group['tasks'])-3}个其他实例")
        else:
            print("未发现重复任务")
            
        # 是否执行修复
        print("\n是否执行自动修复? (将清理过期任务、标记重复任务并重置卡住的任务)")
        print("自动修复功能可以通过环境变量 AUTO_REPAIR_TASKS=true 自动执行")
        
        auto_repair = os.environ.get("AUTO_REPAIR_TASKS", "").lower() == "true"
        if auto_repair:
            print("正在执行自动修复...")
            repair_results = await diagnostics.repair_tasks()
            print("修复完成:")
            print(f"  清理过期任务: {repair_results['cleaned_expired']}")
            print(f"  标记重复任务: {repair_results['marked_duplicates']}")
            print(f"  重置卡住任务: {repair_results['reset_stalled']}")
            print(f"  失败尝试: {repair_results['failed_attempts']}")
        
    finally:
        await diagnostics.close()

if __name__ == "__main__":
    asyncio.run(check_task_system()) 