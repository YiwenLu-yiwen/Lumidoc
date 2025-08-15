import { apiClient } from './client'
import { ApiResponse } from '../types/api';

export interface Question {
  id: string;
  project_id: string;
  content: string;
  created_at: string;
  updated_at: string;
  status: string;
}

export interface Answer {
  id: string;
  question_id: string;
  content: string;
  sources?: string[];
  created_at: string;
  confidence?: number;
}

export interface QuestionWithAnswers extends Question {
  answers: Answer[];
}

export const questionApi = {
  // 获取项目的所有问题
  listQuestions: async (projectId: string): Promise<Question[]> => {
    const response = await apiClient.get<Question[]>(`/projects/${projectId}/questions`);
    return response.data;
  },
  
  // 获取单个问题及其答案
  getQuestion: async (projectId: string, questionId: string): Promise<QuestionWithAnswers> => {
    const response = await apiClient.get<QuestionWithAnswers>(`/projects/${projectId}/questions/${questionId}`);
    return response.data;
  },
  
  // 创建新问题
  createQuestion: async (projectId: string, content: string): Promise<Question> => {
    const response = await apiClient.post<Question>(`/projects/${projectId}/questions`, { content });
    return response.data;
  },
  
  // 回答问题
  answerQuestion: async (projectId: string, questionId: string): Promise<Answer> => {
    const response = await apiClient.post<Answer>(`/projects/${projectId}/questions/${questionId}/answer`);
    return response.data;
  },
  
  // 直接提问并获取答案
  askQuestion: async (projectId: string, content: string): Promise<Answer> => {
    const response = await apiClient.post<Answer>(`/projects/${projectId}/ask`, { content });
    return response.data;
  },
  
  // 删除问题
  deleteQuestion: async (projectId: string, questionId: string): Promise<ApiResponse> => {
    const response = await apiClient.delete<ApiResponse>(`/projects/${projectId}/questions/${questionId}`);
    return response.data;
  }
}; 