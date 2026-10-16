"""
企业级 RAG 路由

完全重写的路由系统，集成企业级 LightRAG 服务
支持完全项目隔离和企业级部署
"""

from fastapi import APIRouter, Body, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import json
import re

from ..services.enterprise_lightrag_service import get_enterprise_lightrag_service
from .graph_utils import build_relationship_edges
from src.shared.project_access import (
    require_authenticated as _require_authenticated,
    require_project_access as _require_project_access,
)

# 全局文件状态管理器
processing_files: Dict[str, Dict[str, Any]] = {}

router = APIRouter(prefix="/rag", tags=["enterprise-rag"])
logger = logging.getLogger(__name__)

async def fix_unknown_source_references(result_text: str, project_id: str) -> str:
    """
    修复查询结果中的unknown_source引用，替换为实际文件名
    """
    if not result_text or "unknown_source" not in result_text:
        return result_text

    try:
        # 引用文件名也从当前项目实际工作区读取。
        service = await get_enterprise_lightrag_service()
        await service._get_project_rag(project_id)
        adapter = service._project_adapters.get(project_id)
        working_dir = adapter.get_working_dir() if adapter else str(Path(service.base_storage_dir) / f"project_{project_id}")
        project_dir = Path(working_dir) / f"project_{project_id}"
        chunks_file = project_dir / "vdb_chunks.json"

        # 构建文件名映射
        file_mapping = {}

        if chunks_file.exists():
            with open(chunks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chunks = data.get('data', [])

                # 从chunks中提取文件信息
                for chunk in chunks:
                    # 尝试多种方式获取文件路径
                    file_path = (chunk.get('file_path') or
                               chunk.get('source') or
                               chunk.get('metadata', {}).get('file_path') or
                               chunk.get('metadata', {}).get('source') or
                               chunk.get('metadata', {}).get('filename'))

                    if file_path and file_path != 'unknown_source':
                        # 提取文件名
                        if file_path.startswith('http'):
                            filename = Path(file_path).name or file_path.split('/')[-1]
                        else:
                            filename = Path(file_path).name

                        if filename:
                            file_mapping['unknown_source'] = filename
                            break

                # 如果没有找到文件路径，尝试从chunk内容推断
                if 'unknown_source' not in file_mapping or file_mapping['unknown_source'] == 'unknown_source':
                    for chunk in chunks:
                        title = chunk.get('title') or chunk.get('metadata', {}).get('title')
                        if title:
                            file_mapping['unknown_source'] = f"{title}.txt"
                            break

                    # 最后的备选方案
                    if 'unknown_source' not in file_mapping:
                        file_mapping['unknown_source'] = f"项目{project_id}文档"

        # 执行替换
        fixed_text = result_text
        for old_ref, new_ref in file_mapping.items():
            # 替换各种格式的引用
            fixed_text = re.sub(r'\[KG/DC\]\s*unknown_source', f'[DC] {new_ref}', fixed_text)
            fixed_text = re.sub(r'\[DC\]\s*unknown_source', f'[DC] {new_ref}', fixed_text)
            fixed_text = re.sub(r'\[KG\]\s*unknown_source', f'[KG] {new_ref}', fixed_text)
            fixed_text = re.sub(r'unknown_source\s*\(Document Chunks\)', f'{new_ref} (Document Chunks)', fixed_text)
            fixed_text = re.sub(r'unknown_source\s*\(Knowledge Graph\)', f'{new_ref} (Knowledge Graph)', fixed_text)

        return fixed_text

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"修复unknown_source引用失败: {e}")
        return result_text

# ===== 请求/响应模型 =====

class DocumentInsertRequest(BaseModel):
    """文档插入请求"""
    project_id: str = Field(..., description="项目ID")
    content: str = Field(..., description="文档内容")
    metadata: Optional[Dict[str, Any]] = Field(None, description="文档元数据")

class DocumentInsertResponse(BaseModel):
    """文档插入响应"""
    success: bool
    project_id: str
    content_length: Optional[int] = None
    duration_seconds: Optional[float] = None
    timestamp: str
    error: Optional[str] = None

class KnowledgeQueryRequest(BaseModel):
    """知识查询请求"""
    project_id: str = Field(..., description="项目ID")
    query: str = Field(..., description="查询内容")
    mode: str = Field("naive", description="查询模式: naive, local, global, hybrid")

class KnowledgeQueryResponse(BaseModel):
    """知识查询响应"""
    success: bool
    project_id: str
    query: str
    result: Optional[str] = None
    duration_seconds: Optional[float] = None
    timestamp: str
    error: Optional[str] = None


class DocumentDeleteRequest(BaseModel):
    """文档删除请求"""
    project_id: str = Field(..., description="项目ID")
    doc_id: str = Field(..., description="文档ID")

class ProjectStatsResponse(BaseModel):
    """项目统计响应"""
    project_id: str
    exists: bool
    directory: Optional[str] = None
    total_size_mb: Optional[float] = None
    file_count: Optional[int] = None
    is_active: Optional[bool] = None
    timestamp: str
    error: Optional[str] = None

class ServiceStatsResponse(BaseModel):
    """服务统计响应"""
    service_name: str
    total_projects: int
    active_instances: int
    active_projects: List[str]
    timestamp: str

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    lightrag_available: bool
    timestamp: str

# ===== 核心 API 端点 =====

@router.post("/insert", response_model=DocumentInsertResponse)
async def insert_document(request: DocumentInsertRequest, http_request: Request):
    """
    为特定项目插入文档

    实现完全项目隔离，每个项目的数据完全独立
    """
    try:
        await _require_project_access(http_request, request.project_id)
        service = await get_enterprise_lightrag_service()
        result = await service.insert_document(
            project_id=request.project_id,
            content=request.content,
            metadata=request.metadata
        )

        if result["success"]:
            return DocumentInsertResponse(**result)
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "插入失败"))

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"文档插入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(request: KnowledgeQueryRequest, http_request: Request):
    """
    查询特定项目的知识

    确保只能查询到指定项目的内容，完全隔离
    """
    try:
        await _require_project_access(http_request, request.project_id)
        service = await get_enterprise_lightrag_service()
        result = await service.query_project(
            project_id=request.project_id,
            query=request.query,
            mode=request.mode
        )

        if result["success"]:
            return KnowledgeQueryResponse(**result)
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "查询失败"))

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"知识查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/document")
async def delete_document(request: DocumentDeleteRequest, http_request: Request):
    """
    删除特定项目的文档
    """
    try:
        await _require_project_access(http_request, request.project_id)
        service = await get_enterprise_lightrag_service()
        result = await service.delete_document(
            project_id=request.project_id,
            doc_id=request.doc_id
        )

        if result["success"]:
            return {"status": "success", "message": "文档删除成功", "result": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "删除失败"))

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"文档删除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 管理 API 端点 =====

@router.get("/project/{project_id}/stats", response_model=ProjectStatsResponse)
async def get_project_stats(project_id: str, http_request: Request):
    """
    获取项目统计信息
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()
        stats = service.get_project_stats(project_id)
        return ProjectStatsResponse(**stats)

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"获取项目统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/service/stats", response_model=ServiceStatsResponse)
async def get_service_stats(http_request: Request):
    """
    获取服务级统计信息
    """
    try:
        await _require_authenticated(http_request)
        service = await get_enterprise_lightrag_service()
        stats = service.get_service_stats()
        return ServiceStatsResponse(**stats)

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"获取服务统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/project/{project_id}/cleanup")
async def cleanup_project(project_id: str, http_request: Request):
    """
    清理项目实例（不删除数据）
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()
        result = await service.cleanup_project(project_id)

        if result["success"]:
            return {"status": "success", "message": "项目清理成功", "result": result}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "清理失败"))

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"项目清理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/healthz", response_model=HealthCheckResponse)
async def health_check():
    """
    服务健康检查
    """
    try:
        service = await get_enterprise_lightrag_service()
        health = await service.health_check()

        status_code = 200 if health["status"] == "healthy" else 503
        return JSONResponse(content=health, status_code=status_code)

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            status_code=503
        )

# ===== 兼容性 API（保持向后兼容）=====

@router.post("/insert_legacy")
async def insert_document_legacy(
    http_request: Request,
    project_id: str = Body(...),
    content: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None)
):
    """向后兼容的文档插入接口"""
    request = DocumentInsertRequest(
        project_id=project_id,
        content=content,
        metadata=metadata
    )
    return await insert_document(request, http_request)

@router.post("/query_legacy")
async def query_knowledge_legacy(
    http_request: Request,
    project_id: str = Body(...),
    query: str = Body(...),
    mode: str = Body("naive")
):
    """向后兼容的知识查询接口"""
    request = KnowledgeQueryRequest(
        project_id=project_id,
        query=query,
        mode=mode
    )
    return await query_knowledge(request, http_request)

# ===== 批量操作 API =====

@router.post("/batch/insert")
async def batch_insert_documents(
    requests: List[DocumentInsertRequest],
    background_tasks: BackgroundTasks,
    http_request: Request
):
    """
    批量插入文档
    """
    try:
        auth_context = await _require_authenticated(http_request)
        verified_projects = set()
        for req in requests:
            if req.project_id not in verified_projects:
                await _require_project_access(http_request, req.project_id, auth_context=auth_context)
                verified_projects.add(req.project_id)

        service = await get_enterprise_lightrag_service()

        # 启动后台任务进行批量插入
        task_id = f"batch_insert_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        async def batch_insert_task():
            results = []
            for req in requests:
                try:
                    result = await service.insert_document(
                        project_id=req.project_id,
                        content=req.content,
                        metadata=req.metadata
                    )
                    results.append(result)
                except HTTPException:
                    raise
                except Exception as e:
                    results.append({
                        "success": False,
                        "project_id": req.project_id,
                        "error": str(e)
                    })

            logger.info(f"批量插入任务 {task_id} 完成: {len(results)} 个文档")
            return results

        background_tasks.add_task(batch_insert_task)

        return {
            "status": "accepted",
            "task_id": task_id,
            "message": f"批量插入任务已启动，共 {len(requests)} 个文档",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"批量插入失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 高级查询 API =====

@router.post("/advanced/query")
async def advanced_query(
    http_request: Request,
    project_id: str = Body(...),
    query: str = Body(...),
    mode: str = Body("hybrid"),
    top_k: int = Body(5),
    include_metadata: bool = Body(True),
    timeout_seconds: int = Body(30)
):
    """
    高级知识查询接口

    支持更多查询参数和配置
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()

        # 使用超时控制
        result = await asyncio.wait_for(
            service.query_project(
                project_id=project_id,
                query=query,
                mode=mode
            ),
            timeout=timeout_seconds
        )

        if result["success"]:
            # 增强响应信息
            enhanced_result = {
                **result,
                "query_config": {
                    "mode": mode,
                    "top_k": top_k,
                    "include_metadata": include_metadata,
                    "timeout_seconds": timeout_seconds
                }
            }
            return enhanced_result
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "查询失败"))

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="查询超时")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"高级查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 前端兼容性API =====

@router.get("/files/{project_id}")
async def get_rag_files(project_id: str, http_request: Request):
    """
    获取项目RAG文件列表 - 返回已处理的文档信息
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()

        # 直接使用存储适配器获取项目数据，不依赖get_project_stats
        storage_adapter = None
        project_exists = False
        files = []

        try:
            # 首先尝试获取现有的存储适配器
            if project_id in service._project_adapters:
                storage_adapter = service._project_adapters[project_id]
                logger.info("📁 使用现有存储适配器")
            else:
                # 如果没有现有适配器，通过获取RAG实例来创建
                logger.info("📁 创建新的存储适配器")
                await service._get_project_rag(project_id)
                if project_id in service._project_adapters:
                    storage_adapter = service._project_adapters[project_id]

            if storage_adapter:
                # 如果是S3模式，先同步数据到本地
                if storage_adapter.storage_type == 's3':
                    logger.info("🔄 S3模式：同步数据到本地缓存")
                    await storage_adapter.sync_from_s3()

                working_dir = storage_adapter.get_working_dir()
                logger.info(f"📁 使用存储适配器路径: {working_dir}")

                # 查找chunks文件 - 直接在工作目录根目录查找
                chunks_file = Path(working_dir) / f"project_{project_id}" / "vdb_chunks.json"
                logger.info(f"📁 查找chunks文件: {chunks_file}")

                if chunks_file.exists():
                    project_exists = True
                    try:
                        with open(chunks_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            chunks = data.get('data', [])
                            logger.info(f"📊 找到 {len(chunks)} 个数据块")

                            # 从chunks中提取文档信息
                            doc_info = {}
                            for chunk in chunks:
                                # 尝试多种方式获取文件路径
                                file_path = (chunk.get('file_path') or
                                           chunk.get('source') or
                                           chunk.get('metadata', {}).get('file_path') or
                                           chunk.get('metadata', {}).get('source') or
                                           chunk.get('metadata', {}).get('filename') or
                                           'unknown_source')

                                doc_id = chunk.get('full_doc_id', chunk.get('__id__', ''))

                                if file_path not in doc_info:
                                    # 智能提取文件名
                                    if file_path != 'unknown_source':
                                        if file_path.startswith('http'):
                                            # URL情况，取最后一部分
                                            filename = Path(file_path).name or file_path.split('/')[-1]
                                        else:
                                            # 普通文件路径
                                            filename = Path(file_path).name
                                    else:
                                        # 从chunk内容或其他字段尝试获取文件名
                                        filename = (chunk.get('title') or
                                                  chunk.get('metadata', {}).get('title') or
                                                  f"文档_{doc_id[:8]}" if doc_id else 'direct_content')

                                    doc_info[file_path] = {
                                        'filename': filename,
                                        'file_id': doc_id,
                                        'status': 'processed',
                                        'chunks_count': 0,
                                        'created_at': chunk.get('__created_at__', 0)
                                    }
                                doc_info[file_path]['chunks_count'] += 1

                            files = list(doc_info.values())
                            logger.info(f"✅ 处理后得到 {len(files)} 个文件")
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(f"读取chunks文件失败: {e}")
                else:
                    logger.warning(f"⚠️ chunks文件不存在: {chunks_file}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"⚠️ 获取存储适配器失败: {e}，使用本地路径")
            # 回退到本地模式检查
            project_data_dir = Path(f"./rag_storage/project_{project_id}/project_{project_id}")
            chunks_file = project_data_dir / "vdb_chunks.json"
            if chunks_file.exists():
                project_exists = True
                # 这里可以加载本地文件的逻辑，但通常S3模式不应该回退到这里

        # 添加正在处理的文件
        project_key = f"project_{project_id}"
        if project_key in processing_files:
            for file_id, file_info in processing_files[project_key].items():
                # 检查是否已经在已处理文件中
                if not any(f.get('file_id') == file_id for f in files):
                    files.append(file_info)

        return {
            "success": True,
            "project_id": project_id,
            "files": files,
            "total_documents": len(files),
            "project_exists": project_exists,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/build/{project_id}")
async def build_rag(
    project_id: str,
    selected_files: List[str] = Body([], embed=True),
    http_request: Request = None
):
    """
    构建RAG索引 - 从选定的文件构建知识库
    """
    try:
        if http_request is not None:
            await _require_project_access(http_request, project_id)
        logger.info(f"🔨 开始构建RAG: project_id={project_id}, selected_files={selected_files}")

        service = await get_enterprise_lightrag_service()

        # 如果没有选择文件，返回当前状态
        if not selected_files:
            stats = service.get_project_stats(project_id)
            return {
                "success": True,
                "project_id": project_id,
                "message": "未选择文件，返回当前项目状态",
                "status": "empty" if not stats["exists"] else "ready",
                "project_stats": stats,
                "timestamp": datetime.now().isoformat()
            }

        # 先获取所有文件名并立即添加到显示列表
        project_key = f"project_{project_id}"
        if project_key not in processing_files:
            processing_files[project_key] = {}

        for file_id in selected_files:
            # 立即获取文件名并添加到处理列表，显示"处理中"状态
            file_name = await get_file_name_from_service(project_id, file_id)
            processing_files[project_key][file_id] = {
                'filename': file_name or f"file_{file_id}.txt",
                'file_id': file_id,
                'status': 'processing',
                'chunks_count': 0,
                'created_at': datetime.now().timestamp()
            }

        # 处理选定的文件
        processed_files = []
        failed_files = []

        for file_id in selected_files:
            try:
                logger.info(f"📄 处理文件: {file_id}")

                # 尝试从文件服务获取文件内容
                file_content = await get_file_content_from_service(project_id, file_id)

                if file_content:
                    # 文件名已经在上面获取过了
                    file_name = processing_files[project_key][file_id]['filename']

                    # 插入文档到LightRAG，传递file_path参数
                    result = await service.insert_document(
                        project_id=project_id,
                        content=file_content,
                        metadata={
                            "file_id": file_id,
                            "source": "file_service",
                            "imported_at": datetime.now().isoformat(),
                            "filename": file_name or f"file_{file_id}.txt"  # 使用filename而不是file_name
                        }
                    )

                    if result["success"]:
                        processed_files.append(file_id)
                        # 更新状态为已完成
                        processing_files[project_key][file_id]['status'] = 'completed'
                        processing_files[project_key][file_id]['chunks_count'] = 1  # 暂时设为1，后续可以优化
                        logger.info(f"✅ 文件处理成功: {file_id}")
                    else:
                        failed_files.append({"file_hash": file_id, "error": result.get("error", "处理失败")})
                        # 更新状态为失败
                        processing_files[project_key][file_id]['status'] = 'failed'
                        processing_files[project_key][file_id]['error'] = result.get("error", "处理失败")
                        logger.error(f"❌ 文档插入失败: {file_id} - {result.get('error')}")
                else:
                    failed_files.append({"file_hash": file_id, "error": "无法获取文件内容"})
                    # 更新状态为失败
                    processing_files[project_key][file_id]['status'] = 'failed'
                    processing_files[project_key][file_id]['error'] = "无法获取文件内容"
                    logger.error(f"❌ 无法获取文件内容: {file_id}")

            except HTTPException:

                raise

            except Exception as e:
                failed_files.append({"file_hash": file_id, "error": str(e)})
                # 更新状态为失败
                if project_key in processing_files and file_id in processing_files[project_key]:
                    processing_files[project_key][file_id]['status'] = 'failed'
                    processing_files[project_key][file_id]['error'] = str(e)
                logger.error(f"❌ 处理文件异常: {file_id} - {e}")

        # 返回处理结果
        success_count = len(processed_files)
        total_count = len(selected_files)

        return {
            "success": success_count > 0,
            "project_id": project_id,
            "message": f"处理完成: {success_count}/{total_count} 个文件成功",
            "status": "completed" if success_count > 0 else "failed",
            "file_count": total_count,
            "processed_count": success_count,
            "processed_files": processed_files,
            "failed_files": failed_files,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ RAG构建失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_file_content_from_service(project_id: str, file_id: str) -> Optional[str]:
    """根据存储类型从不同位置获取文件内容"""
    import os

    try:
        # 优先通过文件服务API读取，避免依赖底层对象存储路径细节
        try:
            from src.shared.service_client import ServiceClient

            client = ServiceClient()
            response = await client.call_service(
                service_name="file",
                endpoint=f"/api/file/content/{project_id}/{file_id}",
                method="GET",
                use_service_auth=True
            )

            if response:
                content = response.get("content")
                if not content and isinstance(response.get("data"), dict):
                    content = (
                        response["data"].get("content")
                        or response["data"].get("markdown_content")
                    )
                if content:
                    logger.info(f"✅ 通过文件服务API获取文件内容成功: {file_id} ({len(content)} 字符)")
                    return content
        except Exception as api_error:
            logger.warning(f"⚠️ 文件服务API获取内容失败，回退存储层读取: {file_id}, error={api_error}")

        storage_type = os.getenv("STORAGE_TYPE", "local")
        logger.info(f"📁 存储类型: {storage_type}, 获取文件: {file_id}")

        if storage_type == "s3":
            # 从MinIO获取文件内容
            return await get_file_content_from_minio(project_id, file_id)
        else:
            # 从本地content_dir获取文件内容
            return await get_file_content_from_local(project_id, file_id)

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ 获取文件内容异常: {file_id} - {e}")
        return None


async def get_file_content_from_minio(project_id: str, file_id: str) -> Optional[str]:
    """从MinIO获取文件内容"""
    try:
        # 使用存储工厂获取MinIO存储实例
        from src.shared.storage.storage_factory import get_storage

        # 同时尝试 content 与 upload 两种目录前缀
        for directory_type in ("content", "upload"):
            storage = await get_storage(directory_type=directory_type)

            # 智能处理文件路径：兼容是否带项目目录、是否带扩展名
            possible_paths = [
                file_id,
                f"{file_id}.txt",
                file_id.rstrip(".txt"),
                f"{project_id}/{file_id}",
                f"{project_id}/{file_id}.txt",
            ]

            seen = set()
            unique_paths = []
            for path in possible_paths:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)

            logger.info(f"🗄️ 尝试从MinIO获取文件: {file_id}, directory_type={directory_type}")

            for file_path in unique_paths:
                logger.debug(f"  尝试路径: {file_path}")
                if await storage.file_exists(file_path):
                    content = await storage.get_file(file_path)
                    if isinstance(content, bytes):
                        content = content.decode("utf-8")

                    logger.info(
                        f"✅ 成功从MinIO获取文件内容: {file_id} -> {file_path} "
                        f"(directory_type={directory_type}, {len(content)} 字符)"
                    )
                    return content

        logger.warning(f"⚠️ MinIO中文件不存在（content/upload均已尝试）: {file_id}")
        return None

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ 从MinIO获取文件失败: {file_id} - {e}")
        return None


async def get_file_name_from_service(project_id: str, file_id: str) -> Optional[str]:
    """从文件服务获取文件名"""
    try:
        # 通过API调用获取文件信息，使用正确的API路径
        from src.shared.service_client import ServiceClient

        client = ServiceClient()
        response = await client.call_service(
            service_name="file",
            endpoint=f"/api/file/info/{project_id}/{file_id}",
            method="GET",
            use_service_auth=True
        )

        if response and response.get("success"):
            file_info = response.get("data") or response
            # 优先使用filename，然后是name，最后使用file_id
            filename = file_info.get("filename") or file_info.get("name") or file_info.get("original_filename")
            if filename:
                logger.info(f"✅ 获取到原始文件名: {file_id} -> {filename}")
                return filename

        logger.warning(f"⚠️ 无法获取文件名，使用默认名: {file_id}")
        return f"file_{file_id}.txt"

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ 获取文件名异常: {file_id} - {e}")
        return f"file_{file_id}.txt"


async def get_file_content_from_local(project_id: str, file_id: str) -> Optional[str]:
    """从本地content_dir获取文件内容"""
    import os
    from pathlib import Path

    try:
        # 获取content目录路径，使用hashkey + .txt扩展名
        content_dir = os.getenv("CONTENT_DIR", "./content")
        file_path = Path(content_dir) / f"{file_id}.txt"

        logger.info(f"📁 从本地获取文件: {file_path}")

        if file_path.exists() and file_path.is_file():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            logger.info(f"✅ 成功从本地获取文件内容: {file_id} ({len(content)} 字符)")
            return content
        else:
            logger.warning(f"⚠️ 本地文件不存在: {file_path}")
            return None

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ 从本地获取文件失败: {file_id} - {e}")
        return None

@router.get("/status/{project_id}")
async def get_file_status(project_id: str, http_request: Request):
    """
    获取项目状态 - 返回实际的项目和文档状态
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()

        # 获取项目统计信息
        stats = service.get_project_stats(project_id)

        # 从实际工作区读取状态，S3 模式的索引位于本地缓存目录。
        await service._get_project_rag(project_id)
        adapter = service._project_adapters.get(project_id)
        working_dir = adapter.get_working_dir() if adapter else str(Path(service.base_storage_dir) / f"project_{project_id}")
        project_dir = Path(working_dir) / f"project_{project_id}"

        statuses = {}
        entities_count = 0
        relationships_count = 0
        chunks_count = 0

        # 检查各个数据文件
        for file_name, description in [
            ("vdb_entities.json", "实体数据"),
            ("vdb_relationships.json", "关系数据"),
            ("vdb_chunks.json", "文档块数据")
        ]:
            file_path = project_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        count = len(data.get('data', []))

                        if 'entities' in file_name:
                            entities_count = count
                        elif 'relationships' in file_name:
                            relationships_count = count
                        elif 'chunks' in file_name:
                            chunks_count = count

                        statuses[file_name] = {
                            "status": "ready",
                            "count": count,
                            "description": description
                        }
                except HTTPException:
                    raise
                except Exception as e:
                    statuses[file_name] = {
                        "status": "error",
                        "error": str(e),
                        "description": description
                    }
            else:
                statuses[file_name] = {
                    "status": "missing",
                    "description": description
                }

        # 确定整体状态
        if entities_count > 0 and chunks_count > 0:
            overall_status = "ready"
            message = f"项目就绪: {entities_count}个实体, {relationships_count}个关系, {chunks_count}个文档块"
        elif chunks_count > 0:
            overall_status = "processing"
            message = f"处理中: {chunks_count}个文档块, {entities_count}个实体"
        else:
            overall_status = "empty"
            message = "项目为空，尚未处理任何文档"

        return {
            "success": True,
            "project_id": project_id,
            "statuses": statuses,
            "overall_status": overall_status,
            "message": message,
            "stats": {
                "entities_count": entities_count,
                "relationships_count": relationships_count,
                "chunks_count": chunks_count
            },
            "project_stats": stats,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_rag(
    http_request: Request,
    query: str = Body(...),
    project_id: str = Body(...),
    mode: str = Body("hybrid"),
    top_k: int = Body(5),
    rerank: bool = Body(False),
    only_need_context: bool = Body(False)
):
    """
    RAG搜索 - 前端兼容接口
    """
    try:
        await _require_project_access(http_request, project_id)
        service = await get_enterprise_lightrag_service()

        result = await service.query_project(
            project_id=project_id,
            query=query,
            mode=mode,
            only_need_context=only_need_context,
            top_k=top_k, rerank=rerank
        )

        if result["success"]:
            # 修复结果中的unknown_source引用
            fixed_result = result["result"] if only_need_context else await fix_unknown_source_references(result["result"], project_id)

            return {
                "success": True,
                "result": fixed_result,
                "project_id": project_id,
                "query": query,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "搜索失败"))

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/knowledge-graph")
async def get_knowledge_graph(project_id: str, http_request: Request):
    """
    获取项目的知识图谱数据 - 前端图谱组件专用接口
    """
    try:
        await _require_project_access(http_request, project_id)
        logger.info(f"🌐 获取项目 {project_id} 的知识图谱数据")

        # 获取企业级LightRAG服务实例
        service = await get_enterprise_lightrag_service()

        nodes = []
        edges = []

        # 获取项目的RAG实例以访问存储适配器
        try:
            await service._get_project_rag(project_id)

            # 获取存储适配器
            storage_adapter = None
            if project_id in service._project_adapters:
                storage_adapter = service._project_adapters[project_id]
                working_dir = storage_adapter.get_working_dir()
                project_data_dir = Path(working_dir) / f"project_{project_id}"
            else:
                # 回退到本地模式
                project_data_dir = Path(f"./rag_storage/project_{project_id}/project_{project_id}")

            # 读取实体数据
            entities_file = project_data_dir / "vdb_entities.json"
            if entities_file.exists():
                try:
                    with open(entities_file, 'r', encoding='utf-8') as f:
                        entities_data = json.load(f)
                        entities = entities_data.get('data', [])

                        for entity in entities:
                            entity_id = entity.get('__id__', entity.get('id'))
                            entity_name = entity.get('entity_name', entity.get('name', ''))
                            entity_type = entity.get('entity_type', 'Entity')
                            description = entity.get('description', '')

                            if entity_id and entity_name:
                                nodes.append({
                                    "id": str(entity_id),
                                    "label": str(entity_name),
                                    "type": str(entity_type),
                                    "description": str(description),
                                    "properties": entity
                                })

                    logger.info(f"✅ 加载了 {len(nodes)} 个实体节点")
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"❌ 读取实体数据失败: {e}")

            # 读取关系数据
            relationships_file = project_data_dir / "vdb_relationships.json"
            if relationships_file.exists():
                try:
                    with open(relationships_file, 'r', encoding='utf-8') as f:
                        relationships_data = json.load(f)
                        relationships = relationships_data.get('data', [])

                        edges.extend(
                            build_relationship_edges(nodes, relationships)
                        )

                    logger.info(f"✅ 加载了 {len(edges)} 个关系边")
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"❌ 读取关系数据失败: {e}")

            # 如果没有关系数据，从文档块中推断一些连接
            if not edges and nodes:
                logger.info("🔗 尝试从文档块推断节点连接")

                chunks_file = project_data_dir / "vdb_chunks.json"
                if chunks_file.exists():
                    try:
                        with open(chunks_file, 'r', encoding='utf-8') as f:
                            chunks_data = json.load(f)
                            chunks = chunks_data.get('data', [])

                            # 为同一文档的实体创建连接
                            doc_entities = {}
                            for chunk in chunks:
                                doc_id = chunk.get('full_doc_id', chunk.get('__id__', ''))
                                if doc_id:
                                    if doc_id not in doc_entities:
                                        doc_entities[doc_id] = []

                                    # 从chunk内容中查找提到的实体
                                    chunk_content = chunk.get('content', '').lower()
                                    for node in nodes:
                                        if node['label'].lower() in chunk_content:
                                            doc_entities[doc_id].append(node['id'])

                            # 为同一文档中的实体创建关联边
                            edge_id = 0
                            for doc_id, entity_ids in doc_entities.items():
                                if len(entity_ids) > 1:
                                    for i in range(len(entity_ids)):
                                        for j in range(i + 1, len(entity_ids)):
                                            edges.append({
                                                "source": entity_ids[i],
                                                "target": entity_ids[j],
                                                "label": "共现于文档",
                                                "type": "document_cooccurrence",
                                                "properties": {
                                                    "doc_id": doc_id,
                                                    "edge_id": f"inferred_{edge_id}"
                                                }
                                            })
                                            edge_id += 1

                            logger.info(f"🔗 从文档推断了 {len(edges)} 个连接")
                    except HTTPException:
                        raise
                    except Exception as e:
                        logger.error(f"❌ 推断连接失败: {e}")

        except HTTPException:

            raise

        except Exception as e:
            logger.error(f"❌ 无法获取项目RAG实例: {e}")
            # 即使获取RAG实例失败，也创建示例数据

        # 确保至少有一些可视化的数据
        if not nodes:
            logger.warning("⚠️ 没有找到实体数据，创建示例节点")
            nodes = [
                {
                    "id": "empty_project",
                    "label": f"项目 {project_id}",
                    "type": "Project",
                    "description": "该项目暂无图谱数据",
                    "properties": {}
                }
            ]

        response_data = {
            "success": True,
            "nodes": nodes,
            "edges": edges,
            "project_id": project_id,
            "stats": {
                "nodes_count": len(nodes),
                "edges_count": len(edges)
            },
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"🌐 知识图谱数据准备完成: {len(nodes)} 个节点, {len(edges)} 条边")
        return response_data

    except HTTPException:

        raise

    except Exception as e:
        logger.error(f"❌ 获取知识图谱失败: {e}")
        # 返回空图谱而不是抛出异常，确保前端能正常显示
        return {
            "success": False,
            "nodes": [],
            "edges": [],
            "error": str(e),
            "project_id": project_id,
            "timestamp": datetime.now().isoformat()
        }
