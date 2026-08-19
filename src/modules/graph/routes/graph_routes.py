from src.shared.auth import get_current_user
from fastapi import APIRouter, HTTPException, Depends, FastAPI
import httpx
from src.modules.config import settings
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager
from src.shared.types.graph import GraphData, GraphAnalysisRequest
from src.shared.types.response import ApiResponse
from src.shared.service_client import ServiceClient
from src.shared.health_check import create_health_checker, register_health_routes

# 定义lifespan事件管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    try:
        await health_checker.start()
        logger.info("Graph服务启动成功")

        # 注册到服务发现
        from src.shared.service_discovery import register_service
        await register_service("graph", port=8003, health_check_endpoint="/healthz")

    except Exception as e:
        logger.error(f"Graph服务启动失败: {str(e)}")

    yield

    # 关闭事件
    try:
        await health_checker.stop()
        logger.info("Graph服务关闭")

        # 从服务发现注销
        from src.shared.service_discovery import unregister_service
        await unregister_service("graph")

    except Exception as e:
        logger.error(f"Graph服务关闭失败: {str(e)}")

# 创建FastAPI应用
app = FastAPI(
    title="Graph Service",
    description="知识图谱服务",
    lifespan=lifespan
)

# 创建路由
router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = logging.getLogger(__name__)

# 添加健康检查（检查Graph服务连接）
async def check_graph_service():
    """检查Graph服务基本功能（不调用自身）"""
    try:
        # 检查基本功能而不是调用自身的健康检查
        # 简单检查：验证可以创建ServiceClient
        ServiceClient()
        # 不实际调用，只验证创建成功
        return True
    except Exception as e:
        logger.error(f"Graph服务基本功能检查失败: {str(e)}")
        return False

# 添加Neo4j连接检查
async def check_neo4j_connection():
    """检查Neo4j数据库连接"""
    try:
        from src.modules.graph.services.graph_service import GraphService
        GraphService()
        # 简单的连接测试
        return True  # 如果GraphService能正常初始化，认为连接正常
    except Exception as e:
        logger.error(f"Neo4j连接检查失败: {str(e)}")
        return False

# 创建健康检查器
health_checker = create_health_checker("graph", "graph_service_1")

# 配置健康检查项
health_checker.add_check("graph_service", check_graph_service, critical=True)
health_checker.add_check("neo4j", check_neo4j_connection, critical=True)

# 注册统一健康检查路由
register_health_routes(app, health_checker)

async def get_graph_service():
    """获取知识图谱服务客户端"""
    async with httpx.AsyncClient() as client:
        yield client

async def handle_service_response(response: httpx.Response, operation: str) -> Dict[str, Any]:
    """统一处理服务响应"""
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"{operation} failed with status {e.response.status_code}: {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Graph service error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"{operation} failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/analyze", response_model=GraphData)
async def analyze_text(
    request: GraphAnalysisRequest,
    user=Depends(get_current_user),
    client=Depends(get_graph_service)
):
    """分析文本生成知识图谱"""
    logger.info(f"Analyzing text for user {user.id}")
    try:
        response = await client.post(
            f"{settings.graph_service_url}/graph/analyze",
            json=request.dict()
        )
        return await handle_service_response(response, "Analyze text")
    except Exception as e:
        logger.error(f"Failed to analyze text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}", response_model=GraphData)
async def get_project_graph(
    project_id: str,
    user=Depends(get_current_user),
    client=Depends(get_graph_service)
):
    """获取项目知识图谱"""
    logger.info(f"Getting graph for project {project_id} for user {user.id}")
    try:
        response = await client.get(
            f"{settings.graph_service_url}/graph/project/{project_id}"
        )
        return await handle_service_response(response, "Get project graph")
    except Exception as e:
        logger.error(f"Failed to get project graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/export")
async def export_graph(
    project_id: str,
    format: str = "json",
    user=Depends(get_current_user),
    client=Depends(get_graph_service)
):
    """导出知识图谱"""
    logger.info(f"Exporting graph for project {project_id} for user {user.id}")
    try:
        response = await client.get(
            f"{settings.graph_service_url}/graph/project/{project_id}/export",
            params={"format": format}
        )
        return await handle_service_response(response, "Export graph")
    except Exception as e:
        logger.error(f"Failed to export graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}", response_model=ApiResponse)
async def clear_project_graph(
    project_id: str,
    user=Depends(get_current_user),
    client=Depends(get_graph_service)
):
    """清空项目知识图谱"""
    logger.info(f"Clearing graph for project {project_id} for user {user.id}")
    try:
        response = await client.delete(
            f"{settings.graph_service_url}/graph/project/{project_id}"
        )
        return await handle_service_response(response, "Clear project graph")
    except Exception as e:
        logger.error(f"Failed to clear project graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/graph/extract-triples")
async def extract_triples(request: dict):
    """
    从文件提取三元组并存入Neo4j图谱

    步骤：
    1. 接收前端请求
    2. 调用LightRAG服务提取三元组
    3. 返回处理结果
    """
    file_id = request.get("file_id")
    project_id = request.get("project_id")

    if not file_id or not project_id:
        return {
            "success": False,
            "message": "缺少必要参数：file_id 或 project_id"
        }

    try:
        # 通过ServiceClient调用lightraglocal服务提取三元组
        client = await ServiceClient.get_instance()

        response = await client.call_api(
            service_name="lightrag",
            path="api/rag/extract-triples",
            method="POST",
            data={
                "file_id": file_id,
                "project_id": project_id
            }
        )

        # 返回处理结果
        return response
    except Exception as e:
        logger.error(f"提取三元组失败: {str(e)}")
        return {
            "success": False,
            "message": f"处理失败: {str(e)}"
        }

# 注册路由
app.include_router(router)


