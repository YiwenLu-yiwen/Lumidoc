import { apiClient } from './client';
import { ApiResponse } from '../types/api';
import {
  GraphData,
  GraphEntity,
  GraphRelationship,
  GraphQuery,
  GraphQueryResult,
  EntityCreateRequest,
  EntityUpdateRequest,
  RelationshipCreateRequest,
  RelationshipUpdateRequest,
  GraphAnalysisRequest,
  GraphAnalysisResult,
  GraphStatistics,
  GraphSearchRequest,
  GraphSearchResult,
  GraphImportRequest,
  GraphExportRequest,
  GraphSyncRequest,
  GraphSyncResult
} from '../types/graph';


export const graphApi = {
  // 获取项目的知识图谱（带项目隔离）
  getProjectGraph: async (projectId: string): Promise<GraphData> => {
    console.log(`[Graph API] 获取项目${projectId}的图谱数据`);
    try {
      // 首先尝试直接调用LightRAG服务
      console.log(`[Graph API] 直接调用LightRAG服务`);
      const directResponse = await fetch(`http://localhost:8006/rag/projects/${projectId}/knowledge-graph`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (directResponse.ok) {
        const directData = await directResponse.json();
        console.log(`[Graph API] 直接LightRAG响应:`, directData);
        
        if (directData && directData.success) {
          const convertedData: GraphData = {
            nodes: directData.nodes || [],
            edges: directData.edges || []
          };
          console.log(`[Graph API] 成功获取图谱数据: ${convertedData.nodes.length}个节点, ${convertedData.edges.length}条边`);
          return convertedData;
        }
      }
      
      // 备用：使用Gateway
      const response = await apiClient.get<any>(`/lightrag/projects/${projectId}/knowledge-graph`);
      console.log(`[Graph API] Gateway响应:`, response.data);
      
      // 检查返回数据格式
      if (response.data && response.data.success) {
        const convertedData: GraphData = {
          nodes: response.data.nodes || [],
          edges: response.data.edges || []
        };
        console.log(`[Graph API] 成功获取图谱数据: ${convertedData.nodes.length}个节点, ${convertedData.edges.length}条边`);
        return convertedData;
      } else {
        console.warn(`[Graph API] API返回错误:`, response.data);
        return {
          nodes: [],
          edges: []
        };
      }
    } catch (error: any) {
      console.error(`[Graph API] 获取图谱数据失败:`, error);
      
      // 尝试Graph服务的备用端点
      try {
        console.log(`[Graph API] 尝试Graph服务备用端点`);
        const fallbackResponse = await apiClient.get<any>(`/graph/projects/${projectId}`);
        console.log(`[Graph API] Graph服务响应:`, fallbackResponse.data);
        
        if (fallbackResponse.data) {
          const fallbackData: GraphData = {
            nodes: fallbackResponse.data.nodes || [],
            edges: fallbackResponse.data.edges || []
          };
          console.log(`[Graph API] 备用端点成功: ${fallbackData.nodes.length}个节点, ${fallbackData.edges.length}条边`);
          return fallbackData;
        }
      } catch (fallbackError: any) {
        console.error(`[Graph API] 备用端点也失败:`, fallbackError);
      }
      
      // 返回空数据
      return {
        nodes: [],
        edges: []
      };
    }
  },
  
  // 获取项目图谱的可视化数据
  getVisualizationData: async (projectId: string): Promise<GraphData> => {
    console.log(`[Graph API] 获取项目${projectId}的可视化数据`);
    const response = await apiClient.get<GraphData>(`/graph/projects/${projectId}/visualization`);
    return response.data;
  },
  
  // 根据节点ID获取其邻居节点（项目隔离）
  getNodeNeighbors: async (projectId: string, nodeId: string, depth: number = 1): Promise<GraphData> => {
    console.log(`[Graph API] 获取节点${nodeId}的邻居，深度${depth}`);
    const response = await apiClient.get<GraphData>(`/graph/projects/${projectId}/nodes/${nodeId}/neighbors?depth=${depth}`);
    return response.data;
  },
  
  // 执行自定义图谱查询（项目隔离）
  queryGraph: async (projectId: string, query: GraphQuery): Promise<GraphQueryResult> => {
    console.log(`[Graph API] 执行图谱查询:`, query);
    const response = await apiClient.post<GraphQueryResult>(`/graph/projects/${projectId}/query`, {
      ...query,
      project_id: projectId
    });
    return response.data;
  },
  
  // 获取某种类型的所有节点（项目隔离）
  getNodesByType: async (projectId: string, nodeType: string): Promise<GraphEntity[]> => {
    console.log(`[Graph API] 获取类型为${nodeType}的节点`);
    const response = await apiClient.get<GraphEntity[]>(`/graph/projects/${projectId}/nodes/type/${nodeType}`);
    return response.data;
  },
  
  // 获取某个文档的关系图谱（项目隔离）
  getDocumentGraph: async (projectId: string, documentId: string): Promise<GraphData> => {
    console.log(`[Graph API] 获取文档${documentId}的图谱`);
    const response = await apiClient.get<GraphData>(`/graph/projects/${projectId}/documents/${documentId}/graph`);
    return response.data;
  },
  
  // 创建实体节点
  createEntity: async (projectId: string, entity: EntityCreateRequest): Promise<GraphEntity> => {
    console.log(`[Graph API] 创建实体节点:`, entity);
    const response = await apiClient.post<GraphEntity>(`/graph/projects/${projectId}/nodes`, {
      ...entity,
      project_id: projectId
    });
    return response.data;
  },
  
  // 更新实体节点
  updateEntity: async (projectId: string, nodeId: string, entity: EntityUpdateRequest): Promise<GraphEntity> => {
    console.log(`[Graph API] 更新实体节点${nodeId}:`, entity);
    const response = await apiClient.put<GraphEntity>(`/graph/projects/${projectId}/nodes/${nodeId}`, entity);
    return response.data;
  },
  
  // 删除实体节点
  deleteEntity: async (projectId: string, nodeId: string): Promise<ApiResponse> => {
    console.log(`[Graph API] 删除实体节点${nodeId}`);
    const response = await apiClient.delete<ApiResponse>(`/graph/projects/${projectId}/nodes/${nodeId}`);
    return response.data;
  },
  
  // 创建关系
  createRelationship: async (projectId: string, relationship: RelationshipCreateRequest): Promise<GraphRelationship> => {
    console.log(`[Graph API] 创建关系:`, relationship);
    const response = await apiClient.post<GraphRelationship>(`/graph/projects/${projectId}/edges`, {
      ...relationship,
      project_id: projectId
    });
    return response.data;
  },
  
  // 更新关系
  updateRelationship: async (projectId: string, edgeId: string, relationship: RelationshipUpdateRequest): Promise<GraphRelationship> => {
    console.log(`[Graph API] 更新关系${edgeId}:`, relationship);
    const response = await apiClient.put<GraphRelationship>(`/graph/projects/${projectId}/edges/${edgeId}`, relationship);
    return response.data;
  },
  
  // 删除关系
  deleteRelationship: async (projectId: string, edgeId: string): Promise<ApiResponse> => {
    console.log(`[Graph API] 删除关系${edgeId}`);
    const response = await apiClient.delete<ApiResponse>(`/graph/projects/${projectId}/edges/${edgeId}`);
    return response.data;
  },
  
  // 批量添加节点和边
  addGraphElements: async (projectId: string, data: GraphData): Promise<ApiResponse> => {
    console.log(`[Graph API] 批量添加图谱元素: ${data.nodes.length}个节点, ${data.edges.length}条边`);
    const response = await apiClient.post<ApiResponse>(`/graph/projects/${projectId}/add`, {
      nodes: data.nodes.map(node => ({ ...node, project_id: projectId })),
      edges: data.edges.map(edge => ({ ...edge, project_id: projectId }))
    });
    return response.data;
  },
  
  // 图谱分析
  analyzeGraph: async (projectId: string, analysis: GraphAnalysisRequest): Promise<GraphAnalysisResult> => {
    console.log(`[Graph API] 分析图谱:`, analysis);
    const response = await apiClient.post<GraphAnalysisResult>(`/graph/projects/${projectId}/analyze`, {
      ...analysis,
      project_id: projectId
    });
    return response.data;
  },
  
  // 获取图谱统计信息
  getGraphStatistics: async (projectId: string): Promise<GraphStatistics> => {
    console.log(`[Graph API] 获取图谱统计信息`);
    const response = await apiClient.get<GraphStatistics>(`/graph/projects/${projectId}/statistics`);
    return response.data;
  },
  
  // 搜索图谱
  searchGraph: async (projectId: string, search: GraphSearchRequest): Promise<GraphSearchResult> => {
    console.log(`[Graph API] 搜索图谱:`, search);
    try {
      // 首先尝试LightRAG的搜索端点
      const response = await apiClient.post<any>(`/lightrag/rag/query-with-graph`, {
        project_id: projectId,
        query: search.search_term,
        top_k: search.limit || 10,
        use_path_context: true,
        use_entity_expansion: true
      });
      
      if (response.data && response.data.success) {
        // 将LightRAG的响应格式转换为GraphSearchResult格式
        const nodes = response.data.nodes || [];
        const edges = response.data.edges || [];
        
        return {
          entities: nodes.map((node: any) => ({
            id: node.id,
            label: node.label,
            type: node.type,
            properties: node.properties || {}
          })),
          relationships: edges.map((edge: any) => ({
            source: edge.source,
            target: edge.target,
            label: edge.label,
            type: edge.type,
            properties: edge.properties || {}
          })),
          total_count: nodes.length,
          search_term: search.search_term
        };
      }
      
      // 如果LightRAG搜索失败，尝试Graph服务
      const fallbackResponse = await apiClient.post<GraphSearchResult>(`/graph/projects/${projectId}/search`, {
        ...search,
        project_id: projectId
      });
      return fallbackResponse.data;
    } catch (error: any) {
      console.warn(`[Graph API] 搜索API不可用，返回空结果:`, error.message);
      return {
        entities: [],
        relationships: [],
        total_count: 0,
        search_term: search.search_term
      };
    }
  },
  
  // 与LightRAG同步
  syncWithLightRAG: async (projectId: string, syncRequest: GraphSyncRequest): Promise<GraphSyncResult> => {
    console.log(`[Graph API] 与LightRAG同步:`, syncRequest);
    const response = await apiClient.post<GraphSyncResult>(`/graph/projects/${projectId}/sync-lightrag`, {
      ...syncRequest,
      project_id: projectId
    });
    return response.data;
  },
  
  // 从LightRAG导入
  importFromLightRAG: async (projectId: string): Promise<GraphSyncResult> => {
    console.log(`[Graph API] 从LightRAG导入图谱数据`);
    const response = await apiClient.post<GraphSyncResult>(`/graph/projects/${projectId}/import-from-lightrag`);
    return response.data;
  },
  
  // 导出图谱
  exportGraph: async (projectId: string, exportRequest: GraphExportRequest): Promise<{ download_url: string; message: string }> => {
    console.log(`[Graph API] 导出图谱:`, exportRequest);
    const response = await apiClient.post<{ download_url: string; message: string }>(`/graph/projects/${projectId}/export`, {
      ...exportRequest,
      project_id: projectId
    });
    return response.data;
  },
  
  // 导入图谱
  importGraph: async (projectId: string, importRequest: GraphImportRequest): Promise<GraphSyncResult> => {
    console.log(`[Graph API] 导入图谱:`, importRequest);
    const response = await apiClient.post<GraphSyncResult>(`/graph/projects/${projectId}/import`, {
      ...importRequest,
      project_id: projectId
    });
    return response.data;
  },
  
  // 获取图谱建议（用于问答和聊天）
  getGraphSuggestions: async (projectId: string): Promise<{ nodes: any[]; relationships: any[] }> => {
    console.log(`[Graph API] 获取图谱建议`);
    const response = await apiClient.get<{ nodes: any[]; relationships: any[] }>(`/graph/projects/${projectId}/suggestions`);
    return response.data;
  }
}; 