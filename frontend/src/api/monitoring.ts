import { apiClient } from './client';

export interface HealthStatus {
  status: string;
  metrics?: {
    timestamp: string;
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
    process_memory_percent: number;
  };
}

export interface LiveStatus {
  status: string;
}

export interface ReadyStatus {
  status: string;
}

export const monitoringApi = {
  // 健康状态检查
  checkHealth: async (): Promise<HealthStatus> => {
    const response = await apiClient.get<HealthStatus>('/health');
    return response.data;
  },
  
  // 存活探针
  checkLiveness: async (): Promise<LiveStatus> => {
    const response = await apiClient.get<LiveStatus>('/health/live');
    return response.data;
  },
  
  // 就绪探针
  checkReadiness: async (): Promise<ReadyStatus> => {
    const response = await apiClient.get<ReadyStatus>('/health/ready');
    return response.data;
  }
}; 