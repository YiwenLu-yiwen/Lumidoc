"""
统一的LightRAG服务接口
提供本地和远程两种调用模式，根据环境配置自动选择
"""

import os
import asyncio
import logging
import uuid
import time
from typing import Optional, List, Dict, Any
import httpx
from fastapi import HTTPException
from pathlib import Path
from dotenv import load_dotenv
import functools
from src.shared.config_utils import get_service_url
from src.shared.service_client import ServiceClientBase
from src.modules.lightraglocal.config.config import config

# 配置日志
logger = logging.getLogger(__name__)

# 加载环境变量
env_path = Path(__file__).resolve().parent.parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# 确保URL总是包含协议
def ensure_url_protocol(url: str) -> str:
    """确保URL包含http://或https://前缀"""
    if not url.startswith(('http://', 'https://')):
        return f"http://{url}"
    return url

# 从环境变量获取配置
RAG_SERVICE_MODE = os.getenv('RAG_SERVICE_MODE', 'AUTO').upper()
# 使用统一配置工具获取服务URL
LIGHTRAG_SERVICE_URL = get_service_url("RAG")

# 请求超时(秒)
DEFAULT_TIMEOUT = float(os.getenv('LLM_REQUEST_TIMEOUT', '60.0'))

class TimeoutContext:
    """为同步和异步函数提供统一的超时机制"""
    
    @staticmethod
    async def run_with_timeout(coro, timeout, error_msg="操作超时"):
        """使用asyncio.wait_for运行协程，添加超时限制"""
        try:
            return await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            logger.error(f"操作超时: {error_msg}, 超时限制: {timeout}秒")
            raise HTTPException(status_code=504, detail=error_msg)

# 统一错误处理装饰器
def handle_rag_errors(func):
    """统一的RAG服务错误处理装饰器"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())[:8]  # 生成请求追踪ID
        start_time = time.time()
        
        # 记录请求开始
        method_name = func.__name__
        logger.debug(f"[{request_id}] 开始调用 {method_name}, 参数: {kwargs}")
        
        try:
            # 执行原始方法
            result = await func(*args, **kwargs)
            
            # 记录请求结束
            duration = time.time() - start_time
            logger.debug(f"[{request_id}] {method_name} 调用完成, 耗时: {duration:.3f}秒")
            return result
            
        except HTTPException as e:
            # 直接重新抛出HTTP异常，保留状态码
            logger.error(f"[{request_id}] {method_name} HTTP错误: {e.status_code}, {e.detail}")
            raise
            
        except Exception as e:
            # 转换其他异常为HTTP异常
            logger.error(f"[{request_id}] {method_name} 错误: {str(e)}", exc_info=True)
            # 标准化错误响应
            raise HTTPException(status_code=500, detail=f"LightRAG服务错误: {str(e)}")
            
    return wrapper

class LightRAGServiceClient(ServiceClientBase):
    """
    LightRAG服务客户端
    提供文档检索、相似搜索功能
    """
    
    def __init__(self):
        """初始化LightRAG服务客户端"""
        # 从环境变量获取服务URL（优先使用RAG_SERVICE_URL，兼容LIGHTRAG_SERVICE_URL）
        service_url = os.getenv("RAG_SERVICE_URL") or os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8006")
        
        # 调用父类初始化
        super().__init__(
            service_name="LightRAG",
            service_url=service_url,
            local_module_path="src.services.local.lightrag_local",
            local_service_name="lightrag_service"
        )
        
        # 本地服务实例
        self._local_instance = None
        
        # 索引连接实例
        self._index_client = None
        self._db_client = None
        
    async def _init_local_service(self):
        """初始化本地服务实例（不进行项目初始化）"""
        if self._local_instance is None:
            local_service = await self._get_local_service()
            if local_service:
                self._local_instance = local_service()
                # 🚨 修复：不在这里调用initialize()，因为需要项目ID
                # await self._local_instance.initialize()  # 删除这行
                logger.info("已创建本地LightRAG服务实例（未初始化）")
    
    async def add_documents(self, 
                           project_id: str, 
                           document_list: List[Dict[str, Any]],
                           index_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        添加文档到索引
        
        Args:
            project_id: 项目ID
            document_list: 文档列表，每个文档需包含id, text和metadata
            index_options: 索引选项
            
        Returns:
            Dict: 添加结果，包含成功和失败数量
        """
        if not document_list:
            return {"status": "error", "message": "文档列表为空"}
        
        # 设置默认索引选项
        if not index_options:
            index_options = {
                "chunk_size": 512,
                "chunk_overlap": 50,
                "index_mode": "auto",
            }
        
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地索引函数
                result = await self._local_instance.add_documents(
                    project_id=project_id,
                    document_list=document_list,
                    **index_options
                )
                return result
            except Exception as e:
                logger.error(f"本地添加文档出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "documents": document_list,
                    "options": index_options
                }
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="documents",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程添加文档出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"status": "error", "message": "添加文档失败，本地和远程调用均失败"}
    
    async def search(self, 
                    project_id: str, 
                    query: str,
                    top_k: int = 3,
                    filters: Optional[Dict[str, Any]] = None,
                    search_options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相关文档
        
        Args:
            project_id: 项目ID
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
            search_options: 搜索选项
            
        Returns:
            List[Dict[str, Any]]: 相关文档列表
        """
        # 设置默认搜索选项
        if not search_options:
            search_options = {
                "mode": config.default_query_mode,
                "rerank": True
            }
        
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地搜索函数
                results = await self._local_instance.search(
                    query=query,
                    project_id=project_id,
                    top_k=top_k,
                    mode=search_options.get("mode", config.default_query_mode),
                    rerank=search_options.get("rerank", True)
                )
                return results
            except Exception as e:
                logger.error(f"本地搜索出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求参数
                params = {
                    "project_id": project_id,
                    "query": query,
                    "top_k": top_k
                }
                
                if filters:
                    params["filters"] = filters
                    
                if search_options:
                    params.update(search_options)
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="search",
                    method="GET",
                    params=params
                )
                
                if isinstance(result, dict) and "documents" in result:
                    return result["documents"]
                return result
            except Exception as e:
                logger.error(f"远程搜索出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return []
    
    async def query_knowledge(self, 
                             project_id: str, 
                             question: str,
                             chat_history: Optional[List[Dict[str, str]]] = None,
                             top_k: int = 5,
                             filters: Optional[Dict[str, Any]] = None,
                             options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        查询知识库并生成回答
        
        Args:
            project_id: 项目ID
            question: 问题
            chat_history: 聊天历史
            top_k: 检索结果数量
            filters: 过滤条件
            options: 其他选项
            
        Returns:
            Dict[str, Any]: 包含answer和sources的响应
        """
        # 设置默认选项
        if not options:
            options = {
                "mode": config.default_query_mode,
                "use_history": True,
                "stream": False
            }
        
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地查询函数
                result = await self._local_instance.query(
                    query=question,
                    project_id=project_id,
                    top_k=top_k
                )
                return result
            except Exception as e:
                logger.error(f"本地查询出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "question": question,
                    "top_k": top_k
                }
                
                if chat_history:
                    data["chat_history"] = chat_history
                    
                if filters:
                    data["filters"] = filters
                    
                if options:
                    data.update(options)
                
                # 检查是否流式请求
                if options and options.get("stream", False):
                    # 创建流式响应生成器
                    async def stream_response():
                        async with httpx.AsyncClient(timeout=self.timeout) as client:
                            url = f"{self.service_url}/query_stream"
                            async with client.stream("POST", url, json=data) as response:
                                if response.status_code != 200:
                                    error_text = await response.aread()
                                    raise RuntimeError(f"流式查询请求失败: {response.status_code}, {error_text}")
                                
                                async for chunk in response.aiter_text():
                                    if chunk.strip():
                                        yield chunk
                    
                    return stream_response()
                
                # 非流式请求
                result = await self.call_remote_api(
                    endpoint="query",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程查询出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"answer": "无法获取答案，本地和远程调用均失败", "sources": []}
    
    async def delete_documents(self,
                              project_id: str,
                              doc_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        删除文档
        
        Args:
            project_id: 项目ID
            doc_ids: 文档ID列表，如果为None则删除项目所有文档
            
        Returns:
            Dict[str, Any]: 删除结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地删除函数
                if doc_ids:
                    results = []
                    for doc_id in doc_ids:
                        result = await self._local_instance.delete_document(
                            project_id=project_id,
                            doc_id=doc_id
                        )
                        results.append(result)
                    return {"status": "success", "deleted": len(results)}
                else:
                    # 删除项目所有文档
                    # 这里假设本地服务有clear_project方法
                    if hasattr(self._local_instance, "clear_project"):
                        await self._local_instance.clear_project(project_id)
                        return {"status": "success", "message": "已删除项目所有文档"}
                    else:
                        return {"status": "error", "message": "本地服务不支持删除项目所有文档"}
            except Exception as e:
                logger.error(f"本地删除文档出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id
                }
                
                if doc_ids:
                    data["doc_ids"] = doc_ids
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="documents/delete",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程删除文档出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"status": "error", "message": "删除文档失败，本地和远程调用均失败"}
    
    async def extract_and_store_triples(self,
                                       project_id: str,
                                       file_id: str,
                                       extraction_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        从文件提取三元组并存储到图数据库
        
        Args:
            project_id: 项目ID
            file_id: 文件ID
            extraction_options: 提取选项
            
        Returns:
            Dict[str, Any]: 提取结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地提取函数
                result = await self._local_instance.extract_triples(
                    project_id=project_id,
                    file_id=file_id,
                    options=extraction_options or {}
                )
                return result
            except Exception as e:
                logger.error(f"本地提取三元组出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "file_id": file_id,
                    "project_id": project_id
                }
                
                if extraction_options:
                    data["options"] = extraction_options
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="extract-triples",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程提取三元组出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "提取三元组失败，本地和远程调用均失败"}
    
    async def query_with_graph_enhancement(self,
                                          project_id: str,
                                          query: str,
                                          top_k: int = 5,
                                          use_path_context: bool = True,
                                          use_entity_expansion: bool = True,
                                          options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        使用图谱增强进行查询
        
        Args:
            project_id: 项目ID
            query: 查询文本
            top_k: 返回文档数量
            use_path_context: 是否使用路径上下文
            use_entity_expansion: 是否使用实体扩展
            options: 其他选项
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地查询函数
                result = await self._local_instance.query_with_graph(
                    project_id=project_id,
                    query=query,
                    top_k=top_k,
                    use_path_context=use_path_context,
                    use_entity_expansion=use_entity_expansion,
                    options=options or {}
                )
                return result
            except Exception as e:
                logger.error(f"本地图谱增强查询出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "query": query,
                    "top_k": top_k,
                    "use_path_context": use_path_context,
                    "use_entity_expansion": use_entity_expansion
                }
                
                if options:
                    data.update(options)
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="query-with-graph",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程图谱增强查询出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "图谱增强查询失败，本地和远程调用均失败"}
    
    async def import_graph_data(self,
                              project_id: str,
                              graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        导入图谱数据
        
        Args:
            project_id: 项目ID
            graph_data: 图谱数据，包含entities、relationships等
            
        Returns:
            Dict[str, Any]: 导入结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地导入函数
                result = await self._local_instance.import_graph(
                    project_id=project_id,
                    graph_data=graph_data
                )
                return result
            except Exception as e:
                logger.error(f"本地导入图谱出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "graph_data": graph_data
                }
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="import-graph",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程导入图谱出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "导入图谱失败，本地和远程调用均失败"}

    async def process_multiple_files(self,
                                  project_id: str,
                                  file_ids: List[str],
                                  options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        批量处理多个文件，提取三元组并存储到图数据库
        
        Args:
            project_id: 项目ID
            file_ids: 文件ID列表
            options: 处理选项
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地批量处理函数
                result = await self._local_instance.process_multiple_files(
                    project_id=project_id,
                    file_ids=file_ids,
                    options=options or {}
                )
                return result
            except Exception as e:
                logger.error(f"本地批量处理文件出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "file_ids": file_ids
                }
                
                if options:
                    data["options"] = options
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="process-batch",
                    method="POST",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程批量处理文件出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "批量处理文件失败，本地和远程调用均失败"}
        
    async def remove_file_from_graph(self,
                                   project_id: str,
                                   file_id: str) -> Dict[str, Any]:
        """
        从图谱中删除指定文件的三元组
        
        Args:
            project_id: 项目ID
            file_id: 文件ID
            
        Returns:
            Dict[str, Any]: 删除结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地删除函数
                result = await self._local_instance.remove_file_from_graph(
                    project_id=project_id,
                    file_id=file_id
                )
                return result
            except Exception as e:
                logger.error(f"本地删除文件图谱数据出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 调用API
                result = await self.call_remote_api(
                    endpoint=f"file/{project_id}/{file_id}",
                    method="DELETE"
                )
                
                return result
            except Exception as e:
                logger.error(f"远程删除文件图谱数据出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "删除文件图谱数据失败，本地和远程调用均失败"}
        
    async def remove_multiple_files(self,
                                  project_id: str,
                                  file_ids: List[str]) -> Dict[str, Any]:
        """
        批量从图谱中删除多个文件的数据
        
        Args:
            project_id: 项目ID
            file_ids: 文件ID列表
            
        Returns:
            Dict[str, Any]: 删除结果
        """
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地批量删除函数
                result = await self._local_instance.remove_multiple_files(
                    project_id=project_id,
                    file_ids=file_ids
                )
                return result
            except Exception as e:
                logger.error(f"本地批量删除文件图谱数据出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "file_ids": file_ids
                }
                
                # 调用API
                result = await self.call_remote_api(
                    endpoint="files",
                    method="DELETE",
                    data=data
                )
                
                return result
            except Exception as e:
                logger.error(f"远程批量删除文件图谱数据出错: {str(e)}")
                if self.service_mode == self.MODE_REMOTE:
                    raise
        
        # 如果所有尝试都失败
        return {"success": False, "message": "批量删除文件图谱数据失败，本地和远程调用均失败"}

    async def query_stream(self, query_text: str, project_id: str = None, mode: str = None, **kwargs):
        """
        流式查询知识库
        
        Args:
            query_text: 查询文本
            project_id: 项目ID
            mode: 查询模式
            **kwargs: 其他参数
            
        Returns:
            异步生成器，生成响应片段
        """
        # 使用配置中的默认查询模式
        if mode is None:
            mode = config.default_query_mode
        
        # 本地模式
        if self.service_mode in [self.MODE_LOCAL, self.MODE_AUTO]:
            try:
                await self._init_local_service()
                
                # 调用本地流式查询函数
                async for chunk in self._local_instance.query_stream(
                    query_text=query_text,
                    project_id=project_id,
                    mode=mode,
                    **kwargs
                ):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"本地流式查询出错: {str(e)}")
                if self.service_mode == self.MODE_LOCAL:
                    raise
        
        # 远程模式
        if self.service_mode in [self.MODE_REMOTE, self.MODE_AUTO]:
            try:
                # 准备请求数据
                data = {
                    "project_id": project_id,
                    "query": query_text,
                    "mode": mode,
                    "stream": True
                }
                
                if kwargs:
                    data.update(kwargs)
                
                # 创建流式响应生成器
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    url = f"{self.service_url}/query_stream"
                    async with client.stream("POST", url, json=data) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            raise RuntimeError(f"流式查询请求失败: {response.status_code}, {error_text}")
                        
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                yield chunk
                
            except Exception as e:
                logger.error(f"远程流式查询出错: {str(e)}")
                # 如果远程调用失败，返回错误信息
                yield f"查询处理过程中出错: {str(e)}"

# 创建默认客户端实例
default_client = LightRAGServiceClient() 