"""
文件服务模块
"""

# 更新导出的服务列表，移除已迁移到fileproc的服务
__all__ = [
    'FileService',
    'process_file', 
    'get_task_progress', 
    'get_task_result'
]

from .file_processor_service import FileProcessorService as FileService
from .tasks import process_file, get_task_progress, get_task_result