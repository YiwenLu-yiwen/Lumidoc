import os
import json
import random
import uvicorn
import logging
from typing import List, Optional, Dict, Any
from neo4j import GraphDatabase
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import FastAPI, HTTPException, Depends
from pathlib import Path
from src.database import get_db
import math
import networkx as nx
import uuid

logger = logging.getLogger(__name__)

# 导入共享类型
from src.shared.types.graph import GraphNode, GraphEdge, GraphData, GraphAnalysisRequest
from src.shared.types.response import ApiResponse

# 更新配置导入
from ..config.config import settings

# 导入创建和更新数据的模型
from ..models.graph import (
    NodeCreate,
    NodeUpdate,
    EdgeCreate,
    EdgeUpdate,
    GraphLayout
)

app = FastAPI()

@app.get("/projects/{project_id}/brands", response_model=Dict[str, List[str]])
async def get_project_brands(project_id: str, db: Session = Depends(get_db)):
    """获取项目品牌列表"""
    try:
        path = Path(f"projects/{project_id}/brands.json")
        if not path.exists():
            return {"brands": []}
            
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 获取所有品牌名称
        brands = []
        for item in data:
            if "name" in item:
                brands.append(item["name"])
                
        return {"brands": list(set(brands))}  # 去重
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/graph/analyze", response_model=GraphData)
async def analyze_text(
    request: GraphAnalysisRequest,
    db: Session = Depends(get_db)
):
    """分析文本生成知识图谱"""
    try:
        graph_service = GraphService(db)
        result = await graph_service.analyze_text(request.query, request.project_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/project/{project_id}", response_model=GraphData)
async def get_project_graph(project_id: str, db: Session = Depends(get_db)):
    """获取项目知识图谱"""
    try:
        graph_service = GraphService(db)
        result = await graph_service.get_project_graph(project_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph/project/{project_id}/export")
async def export_graph(project_id: str, format: str = "json", db: Session = Depends(get_db)):
    """导出知识图谱"""
    try:
        graph_service = GraphService(db)
        result = await graph_service.export_graph(project_id, format)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/graph/project/{project_id}", response_model=ApiResponse)
async def clear_project_graph(project_id: str, db: Session = Depends(get_db)):
    """清空项目知识图谱"""
    try:
        graph_service = GraphService(db)
        await graph_service.clear_project_graph(project_id)
        return ApiResponse(
            success=True,
            message="Project graph cleared successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GraphService:
    def __init__(self, db: Optional[Session] = None):
        self.driver = None
        self.db = db
        
        if settings.storage_mode == "neo4j":
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
        elif settings.storage_mode == "local":
            os.makedirs(settings.local_storage_dir, exist_ok=True)
        elif settings.storage_mode == "postgresql" and db is None:
            raise ValueError("PostgreSQL storage mode requires a database session")

    def _init_neo4j(self):
        """初始化 Neo4j 数据库"""
        if self.driver is None:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )

    async def _init_postgresql(self):
        """初始化 PostgreSQL 数据库"""
        if self.db is None:
            raise ValueError("PostgreSQL storage mode requires a database session")
            
        # 检查并创建节点表
        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id VARCHAR(255) PRIMARY KEY,
                project_id VARCHAR(255) NOT NULL,
                label TEXT NOT NULL,
                type VARCHAR(255) DEFAULT 'default',
                properties JSONB
            )
        """))
        
        # 检查并创建边表
        self.db.execute(text("""
            CREATE TABLE IF NOT EXISTS graph_edges (
                id VARCHAR(255) PRIMARY KEY,
                project_id VARCHAR(255) NOT NULL,
                source VARCHAR(255) NOT NULL,
                target VARCHAR(255) NOT NULL,
                label TEXT,
                properties JSONB,
                FOREIGN KEY (source) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target) REFERENCES graph_nodes(id) ON DELETE CASCADE
            )
        """))
        
        self.db.commit()

    async def _save_to_local(self, project_id: str, graph_data: GraphData):
        """保存图谱到本地文件"""
        filename = f"graph_{project_id}.json"
        path = os.path.join(settings.local_storage_dir, filename)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(graph_data.dict(), f, ensure_ascii=False, indent=2)

    async def _load_from_local(self, project_id: str) -> Optional[GraphData]:
        """从本地文件加载图谱"""
        filename = f"graph_{project_id}.json"
        path = os.path.join(settings.local_storage_dir, filename)
        
        if not os.path.exists(path):
            return None
            
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return GraphData(**data)

    async def create_node(self, project_id: str, node: NodeCreate) -> GraphNode:
        """创建节点"""
        node_id = f"node_{datetime.now().timestamp()}_{random.randint(1000, 9999)}"
        
        # 准备属性
        node_properties = node.properties or {}
        node_properties["project_id"] = project_id
        
        # 节点类型，从属性中获取或使用默认值
        node_type = node_properties.get("type", "default")
        
        # 创建节点对象
        graph_node = GraphNode(
            id=node_id,
            label=node.label,
            type=node_type,
            properties={
                **node_properties,
                "x": node.x,
                "y": node.y,
                "size": node.size,
                "color": node.color
            }
        )
        
        if settings.storage_mode == "neo4j":
            self._init_neo4j()
            with self.driver.session() as session:
                session.run(
                    """
                    CREATE (n:Node:$type {
                        id: $id,
                        label: $label,
                        project_id: $project_id,
                        properties: $properties
                    })
                    """,
                    id=node_id,
                    label=node.label,
                    project_id=project_id,
                    type=node_type,
                    properties=node_properties
                )
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            self.db.execute(
                text("""
                    INSERT INTO graph_nodes (id, project_id, label, type, properties)
                    VALUES (:id, :project_id, :label, :type, :properties)
                """),
                {
                    "id": node_id,
                    "project_id": project_id,
                    "label": node.label,
                    "type": node_type,
                    "properties": json.dumps(node_properties)
                }
            )
            self.db.commit()
        else:
            # 本地存储
            graph_data = await self._load_from_local(project_id) or GraphData(nodes=[], edges=[])
            graph_data.nodes.append(graph_node)
            await self._save_to_local(project_id, graph_data)
            
        return graph_node

    async def create_edge(self, project_id: str, edge: EdgeCreate) -> GraphEdge:
        """创建边"""
        edge_id = f"edge_{datetime.now().timestamp()}_{random.randint(1000, 9999)}"
        
        # 准备属性
        edge_properties = edge.properties or {}
        edge_properties["project_id"] = project_id
        
        # 创建边对象
        graph_edge = GraphEdge(
            id=edge_id,
            source=edge.source,
            target=edge.target,
            label=edge.label or "",
            properties={
                **edge_properties,
                "size": edge.size,
                "color": edge.color
            }
        )
        
        if settings.storage_mode == "neo4j":
            self._init_neo4j()
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (source:Node {id: $source_id}), (target:Node {id: $target_id})
                    CREATE (source)-[r:RELATES_TO {
                        id: $id,
                        label: $label,
                        project_id: $project_id,
                        properties: $properties
                    }]->(target)
                    """,
                    id=edge_id,
                    source_id=edge.source,
                    target_id=edge.target,
                    label=edge.label or "",
                    project_id=project_id,
                    properties=edge_properties
                )
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            self.db.execute(
                text("""
                    INSERT INTO graph_edges (id, project_id, source, target, label, properties)
                    VALUES (:id, :project_id, :source, :target, :label, :properties)
                """),
                {
                    "id": edge_id,
                    "project_id": project_id,
                    "source": edge.source,
                    "target": edge.target,
                    "label": edge.label,
                    "properties": json.dumps(edge_properties)
                }
            )
            self.db.commit()
        else:
            # 本地存储
            graph_data = await self._load_from_local(project_id) or GraphData(nodes=[], edges=[])
            graph_data.edges.append(graph_edge)
            await self._save_to_local(project_id, graph_data)
            
        return graph_edge

    async def get_graph(self, project_id: str, layout: Optional[GraphLayout] = None) -> GraphData:
        """获取图谱数据"""
        if settings.storage_mode == "neo4j":
            self._init_neo4j()
            with self.driver.session() as session:
                # 获取节点
                result = session.run(
                    """
                    MATCH (n:Node)
                    WHERE n.project_id = $project_id
                    RETURN n
                    """,
                    project_id=project_id
                )
                
                nodes = []
                for record in result:
                    node_data = record["n"]
                    node_type = node_data.get("type", "default")
                    properties = node_data.get("properties", {})
                    
                    nodes.append(GraphNode(
                        id=node_data["id"],
                        label=node_data["label"],
                        type=node_type,
                        properties=properties
                    ))
                
                # 获取边
                result = session.run(
                    """
                    MATCH (source:Node)-[r]->(target:Node)
                    WHERE source.project_id = $project_id AND target.project_id = $project_id
                    RETURN r, source.id as source_id, target.id as target_id
                    """,
                    project_id=project_id
                )
                
                edges = []
                for record in result:
                    edge_data = record["r"]
                    properties = edge_data.get("properties", {})
                    edges.append(GraphEdge(
                        id=edge_data["id"],
                        source=record["source_id"],
                        target=record["target_id"],
                        label=edge_data.get("label", ""),
                        properties=properties
                    ))
                
                return GraphData(nodes=nodes, edges=edges)
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            # 获取节点
            result = self.db.execute(
                text("""
                    SELECT id, label, type, properties
                    FROM graph_nodes
                    WHERE project_id = :project_id
                """),
                {"project_id": project_id}
            )
            
            nodes = []
            for row in result:
                properties = row.properties if row.properties else {}
                nodes.append(GraphNode(
                    id=row.id,
                    label=row.label,
                    type=row.type or "default",
                    properties=properties
                ))
            
            # 获取边
            result = self.db.execute(
                text("""
                    SELECT id, source, target, label, properties
                    FROM graph_edges
                    WHERE project_id = :project_id
                """),
                {"project_id": project_id}
            )
            
            edges = []
            for row in result:
                properties = row.properties if row.properties else {}
                edges.append(GraphEdge(
                    id=row.id,
                    source=row.source,
                    target=row.target,
                    label=row.label or "",
                    properties=properties
                ))
            
            return GraphData(nodes=nodes, edges=edges)
        else:
            # 从本地文件加载
            return await self._load_from_local(project_id) or GraphData(nodes=[], edges=[])

    def _apply_layout(self, graph_data: GraphData, layout: Optional[GraphLayout] = None) -> GraphData:
        """应用布局算法"""
        if not layout or not graph_data.nodes:
            return graph_data
        
        # 复制图谱数据，避免修改原始数据
        graph_copy = GraphData(
            nodes=[GraphNode(**node.dict()) for node in graph_data.nodes],
            edges=[GraphEdge(**edge.dict()) for edge in graph_data.edges]
        )
        
        # 根据布局类型应用不同算法
        if layout.type == "circular":
            # 圆形布局
            node_count = len(graph_copy.nodes)
            radius = layout.config.get("radius", 200) if layout.config else 200
            
            for i, node in enumerate(graph_copy.nodes):
                angle = 2 * math.pi * i / node_count
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                # 更新节点属性
                node.properties["x"] = x
                node.properties["y"] = y
        
        elif layout.type == "grid":
            # 网格布局
            cols = layout.config.get("cols", 5) if layout.config else 5
            spacing = layout.config.get("spacing", 100) if layout.config else 100
            
            for i, node in enumerate(graph_copy.nodes):
                row = i // cols
                col = i % cols
                
                # 更新节点属性
                node.properties["x"] = col * spacing
                node.properties["y"] = row * spacing
                
        # 可以添加更多布局算法
        
        return graph_copy

    async def update_node(self, project_id: str, node_id: str, node: NodeUpdate) -> Optional[GraphNode]:
        """更新节点"""
        # 首先获取当前节点
        graph_data = await self.get_graph(project_id)
        target_node = next((n for n in graph_data.nodes if n.id == node_id), None)
        
        if not target_node:
            return None
            
        # 更新节点属性
        if node.label is not None:
            target_node.label = node.label
            
        if node.properties is not None:
            # 更新属性，保留原有属性
            target_node.properties.update(node.properties)
            
        # 更新坐标和样式信息
        if node.x is not None:
            target_node.properties["x"] = node.x
        if node.y is not None:
            target_node.properties["y"] = node.y
        if node.size is not None:
            target_node.properties["size"] = node.size
        if node.color is not None:
            target_node.properties["color"] = node.color
            
        # 保存更新
        if settings.storage_mode == "local":
            await self._save_to_local(project_id, graph_data)
            return target_node
        else:
            # 对于数据库存储，直接更新
            updated_node = await self.create_node(project_id, NodeCreate(
                label=target_node.label,
                properties=target_node.properties
            ))
            return updated_node

    async def update_edge(self, project_id: str, edge_id: str, edge: EdgeUpdate) -> Optional[GraphEdge]:
        """更新边"""
        # 首先获取当前边
        graph_data = await self.get_graph(project_id)
        target_edge = next((e for e in graph_data.edges if e.id == edge_id), None)
        
        if not target_edge:
            return None
            
        # 更新边属性
        if edge.label is not None:
            target_edge.label = edge.label
            
        if edge.properties is not None:
            # 更新属性，保留原有属性
            target_edge.properties.update(edge.properties)
            
        # 更新源和目标节点
        if edge.source is not None:
            target_edge.source = edge.source
        if edge.target is not None:
            target_edge.target = edge.target
            
        # 更新样式信息
        if edge.size is not None:
            target_edge.properties["size"] = edge.size
        if edge.color is not None:
            target_edge.properties["color"] = edge.color
            
        # 保存更新
        if settings.storage_mode == "local":
            await self._save_to_local(project_id, graph_data)
            return target_edge
        else:
            # 对于数据库存储，直接更新
            updated_edge = await self.create_edge(project_id, EdgeCreate(
                source=target_edge.source,
                target=target_edge.target,
                label=target_edge.label,
                properties=target_edge.properties
            ))
            return updated_edge

    async def delete_node(self, project_id: str, node_id: str) -> bool:
        """删除节点"""
        if settings.storage_mode == "neo4j":
            self._init_neo4j()
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (n:Node {id: $node_id})
                    DETACH DELETE n
                    """,
                    node_id=node_id
                )
                return True
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            self.db.execute(
                text("""
                    DELETE FROM graph_nodes
                    WHERE id = :node_id AND project_id = :project_id
                """),
                {
                    "node_id": node_id,
                    "project_id": project_id
                }
            )
            self.db.commit()
            return True
        else:
            # 本地文件存储
            graph_data = await self._load_from_local(project_id)
            if not graph_data:
                return False
                
            # 过滤节点
            original_count = len(graph_data.nodes)
            graph_data.nodes = [n for n in graph_data.nodes if n.id != node_id]
            
            # 过滤与该节点关联的边
            graph_data.edges = [e for e in graph_data.edges 
                              if e.source != node_id and e.target != node_id]
            
            # 保存更新
            await self._save_to_local(project_id, graph_data)
            return len(graph_data.nodes) < original_count
            
    async def delete_edge(self, project_id: str, edge_id: str) -> bool:
        """删除边"""
        if settings.storage_mode == "neo4j":
            self._init_neo4j()
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH ()-[r {id: $edge_id}]->()
                    DELETE r
                    """,
                    edge_id=edge_id
                )
                return True
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            self.db.execute(
                text("""
                    DELETE FROM graph_edges
                    WHERE id = :edge_id AND project_id = :project_id
                """),
                {
                    "edge_id": edge_id,
                    "project_id": project_id
                }
            )
            self.db.commit()
            return True
        else:
            # 本地文件存储
            graph_data = await self._load_from_local(project_id)
            if not graph_data:
                return False
                
            # 过滤边
            original_count = len(graph_data.edges)
            graph_data.edges = [e for e in graph_data.edges if e.id != edge_id]
            
            # 保存更新
            await self._save_to_local(project_id, graph_data)
            return len(graph_data.edges) < original_count

    async def get_project_graph(self, project_id: str, layout: Optional[GraphLayout] = None) -> GraphData:
        """获取项目知识图谱"""
        graph_data = await self.get_graph(project_id)
        
        # 如果提供了布局参数，应用布局
        if layout:
            graph_data = self._apply_layout(graph_data, layout)
            
        return graph_data

    async def analyze_graph(self, project_id: str) -> Dict[str, Any]:
        """分析图谱，计算关键指标"""
        graph_data = await self.get_graph(project_id)
        
        # 计算节点中心性
        centrality = self._calculate_node_centrality(graph_data)
        
        # 计算关系强度
        relationship_strength = self._calculate_relationship_strength(graph_data)
        
        # 识别关键节点
        key_nodes = self._identify_key_nodes(graph_data, centrality)
        
        # 识别关键关系
        key_relationships = self._identify_key_relationships(graph_data, relationship_strength)
        
        return {
            "metrics": {
                "node_count": len(graph_data.nodes),
                "edge_count": len(graph_data.edges),
                "density": len(graph_data.edges) / max(1, len(graph_data.nodes) * (len(graph_data.nodes) - 1) / 2)
            },
            "key_nodes": key_nodes,
            "key_relationships": key_relationships
        }

    def _calculate_node_centrality(self, graph_data: GraphData) -> Dict[str, float]:
        """计算节点中心性"""
        # 创建临时图
        G = nx.DiGraph()
        
        # 添加节点和边
        for node in graph_data.nodes:
            G.add_node(node.id)
        
        for edge in graph_data.edges:
            G.add_edge(edge.source, edge.target)
        
        # 计算中心性
        centrality = nx.degree_centrality(G)
        return centrality
        
    def _calculate_relationship_strength(self, graph_data: GraphData) -> Dict[str, float]:
        """计算关系强度"""
        relationship_strength = {}
        
        # 获取关系权重配置
        weights = settings.analysis_config["relationship_strength_weights"]
        default_weight = weights.get("default", 1.0)
        
        for edge in graph_data.edges:
            # 基础权重
            label = edge.label.lower() if edge.label else ""
            weight = weights.get(label, default_weight)
            
            # 考虑属性中的权重
            if edge.properties and "weight" in edge.properties:
                weight *= float(edge.properties["weight"])
                
            relationship_strength[edge.id] = weight
            
        return relationship_strength
    
    def _identify_key_nodes(self, graph_data: GraphData, centrality: Dict[str, float]) -> List[Dict[str, Any]]:
        """识别关键节点"""
        if not graph_data.nodes:
            return []
            
        # 获取节点阈值
        threshold = settings.analysis_config["key_node_threshold"]
        
        # 按中心性排序
        sorted_nodes = sorted([(node.id, centrality.get(node.id, 0)) 
                             for node in graph_data.nodes], 
                            key=lambda x: x[1], reverse=True)
        
        # 获取前N%的节点
        cutoff = max(1, int(len(sorted_nodes) * threshold))
        key_node_ids = [node_id for node_id, score in sorted_nodes[:cutoff]]
        
        # 构建结果
        key_nodes = []
        for node in graph_data.nodes:
            if node.id in key_node_ids:
                key_nodes.append({
                    "id": node.id,
                    "label": node.label,
                    "type": node.type,
                    "centrality": centrality.get(node.id, 0),
                    "properties": node.properties
                })
                
        return key_nodes
    
    def _identify_key_relationships(self, graph_data: GraphData, strength: Dict[str, float]) -> List[Dict[str, Any]]:
        """识别关键关系"""
        if not graph_data.edges:
            return []
            
        # 获取关系阈值
        threshold = settings.analysis_config["key_relationship_threshold"]
        
        # 按强度排序
        sorted_edges = sorted([(edge.id, strength.get(edge.id, 0)) 
                             for edge in graph_data.edges], 
                            key=lambda x: x[1], reverse=True)
        
        # 获取前N%的关系
        cutoff = max(1, int(len(sorted_edges) * threshold))
        key_edge_ids = [edge_id for edge_id, score in sorted_edges[:cutoff]]
        
        # 构建结果
        key_relationships = []
        for edge in graph_data.edges:
            if edge.id in key_edge_ids:
                # 查找源节点和目标节点
                source = next((n for n in graph_data.nodes if n.id == edge.source), None)
                target = next((n for n in graph_data.nodes if n.id == edge.target), None)
                
                if not source or not target:
                    continue
                    
                score = strength.get(edge.id, 0)
                key_relationships.append({
                    "id": edge.id,
                    "source": {
                        "id": source.id,
                        "label": source.label
                    },
                    "target": {
                        "id": target.id,
                        "label": target.label
                    },
                    "label": edge.label,
                    "strength": score,
                    "properties": edge.properties
                })
        
        return key_relationships

    async def analyze_text(self, query: str, project_id: str) -> GraphData:
        """分析文本生成知识图谱"""
        # 此处应该包含文本分析和图谱生成的逻辑
        # 为了示例，我们创建一个简单的图谱
        
        # 创建示例节点
        nodes = [
            GraphNode(
                id=f"node_{datetime.now().timestamp()}_1",
                label=query,
                type="query",
                properties={"project_id": project_id}
            ),
            GraphNode(
                id=f"node_{datetime.now().timestamp()}_2",
                label=f"Entity from {query}",
                type="entity",
                properties={"project_id": project_id}
            ),
            GraphNode(
                id=f"node_{datetime.now().timestamp()}_3",
                label=f"Concept related to {query}",
                type="concept",
                properties={"project_id": project_id}
            )
        ]
        
        # 创建示例边
        edges = [
            GraphEdge(
                id=f"edge_{datetime.now().timestamp()}_1",
                source=nodes[0].id,
                target=nodes[1].id,
                label="CONTAINS",
                properties={"project_id": project_id}
            ),
            GraphEdge(
                id=f"edge_{datetime.now().timestamp()}_2",
                source=nodes[0].id,
                target=nodes[2].id,
                label="RELATED_TO",
                properties={"project_id": project_id}
            )
        ]
        
        # 创建图谱数据
        graph_data = GraphData(nodes=nodes, edges=edges)
        
        # 保存到存储
        if settings.storage_mode == "local":
            await self._save_to_local(project_id, graph_data)
        
        return graph_data

    async def add_nodes_and_edges(self, project_id: str, graph_data: GraphData) -> GraphData:
        """添加多个节点和边"""
        # 获取已有的图谱
        existing_graph = await self.get_graph(project_id)
        
        # 合并节点
        for node in graph_data.nodes:
            # 检查节点是否已存在
            if not any(n.id == node.id for n in existing_graph.nodes):
                node_create = NodeCreate(
                    label=node.label,
                    properties=node.properties
                )
                await self.create_node(project_id, node_create)
        
        # 合并边
        for edge in graph_data.edges:
            # 检查边是否已存在
            if not any(e.id == edge.id for e in existing_graph.edges):
                edge_create = EdgeCreate(
                    source=edge.source,
                    target=edge.target,
                    label=edge.label,
                    properties=edge.properties
                )
                await self.create_edge(project_id, edge_create)
        
        # 返回更新后的图谱
        return await self.get_graph(project_id)

    async def get_node_by_id(self, project_id: str, node_id: str) -> Optional[GraphNode]:
        """通过ID获取节点"""
        graph_data = await self.get_graph(project_id)
        return next((n for n in graph_data.nodes if n.id == node_id), None)
        
    async def get_edge_by_id(self, project_id: str, edge_id: str) -> Optional[GraphEdge]:
        """通过ID获取边"""
        graph_data = await self.get_graph(project_id)
        return next((e for e in graph_data.edges if e.id == edge_id), None)

    async def clear_project_graph(self, project_id: str) -> bool:
        """清空项目知识图谱"""
        if settings.storage_mode == "database":
            self._init_neo4j()
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (n:Node)
                    WHERE n.project_id = $project_id
                    DETACH DELETE n
                    """,
                    project_id=project_id
                )
                return True
        elif settings.storage_mode == "postgresql":
            await self._init_postgresql()
            self.db.execute(
                text("""
                    DELETE FROM graph_edges WHERE project_id = :project_id
                """),
                {"project_id": project_id}
            )
            self.db.execute(
                text("""
                    DELETE FROM graph_nodes WHERE project_id = :project_id
                """),
                {"project_id": project_id}
            )
            self.db.commit()
            return True
        else:
            filename = f"graph_{project_id}.json"
            path = os.path.join(settings.local_storage_dir, filename)
            
            if os.path.exists(path):
                os.remove(path)
            return True
    
    async def export_graph(self, project_id: str, format: str = "json") -> Dict[str, Any]:
        """导出图谱数据"""
        graph_data = await self.get_project_graph(project_id)
        
        if format.lower() == "json":
            return graph_data.dict()
        elif format.lower() == "cypher":
            # 生成Cypher创建语句
            cypher = []
            
            # 创建节点
            for node in graph_data.nodes:
                properties = {k: v for k, v in node.properties.items()}
                properties["id"] = node.id
                properties["label"] = node.label
                properties["type"] = node.type
                
                props_str = ", ".join([f"{k}: '{v}'" if isinstance(v, str) else f"{k}: {v}" 
                                     for k, v in properties.items()])
                
                cypher.append(f"CREATE (:{node.type} {{{props_str}}})")
            
            # 创建关系
            for edge in graph_data.edges:
                source_node = next((n for n in graph_data.nodes if n.id == edge.source), None)
                target_node = next((n for n in graph_data.nodes if n.id == edge.target), None)
                
                if source_node and target_node:
                    properties = {k: v for k, v in edge.properties.items()}
                    properties["id"] = edge.id
                    
                    props_str = ", ".join([f"{k}: '{v}'" if isinstance(v, str) else f"{k}: {v}" 
                                         for k, v in properties.items()])
                    
                    cypher.append(
                        f"MATCH (s:{source_node.type} {{id: '{source_node.id}'}}), "
                        f"(t:{target_node.type} {{id: '{target_node.id}'}}) "
                        f"CREATE (s)-[:{edge.label} {{{props_str}}}]->(t)"
                    )
            
            return {"cypher": "\n".join(cypher)}
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def import_from_lightrag(self, project_id: str) -> Dict[str, Any]:
        """
        从LightRAG导入图谱数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 导入结果
        """
        try:
            # 导入LightRAG客户端
            from src.shared.clients.lightrag_client import default_client as lightrag_client
            
            # 获取项目图谱数据
            graph_data = await self.get_project_graph(project_id)
            
            if not graph_data:
                return {
                    "success": False,
                    "message": "获取图谱数据失败或项目无图谱数据"
                }
                
            # 导入到LightRAG
            result = await lightrag_client.import_graph_data(
                project_id=project_id,
                graph_data=graph_data.dict()
            )
            
            return result
        except Exception as e:
            logger.error(f"从LightRAG导入图谱数据失败: {str(e)}")
            return {
                "success": False,
                "message": f"从LightRAG导入图谱数据失败: {str(e)}"
            }
            
    async def export_to_neo4j(self, project_id: str, graph_data: GraphData) -> Dict[str, Any]:
        """
        导出图谱数据到Neo4j
        
        Args:
            project_id: 项目ID
            graph_data: 图谱数据
            
        Returns:
            Dict[str, Any]: 导出结果
        """
        try:
            # 格式化为Neo4j兼容格式
            nodes = []
            relationships = []
            
            for entity in graph_data.entities:
                # 转换实体为Neo4j节点
                node = {
                    "entity_name": entity.name,
                    "entity_type": entity.type or "UNKNOWN",
                    "description": entity.description or "",
                    "source_id": entity.id or str(uuid.uuid4())
                }
                nodes.append(node)
                
            for rel in graph_data.relationships:
                # 转换关系为Neo4j关系
                relationship = {
                    "src_id": rel.source,
                    "tgt_id": rel.target,
                    "relation": rel.relation or "RELATED",
                    "description": rel.description or "",
                    "weight": rel.weight or 1.0,
                    "source_id": rel.id or str(uuid.uuid4())
                }
                relationships.append(relationship)
                
            # 通过LightRAG客户端导入到Neo4j
            from src.shared.clients.lightrag_client import default_client as lightrag_client
            result = await lightrag_client.import_graph_data(
                project_id=project_id,
                graph_data={
                    "entities": nodes,
                    "relationships": relationships
                }
            )
            
            return result
        except Exception as e:
            logger.error(f"导出图谱数据到Neo4j失败: {str(e)}")
            return {
                "success": False,
                "message": f"导出图谱数据到Neo4j失败: {str(e)}"
            }
            
    async def sync_with_lightrag(self, project_id: str) -> Dict[str, Any]:
        """
        同步图谱数据与LightRAG
        
        Args:
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        try:
            # 导入LightRAG客户端
            from src.shared.clients.lightrag_client import default_client as lightrag_client
            
            # 获取项目图谱数据
            graph_data = await self.get_project_graph(project_id)
            
            if not graph_data:
                return {
                    "success": False,
                    "message": "获取图谱数据失败或项目无图谱数据"
                }
                
            # 导入到LightRAG
            result = await lightrag_client.import_graph_data(
                project_id=project_id,
                graph_data=graph_data.dict()
            )
            
            return {
                "success": result.get("success", False),
                "message": result.get("message", "同步完成"),
                "neo4j_status": "已同步",
                "lightrag_status": "已同步"
            }
        except Exception as e:
            logger.error(f"同步图谱数据与LightRAG失败: {str(e)}")
            return {
                "success": False,
                "message": f"同步图谱数据与LightRAG失败: {str(e)}"
            }

    async def get_node_neighbors(self, project_id: str, node_id: str, depth: int = 1) -> GraphData:
        """
        获取节点的邻居节点
        
        Args:
            project_id: 项目ID
            node_id: 节点ID
            depth: 查询深度
            
        Returns:
            GraphData: 包含邻居节点和边的图谱数据
        """
        try:
            if settings.storage_mode == "neo4j":
                self._init_neo4j()
                with self.driver.session() as session:
                    # 构建查询，支持多层邻居查询
                    # 先尝试使用LightRAG的__Entity__标签，如果失败则使用通用查询
                    if depth == 1:
                        cypher_query = """
                        MATCH (center {entity_name: $node_id, workspace: $workspace})
                        OPTIONAL MATCH (center)-[r]-(neighbor {workspace: $workspace})
                        RETURN center, neighbor, r
                        UNION
                        MATCH (center:Node {id: $node_id, project_id: $project_id})
                        OPTIONAL MATCH (center)-[r]-(neighbor:Node {project_id: $project_id})
                        RETURN center, neighbor, r
                        """
                    else:
                        # 对于更深层次的查询，使用递归查询
                        cypher_query = f"""
                        MATCH (center {{entity_name: $node_id, workspace: $workspace}})
                        OPTIONAL MATCH (center)-[*1..{depth}]-(neighbor {{workspace: $workspace}})
                        WITH center, neighbor
                        OPTIONAL MATCH (n1)-[r]-(n2)
                        WHERE (n1 = center OR n1 = neighbor) AND (n2 = center OR n2 = neighbor)
                            AND n1.workspace = $workspace AND n2.workspace = $workspace
                        RETURN DISTINCT n1 as node1, n2 as node2, r
                        UNION
                        MATCH (center:Node {{id: $node_id, project_id: $project_id}})
                        OPTIONAL MATCH (center)-[*1..{depth}]-(neighbor:Node {{project_id: $project_id}})
                        WITH center, neighbor
                        OPTIONAL MATCH (n1)-[r]-(n2)
                        WHERE (n1 = center OR n1 = neighbor) AND (n2 = center OR n2 = neighbor)
                            AND n1.project_id = $project_id AND n2.project_id = $project_id
                        RETURN DISTINCT n1 as node1, n2 as node2, r
                        """
                    
                    workspace = f"stp_{project_id}_chunk_entity_relation"
                    result = session.run(cypher_query, node_id=node_id, project_id=project_id, workspace=workspace)
                    
                    nodes = set()
                    edges = []
                    
                    for record in result:
                        if depth == 1:
                            # 处理深度为1的结果
                            center = record.get("center")
                            neighbor = record.get("neighbor")
                            relation = record.get("r")
                            
                            if center:
                                nodes.add((center["id"], center))
                            if neighbor:
                                nodes.add((neighbor["id"], neighbor))
                            if relation:
                                edges.append(relation)
                        else:
                            # 处理更深层次的结果
                            node1 = record.get("node1")
                            node2 = record.get("node2")
                            relation = record.get("r")
                            
                            if node1:
                                nodes.add((node1["id"], node1))
                            if node2:
                                nodes.add((node2["id"], node2))
                            if relation:
                                edges.append(relation)
                    
                    # 转换为GraphData格式
                    graph_nodes = []
                    for node_id, node_data in nodes:
                        graph_nodes.append(GraphNode(
                            id=node_data["id"],
                            label=node_data["label"],
                            type=node_data.get("type", "default"),
                            properties=node_data.get("properties", {})
                        ))
                    
                    graph_edges = []
                    for edge_data in edges:
                        graph_edges.append(GraphEdge(
                            id=edge_data["id"],
                            source=edge_data.start_node["id"],
                            target=edge_data.end_node["id"],
                            label=edge_data.get("label", ""),
                            properties=edge_data.get("properties", {})
                        ))
                    
                    return GraphData(nodes=graph_nodes, edges=graph_edges)
            else:
                # 对于非Neo4j存储，使用本地图谱数据
                graph_data = await self.get_graph(project_id)
                
                # 找到指定节点
                target_node = next((n for n in graph_data.nodes if n.id == node_id), None)
                if not target_node:
                    return GraphData(nodes=[], edges=[])
                
                # 找到所有相关的边和邻居节点
                related_edges = [e for e in graph_data.edges if e.source == node_id or e.target == node_id]
                neighbor_ids = set()
                for edge in related_edges:
                    if edge.source == node_id:
                        neighbor_ids.add(edge.target)
                    else:
                        neighbor_ids.add(edge.source)
                
                # 获取邻居节点
                neighbor_nodes = [n for n in graph_data.nodes if n.id in neighbor_ids]
                all_nodes = [target_node] + neighbor_nodes
                
                return GraphData(nodes=all_nodes, edges=related_edges)
                
        except Exception as e:
            logger.error(f"获取节点邻居失败: {str(e)}")
            return GraphData(nodes=[], edges=[])

    async def search_graph(self, project_id: str, search_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索图谱节点和边
        
        Args:
            project_id: 项目ID
            search_request: 搜索请求
            
        Returns:
            Dict[str, Any]: 搜索结果
        """
        try:
            search_term = search_request.get("search_term", "")
            search_type = search_request.get("search_type", "both")  # both, entities, relationships
            
            if not search_term:
                return {
                    "entities": [],
                    "relationships": [],
                    "total_count": 0,
                    "search_term": search_term
                }
            
            if settings.storage_mode == "neo4j":
                self._init_neo4j()
                workspace = f"stp_{project_id}_chunk_entity_relation"
                with self.driver.session() as session:
                    entities = []
                    relationships = []
                    
                    if search_type in ["both", "entities"]:
                        # 搜索节点 - 支持LightRAG和标准Neo4j数据
                        node_query = """
                        MATCH (n)
                        WHERE (n.workspace = $workspace 
                        AND (toLower(n.entity_name) CONTAINS toLower($search_term)
                             OR toLower(toString(n.entity_type)) CONTAINS toLower($search_term)
                             OR toLower(toString(n.description)) CONTAINS toLower($search_term)))
                        OR (n.project_id = $project_id 
                        AND (toLower(n.label) CONTAINS toLower($search_term)
                             OR toLower(toString(n.type)) CONTAINS toLower($search_term)
                             OR any(key IN keys(n.properties) WHERE toLower(toString(n.properties[key])) CONTAINS toLower($search_term))))
                        RETURN n
                        LIMIT 50
                        """
                        
                        result = session.run(node_query, project_id=project_id, search_term=search_term, workspace=workspace)
                        for record in result:
                            node_data = record["n"]
                            # 处理LightRAG格式的节点
                            if hasattr(node_data, "entity_name") or "entity_name" in node_data:
                                entities.append({
                                    "id": node_data.get("entity_name", node_data.get("id", "")),
                                    "label": node_data.get("entity_name", node_data.get("label", "")),
                                    "type": node_data.get("entity_type", "Entity"),
                                    "properties": {
                                        "description": node_data.get("description", ""),
                                        "workspace": node_data.get("workspace", "")
                                    }
                                })
                            else:
                                # 处理标准Neo4j格式的节点
                                entities.append({
                                    "id": node_data.get("id", ""),
                                    "label": node_data.get("label", ""),
                                    "type": node_data.get("type", "default"),
                                    "properties": node_data.get("properties", {})
                                })
                    
                    if search_type in ["both", "relationships"]:
                        # 搜索边
                        edge_query = """
                        MATCH (source:Node)-[r]->(target:Node)
                        WHERE source.project_id = $project_id AND target.project_id = $project_id
                        AND (toLower(r.label) CONTAINS toLower($search_term)
                             OR any(key IN keys(r.properties) WHERE toLower(toString(r.properties[key])) CONTAINS toLower($search_term)))
                        RETURN r, source.id as source_id, target.id as target_id
                        LIMIT 50
                        """
                        
                        result = session.run(edge_query, project_id=project_id, search_term=search_term)
                        for record in result:
                            edge_data = record["r"]
                            relationships.append({
                                "id": edge_data["id"],
                                "source": record["source_id"],
                                "target": record["target_id"],
                                "label": edge_data.get("label", ""),
                                "type": edge_data.get("type", ""),
                                "properties": edge_data.get("properties", {})
                            })
                    
                    return {
                        "entities": entities,
                        "relationships": relationships,
                        "total_count": len(entities) + len(relationships),
                        "search_term": search_term
                    }
            else:
                # 对于非Neo4j存储，使用本地图谱数据搜索
                graph_data = await self.get_graph(project_id)
                
                entities = []
                relationships = []
                
                search_term_lower = search_term.lower()
                
                if search_type in ["both", "entities"]:
                    for node in graph_data.nodes:
                        if (search_term_lower in node.label.lower() or
                            search_term_lower in (node.type or "").lower() or
                            any(search_term_lower in str(v).lower() for v in (node.properties or {}).values())):
                            entities.append({
                                "id": node.id,
                                "label": node.label,
                                "type": node.type,
                                "properties": node.properties
                            })
                
                if search_type in ["both", "relationships"]:
                    for edge in graph_data.edges:
                        if (search_term_lower in (edge.label or "").lower() or
                            any(search_term_lower in str(v).lower() for v in (edge.properties or {}).values())):
                            relationships.append({
                                "id": edge.id,
                                "source": edge.source,
                                "target": edge.target,
                                "label": edge.label,
                                "type": getattr(edge, "type", ""),
                                "properties": edge.properties
                            })
                
                return {
                    "entities": entities,
                    "relationships": relationships,
                    "total_count": len(entities) + len(relationships),
                    "search_term": search_term
                }
                
        except Exception as e:
            logger.error(f"搜索图谱失败: {str(e)}")
            return {
                "entities": [],
                "relationships": [],
                "total_count": 0,
                "search_term": search_request.get("search_term", ""),
                "error": str(e)
            }

    async def get_nodes_by_type(self, project_id: str, node_type: str) -> List[GraphNode]:
        """
        根据节点类型获取节点列表
        
        Args:
            project_id: 项目ID
            node_type: 节点类型
            
        Returns:
            List[GraphNode]: 节点列表
        """
        try:
            if settings.storage_mode == "neo4j":
                self._init_neo4j()
                workspace = f"stp_{project_id}_chunk_entity_relation"
                with self.driver.session() as session:
                    query = """
                    MATCH (n)
                    WHERE (n.workspace = $workspace AND n.entity_type = $node_type)
                    OR (n.project_id = $project_id AND n.type = $node_type)
                    RETURN n
                    ORDER BY COALESCE(n.entity_name, n.label)
                    """
                    
                    result = session.run(query, project_id=project_id, node_type=node_type, workspace=workspace)
                    nodes = []
                    
                    for record in result:
                        node_data = record["n"]
                        # 处理LightRAG格式的节点
                        if hasattr(node_data, "entity_name") or "entity_name" in node_data:
                            nodes.append(GraphNode(
                                id=node_data.get("entity_name", ""),
                                label=node_data.get("entity_name", ""),
                                type=node_data.get("entity_type", "Entity"),
                                properties={
                                    "description": node_data.get("description", ""),
                                    "workspace": node_data.get("workspace", "")
                                }
                            ))
                        else:
                            # 处理标准Neo4j格式的节点
                            nodes.append(GraphNode(
                                id=node_data.get("id", ""),
                                label=node_data.get("label", ""),
                                type=node_data.get("type", "default"),
                                properties=node_data.get("properties", {})
                            ))
                    
                    return nodes
            else:
                # 对于非Neo4j存储，使用本地图谱数据
                graph_data = await self.get_graph(project_id)
                return [node for node in graph_data.nodes if node.type == node_type]
                
        except Exception as e:
            logger.error(f"根据类型获取节点失败: {str(e)}")
            return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port) 