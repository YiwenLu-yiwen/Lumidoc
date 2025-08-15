import { graphApi } from '../../api/graph';
import { GraphData, GraphEntity, GraphRelationship } from '../../types/graph';

// 兼容旧的接口，使用新的图谱API
export interface Node {
  id: string;
  label: string;
  type?: string;
  description?: string;
  properties?: Record<string, any>;
  x?: number;
  y?: number;
  size?: number;
  color?: string;
}

export interface Edge {
  id: string;
  source: string;
  target: string;
  label?: string;
  type?: string;
  properties?: Record<string, any>;
  size?: number;
  color?: string;
}

export interface GraphDataLegacy {
  nodes: Node[];
  edges: Edge[];
}

// 将新的GraphData转换为旧格式，保证兼容性
function convertGraphData(data: GraphData): GraphDataLegacy {
  return {
    nodes: data.nodes.map((node: GraphEntity) => ({
      id: node.id,
      label: node.label,
      type: node.type,
      description: node.properties?.description || '',
      properties: node.properties,
      x: node.x,
      y: node.y,
      size: node.size || 8,
      color: node.color || '#1f77b4'
    })),
    edges: data.edges.map((edge: GraphRelationship) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: edge.type,
      properties: edge.properties,
      size: edge.width || 2,
      color: edge.color || '#666666'
    }))
  };
}

export async function fetchGraphData(projectId: string): Promise<GraphDataLegacy> {
  try {
    console.log(`[Graph API] 获取项目${projectId}的图谱数据`);
    // 使用新的图谱API
    const data = await graphApi.getProjectGraph(projectId);
    console.log(`[Graph API] 收到图谱数据:`, data);
    
    // 检查数据结构
    if (!data || !data.nodes || !data.edges) {
      console.warn('[Graph API] 返回的数据格式不正确，使用空数据');
      return {
        nodes: [],
        edges: []
      };
    }
    
    console.log(`[Graph API] 数据验证通过: ${data.nodes.length}个节点, ${data.edges.length}条边`);
    
    // 转换为旧格式
    const convertedData = convertGraphData(data);
    console.log(`[Graph API] 转换完成: ${convertedData.nodes.length}个节点, ${convertedData.edges.length}条边`);
    
    return convertedData;
  } catch (error) {
    console.error('[Graph API] 获取图谱数据失败:', error);
    // 返回空数据而不是抛出错误
    return {
      nodes: [],
      edges: []
    };
  }
}

export async function updateNodePosition(projectId: string, nodeId: string, x: number, y: number): Promise<void> {
  try {
    console.log(`[Graph API] 更新节点${nodeId}位置: (${x}, ${y})`);
    await graphApi.updateEntity(projectId, nodeId, { 
      properties: { x, y } 
    });
  } catch (error) {
    console.error('[Graph API] 更新节点位置失败:', error);
    throw error;
  }
}

export const updateEdge = async (projectId: string, edgeId: string, data: Partial<Edge>): Promise<void> => {
  try {
    console.log(`[Graph API] 更新边${edgeId}:`, data);
    await graphApi.updateRelationship(projectId, edgeId, {
      label: data.label,
      type: data.type,
      properties: data.properties
    });
  } catch (error) {
    console.error('[Graph API] 更新边失败:', error);
    throw error;
  }
}

// 新增的项目隔离相关功能
export async function getNodeNeighbors(projectId: string, nodeId: string, depth: number = 1): Promise<GraphDataLegacy> {
  try {
    console.log(`[Graph API] 获取节点${nodeId}的邻居，深度${depth}`);
    const data = await graphApi.getNodeNeighbors(projectId, nodeId, depth);
    return convertGraphData(data);
  } catch (error) {
    console.error('[Graph API] 获取邻居节点失败:', error);
    throw error;
  }
}

export async function searchNodes(projectId: string, searchTerm: string): Promise<GraphDataLegacy> {
  try {
    console.log(`[Graph API] 搜索节点: ${searchTerm}`);
    const searchResult = await graphApi.searchGraph(projectId, {
      project_id: projectId,
      search_term: searchTerm,
      search_type: 'both',
      search_fields: ['label', 'type', 'properties.description']
    });
    
    return convertGraphData({
      nodes: searchResult.entities,
      edges: searchResult.relationships
    });
  } catch (error) {
    console.error('[Graph API] 搜索节点失败:', error);
    throw error;
  }
}

export async function getNodesByType(projectId: string, nodeType: string): Promise<Node[]> {
  try {
    console.log(`[Graph API] 获取类型为${nodeType}的节点`);
    const entities = await graphApi.getNodesByType(projectId, nodeType);
    return entities.map(entity => ({
      id: entity.id,
      label: entity.label,
      type: entity.type,
      description: entity.properties?.description || '',
      properties: entity.properties,
      x: entity.x,
      y: entity.y,
      size: entity.size || 8,
      color: entity.color || '#1f77b4'
    }));
  } catch (error) {
    console.error('[Graph API] 获取特定类型节点失败:', error);
    throw error;
  }
}

export async function syncWithLightRAG(projectId: string): Promise<void> {
  try {
    console.log(`[Graph API] 与LightRAG同步`);
    await graphApi.syncWithLightRAG(projectId, {
      project_id: projectId,
      sync_source: 'lightrag',
      sync_type: 'full',
      conflict_resolution: 'merge'
    });
  } catch (error) {
    console.error('[Graph API] 与LightRAG同步失败:', error);
    throw error;
  }
}

export async function importFromLightRAG(projectId: string): Promise<void> {
  try {
    console.log(`[Graph API] 从LightRAG导入`);
    await graphApi.importFromLightRAG(projectId);
  } catch (error) {
    console.error('[Graph API] 从LightRAG导入失败:', error);
    throw error;
  }
} 