"""
企业级 RAG 路由

完全重写的路由系统，集成企业级 LightRAG 服务
支持完全项目隔离和企业级部署
"""

from fastapi import APIRouter, Body, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import json
import re
import os

from ..services.enterprise_lightrag_service import get_enterprise_lightrag_service
from .graph_utils import build_relationship_edges
from src.shared.project_access import (
    require_authenticated as _require_authenticated,
    require_service_access as _require_service_access,
    require_project_access as _require_project_access,
)

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
        records = await _document_statuses(service, request.project_id)
        file_id = next((identifier for identifier, record in records.items()
                        if record.get('doc_id') == request.doc_id), request.doc_id)
        return await delete_rag_file(request.project_id, file_id, http_request)

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
        await _require_service_access(http_request)
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

def _import_jobs(service):
    from ..services.import_jobs import ImportJobs
    if not hasattr(service, "import_jobs"):
        service.import_jobs = ImportJobs(Path(os.getenv("RAG_DIR", service.base_storage_dir)) / "import_jobs")
    return service.import_jobs


async def _document_statuses(service, project_id):
    from lightrag.base import DocStatus
    rag = await service._get_project_rag(project_id)
    statuses = {}
    # Read the status store, not vector files or a fresh S3 download on each poll.
    for state in DocStatus:
        for doc_id, doc in (await rag.doc_status.get_docs_by_status(state)).items():
            statuses[doc_id] = {
                "status": state.value, "file_name": Path(doc.file_path).name,
                "doc_id": doc_id, "chunks_count": doc.chunks_count or 0,
                "created_at": doc.created_at, "updated_at": doc.updated_at,
                "error": doc.error,
            }
    for file_id, job in _import_jobs(service).statuses(project_id).items():
        # Imported files use a stable file-service ID; legacy documents keep theirs.
        doc_id = job.get("doc_id")
        indexed = statuses.pop(doc_id, {}) if doc_id else {}
        statuses[file_id] = {**indexed, **job}
    return statuses


@router.get("/files/{project_id}")
async def get_rag_files(project_id: str, http_request: Request):
    await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()
    statuses = await _document_statuses(service, project_id)
    files = [{**record, "file_id": file_id, "filename": record["file_name"]}
             for file_id, record in statuses.items()]
    return {"success": True, "project_id": project_id, "files": files,
            "total_documents": len(files), "project_exists": bool(files)}


@router.delete("/file/{project_id}/{file_id}")
async def delete_rag_file(project_id: str, file_id: str, http_request: Request):
    await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()
    return await _delete_rag_file(service, project_id, file_id)


async def _delete_rag_file(service, project_id, file_id):
    jobs = _import_jobs(service)
    records = await _document_statuses(service, project_id)
    record = records.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found in this knowledge base")
    if record.get('status') in ('pending', 'processing'):
        raise HTTPException(status_code=409, detail="Document is still importing; retry deletion after it finishes")
    async with jobs.capacity:
        if jobs.statuses(project_id).get(file_id, {}).get('status') in ('pending', 'processing'):
            raise HTTPException(status_code=409, detail="Document is still importing")
        doc_id = record.get('doc_id')
        if doc_id:
            result = await service.delete_document(project_id, doc_id)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Deletion failed'))
        jobs.remove(project_id, file_id, doc_id)
    return {'success': True, 'message': 'Document removed from knowledge base', 'file_id': file_id}


@router.post("/files/delete/{project_id}")
async def delete_rag_files(project_id: str, http_request: Request,
                           file_ids: List[str] = Body(..., embed=True, min_length=1, max_length=100)):
    """Authorize once, delete sequentially, and report each result independently."""
    from time import perf_counter
    await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()
    started = perf_counter()
    results = []
    for file_id in dict.fromkeys(file_ids):
        item_started = perf_counter()
        try:
            result = await _delete_rag_file(service, project_id, file_id)
        except HTTPException as exc:
            result = {'file_id': file_id, 'success': False, 'status_code': exc.status_code, 'message': str(exc.detail)}
        except Exception:
            logger.exception('Batch document deletion failed')
            result = {'file_id': file_id, 'success': False, 'status_code': 500, 'message': 'Document deletion failed'}
        result['duration_seconds'] = round(perf_counter() - item_started, 3)
        results.append(result)
    return {'success': all(item['success'] for item in results), 'results': results,
            'duration_seconds': round(perf_counter() - started, 3)}


@router.post("/build/{project_id}")
async def build_rag(
    project_id: str,
    selected_files: List[str] = Body([], embed=True),
    http_request: Request = None,
):
    if http_request is not None:
        await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()
    jobs = _import_jobs(service)

    async def import_file(file_id):
        name = await get_file_name_from_service(project_id, file_id)
        jobs.update(project_id, file_id, file_name=name or file_id)
        await wait_for_file_processing(project_id, file_id, jobs)
        content = await get_file_content_from_service(project_id, file_id)
        if not content:
            raise ValueError("No extracted text available; finish document processing before importing.")
        from lightrag.utils import clean_text, compute_mdhash_id
        doc_id = compute_mdhash_id(clean_text(content), prefix="doc-")
        jobs.update(project_id, file_id, stage="indexing", doc_id=doc_id)
        result = await service.insert_document(project_id=project_id, content=content,
            metadata={"file_id": file_id, "source": "file_service", "filename": name or file_id})
        if not result.get("success"):
            raise RuntimeError(result.get("error", "Indexing failed"))
        jobs.update(project_id, file_id, doc_id=result.get("doc_id", doc_id))

    accepted = jobs.enqueue(project_id, selected_files, import_file)
    return {"success": True, "project_id": project_id, "status": "accepted",
            "message": "Import queued; poll document status for completion.",
            "file_count": len(accepted), "accepted_files": accepted}


async def wait_for_file_processing(project_id, file_id, jobs):
    """Do not import raw PDF bytes while the file processor is still extracting text."""
    from src.shared.service_client import ServiceClient
    client = ServiceClient()
    async with asyncio.timeout(float(os.getenv("RAG_FILE_READY_TIMEOUT", "300"))):
        while True:
            info = await client.call_service(
                service_name="file", endpoint=f"/api/file/info/{project_id}/{file_id}",
                method="GET", use_service_auth=True)
            if not info or not info.get("success"):
                raise ValueError("File not found in this project")
            state = (info.get("data") or info).get("status")
            if state in ("failed", "error"):
                raise ValueError("Document extraction failed; reprocess the file before importing")
            if state in ("completed", "processed", "ready"):
                return
            jobs.update(project_id, file_id, stage="waiting_extraction")
            await asyncio.sleep(2)


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
    await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()
    statuses = await _document_statuses(service, project_id)
    active = any(item["status"] in ("pending", "processing") for item in statuses.values())
    return {"success": True, "project_id": project_id, "statuses": statuses,
            "overall_status": "processing" if active else ("ready" if statuses else "empty"),
            "progress": _import_jobs(service).progress(project_id)}

@router.post("/search/stream")
async def stream_search_rag(
    http_request: Request,
    query: str = Body(..., min_length=1, max_length=10000),
    project_id: str = Body(...),
    mode: str = Body("hybrid", pattern="^(naive|local|global|hybrid)$"),
):
    # Authorize before sending HTTP 200 or any knowledge content.
    await _require_project_access(http_request, project_id)
    service = await get_enterprise_lightrag_service()

    async def events():
        yield 'data: {"stage": "retrieving"}\n\n'
        try:
            async with asyncio.timeout(120):
                async for event in service.stream_query_project(project_id, query, mode):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            yield 'data: {"error": "Knowledge query timed out"}\n\n'
        except Exception:
            logger.exception("Knowledge query stream failed")
            yield 'data: {"error": "Knowledge query failed; please retry"}\n\n'

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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


@router.get('/admin/tasks')
async def admin_import_tasks(request: Request):
    from src.shared.project_access import require_admin
    await require_admin(request)
    service = await get_enterprise_lightrag_service()
    jobs = _import_jobs(service)
    rows = []
    for path in jobs.directory.glob('*.json'):
        records = json.loads(path.read_text())
        for file_id, record in records.items():
            error = str(record.get('error', '')).lower()
            reason = ('timeout' if 'timeout' in error or 'timed out' in error else
                      'connection' if 'connect' in error else 'processing_failed') if error else None
            rows.append({key: record.get(key) for key in ('project_id', 'status', 'stage', 'created_at', 'updated_at', 'duration_seconds')} | {'file_id': file_id, 'failure_reason': reason})
    rows.sort(key=lambda row: row.get('updated_at') or row.get('created_at') or '', reverse=True)
    return {'tasks': rows[:200], 'total': len(rows)}


@router.post('/admin/retry/{project_id}/{file_id}')
async def admin_retry_import(project_id: str, file_id: str, request: Request):
    from src.shared.project_access import require_admin
    context = await require_admin(request)
    service = await get_enterprise_lightrag_service()
    record = _import_jobs(service).statuses(project_id).get(file_id)
    if not record or record.get('status') != 'failed':
        raise HTTPException(409, 'Only failed import jobs can be retried')
    logger.info('admin_import_retry actor=%s project=%s file=%s', context['user']['user_id'], project_id, file_id)
    return await build_rag(project_id, [file_id], http_request=None)
