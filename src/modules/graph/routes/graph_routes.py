from fastapi import APIRouter, HTTPException, Depends, Body, Query
import logging
from typing import Optional, Dict, Any, List
from ..models.graph import (
    NodeCreate,
    NodeUpdate,
    EdgeCreate,
    EdgeUpdate,
    GraphLayout
)
from ..services.graph_service import GraphService
from ..services.graph_visualizer import graph_visualizer
from src.modules.question.services.question_service import QuestionService
from src.modules.chat.chat_service import ChatService

# 导入共享类型
from src.shared.types.graph import GraphNode, GraphEdge, GraphData
from src.shared.types.response import ApiResponse

router = APIRouter(prefix="/graph", tags=["graph"])
graph_service = GraphService()
question_service = QuestionService()
chat_service = ChatService()
logger = logging.getLogger(__name__)

@router.get("/projects/{project_id}", response_model=GraphData)
async def get_graph(project_id: str, layout: Optional[GraphLayout] = None):
    """获取项目图谱"""
    try:
        return await graph_service.get_project_graph(project_id, layout)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/nodes", response_model=GraphNode)
async def create_node(project_id: str, node: NodeCreate):
    """创建节点"""
    try:
        node_result = await graph_service.create_node(project_id, node)
        return await graph_service.get_node_by_id(project_id, node_result.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/edges", response_model=GraphEdge)
async def create_edge(project_id: str, edge: EdgeCreate):
    """创建边"""
    try:
        edge_result = await graph_service.create_edge(project_id, edge)
        return await graph_service.get_edge_by_id(project_id, edge_result.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 添加批量操作接口
@router.post("/projects/{project_id}/add", response_model=ApiResponse)
async def add_graph_elements(
    project_id: str, 
    data: Dict[str, Any] = Body(...)
):
    """
    批量添加节点和边到项目知识图谱
    
    参数:
        project_id: 项目ID
        data: 包含nodes和edges的字典
              - nodes: 节点列表
              - edges: 边列表
    
    返回:
        ApiResponse: 操作结果
    """
    try:
        # 转换输入数据为GraphData对象
        nodes = [GraphNode(**node) for node in data.get("nodes", [])]
        edges = [GraphEdge(**edge) for edge in data.get("edges", [])]
        
        graph_data = GraphData(nodes=nodes, edges=edges)
        
        # 调用服务添加节点和边
        result = await graph_service.add_nodes_and_edges(project_id, graph_data)
        
        return ApiResponse(
            success=True,
            message=f"成功添加 {len(nodes)} 个节点和 {len(edges)} 条边到项目图谱",
            data={
                "node_count": len(result.nodes),
                "edge_count": len(result.edges)
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加图谱元素失败: {str(e)}")

@router.put("/projects/{project_id}/nodes/{node_id}", response_model=GraphNode)
async def update_node(project_id: str, node_id: str, node: NodeUpdate):
    """更新节点"""
    try:
        result = await graph_service.update_node(project_id, node_id, node)
        if not result:
            raise HTTPException(status_code=404, detail="Node not found")
        return await graph_service.get_node_by_id(project_id, node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_id}/edges/{edge_id}", response_model=GraphEdge)
async def update_edge(project_id: str, edge_id: str, edge: EdgeUpdate):
    """更新边"""
    try:
        result = await graph_service.update_edge(project_id, edge_id, edge)
        if not result:
            raise HTTPException(status_code=404, detail="Edge not found")
        return await graph_service.get_edge_by_id(project_id, edge_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/nodes/{node_id}", response_model=ApiResponse)
async def delete_node(project_id: str, node_id: str):
    """删除节点"""
    try:
        success = await graph_service.delete_node(project_id, node_id)
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        return ApiResponse(
            success=True,
            message="Node deleted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/edges/{edge_id}", response_model=ApiResponse)
async def delete_edge(project_id: str, edge_id: str):
    """删除边"""
    try:
        success = await graph_service.delete_edge(project_id, edge_id)
        if not success:
            raise HTTPException(status_code=404, detail="Edge not found")
        return ApiResponse(
            success=True,
            message="Edge deleted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/suggestions")
async def get_suggestions(project_id: str):
    """获取图谱建议（用于出题和聊天）"""
    try:
        graph_data = await graph_service.get_project_graph(project_id)
        
        # 提取关键节点和关系
        suggestions = {
            "nodes": [],
            "relationships": []
        }
        
        for node in graph_data.nodes:
            if node.properties and "importance" in node.properties:
                suggestions["nodes"].append({
                    "id": node.id,
                    "label": node.label,
                    "importance": node.properties["importance"]
                })
        
        for edge in graph_data.edges:
            if edge.properties and "strength" in edge.properties:
                suggestions["relationships"].append({
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    "strength": edge.properties["strength"]
                })
        
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/analyze")
async def analyze_graph(project_id: str):
    """分析图谱（用于出题和聊天）"""
    try:
        # 直接使用服务层的分析方法
        return await graph_service.analyze_graph(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/visualization")
async def get_graph_visualization_data(project_id: str):
    """获取适用于Web前端可视化的图谱数据"""
    try:
        return await graph_visualizer.generate_web_visualization_data(project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/visualizer/launch")
async def launch_3d_visualizer(project_id: str):
    """启动3D图可视化界面"""
    try:
        await graph_visualizer.launch_3d_viewer(project_id)
        return {"message": "已启动3D图可视化界面，请查看独立窗口"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/export/graphml")
async def export_graph_to_graphml(project_id: str):
    """导出图谱为GraphML格式"""
    try:
        graphml_path = await graph_visualizer.export_to_graphml(project_id)
        return {"file_path": graphml_path, "message": f"已导出图谱到 {graphml_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 添加与LightRAG同步相关的API端点

@router.post("/{project_id}/sync-lightrag")
async def sync_with_lightrag(
    project_id: str
):
    """
    同步图谱数据与LightRAG
    """
    try:
        result = await graph_service.sync_with_lightrag(project_id)
        return result
    except Exception as e:
        logger.error(f"同步图谱数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/import-from-lightrag")
async def import_from_lightrag(
    project_id: str
):
    """
    从LightRAG导入图谱数据
    """
    try:
        result = await graph_service.import_from_lightrag(project_id)
        return result
    except Exception as e:
        logger.error(f"从LightRAG导入图谱数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 添加缺失的查询功能端点

@router.get("/projects/{project_id}/nodes/{node_id}/neighbors")
async def get_node_neighbors(
    project_id: str, 
    node_id: str, 
    depth: int = Query(1, description="查询深度")
):
    """
    获取节点的邻居节点
    
    Args:
        project_id: 项目ID
        node_id: 节点ID
        depth: 查询深度，默认为1
        
    Returns:
        GraphData: 包含邻居节点和边的图谱数据
    """
    try:
        result = await graph_service.get_node_neighbors(project_id, node_id, depth)
        return result
    except Exception as e:
        logger.error(f"获取节点邻居失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/search")
async def search_graph(
    project_id: str,
    search_request: Dict[str, Any] = Body(...)
):
    """
    搜索图谱节点和边
    
    Args:
        project_id: 项目ID
        search_request: 搜索请求，包含search_term等参数
        
    Returns:
        Dict[str, Any]: 搜索结果
    """
    try:
        result = await graph_service.search_graph(project_id, search_request)
        return result
    except Exception as e:
        logger.error(f"搜索图谱失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/nodes/type/{node_type}")
async def get_nodes_by_type(
    project_id: str,
    node_type: str
):
    """
    根据节点类型获取节点列表
    
    Args:
        project_id: 项目ID
        node_type: 节点类型
        
    Returns:
        List[GraphNode]: 节点列表
    """
    try:
        result = await graph_service.get_nodes_by_type(project_id, node_type)
        return result
    except Exception as e:
        logger.error(f"根据类型获取节点失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 