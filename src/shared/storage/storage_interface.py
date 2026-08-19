"""
存储接口抽象类
定义文件存储的基本操作
"""

from abc import ABC, abstractmethod
from typing import Union
from pathlib import Path


class StorageInterface(ABC):
    """存储接口抽象类，定义文件存储的基本操作"""

    @abstractmethod
    async def save_file(self, file_id: str, content: bytes, file_extension: str = "") -> str:
        """
        保存文件到存储系统
        
        Args:
            file_id: 文件ID
            content: 文件内容
            file_extension: 文件扩展名
            
        Returns:
            str: 存储路径
        """
        pass
    
    @abstractmethod
    async def get_file(self, file_path: Union[str, Path]) -> bytes:
        """
        获取文件内容
        
        Args:
            file_path: 文件路径或文件标识符
            
        Returns:
            bytes: 文件内容
        """
        pass
    
    @abstractmethod
    async def get_file_content(self, file_path: Union[str, Path]) -> str:
        """
        获取文本文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件文本内容
        """
        pass
    
    @abstractmethod
    async def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径或文件标识符
            
        Returns:
            bool: 删除是否成功
        """
        pass
    
    @abstractmethod
    async def file_exists(self, file_path: Union[str, Path]) -> bool:
        """
        检查文件是否存在
        
        Args:
            file_path: 文件路径或文件标识符
            
        Returns:
            bool: 文件是否存在
        """
        pass
    
    @abstractmethod
    def get_file_url(self, file_path: Union[str, Path], expire: int = 3600) -> str:
        """
        获取文件访问URL
        
        Args:
            file_path: 文件路径或文件标识符
            expire: URL过期时间(秒)，仅对对象存储有效
            
        Returns:
            str: 文件访问URL
        """
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """
        检查存储连接是否可用
        
        Returns:
            bool: 连接是否可用
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        关闭存储服务，释放资源
        """
        pass 