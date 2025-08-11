"""
本地文件存储实现
"""

import os
import aiofiles
from pathlib import Path
from typing import Union, BinaryIO, Optional
import logging
from .storage_interface import StorageInterface

logger = logging.getLogger(__name__)

class LocalStorage(StorageInterface):
    """本地文件存储实现"""
    
    def __init__(self, base_dir: Union[str, Path]):
        """
        初始化本地存储
        
        Args:
            base_dir: 基础存储目录
        """
        self.base_dir = Path(base_dir)
        # 确保存储目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"本地存储初始化完成，存储路径: {self.base_dir}")
    
    async def save_file(self, file_id: str, content: bytes, file_extension: str = "") -> str:
        """
        保存文件到本地存储
        
        Args:
            file_id: 文件ID
            content: 文件内容
            file_extension: 文件扩展名
            
        Returns:
            str: 存储路径
        """
        # 确保存储目录存在
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"确保基础存储目录存在: {self.base_dir}")
        except Exception as e:
            logger.error(f"创建基础存储目录失败: {str(e)}")
            # 尝试使用os.makedirs
            try:
                os.makedirs(str(self.base_dir), exist_ok=True)
                logger.info(f"使用os.makedirs创建基础存储目录: {self.base_dir}")
            except Exception as e2:
                logger.error(f"使用os.makedirs创建基础存储目录失败: {str(e2)}")
                raise
        
        # 检查是否包含项目ID (格式如 "51/uuid")
        if '/' in file_id:
            # 解析项目ID和文件ID
            parts = file_id.split('/')
            project_id = parts[0]
            
            # 确保项目目录存在
            project_dir = self.base_dir / project_id
            try:
                project_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"确保项目目录存在: {project_dir}")
            except Exception as e:
                logger.error(f"创建项目目录失败: {str(e)}")
                # 尝试使用os.makedirs
                try:
                    os.makedirs(str(project_dir), exist_ok=True)
                    logger.info(f"使用os.makedirs创建项目目录: {project_dir}")
                except Exception as e2:
                    logger.error(f"使用os.makedirs创建项目目录失败: {str(e2)}")
                    raise
            
            # 创建完整的文件路径
            file_path = project_dir / f"{parts[1]}{file_extension}"
        else:
            # 直接在base_dir下创建文件
            file_path = self.base_dir / f"{file_id}{file_extension}"
        
        # 写入文件内容
        try:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            logger.info(f"文件已保存到本地存储: {file_path}")
        except Exception as e:
            logger.error(f"写入文件失败: {str(e)}")
            raise
        
        return str(file_path)
    
    async def get_file(self, file_path: Union[str, Path]) -> bytes:
        """
        从本地存储读取文件内容
        
        Args:
            file_path: 相对于base_dir的文件路径
            
        Returns:
            bytes: 文件内容
        """
        full_path = self._get_full_path(file_path)
        try:
            async with aiofiles.open(full_path, 'rb') as f:
                content = await f.read()
            return content
        except FileNotFoundError:
            logger.error(f"文件不存在: {full_path}")
            raise
        except Exception as e:
            logger.error(f"读取文件失败 {full_path}: {str(e)}")
            raise
    
    async def delete_file(self, file_path: Union[str, Path]) -> bool:
        """删除文件"""
        try:
            # 使用原有的路径解析方法
            full_path = self._get_full_path(file_path)
            logger.info(f"尝试删除文件: {full_path}")
            
            # 检查文件是否存在
            if not os.path.exists(full_path):
                # 尝试只用基本文件名
                norm_path = Path(str(file_path)).name
                abs_path = Path(self.base_dir) / norm_path
                
                if not abs_path.exists():
                    logger.warning(f"要删除的文件不存在: {full_path} 或 {abs_path}")
                    return False
                else:
                    # 使用找到的简单名称路径
                    full_path = str(abs_path)
                    logger.info(f"找到基本文件名路径: {full_path}")
            
            # 尝试删除文件
            try:
                os.remove(full_path)
                logger.info(f"成功删除文件: {full_path}")
                return True
            except PermissionError:
                # 处理权限错误 - 尝试更改权限后再次删除
                logger.warning(f"删除文件时遇到权限问题: {full_path}, 尝试更改权限")
                try:
                    os.chmod(full_path, 0o666)  # 赋予读写权限
                    os.remove(full_path)
                    logger.info(f"更改权限后成功删除文件: {full_path}")
                    return True
                except Exception as perm_err:
                    logger.error(f"更改权限后删除文件仍然失败: {str(perm_err)}")
                    
            # 最后手段 - 尝试使用系统命令强制删除
            try:
                import subprocess
                if os.name == 'nt':  # Windows
                    subprocess.run(['del', '/f', '/q', str(full_path)], check=True)
                else:  # Unix/Linux/Mac
                    subprocess.run(['rm', '-f', str(full_path)], check=True)
                logger.info(f"使用系统命令强制删除文件成功: {full_path}")
                return True
            except Exception as cmd_err:
                logger.error(f"使用系统命令删除文件失败: {str(cmd_err)}")
                        
            return False  # 如果所有删除尝试都失败
        except Exception as e:
            logger.error(f"删除文件时发生错误: {str(e)}")
            return False
    
    async def file_exists(self, file_path: Union[str, Path]) -> bool:
        """
        检查文件是否存在于本地存储
        
        Args:
            file_path: 相对于base_dir的文件路径
            
        Returns:
            bool: 文件是否存在
        """
        full_path = self._get_full_path(file_path)
        return full_path.exists() and full_path.is_file()
    
    def get_file_url(self, file_path: Union[str, Path], expire: int = 3600) -> str:
        """
        获取本地文件的URL（本地文件系统中，返回文件路径）
        
        Args:
            file_path: 相对于base_dir的文件路径
            expire: 不适用于本地存储
            
        Returns:
            str: 文件路径
        """
        return str(self._get_full_path(file_path))
    
    async def get_file_content(self, file_path: Union[str, Path]) -> str:
        """
        从本地存储读取文本文件内容
        
        Args:
            file_path: 相对于base_dir的文件路径
            
        Returns:
            str: 文件文本内容
        """
        full_path = self._get_full_path(file_path)
        try:
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            return content
        except FileNotFoundError:
            logger.error(f"文件不存在: {full_path}")
            raise
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试使用其他编码
            logger.warning(f"UTF-8解码失败，尝试其他编码: {full_path}")
            try:
                async with aiofiles.open(full_path, 'r', encoding='gbk') as f:
                    content = await f.read()
                return content
            except UnicodeDecodeError:
                # 如果GBK也失败，尝试Latin-1（它可以解码任何字节序列）
                async with aiofiles.open(full_path, 'r', encoding='latin-1') as f:
                    content = await f.read()
                return content
        except Exception as e:
            logger.error(f"读取文本文件失败 {full_path}: {str(e)}")
            raise
    
    def _get_full_path(self, file_path: Union[str, Path]) -> Path:
        """
        获取文件的完整路径
        
        Args:
            file_path: 相对于base_dir的文件路径
            
        Returns:
            Path: 完整文件路径
        """
        path = Path(file_path)
        # 如果是绝对路径，并且已经包含基础目录，则直接返回
        if path.is_absolute() and str(path).startswith(str(self.base_dir)):
            return path
        # 否则，拼接基础目录和文件路径
        return self.base_dir / path

    async def is_connected(self) -> bool:
        """
        检查存储连接是否可用
        
        Returns:
            bool: 连接是否可用
        """
        try:
            # 对于本地存储，检查base_dir是否存在且可写
            return os.path.exists(self.base_dir) and os.access(self.base_dir, os.W_OK)
        except Exception as e:
            logger.error(f"检查存储连接状态失败: {str(e)}")
            return False
    
    async def close(self) -> None:
        """
        关闭本地存储服务
        本地存储不需要特殊的关闭操作
        """
        logger.info("本地存储服务关闭")
        pass 