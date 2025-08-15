import { apiClient } from './client';
import { ChatRequest, ChatResponse, ChatSession, ApiResponse, GraphAnalysisRequest } from '../types/api';

export const chatApi = {
  // 发送消息
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat/message', request);
    return response.data;
  },

  // 获取会话列表
  listSessions: async (): Promise<ChatSession[]> => {
    const response = await apiClient.get<ChatSession[]>('/chat/sessions');
    return response.data;
  },

  // 获取特定会话
  getSession: async (sessionId: string): Promise<ChatSession> => {
    const response = await apiClient.get<ChatSession>(`/chat/sessions/${sessionId}`);
    return response.data;
  },

  // 删除会话
  deleteSession: async (sessionId: string): Promise<ApiResponse> => {
    const response = await apiClient.delete<ApiResponse>(`/chat/sessions/${sessionId}`);
    return response.data;
  },

  // 清空所有会话
  clearSessions: async (): Promise<ApiResponse> => {
    const response = await apiClient.delete<ApiResponse>('/chat/sessions');
    return response.data;
  },

  // 获取聊天历史
  getChatHistory: async (projectId: string): Promise<ChatResponse[]> => {
    const response = await apiClient.get<ChatResponse[]>(`/chat/history/${projectId}`);
    return response.data;
  },

  // 清空聊天历史
  clearChatHistory: async (projectId: string): Promise<ApiResponse> => {
    const response = await apiClient.delete<ApiResponse>(`/chat/history/${projectId}`);
    return response.data;
  },
  
  // 知识框架分析
  analyzeKnowledgeFramework: async (request: GraphAnalysisRequest): Promise<any> => {
    const response = await apiClient.post('/chat/knowledge_framework', request);
    return response.data;
  }
}; 