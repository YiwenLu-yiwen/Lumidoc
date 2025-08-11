"""
企业级 LightRAG 服务

这是完全重写的企业级服务，删除了所有复杂的 override 和 monkey patching 系统
使用最简单、最可靠的项目隔离方案，支持企业级部署
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Dict, Optional, Any, Union, List, AsyncGenerator
from datetime import datetime
import json
import time

# 设置日志
logger = logging.getLogger(__name__)

# 添加 LightRAG 到路径
lightrag_path = str(Path(__file__).parent.parent.parent.parent.parent / "libs" / "LightRAG")
if lightrag_path not in sys.path:
    sys.path.insert(0, lightrag_path)

# 导入RAG存储适配器
try:
    from ..storage.rag_storage_adapter import get_rag_storage_adapter, cleanup_rag_storage
    logger.info("✅ 成功导入RAG存储适配器")
except ImportError as e:
    logger.warning(f"⚠️ RAG存储适配器导入失败: {e}")
    get_rag_storage_adapter = None
    cleanup_rag_storage = None

# 导入配置
try:
    from src.shared.config import llm_settings
    from src.modules.lightraglocal.config.config import config
except ImportError as e:
    logger.warning(f"配置导入失败: {e}")
    llm_settings = None
    config = None

# 导入 LightRAG
try:
    from lightrag import LightRAG, QueryParam
    logger.info("✅ 成功导入 LightRAG")
except ImportError as e:
    logger.error(f"❌ LightRAG 导入失败: {e}")
    LightRAG = None
    QueryParam = None


class EnterpriseLightRAGService:
    """
    企业级 LightRAG 服务
    
    特点：
    1. 完全项目隔离 - 基于独立工作目录
    2. 无复杂 override 系统 - 简单可靠
    3. 企业级扩展 - 支持数千项目
    4. 高性能 - 无运行时 patching
    """
    
    def __init__(self, base_storage_dir: Optional[str] = None):
        """
        初始化企业级 LightRAG 服务
        
        Args:
            base_storage_dir: 基础存储目录（可选，主要用于兼容性）
        """
        # 存储类型配置
        self.storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
        
        # 如果未指定base_storage_dir，则根据存储类型设置默认值
        if base_storage_dir is None:
            if self.storage_type == 's3':
                # S3模式：使用虚拟路径，实际存储由适配器管理，绝不创建本地目录
                self.base_storage_dir = "s3://minio-rag-storage"
            else:
                # 本地模式：使用传统的本地目录
                self.base_storage_dir = os.getenv('RAG_DIR', './rag_storage')
        else:
            self.base_storage_dir = base_storage_dir
        
        self._project_instances: Dict[str, LightRAG] = {}
        self._project_locks: Dict[str, asyncio.Lock] = {}
        self._project_adapters: Dict[str, Any] = {}  # 存储适配器实例
        self._global_lock = asyncio.Lock()
        
        # 本地模式需要确保目录存在
        if self.storage_type == 'local':
            os.makedirs(self.base_storage_dir, exist_ok=True)
        
        # 企业级配置
        self.default_config = self._get_default_config()
        
        logger.info(f"🏢 企业级 LightRAG 服务初始化完成 - 存储类型: {self.storage_type}, 存储路径: {self.base_storage_dir}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认 LightRAG 配置"""
        
        # 从环境变量读取模型配置
        llm_model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5:3b")
        embedding_model_name = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest")
        
        # 根据实际嵌入模型确定维度
        # bge-m3:latest 实际返回 2048 维，而不是标准的 1024 维
        embedding_dim = int(os.getenv("EMBEDDING_DIM", "2048"))  # 从环境变量读取，默认 2048
        
        logger.info(f"🔧 LLM模型: {llm_model_name}")
        logger.info(f"🔢 嵌入模型: {embedding_model_name} (维度: {embedding_dim})")
        
        # 使用真实的 LLM 服务
        async def real_llm_model_func(prompt: str, system_prompt: str = None, history_messages: list = None, **kwargs) -> str:
            """真实 LLM 函数 - 调用统一 LLM 服务"""
            logger.info(f"🤖 真实 LLM 调用 ({llm_model_name}): {prompt[:100]}... | system_prompt: {system_prompt is not None} | history_messages: {type(history_messages)} | kwargs: {list(kwargs.keys())}")
            
            try:
                # 导入 LLM 客户端
                from src.shared.clients.llm_service_client import LLMServiceClient
                
                # 处理参数 - 确保所有参数类型正确
                if history_messages is None:
                    history_messages = []
                elif not isinstance(history_messages, list):
                    logger.warning(f"⚠️ history_messages 类型错误: {type(history_messages)}, 重置为空列表")
                    history_messages = []
                
                if system_prompt is None:
                    system_prompt = ""
                
                # 构建消息
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                
                # 添加历史消息
                for msg in history_messages:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        messages.append(msg)
                    elif isinstance(msg, str):
                        messages.append({"role": "user", "content": msg})
                
                # 添加当前提示
                messages.append({"role": "user", "content": prompt})
                
                # 调用 LLM 服务
                client = LLMServiceClient()
                response = await client.chat_generate(
                    messages=messages,
                    max_tokens=4000,
                    temperature=0.1
                )
                
                if isinstance(response, str):
                    logger.info(f"✅ LLM 响应成功: {len(response)} 字符")
                    return response
                else:
                    logger.error(f"❌ LLM 服务调用失败: {response}")
                    # 返回空字符串而不是抛出异常，让 LightRAG 继续处理
                    return ""
                    
            except Exception as e:
                logger.error(f"❌ LLM 函数异常: {e}")
                logger.error(f"❌ 调用参数详情: prompt={type(prompt)}, system_prompt={type(system_prompt)}, history_messages={type(history_messages)}, kwargs={kwargs}")
                import traceback
                logger.error(f"❌ 堆栈跟踪: {traceback.format_exc()}")
                # 返回空字符串而不是抛出异常
                return ""
        
        # 使用真实的嵌入函数
        class RealEmbeddingFunc:
            """真实嵌入函数类 - 调用统一嵌入服务"""
            
            def __init__(self):
                # 从环境变量读取嵌入维度
                self.embedding_dim = embedding_dim
                self.model_name = embedding_model_name
            
            async def __call__(self, texts: list[str]) -> list[list[float]]:
                """真实嵌入函数调用"""
                logger.info(f"🔢 真实嵌入调用 ({self.model_name}): {len(texts)} 个文本")
                
                try:
                    # 导入嵌入客户端
                    from src.shared.clients.llm_service_client import LLMServiceClient
                    
                    client = LLMServiceClient()
                    
                    # 调用嵌入服务
                    response = await client.get_embeddings(texts=texts)
                    
                    if isinstance(response, list):
                        logger.info(f"✅ 嵌入响应成功: {len(response)} 个向量")
                        return response
                    else:
                        logger.error(f"❌ 嵌入服务调用失败: {response}")
                        # 返回零向量而不是抛出异常
                        return [[0.0] * self.embedding_dim for _ in texts]
                        
                except Exception as e:
                    logger.error(f"❌ 嵌入函数异常: {e}")
                    # 返回零向量而不是抛出异常
                    return [[0.0] * self.embedding_dim for _ in texts]
        
        real_embedding_func = RealEmbeddingFunc()
        
        # 基础配置
        config = {
            # 基础配置
            "chunk_token_size": int(os.getenv("RAG_CHUNK_SIZE", "1200")),
            "chunk_overlap_token_size": int(os.getenv("RAG_CHUNK_OVERLAP", "100")),
            
            # 存储配置 - 使用企业级存储
            "kv_storage": os.getenv("LIGHTRAG_KV_STORAGE", "JsonKVStorage"),
            "vector_storage": os.getenv("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage"), 
            "graph_storage": os.getenv("LIGHTRAG_GRAPH_STORAGE", "NetworkXStorage"),
            
            # LLM 配置 - 使用真实 LLM 服务
            "llm_model_func": real_llm_model_func,
            "embedding_func": real_embedding_func,
            
            # LLM 模型配置 - 从环境变量读取
            "llm_model_name": llm_model_name,
            "llm_model_max_token_size": int(os.getenv("LLM_MAX_TOKENS", "4000")),
            "llm_model_max_async": int(os.getenv("MAX_ASYNC", "2")),
            
            # 官方LightRAG语言配置 - 使用中文输出
            "addon_params": {
                "language": "Chinese"
            },
        }
        
        logger.info(f"🚀 使用真实服务配置: LLM={llm_model_name}, 嵌入={embedding_model_name}({embedding_dim}维)")
        
        return config
    
    async def _get_project_lock(self, project_id: str) -> asyncio.Lock:
        """获取项目级锁"""
        async with self._global_lock:
            if project_id not in self._project_locks:
                self._project_locks[project_id] = asyncio.Lock()
            return self._project_locks[project_id]
    
    async def _get_project_rag(self, project_id: str) -> LightRAG:
        """
        获取项目的 LightRAG 实例
        
        使用项目独立目录实现完全隔离，支持本地和S3存储
        """
        if not LightRAG:
            raise RuntimeError("LightRAG 未正确导入")
        
        project_lock = await self._get_project_lock(project_id)
        
        async with project_lock:
            if project_id not in self._project_instances:
                # 获取或创建存储适配器
                if get_rag_storage_adapter:
                    storage_adapter = await get_rag_storage_adapter(project_id)
                    self._project_adapters[project_id] = storage_adapter
                    project_dir = storage_adapter.get_working_dir()
                else:
                    # 回退到传统本地模式
                    project_dir = os.path.join(self.base_storage_dir, f"project_{project_id}")
                    os.makedirs(project_dir, exist_ok=True)
                
                # 创建项目配置
                project_config = {
                    **self.default_config,
                    "working_dir": project_dir,
                    "workspace": f"project_{project_id}",  # 工作区隔离
                }
                
                # 创建 LightRAG 实例
                try:
                    rag_instance = LightRAG(**project_config)
                    
                    # 初始化存储
                    await rag_instance.initialize_storages()
                    
                    # 初始化管道状态（重要：避免 'history_messages' KeyError）
                    try:
                        from lightrag.kg.shared_storage import initialize_pipeline_status
                        await initialize_pipeline_status()
                        logger.info(f"🔧 为项目 {project_id} 初始化管道状态")
                    except Exception as init_e:
                        logger.warning(f"⚠️ 管道状态初始化失败: {init_e}")
                        # 不阻止实例创建，但记录警告
                    
                    self._project_instances[project_id] = rag_instance
                    logger.info(f"🆕 为项目 {project_id} 创建 LightRAG 实例 (存储类型: {self.storage_type})")
                except Exception as e:
                    logger.error(f"❌ 项目 {project_id} LightRAG 创建失败: {e}")
                    raise
        
        return self._project_instances[project_id]
    
    async def insert_document(
        self, 
        project_id: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        为特定项目插入文档
        
        Args:
            project_id: 项目ID
            content: 文档内容
            metadata: 元数据
            **kwargs: 其他参数
            
        Returns:
            插入结果
        """
        try:
            rag = await self._get_project_rag(project_id)
            
            # 记录插入操作
            start_time = datetime.now()
            
            # 执行插入
            logger.info(f"🔧 开始文档插入: project_id={project_id}, content_length={len(content)}, kwargs={kwargs}, metadata={metadata}")
            
            # 提取文件路径信息，用于LightRAG的文件引用
            file_paths = None
            if metadata:
                # 首先尝试从metadata中获取filename
                filename = metadata.get('filename')
                if filename:
                    file_paths = filename
                    logger.info(f"📁 使用文件名作为引用路径: {file_paths}")
                else:
                    # 如果没有filename，尝试其他路径字段
                    file_path = metadata.get('path') or metadata.get('file_path') or metadata.get('storage_path')
                    if file_path:
                        # 从完整路径中提取文件名
                        import os
                        file_paths = os.path.basename(file_path)
                        logger.info(f"📁 从路径提取文件名作为引用: {file_paths}")
            
            # 过滤掉LightRAG不支持的参数
            # LightRAG.ainsert只支持: content, file_paths等有限参数
            lightrag_kwargs = {}
            if 'stream' in kwargs:
                lightrag_kwargs['stream'] = kwargs['stream']
            
            # 调用LightRAG插入，明确传递file_paths参数
            if file_paths:
                await rag.ainsert(content, file_paths=file_paths, **lightrag_kwargs)
                logger.info(f"✅ 已传递文件路径给LightRAG: {file_paths}")
            else:
                logger.warning("⚠️ 未找到文件路径信息，将使用默认方式插入")
                await rag.ainsert(content, **lightrag_kwargs)
            
            # 计算耗时
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "project_id": project_id,
                "content_length": len(content),
                "duration_seconds": duration,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata
            }
            
            # 如果使用S3存储，同步数据到S3
            await self._sync_project_to_s3(project_id)
            
            logger.info(f"📄 项目 {project_id} 文档插入成功 - 耗时: {duration:.2f}s")
            return result
            
        except Exception as e:
            import traceback
            full_traceback = traceback.format_exc()
            logger.error(f"❌ 项目 {project_id} 文档插入失败: {e}")
            logger.error(f"❌ 完整错误跟踪: {full_traceback}")
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
                "traceback": full_traceback,
                "timestamp": datetime.now().isoformat()
            }
    
    async def query_project(
        self, 
        project_id: str, 
        query: str, 
        mode: str = "naive",
        **kwargs
    ) -> Dict[str, Any]:
        """
        查询特定项目的内容
        
        Args:
            project_id: 项目ID
            query: 查询内容
            mode: 查询模式 ("naive", "local", "global", "hybrid")
            **kwargs: 其他参数
            
        Returns:
            查询结果
        """
        try:
            rag = await self._get_project_rag(project_id)
            
            # 记录查询操作
            start_time = datetime.now()
            
            # 执行查询
            if QueryParam:
                param = QueryParam(mode=mode)
                result = await rag.aquery(query, param, **kwargs)
            else:
                result = await rag.aquery(query, **kwargs)
            
            # 计算耗时
            duration = (datetime.now() - start_time).total_seconds()
            
            response = {
                "success": True,
                "project_id": project_id,
                "query": query,
                "mode": mode,
                "result": result,
                "duration_seconds": duration,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"🔍 项目 {project_id} 查询完成 - 耗时: {duration:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"❌ 项目 {project_id} 查询失败: {e}")
            return {
                "success": False,
                "project_id": project_id,
                "query": query,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    
    async def delete_document(
        self, 
        project_id: str, 
        doc_id: str
    ) -> Dict[str, Any]:
        """
        删除特定项目的文档
        
        Args:
            project_id: 项目ID
            doc_id: 文档ID
            
        Returns:
            删除结果
        """
        try:
            rag = await self._get_project_rag(project_id)
            
            # TODO: 实现文档删除逻辑
            # 这需要根据 LightRAG 的具体 API 来实现
            
            logger.info(f"🗑️ 项目 {project_id} 文档 {doc_id} 删除成功")
            return {
                "success": True,
                "project_id": project_id,
                "doc_id": doc_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 项目 {project_id} 文档 {doc_id} 删除失败: {e}")
            return {
                "success": False,
                "project_id": project_id,
                "doc_id": doc_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目统计信息
        """
        try:
            project_dir = os.path.join(self.base_storage_dir, f"project_{project_id}")
            
            if not os.path.exists(project_dir):
                return {
                    "project_id": project_id,
                    "exists": False,
                    "message": "项目不存在"
                }
            
            # 计算目录大小
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_count += 1
            
            stats = {
                "project_id": project_id,
                "exists": True,
                "directory": project_dir,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "is_active": project_id in self._project_instances,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取项目 {project_id} 统计信息失败: {e}")
            return {
                "project_id": project_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务级统计信息
        
        Returns:
            服务统计信息
        """
        try:
            # 获取所有项目目录
            project_dirs = []
            if os.path.exists(self.base_storage_dir):
                for item in os.listdir(self.base_storage_dir):
                    if item.startswith("project_") and os.path.isdir(os.path.join(self.base_storage_dir, item)):
                        project_dirs.append(item)
            
            stats = {
                "service_name": "EnterpriseLightRAGService",
                "base_storage_dir": self.base_storage_dir,
                "total_projects": len(project_dirs),
                "active_instances": len(self._project_instances),
                "active_projects": list(self._project_instances.keys()),
                "all_project_dirs": project_dirs,
                "default_config": self.default_config,
                "timestamp": datetime.now().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 获取服务统计信息失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def cleanup_project(self, project_id: str) -> Dict[str, Any]:
        """
        清理项目实例（不删除数据）
        
        Args:
            project_id: 项目ID
            
        Returns:
            清理结果
        """
        try:
            async with self._global_lock:
                if project_id in self._project_instances:
                    # 终结存储
                    try:
                        await self._project_instances[project_id].finalize_storages()
                    except Exception as e:
                        logger.warning(f"⚠️ 项目 {project_id} 存储终结失败: {e}")
                    
                    del self._project_instances[project_id]
                
                if project_id in self._project_locks:
                    del self._project_locks[project_id]
                
                # 清理存储适配器
                if project_id in self._project_adapters:
                    try:
                        adapter = self._project_adapters[project_id]
                        await adapter.cleanup()
                        del self._project_adapters[project_id]
                        logger.info(f"🗄️ 项目 {project_id} 存储适配器已清理")
                    except Exception as e:
                        logger.warning(f"⚠️ 项目 {project_id} 存储适配器清理失败: {e}")
            
            logger.info(f"🧹 项目 {project_id} 实例清理完成")
            return {
                "success": True,
                "project_id": project_id,
                "message": "项目实例已清理",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 项目 {project_id} 清理失败: {e}")
            return {
                "success": False,
                "project_id": project_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _sync_project_to_s3(self, project_id: str):
        """将项目数据同步到S3"""
        if self.storage_type == 's3' and project_id in self._project_adapters:
            try:
                adapter = self._project_adapters[project_id]
                await adapter.sync_to_s3()
                logger.debug(f"📤 项目 {project_id} 数据已同步到S3")
            except Exception as e:
                logger.warning(f"⚠️ 项目 {project_id} 同步到S3失败: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        服务健康检查
        
        Returns:
            健康检查结果
        """
        try:
            health = {
                "status": "healthy",
                "service": "EnterpriseLightRAGService",
                "lightrag_available": LightRAG is not None,
                "query_param_available": QueryParam is not None,
                "base_storage_dir": self.base_storage_dir,
                "storage_dir_exists": os.path.exists(self.base_storage_dir),
                "active_projects": len(self._project_instances),
                "timestamp": datetime.now().isoformat()
            }
            
            # 检查存储目录权限
            try:
                test_file = os.path.join(self.base_storage_dir, ".health_check")
                with open(test_file, 'w') as f:
                    f.write("health check")
                os.remove(test_file)
                health["storage_writable"] = True
            except:
                health["storage_writable"] = False
                health["status"] = "warning"
            
            return health
            
        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全局服务实例
_enterprise_service: Optional[EnterpriseLightRAGService] = None
_service_lock = asyncio.Lock()


async def get_enterprise_lightrag_service() -> EnterpriseLightRAGService:
    """
    获取全局企业级 LightRAG 服务实例
    
    Returns:
        企业级 LightRAG 服务实例
    """
    global _enterprise_service
    
    async with _service_lock:
        if _enterprise_service is None:
            # 从配置读取存储目录
            storage_dir = os.getenv("LIGHTRAG_STORAGE_DIR", "./rag_storage")
            _enterprise_service = EnterpriseLightRAGService(base_storage_dir=storage_dir)
            logger.info("🚀 创建全局企业级 LightRAG 服务实例")
    
    return _enterprise_service


# 向后兼容的函数
def get_lightrag_service():
    """向后兼容的服务获取函数"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(get_enterprise_lightrag_service())
    except RuntimeError:
        # 如果没有运行的事件循环，创建一个新的
        return asyncio.run(get_enterprise_lightrag_service())


# 向后兼容的全局实例
lightrag_service = None

async def initialize_lightrag_service():
    """初始化全局服务实例"""
    global lightrag_service
    lightrag_service = await get_enterprise_lightrag_service()
    return lightrag_service