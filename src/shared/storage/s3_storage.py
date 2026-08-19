"""
S3/MinIO对象存储实现
"""

import io
import boto3
import logging
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Union, BinaryIO
import asyncio

from .storage_interface import StorageInterface

logger = logging.getLogger(__name__)

class S3Storage(StorageInterface):
    """S3/MinIO对象存储实现"""

    def __init__(self,
                 endpoint_url: str,
                 access_key: str,
                 secret_key: str,
                 bucket_name: str,
                 region_name: str = 'us-east-1',
                 base_prefix: str = ""):
        """
        初始化S3/MinIO存储

        Args:
            endpoint_url: S3/MinIO服务端点URL
            access_key: 访问密钥ID
            secret_key: 秘密访问密钥
            bucket_name: 存储桶名称
            region_name: 区域名称，默认为us-east-1
            base_prefix: 基础路径前缀，用于目录映射
        """
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.base_prefix = base_prefix.strip('/')

        # 初始化S3客户端
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name
        )

        # 检查存储桶是否存在，不存在则创建
        self._ensure_bucket_exists()

        logger.info(f"S3存储初始化完成，端点: {endpoint_url}, 存储桶: {bucket_name}")

    def _ensure_bucket_exists(self):
        """确保存储桶存在，不存在则创建"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"存储桶已存在: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404':
                # 存储桶不存在，创建
                logger.info(f"存储桶不存在，正在创建: {self.bucket_name}")
                try:
                    # 如果不是us-east-1区域，需要指定区域
                    if self.region_name != 'us-east-1':
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region_name}
                        )
                    else:
                        # us-east-1是默认区域，不需要指定
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"存储桶创建成功: {self.bucket_name}")
                except Exception as create_error:
                    logger.error(f"创建存储桶失败: {str(create_error)}")
                    raise
            else:
                # 其他错误
                logger.error(f"检查存储桶时发生错误: {str(e)}")
                raise

    async def _save_file_old(self, file_path: Union[str, Path], file_content: Union[bytes, BinaryIO]) -> str:
        """
        保存文件到S3/MinIO存储 (旧方法)

        Args:
            file_path: 对象键名/路径
            file_content: 文件内容或文件对象

        Returns:
            str: 保存后的对象键名
        """
        object_key = self._normalize_key(file_path)

        try:
            # 将同步上传操作包装在线程池中执行
            if isinstance(file_content, bytes):
                # 如果是字节内容，直接上传
                await asyncio.to_thread(
                    self.s3_client.upload_fileobj,
                    io.BytesIO(file_content),
                    self.bucket_name,
                    object_key
                )
            else:
                # 如果是文件对象
                if hasattr(file_content, 'seek'):
                    file_content.seek(0)

                if hasattr(file_content, 'read'):
                    # 读取并上传
                    content = file_content.read()
                    if isinstance(content, str):
                        content = content.encode('utf-8')
                    await asyncio.to_thread(
                        self.s3_client.upload_fileobj,
                        io.BytesIO(content),
                        self.bucket_name,
                        object_key
                    )
                else:
                    # 不支持的文件内容类型
                    raise ValueError(f"不支持的文件内容类型: {type(file_content)}")

            logger.debug(f"文件上传成功: {object_key}")
            return object_key
        except Exception as e:
            logger.error(f"上传文件失败 {object_key}: {str(e)}")
            raise

    async def save_file(self, file_id: str, content: bytes, file_extension: str = "") -> str:
        """
        保存文件到S3存储

        Args:
            file_id: 文件ID
            content: 文件内容
            file_extension: 文件扩展名

        Returns:
            str: S3对象键
        """
        try:
            # 创建文件路径并规范化（添加前缀）
            file_path = f"{file_id}{file_extension}"
            object_key = self._normalize_key(file_path)

            # 保存到S3
            await asyncio.to_thread(
                self.s3_client.upload_fileobj,
                io.BytesIO(content),
                self.bucket_name,
                object_key
            )

            logger.info(f"文件已保存到S3: {self.bucket_name}/{object_key}")
            return object_key
        except Exception as e:
            logger.error(f"保存文件到S3失败: {str(e)}")
            raise

    async def get_file(self, file_path: Union[str, Path]) -> bytes:
        """
        从S3/MinIO存储获取文件内容

        Args:
            file_path: 对象键名/路径

        Returns:
            bytes: 文件内容
        """
        object_key = self._normalize_key(file_path)

        try:
            # 使用线程池异步获取对象
            response = await asyncio.to_thread(
                self.s3_client.get_object,
                Bucket=self.bucket_name,
                Key=object_key
            )

            # 读取对象内容
            content = await asyncio.to_thread(response['Body'].read)
            return content
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                # 如果找不到，尝试无前缀的路径（兼容旧数据）
                if self.base_prefix and object_key.startswith(f"{self.base_prefix}/"):
                    no_prefix_key = object_key.replace(f"{self.base_prefix}/", "", 1)
                    try:
                        response = await asyncio.to_thread(
                            self.s3_client.get_object,
                            Bucket=self.bucket_name,
                            Key=no_prefix_key
                        )
                        content = await asyncio.to_thread(response['Body'].read)
                        logger.debug(f"文件读取成功，使用无前缀路径: {no_prefix_key}")
                        return content
                    except ClientError:
                        pass

                # 对于新项目，这是正常的，使用debug级别
                if "project_" in object_key and any(f in object_key for f in ["vdb_", "kv_store_", "graph_"]):
                    logger.debug(f"项目文件不存在（新项目正常）: {object_key}")
                else:
                    logger.error(f"文件不存在: {object_key}")
                raise FileNotFoundError(f"文件不存在: {object_key}")
            else:
                logger.error(f"获取文件失败 {object_key}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"获取文件失败 {object_key}: {str(e)}")
            raise

    async def get_file_content(self, file_path: Union[str, Path]) -> str:
        """
        从S3/MinIO存储获取文本文件内容

        Args:
            file_path: 对象键名/路径

        Returns:
            str: 文件文本内容
        """
        try:
            # 获取字节内容（get_file方法已经包含了兼容性逻辑）
            content_bytes = await self.get_file(file_path)
            # 解码为字符串
            return content_bytes.decode('utf-8')
        except UnicodeDecodeError as e:
            logger.error(f"文件编码解析失败 {file_path}: {str(e)}")
            # 尝试其他编码
            try:
                content_bytes = await self.get_file(file_path)
                return content_bytes.decode('gbk')
            except Exception:
                # 最后尝试忽略错误
                content_bytes = await self.get_file(file_path)
                return content_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"获取文件内容失败 {file_path}: {str(e)}")
            raise

    async def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        从S3/MinIO存储删除文件

        Args:
            file_path: 对象键名/路径

        Returns:
            bool: 删除是否成功
        """
        object_key = self._normalize_key(file_path)

        try:
            # 构建所有可能的路径
            paths_to_try = [object_key]

            # 如果有前缀，添加无前缀的路径
            if self.base_prefix and object_key.startswith(f"{self.base_prefix}/"):
                no_prefix_key = object_key.replace(f"{self.base_prefix}/", "", 1)
                paths_to_try.append(no_prefix_key)
            # 如果没有前缀，添加有前缀的路径
            elif self.base_prefix and not object_key.startswith(f"{self.base_prefix}/"):
                with_prefix_key = f"{self.base_prefix}/{object_key}"
                paths_to_try.append(with_prefix_key)

            # 首先检查哪个路径实际存在文件
            existing_path = None
            for path in paths_to_try:
                try:
                    await asyncio.to_thread(
                        self.s3_client.head_object,
                        Bucket=self.bucket_name,
                        Key=path
                    )
                    existing_path = path
                    logger.debug(f"找到存在的文件路径: {path}")
                    break
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code')
                    if error_code == '404' or error_code == 'NoSuchKey':
                        continue
                    else:
                        raise e

            # 如果找到了存在的文件，删除它
            if existing_path:
                try:
                    await asyncio.to_thread(
                        self.s3_client.delete_object,
                        Bucket=self.bucket_name,
                        Key=existing_path
                    )
                    logger.debug(f"文件删除成功: {existing_path}")
                    return True
                except Exception as e:
                    logger.error(f"删除文件失败 {existing_path}: {str(e)}")
                    raise e
            else:
                logger.warning(f"要删除的文件在所有路径中都不存在: {paths_to_try}")
                return False
        except Exception as e:
            logger.error(f"删除文件失败 {object_key}: {str(e)}")
            return False

    async def file_exists(self, file_path: Union[str, Path]) -> bool:
        """
        检查文件是否存在于S3/MinIO存储

        Args:
            file_path: 对象键名/路径

        Returns:
            bool: 文件是否存在
        """
        object_key = self._normalize_key(file_path)

        try:
            # 使用线程池异步检查对象是否存在
            await asyncio.to_thread(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=object_key
            )
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == '404' or error_code == 'NoSuchKey':
                # 如果找不到，尝试无前缀的路径（兼容旧数据）
                if self.base_prefix and object_key.startswith(f"{self.base_prefix}/"):
                    no_prefix_key = object_key.replace(f"{self.base_prefix}/", "", 1)
                    try:
                        await asyncio.to_thread(
                            self.s3_client.head_object,
                            Bucket=self.bucket_name,
                            Key=no_prefix_key
                        )
                        logger.debug(f"文件存在于无前缀路径: {no_prefix_key}")
                        return True
                    except ClientError:
                        pass
                return False
            else:
                logger.error(f"检查文件是否存在时发生错误 {object_key}: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"检查文件是否存在时发生错误 {object_key}: {str(e)}")
            raise

    def get_file_url(self, file_path: Union[str, Path], expire: int = 3600) -> str:
        """
        获取S3/MinIO对象的预签名URL

        Args:
            file_path: 对象键名/路径
            expire: URL过期时间(秒)

        Returns:
            str: 预签名URL
        """
        object_key = self._normalize_key(file_path)

        try:
            # 生成预签名URL
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expire
            )
            return url
        except Exception as e:
            logger.error(f"生成预签名URL失败 {object_key}: {str(e)}")
            raise

    def _normalize_key(self, file_path: Union[str, Path]) -> str:
        """
        规范化对象键名

        Args:
            file_path: 对象键名/路径

        Returns:
            str: 规范化后的对象键名
        """
        # 转换为字符串并去除前导斜杠
        key = str(file_path).lstrip('/')
        # 替换反斜杠为正斜杠（处理Windows路径）
        key = key.replace('\\', '/')

        # 添加基础前缀
        if self.base_prefix and not key.startswith(self.base_prefix):
            key = f"{self.base_prefix}/{key}"

        return key

    async def is_connected(self) -> bool:
        """
        检查S3/MinIO存储连接是否可用

        Returns:
            bool: 连接是否可用
        """
        try:
            # 尝试列出桶来测试连接
            await asyncio.to_thread(
                self.s3_client.head_bucket,
                Bucket=self.bucket_name
            )
            return True
        except Exception as e:
            logger.error(f"S3存储连接检查失败: {str(e)}")
            return False

    async def close(self) -> None:
        """
        关闭S3存储服务
        关闭S3客户端连接
        """
        try:
            if self.s3_client:
                # 关闭底层HTTP连接池
                await asyncio.to_thread(self.s3_client.close)
                logger.info("S3存储服务已关闭")
        except Exception as e:
            logger.error(f"关闭S3存储服务失败: {str(e)}")
            raise
