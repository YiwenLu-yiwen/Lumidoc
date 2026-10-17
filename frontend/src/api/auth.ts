import { apiClient } from './client';
import { isAxiosError } from 'axios';

export interface User {
  id: number;
  username: string;
  nickname: string;
  avatar?: string;
  email?: string;
}

export interface LoginResponse {
  email?: string;
  is_active: boolean;
  is_superuser: boolean;
  id: number;
  username: string;
  nickname: string;
  access_token: string;
  detail?: string;
}

export interface RegisterResponse {
  id: number;
  username: string;
  nickname: string;
}

export const authApi = {
  // 用户注册
  register: async (username: string, password: string, email: string, nickname?: string): Promise<RegisterResponse> => {
    const response = await apiClient.post<RegisterResponse>('/api/auth/register', {
      username,
      password,
      email,
      nickname
    });
    return response.data;
  },
  
  // 用户登录
  login: async (username: string, password: string): Promise<LoginResponse> => {
    try {
      // 使用JSON格式登录，调用新的 /api/auth/login 端点
      const response = await apiClient.post<LoginResponse>('/api/auth/login', {
        username,
        password
      });
      
      // 检查响应状态，如果是401则抛出错误
      if (response.status === 401) {
        throw new Error(response.data?.detail || '账号或密码错误');
      }
      
      // 检查响应数据是否包含错误信息（处理401作为成功响应的情况）
      if (response.data && typeof response.data === 'object' && 'detail' in response.data) {
        throw new Error(String(response.data.detail || '登录失败'));
      }
      
      // 确保响应包含必需的字段
      if (!response.data || !response.data.access_token) {
        throw new Error('登录响应数据不完整');
      }
      
      // 保存token到本地存储
      localStorage.setItem('lumidoc_token', response.data.access_token);
      
      return response.data;
    } catch (error: unknown) {
      // 如果是axios错误，提取错误信息
      if (isAxiosError(error) && error.response) {
        const errorMessage = error.response.data?.detail || '账号或密码错误';
        throw new Error(String(errorMessage));
      }
      // 重新抛出其他错误
      throw error;
    }
  },
  
  // 刷新token
  refreshToken: async (): Promise<{access_token: string}> => {
    const response = await apiClient.post<{access_token: string}>('/auth/refresh_token');
    if (response.data.access_token) {
      localStorage.setItem('lumidoc_token', response.data.access_token);
    }
    return response.data;
  },
  
  // 重置密码
  resetPassword: async (
    username: string,
    currentPassword: string,
    newPassword: string
  ): Promise<{message: string}> => {
    const response = await apiClient.post<{message: string}>('/auth/reset_password', {
      username,
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  },
  
  // 退出登录
  logout: (): void => {
    localStorage.removeItem('lumidoc_token');
  }
};
