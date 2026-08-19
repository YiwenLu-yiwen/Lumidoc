"""
文件处理服务诊断模块
用于监控和诊断文件处理系统状态
"""

import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import aiohttp
import redis.asyncio as aioredis
import psycopg
import socket
import tempfile
import platform
import time

# 配置日志
from src.shared.logger import get_logger
logger = get_logger(__name__)

class FileServiceDiagnostics:
    """文件服务诊断工具，用于排查文件处理和上传相关问题"""

    def __init__(self):
        """初始化诊断服务"""
        # 初始化存储目录
        self.upload_dir = os.getenv("UPLOAD_DIR", "./uploads")

        # 初始化队列名称
        self.file_processing_queue = os.getenv("FILE_PROCESSING_QUEUE", "file_processing")

        # Redis配置
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_password = os.getenv("REDIS_PASSWORD", "")

        # PostgreSQL配置
        self.postgres_host = os.getenv("POSTGRES_HOST", "localhost")
        self.postgres_port = int(os.getenv("POSTGRES_PORT", 5432))
        self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
        self.postgres_password = os.getenv("POSTGRES_PASSWORD", "")
        self.postgres_db = os.getenv("POSTGRES_DB", "lumidoc")

        # 不再使用硬编码服务URL
        self.service_discovery_enabled = os.getenv("SERVICE_DISCOVERY_ENABLED", "true").lower() in ("true", "1", "t")

    async def get_service_url(self, service_name: str) -> str:
        """
        使用服务发现获取服务URL

        Args:
            service_name: 服务名称

        Returns:
            str: 服务URL
        """
        if not self.service_discovery_enabled:
            # 未启用服务发现，回退到环境变量配置
            env_name = f"{service_name.upper()}_SERVICE_URL"
            default_ports = {
                "file": "8004",
                "fileproc": "8005",
                "project": "8000"
            }
            default_port = default_ports.get(service_name.lower(), "8000")
            return os.getenv(env_name, f"http://localhost:{default_port}")

        try:
            # 使用服务发现获取URL
            from src.shared.service_discovery import get_service_url
            url = await get_service_url(service_name)
            if url:
                return url

            # 服务发现失败，回退到环境变量
            env_name = f"{service_name.upper()}_SERVICE_URL"
            default_ports = {
                "file": "8004",
                "fileproc": "8005",
                "project": "8000"
            }
            default_port = default_ports.get(service_name.lower(), "8000")
            return os.getenv(env_name, f"http://localhost:{default_port}")
        except Exception as e:
            logger.warning(f"服务发现获取{service_name}服务URL失败: {str(e)}")
            # 回退到环境变量
            env_name = f"{service_name.upper()}_SERVICE_URL"
            default_ports = {
                "file": "8004",
                "fileproc": "8005",
                "project": "8000"
            }
            default_port = default_ports.get(service_name.lower(), "8000")
            return os.getenv(env_name, f"http://localhost:{default_port}")

    async def check_service_health(self, service_url: str) -> Dict[str, Any]:
        """检查服务健康状态"""
        try:
            health_endpoint = f"{service_url}/health"
            async with aiohttp.ClientSession() as session:
                async with session.get(health_endpoint, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "status": data.get("status", "unknown"),
                            "details": data
                        }
                    else:
                        return {
                            "success": False,
                            "status": "error",
                            "error": f"服务健康检查失败，状态码: {response.status}"
                        }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "status": "timeout",
                "error": "服务健康检查超时"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"服务健康检查异常: {str(e)}"
            }

    async def check_redis_connection(self) -> Dict[str, Any]:
        """检查Redis连接状态"""
        try:
            # 构建Redis URL
            redis_url = "redis://"
            if self.redis_password:
                redis_url += f":{self.redis_password}@"
            redis_url += f"{self.redis_host}:{self.redis_port}/0"

            # 测试连接
            redis = await aioredis.from_url(redis_url)
            await redis.ping()

            # 检查服务注册情况
            services = await redis.keys("service:*")
            registered_services = []
            for service_key in services:
                service_data = await redis.hgetall(service_key)
                if service_data:
                    service_name = service_key.decode('utf-8').split(':')[1]
                    registered_services.append(service_name)

            await redis.close()

            return {
                "success": True,
                "status": "connected",
                "registered_services": registered_services
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"Redis连接失败: {str(e)}"
            }

    async def check_postgres_connection(self) -> Dict[str, Any]:
        """检查PostgreSQL连接状态"""
        try:
            # 构建连接字符串
            conn_str = f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

            # 测试连接
            async with await psycopg.AsyncConnection.connect(conn_str) as conn:
                async with conn.cursor() as cur:
                    # 检查文件相关表是否存在
                    await cur.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND
                              table_name IN ('file_contents', 'project_files');
                    """)
                    tables = await cur.fetchall()
                    existing_tables = [table[0] for table in tables]

                    # 获取项目文件数量
                    file_count = 0
                    if 'project_files' in existing_tables:
                        await cur.execute("SELECT COUNT(*) FROM project_files")
                        file_count = (await cur.fetchone())[0]

            return {
                "success": True,
                "status": "connected",
                "existing_tables": existing_tables,
                "file_count": file_count
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"PostgreSQL连接失败: {str(e)}"
            }

    def check_directories(self) -> Dict[str, Any]:
        """检查文件存储目录状态"""
        try:
            results = {}

            # 检查存储目录
            storage_path = Path(self.upload_dir)
            storage_exists = storage_path.exists()
            storage_is_dir = storage_path.is_dir() if storage_exists else False
            storage_writable = os.access(str(storage_path), os.W_OK) if storage_exists else False

            results["upload_dir"] = {
                "path": str(storage_path.absolute()),
                "exists": storage_exists,
                "is_directory": storage_is_dir,
                "writable": storage_writable
            }

            # 检查内容目录
            content_path = storage_path / "content"
            content_exists = content_path.exists()
            content_is_dir = content_path.is_dir() if content_exists else False
            content_writable = os.access(str(content_path), os.W_OK) if content_exists else False

            results["content_dir"] = {
                "path": str(content_path.absolute()),
                "exists": content_exists,
                "is_directory": content_is_dir,
                "writable": content_writable
            }

            # 检查文件权限和所有者
            try:
                import pwd
                import grp

                if storage_exists:
                    stat_info = os.stat(str(storage_path))
                    owner = pwd.getpwuid(stat_info.st_uid).pw_name
                    group = grp.getgrgid(stat_info.st_gid).gr_name
                    mode = oct(stat_info.st_mode)[-3:]

                    results["upload_dir"]["owner"] = owner
                    results["upload_dir"]["group"] = group
                    results["upload_dir"]["permissions"] = mode
            except Exception as e:
                logger.warning(f"获取文件权限信息失败: {str(e)}")

            return {
                "success": True,
                "directories": results
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"检查目录失败: {str(e)}"
            }

    def check_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            info = {
                "platform": platform.platform(),
                "python_version": sys.version,
                "hostname": socket.gethostname(),
                "current_dir": os.getcwd(),
                "user": os.getenv("USER", "unknown")
            }

            # 检查GPU可用性
            gpu_available = False
            gpu_info = "不可用"
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_available = True
                    gpu_info = f"可用, 设备数: {torch.cuda.device_count()}, 设备名: {torch.cuda.get_device_name(0)}"
            except ImportError:
                gpu_info = "PyTorch未安装"
            except Exception as e:
                gpu_info = f"检测失败: {str(e)}"

            info["gpu"] = {
                "available": gpu_available,
                "info": gpu_info
            }

            # 检查docling库可用性
            docling_available = False
            docling_info = "不可用"
            try:
                import docling
                docling_available = True
                docling_info = f"可用, 版本: {docling.__version__}"
            except ImportError:
                docling_info = "未安装"
            except Exception as e:
                docling_info = f"检测失败: {str(e)}"

            info["docling"] = {
                "available": docling_available,
                "info": docling_info
            }

            # 检查磁盘空间
            try:
                disk_usage = os.statvfs(os.getcwd())
                free_bytes = disk_usage.f_frsize * disk_usage.f_bavail
                total_bytes = disk_usage.f_frsize * disk_usage.f_blocks
                free_gb = free_bytes / (1024**3)
                total_gb = total_bytes / (1024**3)

                info["disk_space"] = {
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "percentage_free": round((free_bytes / total_bytes) * 100, 2)
                }
            except Exception as e:
                info["disk_space"] = {"error": str(e)}

            return {
                "success": True,
                "system_info": info
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"获取系统信息失败: {str(e)}"
            }

    async def test_file_upload(self, project_id: str, test_content: str = "测试文件内容") -> Dict[str, Any]:
        """测试文件上传"""
        try:
            # 创建临时测试文件
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
                temp.write(test_content.encode('utf-8'))
                temp_path = temp.name

            # 获取file服务URL
            file_service_url = await self.get_service_url("file")

            # 发送文件上传请求
            url = f"{file_service_url}/api/files/upload"

            # 准备上传数据
            with open(temp_path, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                data = {'project_id': project_id}

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=data, files=files, timeout=30) as response:
                        if response.status == 200:
                            result = await response.json()
                            return {
                                "success": True,
                                "status": "uploaded",
                                "details": result
                            }
                        else:
                            text = await response.text()
                            return {
                                "success": False,
                                "status": "error",
                                "error": f"上传失败，状态码: {response.status}，响应: {text}"
                            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"测试文件上传失败: {str(e)}"
            }
        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass

    async def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """检查任务状态"""
        try:
            # 使用服务发现获取fileproc服务URL
            fileproc_service_url = await self.get_service_url("fileproc")

            url = f"{fileproc_service_url}/status/{task_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    result = await response.json()

                    return {
                        "success": response.status == 200,
                        "status": result.get("status", "unknown"),
                        "response": result
                    }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"检查任务状态失败: {str(e)}"
            }

    async def check_service_discovery(self) -> Dict[str, Any]:
        """检查服务发现功能"""
        try:
            from src.shared.service_discovery import ServiceRegistry

            registry = ServiceRegistry()
            await registry.connect()

            # 获取已注册服务
            services = await registry.list_services()

            # 查找文件相关服务
            file_service = next((s for s in services if s["name"] == "file"), None)
            fileproc_service = next((s for s in services if s["name"] == "fileproc"), None)

            await registry.close()

            return {
                "success": True,
                "services_count": len(services),
                "file_service": file_service,
                "fileproc_service": fileproc_service
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"检查服务发现失败: {str(e)}"
            }

    async def read_logs(self, lines: int = 100) -> Dict[str, Any]:
        """读取日志文件"""
        try:
            log_file = os.getenv("LOG_FILE")
            if not log_file:
                # 尝试从默认位置读取
                log_paths = [
                    "./logs/lumidoc_app.log",
                    "./logs/fileproc_service.log",
                    "./logs/file_service.log"
                ]

                logs = {}
                for path in log_paths:
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            logs[path] = self._read_last_n_lines(f, lines)

                if not logs:
                    return {
                        "success": False,
                        "error": "未找到日志文件"
                    }

                return {
                    "success": True,
                    "logs": logs
                }
            else:
                # 读取指定的日志文件
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as f:
                        log_content = self._read_last_n_lines(f, lines)

                    return {
                        "success": True,
                        "logs": {log_file: log_content}
                    }
                else:
                    return {
                        "success": False,
                        "error": f"指定的日志文件不存在: {log_file}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"读取日志失败: {str(e)}"
            }

    def _read_last_n_lines(self, file_obj, n: int) -> List[str]:
        """读取文件最后n行"""
        buffer = []
        lines_read = 0

        # 先移动到文件末尾
        file_obj.seek(0, 2)
        block_size = 1024
        block_end_byte = file_obj.tell()

        # 从末尾开始向前读取
        while lines_read < n and block_end_byte > 0:
            # 确定块大小
            if block_end_byte - block_size > 0:
                file_obj.seek(block_end_byte - block_size)
                data = file_obj.read(block_size)
            else:
                file_obj.seek(0)
                data = file_obj.read(block_end_byte)

            # 计算行数
            lines_found = data.count('\n')
            lines_read += lines_found
            block_end_byte -= block_size

            # 添加到缓冲区
            buffer.append(data)

            if lines_read >= n or block_end_byte <= 0:
                break

        # 合并所有块并分割为行
        all_lines = ''.join(reversed(buffer)).splitlines()

        # 返回最后n行
        return all_lines[-n:]

    async def run_full_diagnostics(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        运行完整诊断

        Args:
            project_id: 项目ID，用于测试文件上传

        Returns:
            Dict[str, Any]: 诊断结果
        """
        try:
            results = {}

            # 系统信息
            results["system_info"] = self.check_system_info()

            # 目录检查
            results["directories"] = self.check_directories()

            # Redis连接检查
            results["redis_connection"] = await self.check_redis_connection()

            # PostgreSQL连接检查
            results["postgres_connection"] = await self.check_postgres_connection()

            # 服务发现检查
            results["service_discovery"] = await self.check_service_discovery()

            # 服务健康状态检查
            # 使用服务发现获取服务URL
            file_service_url = await self.get_service_url("file")
            results["file_service_health"] = await self.check_service_health(file_service_url)

            fileproc_service_url = await self.get_service_url("fileproc")
            results["fileproc_service_health"] = await self.check_service_health(fileproc_service_url)

            # 文件上传测试
            if project_id:
                results["file_upload_test"] = await self.test_file_upload(project_id)

            # 日志检查
            results["logs"] = await self.read_logs()

            return {
                "success": True,
                "timestamp": time.time(),
                "diagnostics": results
            }
        except Exception as e:
            logger.error(f"运行完整诊断失败: {str(e)}")
            return {
                "success": False,
                "error": f"运行诊断失败: {str(e)}"
            }
