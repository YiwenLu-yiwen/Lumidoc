import { apiClient } from './client';

export interface User {
  id: number;
  username: string;
  nickname: string;
}

export interface LoginResponse {
  id: number;
  username: string;
  nickname: string;
  access_token: string;
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
    // 使用JSON格式登录，调用新的 /api/auth/login 端点
    const response = await apiClient.post<LoginResponse>('/api/auth/login', {
      username,
      password
    });
    
    // 保存token到本地存储
    if (response.data.access_token) {
      localStorage.setItem('stp_token', response.data.access_token);
    }
    
    return response.data;
  },
  
  // 刷新token
  refreshToken: async (): Promise<{access_token: string}> => {
    const response = await apiClient.post<{access_token: string}>('/auth/refresh_token');
    if (response.data.access_token) {
      localStorage.setItem('stp_token', response.data.access_token);
    }
    return response.data;
  },
  
  // 重置密码
  resetPassword: async (username: string, newPassword: string): Promise<{message: string}> => {
    const response = await apiClient.post<{message: string}>('/auth/reset_password', {
      username,
      new_password: newPassword
    });
    return response.data;
  },
  
  // 退出登录
  logout: (): void => {
    localStorage.removeItem('stp_token');
  }
}; 