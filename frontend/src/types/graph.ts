// 图谱相关的TypeScript类型定义
// 确保与Neo4j数据模型和后端GraphNode/GraphEdge兼容

export interface GraphEntity {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  // 可视化相关属性
  x?: number;
  y?: number;
  size?: number;
  color?: string;
  // 项目隔离
  project_id: string;
  // 元数据
  created_at?: string;
  updated_at?: string;
  source_document?: string;
  confidence?: number;
}

export interface GraphRelationship {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  // 可视化相关属性
  width?: number;
  color?: string;
  // 项目隔离
  project_id: string;
  // 元数据
  created_at?: string;
  updated_at?: string;
  source_document?: string;
  confidence?: number;
}

export interface GraphData {
  nodes: GraphEntity[];
  edges: GraphRelationship[];
  // 图谱元数据
  metadata?: {
    total_nodes: number;
    total_edges: number;
    node_types: string[];
    edge_types: string[];
    last_updated: string;
    project_id: string;
  };
}

// 图谱查询相关类型
export interface GraphQuery {
  project_id: string;
  query_type: 'cypher' | 'neighbors' | 'path' | 'subgraph';
  query: string;
  parameters?: Record<string, any>;
  limit?: number;
  offset?: number;
}

export interface GraphQueryResult {
  success: boolean;
  data: GraphData;
  query: string;
  execution_time: number;
  total_count: number;
  message?: string;
}

// 节点和边的创建/更新类型
export interface EntityCreateRequest {
  label: string;
  type: string;
  properties?: Record<string, any>;
  project_id: string;
  source_document?: string;
  confidence?: number;
}

export interface EntityUpdateRequest {
  label?: string;
  type?: string;
  properties?: Record<string, any>;
  confidence?: number;
}

export interface RelationshipCreateRequest {
  source: string;
  target: string;
  label: string;
  type: string;
  properties?: Record<string, any>;
  project_id: string;
  source_document?: string;
  confidence?: number;
}

export interface RelationshipUpdateRequest {
  source?: string;
  target?: string;
  label?: string;
  type?: string;
  properties?: Record<string, any>;
  confidence?: number;
}

// 图谱分析相关类型
export interface GraphAnalysisRequest {
  project_id: string;
  analysis_type: 'centrality' | 'clustering' | 'path_analysis' | 'subgraph_extraction';
  parameters?: Record<string, any>;
}

export interface GraphAnalysisResult {
  analysis_type: string;
  results: Record<string, any>;
  visualization_data?: GraphData;
  insights: string[];
}

// 图谱可视化配置
export interface GraphVisualizationConfig {
  layout: 'force' | 'hierarchical' | 'circular' | 'random';
  node_size_field?: string;
  node_color_field?: string;
  edge_width_field?: string;
  edge_color_field?: string;
  show_labels: boolean;
  show_node_details: boolean;
  show_edge_details: boolean;
  filter_by_node_type?: string[];
  filter_by_edge_type?: string[];
}

// 图谱统计信息
export interface GraphStatistics {
  project_id: string;
  total_nodes: number;
  total_edges: number;
  node_types: Array<{
    type: string;
    count: number;
    percentage: number;
  }>;
  edge_types: Array<{
    type: string;
    count: number;
    percentage: number;
  }>;
  degree_distribution: Array<{
    degree: number;
    count: number;
  }>;
  connected_components: number;
  average_clustering_coefficient: number;
  graph_density: number;
}

// 图谱导入/导出相关类型
export interface GraphImportRequest {
  project_id: string;
  source_type: 'neo4j' | 'lightrag' | 'csv' | 'json';
  data: any;
  merge_strategy: 'replace' | 'merge' | 'append';
}

export interface GraphExportRequest {
  project_id: string;
  format: 'neo4j' | 'graphml' | 'csv' | 'json';
  include_metadata: boolean;
}

// 图谱搜索相关类型
export interface GraphSearchRequest {
  project_id: string;
  search_term: string;
  search_type: 'nodes' | 'edges' | 'both';
  search_fields: string[];
  limit?: number;
}

export interface GraphSearchResult {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
  total_count: number;
  search_term: string;
}

// 图谱同步相关类型
export interface GraphSyncRequest {
  project_id: string;
  sync_source: 'lightrag' | 'neo4j';
  sync_type: 'full' | 'incremental';
  conflict_resolution: 'overwrite' | 'merge' | 'skip';
}

export interface GraphSyncResult {
  success: boolean;
  synced_nodes: number;
  synced_edges: number;
  conflicts: number;
  errors: string[];
  message: string;
}