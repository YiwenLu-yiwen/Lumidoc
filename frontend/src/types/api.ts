// 这个文件对应后端的共享类型库
// 确保字段命名和类型与后端一致

// API响应基本类型
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
}

export interface ErrorResponse {
  success: boolean;
  error: string;
  code?: number;
  details?: Record<string, any>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// 用户相关类型
export enum UserRole {
  ADMIN = "admin",
  USER = "user",
  GUEST = "guest"
}

export enum UserStatus {
  ACTIVE = "active",
  INACTIVE = "inactive",
  SUSPENDED = "suspended"
}

export interface UserBase {
  username: string;
  email: string;
}

export interface UserCreate extends UserBase {
  password: string;
}

export interface UserUpdate {
  username?: string;
  email?: string;
  password?: string;
  role?: UserRole;
  status?: UserStatus;
}

export interface UserResponse extends UserBase {
  id: string;
  created_at: string; // ISO日期字符串
  last_login?: string; // ISO日期字符串
  role: UserRole;
  status: UserStatus;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// 聊天相关类型
export interface ChatMessage {
  role: string;
  content: string;
  timestamp?: number;
}

export interface ChatSession {
  session_id: string;
  project_id?: string;
  messages: ChatMessage[];
  created_at?: string;
  updated_at?: string;
  graph_analysis?: Record<string, any>;
}

export interface ChatRequest {
  content: string;
  project_id?: string;
  user_id?: string;
  session_id?: string;
  use_stream?: boolean;
}

export interface ChatResponse {
  response: string;
  session_id: string;
}

// 项目相关类型
export enum ProjectStatus {
  ACTIVE = "active",
  ARCHIVED = "archived",
  DELETED = "deleted"
}

export interface ProjectBase {
  name: string;
  description?: string;
}

export interface ProjectCreate extends ProjectBase {}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: ProjectStatus;
}

export interface ProjectResponse extends ProjectBase {
  id: string;
  created_at: string; // ISO日期字符串
  updated_at: string; // ISO日期字符串
  status: ProjectStatus;
}

// 文件相关类型
export enum FileStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
  UNKNOWN = "unknown"  // 添加未知状态，用于初始状态或状态未定义时
}

export interface FileUploadResponse {
  file_path: string;
  task_id: string;
  success: boolean;
  message: string;
  exists?: boolean;  // 文件是否已存在
  filename?: string; // 文件名
  file_id?: string;  // 文件ID
  size?: number;     // 文件大小
  content_type?: string; // 文件类型
  upload_time?: string;  // 上传时间
}

export interface FileInfo {
  filename: string;
  display_name?: string;
  size: number;
  file_type: string;
  file_hash?: string;
  created_at?: string;
  updated_at?: string;
  status?: FileStatus;
}

export interface FileProcessRequest {
  file_id: string;
  project_id?: string;
  options?: Record<string, any>;
}

// 图谱相关类型
export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  properties: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphAnalysisRequest {
  query: string;
  project_id?: string;
  context?: Record<string, any>;
}

// 知识框架分析类型
export interface KnowledgeFrameworkRequest {
  project_id: string;
  query: string;
}

export interface KnowledgeFrameworkResponse {
  query: string;
  knowledge_framework_analysis: string;
  related_documents_count: number;
  graph_node_count: number;
  graph_edge_count: number;
  has_graph_data: boolean;
} 