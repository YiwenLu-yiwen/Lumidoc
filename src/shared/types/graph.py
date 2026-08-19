from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class GraphNode(BaseModel):
    """图谱节点模型"""
    id: str
    label: str
    type: str
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    """图谱边模型"""
    id: str
    source: str
    target: str
    label: str
    properties: Dict[str, Any]


class GraphData(BaseModel):
    """图谱数据模型"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphAnalysisRequest(BaseModel):
    """图谱分析请求模型"""
    project_id: str
    query: str
    context: Optional[Dict[str, Any]] = None


class KnowledgeFrameworkResponse(BaseModel):
    """知识框架分析响应模型"""
    query: str
    knowledge_framework_analysis: str
    related_documents_count: int
    graph_node_count: int
    graph_edge_count: int 