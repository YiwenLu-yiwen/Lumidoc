#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
集成LightRAG的图可视化工具到项目中
"""

import os
import asyncio
import json
import networkx as nx
import importlib
import sys
import platform
import psutil
from pathlib import Path
import logging
import shutil
import threading
import time
import functools
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union, TYPE_CHECKING, Callable, NamedTuple
import warnings

# 更新配置导入
from ..config.config import settings

# 类型检查时导入
if TYPE_CHECKING:
    from lightrag import LightRAG

# 导入LightRAG的相关功能
# 注意: 如需完整功能，请先安装 lightrag 包: pip install lightrag
try:
    from lightrag import LightRAG
except ImportError:
    warnings.warn("LightRAG包未安装或结构已变更，图可视化功能可能受限")
    LightRAG = None

logger = logging.getLogger(__name__)

def retry(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0, 
          exceptions: Tuple = (Exception,)):
    """
    装饰器：为函数添加自动重试功能
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 延迟时间的增长因子
        exceptions: 需要捕获的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"重试{max_retries}次后失败: {func.__name__}(), 错误: {str(e)}")
                        raise
                    
                    logger.warning(f"操作失败，将在{current_delay:.2f}秒后重试({retries}/{max_retries}): {func.__name__}(), 错误: {str(e)}")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_factor
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"重试{max_retries}次后失败: {func.__name__}(), 错误: {str(e)}")
                        raise
                    
                    logger.warning(f"操作失败，将在{current_delay:.2f}秒后重试({retries}/{max_retries}): {func.__name__}(), 错误: {str(e)}")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

class CacheItem:
    """缓存项"""
    def __init__(self, data: Any, ttl: int = 3600):
        """
        初始化缓存项
        
        Args:
            data: 缓存的数据
            ttl: 缓存有效期（秒）
        """
        self.data = data
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(seconds=ttl)
    
    def is_expired(self) -> bool:
        """检查缓存项是否过期"""
        return datetime.now() > self.expires_at

class Cache:
    """简单的内存缓存系统"""
    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存项数
            default_ttl: 默认缓存有效期（秒）
        """
        self.cache: Dict[str, CacheItem] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的数据，如果不存在或已过期则返回None
        """
        with self.lock:
            if key not in self.cache:
                return None
            
            item = self.cache[key]
            if item.is_expired():
                del self.cache[key]
                return None
            
            return item.data
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存项
        
        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 缓存有效期（秒），如果为None则使用默认值
        """
        with self.lock:
            # 如果达到最大缓存大小，删除最老的项
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = None
                oldest_time = datetime.now()
                
                for k, item in self.cache.items():
                    if item.created_at < oldest_time:
                        oldest_key = k
                        oldest_time = item.created_at
                
                if oldest_key:
                    del self.cache[oldest_key]
            
            # 设置新缓存项
            self.cache[key] = CacheItem(data, ttl or self.default_ttl)
    
    def delete(self, key: str) -> bool:
        """
        删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """清空所有缓存"""
        with self.lock:
            self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """
        清理所有过期的缓存项
        
        Returns:
            清理的缓存项数量
        """
        with self.lock:
            expired_keys = [k for k, item in self.cache.items() if item.is_expired()]
            for key in expired_keys:
                del self.cache[key]
            return len(expired_keys)

class HealthStatus(NamedTuple):
    """健康状态报告"""
    status: str  # "healthy", "degraded", "unhealthy"
    details: Dict[str, Any]
    timestamp: datetime

class ServiceStatus(NamedTuple):
    """服务状态详情"""
    uptime: float  # 运行时间（秒）
    memory_usage: Dict[str, float]  # 内存使用情况
    cache_stats: Dict[str, int]  # 缓存统计
    disk_usage: Dict[str, float]  # 磁盘使用情况

class TaskProgress:
    """任务进度跟踪器"""
    def __init__(self, task_id: str, total_steps: int = 100):
        """
        初始化进度跟踪器
        
        Args:
            task_id: 任务ID
            total_steps: 总步骤数
        """
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
        self.status = "pending"  # pending, running, completed, failed
        self.message = ""
        self.start_time = datetime.now()
        self.end_time = None
        self.error = None
    
    def update(self, step: int, message: str = ""):
        """更新进度"""
        self.current_step = min(step, self.total_steps)
        self.message = message
        if self.status == "pending":
            self.status = "running"
            
    def complete(self, message: str = "任务完成"):
        """标记任务完成"""
        self.current_step = self.total_steps
        self.status = "completed"
        self.message = message
        self.end_time = datetime.now()
        
    def fail(self, error: str):
        """标记任务失败"""
        self.status = "failed"
        self.message = f"任务失败: {error}"
        self.error = error
        self.end_time = datetime.now()
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        return (self.current_step / self.total_steps) * 100
    
    @property
    def elapsed_time(self) -> float:
        """已用时间（秒）"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "task_id": self.task_id,
            "status": self.status,
            "progress": {
                "current": self.current_step,
                "total": self.total_steps,
                "percent": self.progress_percent
            },
            "message": self.message,
            "time": {
                "start": self.start_time.isoformat(),
                "elapsed_seconds": self.elapsed_time
            }
        }
        
        if self.end_time:
            result["time"]["end"] = self.end_time.isoformat()
            
        if self.error:
            result["error"] = self.error
            
        return result

class ProgressManager:
    """进度管理器"""
    def __init__(self, max_history: int = 100):
        """
        初始化进度管理器
        
        Args:
            max_history: 最大历史记录数
        """
        self.tasks: Dict[str, TaskProgress] = {}
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self.lock = threading.RLock()
    
    def create_task(self, task_name: str, total_steps: int = 100) -> TaskProgress:
        """创建任务进度跟踪器"""
        with self.lock:
            task_id = f"{task_name}_{datetime.now().timestamp()}"
            task = TaskProgress(task_id, total_steps)
            self.tasks[task_id] = task
            return task
    
    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度跟踪器"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态"""
        with self.lock:
            return {
                task_id: task.to_dict() 
                for task_id, task in self.tasks.items()
            }
    
    def archive_task(self, task_id: str) -> bool:
        """归档已完成的任务"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
                
            if task.status in ["completed", "failed"]:
                # 添加到历史记录
                self.history.append(task.to_dict())
                
                # 如果历史记录超过上限，删除最早的记录
                while len(self.history) > self.max_history:
                    self.history.pop(0)
                    
                # 从当前任务中删除
                del self.tasks[task_id]
                return True
                
            return False
    
    def clean_old_tasks(self, max_age_hours: int = 24) -> int:
        """清理旧任务"""
        with self.lock:
            now = datetime.now()
            to_archive = []
            
            for task_id, task in self.tasks.items():
                # 如果任务已完成或失败，并且超过指定时间，则归档
                if task.status in ["completed", "failed"]:
                    if task.end_time and (now - task.end_time).total_seconds() > max_age_hours * 3600:
                        to_archive.append(task_id)
                # 如果任务正在运行，但已超过指定时间（可能卡住），则标记为失败并归档
                elif task.status == "running":
                    if (now - task.start_time).total_seconds() > max_age_hours * 3600:
                        task.fail("任务超时")
                        to_archive.append(task_id)
            
            # 归档需要清理的任务
            for task_id in to_archive:
                self.archive_task(task_id)
                
            return len(to_archive)

class GraphVisualizer:
    """
    知识图谱可视化服务，集成LightRAG的图可视化工具
    
    两种使用方式:
    1. 启动独立的3D可视化程序，使用ModernGL和ImGui
    2. 生成适用于Web前端的图谱数据，以JSON格式返回
    """
    
    # 依赖版本要求
    REQUIRED_DEPENDENCIES = {
        "networkx": ">=2.5",
        "matplotlib": ">=3.3.0",
        "imgui_bundle": ">=1.0.0",
        "moderngl": ">=5.6.0",
    }
    
    _instance = None
    _lock = threading.RLock()
    
    @classmethod
    def check_dependencies(cls) -> Dict[str, Dict[str, str]]:
        """检查依赖版本兼容性"""
        results = {
            "compatible": {},
            "incompatible": {},
            "missing": {}
        }
        
        for pkg_name, version_req in cls.REQUIRED_DEPENDENCIES.items():
            try:
                pkg = importlib.import_module(pkg_name)
                pkg_version = getattr(pkg, "__version__", "unknown")
                
                # 简单版本检查，实际应使用 packaging.version 进行正确比较
                req_version = version_req.replace(">=", "").strip()
                is_compatible = True
                
                if version_req.startswith(">="):
                    # 非常简化的版本比较，仅作示例
                    pkg_parts = pkg_version.split(".")
                    req_parts = req_version.split(".")
                    
                    for i in range(min(len(pkg_parts), len(req_parts))):
                        if int(pkg_parts[i]) < int(req_parts[i]):
                            is_compatible = False
                            break
                        elif int(pkg_parts[i]) > int(req_parts[i]):
                            break
                
                if is_compatible:
                    results["compatible"][pkg_name] = pkg_version
                else:
                    results["incompatible"][pkg_name] = {
                        "found": pkg_version,
                        "required": version_req
                    }
            except (ImportError, ModuleNotFoundError):
                results["missing"][pkg_name] = version_req
        
        return results
    
    @classmethod
    def get_instance(cls, lightrag_instance: Any = None):
        """获取单例实例（线程安全）"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(lightrag_instance)
            return cls._instance
    
    @staticmethod
    def validate_config():
        """验证配置合法性，返回验证结果和警告消息"""
        warnings_list = []
        
        # 检查临时目录配置
        if not hasattr(settings, 'temp_dir') or not settings.temp_dir:
            warnings_list.append("临时目录未配置，将使用默认目录")
        
        # 检查节点颜色映射
        if not hasattr(settings, 'node_type_colors') or not settings.node_type_colors:
            warnings_list.append("节点类型颜色映射未配置，将使用默认颜色")
        else:
            # 检查default颜色是否存在
            if 'default' not in settings.node_type_colors:
                warnings_list.append("节点类型默认颜色未配置，将使用内置默认颜色")
        
        # 检查边默认颜色
        if not hasattr(settings, 'edge_default_color') or not settings.edge_default_color:
            warnings_list.append("边默认颜色未配置，将使用内置默认颜色")
            
        # 返回验证结果和警告列表
        is_valid = len(warnings_list) == 0
        return is_valid, warnings_list
    
    def __init__(self, lightrag_instance: Any = None):
        """
        初始化图可视化服务
        
        Args:
            lightrag_instance: 可选的LightRAG实例，如果提供则直接使用该实例的图谱数据
        """
        # 使用双检锁确保只有一个实例
        with self.__class__._lock:
            # 验证配置
            _, warnings_list = self.validate_config()
            for warning in warnings_list:
                logger.warning(f"配置警告: {warning}")
            
            # 检查依赖版本
            dep_check = self.__class__.check_dependencies()
            if dep_check["incompatible"]:
                for pkg, details in dep_check["incompatible"].items():
                    logger.warning(f"依赖版本不兼容: {pkg} {details['found']} (需要 {details['required']})")
            
            if dep_check["missing"]:
                for pkg, version in dep_check["missing"].items():
                    logger.warning(f"缺少依赖: {pkg} {version}")
            
            # 设置默认配置值
            self.node_type_colors = getattr(settings, 'node_type_colors', {
                "Person": "#1f77b4",
                "Organization": "#ff7f0e",
                "Concept": "#2ca02c",
                "Event": "#d62728",
                "Location": "#9467bd",
                "Product": "#8c564b",
                "Document": "#e377c2",
                "default": "#7f7f7f"
            })
            
            # 确保default颜色存在
            if 'default' not in self.node_type_colors:
                self.node_type_colors['default'] = "#7f7f7f"
                
            self.edge_default_color = getattr(settings, 'edge_default_color', "#999")
            
            # 初始化缓存
            cache_ttl = getattr(settings, 'cache_ttl', 3600)
            cache_max_size = getattr(settings, 'cache_max_size', 100)
            self.cache = Cache(max_size=cache_max_size, default_ttl=cache_ttl)
            
            # 定期清理缓存的任务
            self._cleanup_task = None
            self._setup_cache_cleanup()
            
        self.lightrag = lightrag_instance
        self.graph_data = None
        self.working_dir = getattr(settings, 'temp_dir', "./temp")
        self.working_dir = os.path.join(self.working_dir, "graph_visualizer")
        self._setup_working_dir()
        self._closed = False
        
        # 记录启动时间
        self.start_time = datetime.now()
        
        # 初始化健康状态
        self.last_health_check = None
        
        # 初始化进度管理器
        self.progress_manager = ProgressManager()
        
        # 定期清理旧任务
        self._progress_cleanup_task = None
        self._setup_progress_cleanup()

    def _setup_working_dir(self):
        """设置工作目录（内部方法）"""
        try:
            os.makedirs(self.working_dir, exist_ok=True)
            logger.debug(f"工作目录已设置: {self.working_dir}")
        except OSError as e:
            logger.warning(f"设置工作目录失败: {str(e)}")
            self.working_dir = os.path.join(os.path.expanduser("~"), ".temp_graph_visualizer")
            os.makedirs(self.working_dir, exist_ok=True)
            logger.info(f"已切换到备用工作目录: {self.working_dir}")
    
    def _setup_cache_cleanup(self):
        """设置定期缓存清理任务"""
        async def cleanup_routine():
            while not self._closed:
                try:
                    # 每小时清理一次过期缓存
                    await asyncio.sleep(3600)
                    if not self._closed:
                        count = self.cache.cleanup_expired()
                        if count > 0:
                            logger.debug(f"已清理{count}个过期缓存项")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"缓存清理任务异常: {str(e)}")
        
        # 启动异步清理任务
        try:
            loop = asyncio.get_event_loop()
            self._cleanup_task = loop.create_task(cleanup_routine())
        except RuntimeError:
            logger.warning("无法启动异步缓存清理任务（非事件循环环境）")
    
    def _setup_progress_cleanup(self):
        """设置定期进度清理任务"""
        async def cleanup_routine():
            while not self._closed:
                try:
                    # 每天清理一次旧任务
                    await asyncio.sleep(86400)  # 24小时
                    if not self._closed:
                        count = self.progress_manager.clean_old_tasks(24)
                        if count > 0:
                            logger.debug(f"已清理{count}个旧任务")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"任务清理异常: {str(e)}")
        
        # 启动异步清理任务
        try:
            loop = asyncio.get_event_loop()
            self._progress_cleanup_task = loop.create_task(cleanup_routine())
        except RuntimeError:
            logger.warning("无法启动异步任务清理（非事件循环环境）")
    
    def _cache_key(self, method_name: str, *args, **kwargs) -> str:
        """生成缓存键"""
        # 将参数序列化为字符串
        args_str = json.dumps(args, sort_keys=True) if args else ""
        kwargs_str = json.dumps(kwargs, sort_keys=True) if kwargs else ""
        
        # 计算哈希值
        key_data = f"{method_name}:{args_str}:{kwargs_str}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    async def close(self):
        """异步关闭资源（推荐替代析构函数）"""
        with self.__class__._lock:
            if not self._closed:
                # 取消缓存清理任务
                if self._cleanup_task and not self._cleanup_task.done():
                    self._cleanup_task.cancel()
                    try:
                        await self._cleanup_task
                    except asyncio.CancelledError:
                        pass
                
                # 清理缓存
                if hasattr(self, 'cache'):
                    self.cache.clear()
                
                # 取消进度清理任务
                if self._progress_cleanup_task and not self._progress_cleanup_task.done():
                    self._progress_cleanup_task.cancel()
                    try:
                        await self._progress_cleanup_task
                    except asyncio.CancelledError:
                        pass
                
                await self._async_cleanup()
                self._closed = True
                logger.info("图谱可视化服务已关闭")
    
    async def _async_cleanup(self):
        """异步清理资源（内部方法）"""
        # 记录所有要关闭的任务
        cleanup_tasks = []
        
        # 1. 清理临时文件
        async def async_cleanup_files():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.cleanup_temp_files)
        
        cleanup_tasks.append(async_cleanup_files())
        
        # 2. 关闭任何打开的异步连接
        # 如果有异步数据库连接或其他资源，在这里关闭
        
        # 等待所有清理任务完成
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)
            logger.debug("所有异步资源已清理完毕")
    
    def cleanup_temp_files(self):
        """清理临时文件和目录"""
        with self.__class__._lock:
            try:
                if os.path.exists(self.working_dir):
                    shutil.rmtree(self.working_dir)
                    logger.info(f"已清理临时目录: {self.working_dir}")
            except (OSError, PermissionError) as e:
                logger.warning(f"清理临时目录失败: {str(e)}")
    
    @retry(max_retries=2, exceptions=(IOError, OSError))
    async def export_to_graphml(self, 
                             project_id: str, 
                             output_path: Optional[str] = None) -> str:
        """
        将项目的知识图谱导出为GraphML格式
        
        Args:
            project_id: 项目ID
            output_path: 输出文件路径，默认为working_dir下的project_id.graphml
            
        Returns:
            导出的文件路径
        """
        if self._closed:
            raise RuntimeError("服务已关闭，无法执行操作")
            
        # 创建进度跟踪器
        task = self.progress_manager.create_task(f"export_graphml_{project_id}", 5)
        
        try:
            task.update(1, "开始导出GraphML")
            
            if output_path is None:
                os.makedirs(self.working_dir, exist_ok=True)
                output_path = os.path.join(self.working_dir, f"{project_id}.graphml")
            
            # 获取项目图谱数据
            task.update(2, "获取图谱数据")
            from .graph_service import GraphService
            graph_service = GraphService()
            graph_data = await graph_service.get_project_graph(project_id)
            
            # 转换为NetworkX格式
            task.update(3, "转换为NetworkX格式")
            G = nx.DiGraph()
            
            # 添加节点
            for node in graph_data.nodes:
                node_attrs = {
                    "label": node.label,
                    "type": node.type
                }
                
                # 添加所有属性
                if node.properties:
                    for key, value in node.properties.items():
                        if isinstance(value, (str, int, float, bool)):
                            node_attrs[key] = value
                
                G.add_node(node.id, **node_attrs)
            
            # 添加边
            for edge in graph_data.edges:
                edge_attrs = {
                    "label": edge.label
                }
                
                # 添加所有属性
                if edge.properties:
                    for key, value in edge.properties.items():
                        if isinstance(value, (str, int, float, bool)):
                            edge_attrs[key] = value
                
                G.add_edge(edge.source, edge.target, **edge_attrs)
            
            # 导出为GraphML格式
            task.update(4, "导出为GraphML格式")
            nx.write_graphml(G, output_path)
            logger.info(f"导出图谱为GraphML格式: {output_path}")
            
            task.complete(f"导出完成: {output_path}")
            return output_path
                
        except Exception as e:
            task.fail(str(e))
            logger.error(f"导出图谱失败: {str(e)}")
            raise
    
    async def launch_3d_viewer(self, project_id: str) -> None:
        """
        启动3D图可视化界面
        
        Args:
            project_id: 项目ID
        """
        if self._closed:
            raise RuntimeError("服务已关闭，无法执行操作")
            
        # 创建进度跟踪器
        task = self.progress_manager.create_task(f"launch_3d_viewer_{project_id}", 6)
        
        try:
            # 首先将图谱导出为GraphML格式
            task.update(1, "导出GraphML文件")
            graphml_path = await self.export_to_graphml(project_id)
            
            # 导入LightRAG的图可视化模块
            import sys
            import subprocess
            import importlib.util
            
            # 检查是否已安装所需依赖
            task.update(2, "检查依赖")
            required_packages = ['imgui_bundle', 'moderngl', 'networkx', 'numpy', 'pyglm', 'python-louvain']
            missing_packages = []
            
            for package in required_packages:
                if importlib.util.find_spec(package) is None:
                    missing_packages.append(package)
            
            # 如果有缺少的包，尝试安装
            if missing_packages:
                task.update(3, f"安装缺少的依赖: {', '.join(missing_packages)}")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
                except subprocess.CalledProcessError as e:
                    logger.error(f"安装依赖失败: {str(e)}")
                    raise RuntimeError(f"安装可视化依赖失败: {str(e)}")
            else:
                task.update(3, "依赖检查完成")
            
            # 检查 LightRAG 是否可用
            if LightRAG is None:
                raise ImportError("LightRAG 包未安装，无法启动可视化工具")
            
            # 启动可视化程序
            try:
                import lightrag
                lightrag_package_dir = os.path.dirname(os.path.abspath(lightrag.__file__))
                visualizer_path = os.path.join(lightrag_package_dir, "tools", "lightrag_visualizer", "graph_visualizer.py")
            except ImportError:
                raise ImportError("找不到lightrag包，请确保已安装")
            
            if not os.path.exists(visualizer_path):
                raise FileNotFoundError(f"找不到图可视化工具: {visualizer_path}")
                
            # 创建一个临时脚本来启动可视化工具
            task.update(4, "创建启动脚本")
            launcher_script = os.path.join(self.working_dir, "launch_visualizer.py")
            with open(launcher_script, 'w') as f:
                f.write(f"""
import sys
import os
import subprocess

# 设置环境变量
os.environ['LIGHTRAG_GRAPH_FILE'] = '{graphml_path}'

# 启动可视化工具
visualizer_path = '{visualizer_path}'
subprocess.run([sys.executable, visualizer_path, '{graphml_path}'])
""")
            
            # 启动可视化工具
            task.update(5, "启动可视化程序")
            logger.info(f"启动3D图可视化工具，加载GraphML文件: {graphml_path}")
            process = subprocess.Popen([sys.executable, launcher_script])
            logger.info(f"3D可视化进程已启动，PID: {process.pid}")
            
            task.complete("3D图可视化程序已启动")
            
        except ImportError as e:
            task.update(5, "尝试降级可视化")
            logger.error(f"启动3D图可视化工具失败: 缺少必要依赖: {str(e)}")
            logger.info("尝试降级到简单可视化模式...")
            
            # 降级到简单可视化：使用matplotlib
            try:
                import matplotlib.pyplot as plt
                import networkx as nx
                G = nx.read_graphml(graphml_path)
                
                # 使用spring布局绘制图谱
                plt.figure(figsize=(12, 8))
                pos = nx.spring_layout(G)
                nx.draw(G, pos, with_labels=True, node_color='skyblue', 
                        node_size=1500, edge_color='gray')
                
                # 保存为图片
                img_path = os.path.join(self.working_dir, f"{project_id}_graph.png")
                plt.savefig(img_path)
                logger.info(f"已生成简单图谱可视化图片: {img_path}")
                
                # 尝试显示图片
                try:
                    plt.show()
                except Exception:
                    logger.info("无法显示图片，但已保存到文件")
                    
                task.complete("已使用简单可视化模式")
                return
            except ImportError:
                logger.error("降级可视化也失败，无法导入matplotlib")
                raise ImportError("无法启动任何可视化工具，请安装必要依赖")
            
        except FileNotFoundError as e:
            logger.error(f"启动3D图可视化工具失败: 文件不存在: {str(e)}")
            raise FileNotFoundError(f"启动可视化工具文件错误: {str(e)}")
        except subprocess.SubprocessError as e:
            logger.error(f"启动3D图可视化工具失败: 子进程错误: {str(e)}")
            raise RuntimeError(f"启动可视化工具进程错误: {str(e)}")
        except Exception as e:
            logger.error(f"启动3D图可视化工具失败: {str(e)}")
            raise
    
    @retry(max_retries=2, exceptions=(IOError, ConnectionError))
    async def generate_web_visualization_data(self, project_id: str) -> Dict[str, Any]:
        """
        生成适用于Web前端的图谱可视化数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            包含nodes和links的字典，可直接用于前端可视化库如D3.js, ECharts等
        """
        if self._closed:
            raise RuntimeError("服务已关闭，无法执行操作")
            
        # 创建进度跟踪器
        task = self.progress_manager.create_task(f"web_visualization_{project_id}", 5)
        
        # 检查缓存
        cache_key = self._cache_key("generate_web_visualization_data", project_id)
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存中获取图谱数据: {project_id}")
            task.complete("从缓存中获取图谱数据")
            return cached_data
            
        try:
            # 获取项目图谱数据
            task.update(1, "获取图谱数据")
            from .graph_service import GraphService
            graph_service = GraphService()
            graph_data = await graph_service.get_project_graph(project_id)
            
            # 转换为Web前端可用的格式
            task.update(2, "转换为Web格式")
            web_data = {
                "nodes": [],
                "links": []
            }
            
            # 使用实例中的节点类型颜色映射
            node_type_colors = self.node_type_colors
            
            # 转换节点
            task.update(3, "处理节点数据")
            for node in graph_data.nodes:
                node_type = node.type.capitalize() if node.type else "default"
                color = node_type_colors.get(node_type, node_type_colors["default"])
                
                web_data["nodes"].append({
                    "id": node.id,
                    "name": node.label,
                    "type": node_type,
                    "symbolSize": node.properties.get("size", 20) if node.properties else 20,
                    "x": node.properties.get("x", None) if node.properties else None,
                    "y": node.properties.get("y", None) if node.properties else None,
                    "category": node_type,
                    "itemStyle": {
                        "color": node.properties.get("color", color) if node.properties else color
                    },
                    "properties": node.properties
                })
            
            # 转换边
            task.update(4, "处理边数据")
            for edge in graph_data.edges:
                web_data["links"].append({
                    "id": edge.id,
                    "source": edge.source, 
                    "target": edge.target,
                    "name": edge.label,
                    "lineStyle": {
                        "width": edge.properties.get("size", 1) if edge.properties else 1,
                        "color": edge.properties.get("color", self.edge_default_color) if edge.properties else self.edge_default_color
                    },
                    "properties": edge.properties
                })
            
            # 添加类别信息
            task.update(5, "处理类别数据")
            categories = []
            for type_name, color in node_type_colors.items():
                if type_name != "default":
                    categories.append({
                        "name": type_name,
                        "itemStyle": {
                            "color": color
                        }
                    })
            
            web_data["categories"] = categories
            
            # 缓存结果
            self.cache.set(cache_key, web_data)
            
            task.complete("生成Web可视化数据完成")
            return web_data
            
        except ImportError as e:
            logger.error(f"生成Web图可视化数据失败: 缺少必要依赖: {str(e)}")
            raise ImportError(f"生成Web图可视化数据依赖缺失: {str(e)}")
        except Exception as e:
            logger.error(f"生成Web图可视化数据失败: {str(e)}")
            raise RuntimeError(f"生成Web图可视化数据失败: {str(e)}")
    
    @retry(max_retries=2, exceptions=(ConnectionError, TimeoutError))
    async def convert_lightrag_graph_to_web_format(self, 
                                               node_label: Optional[str] = None, 
                                               max_depth: int = 3,
                                               max_nodes: int = 100) -> Dict[str, Any]:
        """
        将LightRAG的知识图谱转换为Web前端可用的格式
        
        Args:
            node_label: 开始节点的标签，如果为None则返回整个图谱
            max_depth: 最大遍历深度
            max_nodes: 最大节点数
            
        Returns:
            包含nodes和links的字典，可直接用于前端可视化库
        """
        if self._closed:
            raise RuntimeError("服务已关闭，无法执行操作")
        
        # 检查缓存
        cache_key = self._cache_key("convert_lightrag_graph_to_web_format", node_label, max_depth, max_nodes)
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存中获取LightRAG图谱数据: {node_label}")
            return cached_data
        
        # 检查 LightRAG 是否可用
        if LightRAG is None:
            logger.warning("LightRAG 未安装，无法转换图谱")
            return {"nodes": [], "links": [], "categories": []}
            
        if not self.lightrag:
            logger.warning("未提供LightRAG实例，无法转换图谱")
            return {"nodes": [], "links": [], "categories": []}
        
        try:
            # 获取知识图谱
            if node_label:
                kg = await self.lightrag.get_knowledge_graph(
                    node_label=node_label,
                    max_depth=max_depth,
                    max_nodes=max_nodes
                )
            else:
                # 获取所有图谱节点标签
                labels = await self.lightrag.get_graph_labels()
                if not labels:
                    return {"nodes": [], "links": [], "categories": []}
                    
                # 从第一个标签开始获取图谱
                kg = await self.lightrag.get_knowledge_graph(
                    node_label=labels[0],
                    max_depth=max_depth,
                    max_nodes=max_nodes
                )
            
            # 转换为Web前端可用的格式
            web_data = {
                "nodes": [],
                "links": []
            }
            
            # 使用实例中的节点类型颜色映射
            node_type_colors = self.node_type_colors
            
            # 添加节点
            for node in kg.nodes:
                node_type = node.get("entity_type", "default")
                if isinstance(node_type, list) and len(node_type) > 0:
                    node_type = node_type[0]
                
                node_type = node_type.capitalize() if node_type else "default"
                color = node_type_colors.get(node_type, node_type_colors["default"])
                
                web_data["nodes"].append({
                    "id": node.get("name", ""),
                    "name": node.get("name", ""),
                    "type": node_type,
                    "symbolSize": 20,
                    "category": node_type,
                    "itemStyle": {
                        "color": color
                    },
                    "properties": {
                        "description": node.get("description", ""),
                        "entity_type": node_type
                    }
                })
            
            # 添加边
            for edge in kg.edges:
                web_data["links"].append({
                    "source": edge.get("source", ""),
                    "target": edge.get("target", ""),
                    "name": edge.get("relation", ""),
                    "lineStyle": {
                        "width": 1,
                        "color": self.edge_default_color
                    },
                    "properties": {
                        "description": edge.get("description", ""),
                        "keywords": edge.get("keywords", "")
                    }
                })
            
            # 添加类别信息
            categories = []
            for type_name, color in node_type_colors.items():
                if type_name != "default":
                    categories.append({
                        "name": type_name,
                        "itemStyle": {
                            "color": color
                        }
                    })
            
            web_data["categories"] = categories
                
            # 缓存结果
            self.cache.set(cache_key, web_data)
            
            return web_data

        except AttributeError as e:
            logger.error(f"转换LightRAG图谱失败: API不兼容: {str(e)}")
            raise TypeError(f"LightRAG API不兼容: {str(e)}")
        except Exception as e:
            logger.error(f"转换LightRAG图谱失败: {str(e)}")
            raise RuntimeError(f"转换LightRAG图谱失败: {str(e)}")
    
    async def get_health_status(self) -> HealthStatus:
        """
        获取服务健康状态
        
        Returns:
            包含服务健康状态的结构
        """
        try:
            # 检查服务状态
            status = "healthy"
            details = {}
            
            # 1. 检查服务运行时间
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            # 2. 检查内存使用情况
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_usage = {
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "percent": process.memory_percent()
            }
            
            # 3. 检查缓存状态
            cache_stats = {
                "items": len(self.cache.cache),
                "max_size": self.cache.max_size
            }
            
            # 4. 检查磁盘使用情况
            if os.path.exists(self.working_dir):
                disk_usage = {
                    "total_mb": 0,
                    "files_count": 0
                }
                
                for dirpath, _, filenames in os.walk(self.working_dir):
                    disk_usage["files_count"] += len(filenames)
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        if os.path.exists(fp):
                            disk_usage["total_mb"] += os.path.getsize(fp) / (1024 * 1024)
            else:
                disk_usage = {"error": "工作目录不存在"}
            
            # 5. 检查依赖状态
            dependencies = self.__class__.check_dependencies()
            
            # 汇总服务状态
            service_status = ServiceStatus(
                uptime=uptime,
                memory_usage=memory_usage,
                cache_stats=cache_stats,
                disk_usage=disk_usage
            )
            
            details = {
                "service": service_status._asdict(),
                "dependencies": dependencies,
                "environment": {
                    "python_version": platform.python_version(),
                    "platform": platform.platform(),
                    "lightrag_available": LightRAG is not None
                }
            }
            
            # 根据各项指标确定健康状态
            # 如果内存使用超过80%，则降级为警告状态
            if memory_usage["percent"] > 80:
                status = "degraded"
                details["warnings"] = ["内存使用率过高"]
            
            # 如果工作目录不存在，则降级为警告状态
            if not os.path.exists(self.working_dir):
                status = "degraded"
                if "warnings" not in details:
                    details["warnings"] = []
                details["warnings"].append("工作目录不存在")
            
            # 如果有不兼容的依赖，则降级为警告状态
            if dependencies["incompatible"]:
                status = "degraded"
                if "warnings" not in details:
                    details["warnings"] = []
                details["warnings"].append("存在不兼容依赖")
            
            # 如果服务已关闭，则标记为不健康
            if self._closed:
                status = "unhealthy"
                details["errors"] = ["服务已关闭"]
            
            # 更新最后健康检查时间
            health_status = HealthStatus(
                status=status,
                details=details,
                timestamp=datetime.now()
            )
            self.last_health_check = health_status
            
            return health_status
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return HealthStatus(
                status="unhealthy",
                details={"error": str(e)},
                timestamp=datetime.now()
            )
    
    def __del__(self):
        """析构函数，清理资源"""
        # 注意：析构函数中不应运行异步代码
        # 使用同步清理
        if hasattr(self, '_closed') and not self._closed:
            self.cleanup_temp_files()
            logger.debug("图谱可视化服务资源已在析构函数中清理")

    async def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务进度
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务进度信息
        """
        task = self.progress_manager.get_task(task_id)
        if task:
            return task.to_dict()
        return None
    
    async def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有任务进度
        
        Returns:
            所有任务的进度信息
        """
        return self.progress_manager.get_all_tasks()

# 创建单例实例（兼容现有代码）
graph_visualizer = GraphVisualizer.get_instance() 