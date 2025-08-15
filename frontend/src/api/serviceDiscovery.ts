/**
 * 服务发现客户端
 * 通过后端API获取服务信息和WebSocket端点
 */

import { apiClient } from './client';

export interface ServiceInstance {
  service_name: string;
  service_id: string;
  host: string;
  port: number;
  metadata: Record<string, any>;
  endpoints: Record<string, string>;
  websocket_endpoints: Record<string, string>;
  health_status: string;
  health_check_endpoint?: string;
}

export interface ServiceDiscoveryResponse {
  services: Record<string, ServiceInstance[]>;
}

/**
 * 获取所有注册的服务
 */
export async function getAllServices(): Promise<Record<string, ServiceInstance[]>> {
  try {
    const response = await apiClient.get('/api/services/discovery/all');
    if (response.data && response.data.services) {
      return response.data.services;
    }
    return {};
  } catch (error) {
    console.error('[Service Discovery] 获取所有服务失败:', error);
    return {};
  }
}

/**
 * 获取指定服务的实例列表
 */
export async function getServiceInstances(serviceName: string, healthyOnly = true): Promise<ServiceInstance[]> {
  try {
    const response = await apiClient.get(`/api/services/discovery/${serviceName}`, {
      params: { healthy_only: healthyOnly }
    });
    
    if (response.data && Array.isArray(response.data)) {
      return response.data;
    }
    return [];
  } catch (error) {
    console.error(`[Service Discovery] 获取服务 ${serviceName} 实例失败:`, error);
    return [];
  }
}

/**
 * 获取服务的WebSocket URL
 */
export async function getServiceWebSocketUrl(
  serviceName: string, 
  endpointName: string,
  pathParams?: Record<string, string>
): Promise<string | null> {
  try {
    const instances = await getServiceInstances(serviceName, true);
    
    if (instances.length === 0) {
      console.warn(`[Service Discovery] 没有找到健康的 ${serviceName} 服务实例`);
      return null;
    }
    
    // 选择第一个健康的实例
    const instance = instances[0];
    const wsEndpoints = instance.websocket_endpoints || {};
    
    if (!wsEndpoints[endpointName]) {
      console.warn(`[Service Discovery] 服务 ${serviceName} 没有 WebSocket 端点: ${endpointName}`);
      return null;
    }
    
    let endpointPath = wsEndpoints[endpointName];
    
    // 替换路径参数
    if (pathParams) {
      Object.entries(pathParams).forEach(([key, value]) => {
        endpointPath = endpointPath.replace(`{${key}}`, value);
      });
    }
    
    // 构建WebSocket URL
    const protocol = instance.port === 443 ? 'wss' : 'ws';
    const portSuffix = (instance.port === 80 || instance.port === 443) ? '' : `:${instance.port}`;
    
    return `${protocol}://${instance.host}${portSuffix}${endpointPath}`;
    
  } catch (error) {
    console.error(`[Service Discovery] 获取 ${serviceName}/${endpointName} WebSocket URL 失败:`, error);
    return null;
  }
}

/**
 * 获取服务的HTTP URL
 */
export async function getServiceUrl(serviceName: string): Promise<string | null> {
  try {
    const instances = await getServiceInstances(serviceName, true);
    
    if (instances.length === 0) {
      console.warn(`[Service Discovery] 没有找到健康的 ${serviceName} 服务实例`);
      return null;
    }
    
    // 选择第一个健康的实例
    const instance = instances[0];
    
    // 构建HTTP URL
    const protocol = instance.port === 443 ? 'https' : 'http';
    const portSuffix = (instance.port === 80 || instance.port === 443) ? '' : `:${instance.port}`;
    
    return `${protocol}://${instance.host}${portSuffix}`;
    
  } catch (error) {
    console.error(`[Service Discovery] 获取 ${serviceName} HTTP URL 失败:`, error);
    return null;
  }
}

/**
 * WebSocket端点映射
 * 定义不同服务的WebSocket端点名称
 */
export const WS_ENDPOINTS = {
  fileproc: {
    progress: 'progress',
    status: 'status'
  },
  graph: {
    graph: 'graph',
    updates: 'updates'
  },
  monitoring: {
    admin: 'monitoring',
    project: 'project'
  }
} as const;

/**
 * 获取FileProc服务的进度WebSocket URL
 */
export async function getFileProcessWebSocketUrl(projectId: string): Promise<string | null> {
  const fallbackUrl = `ws://localhost:8005/api/ws/progress/${projectId}`;
  
  try {
    const url = await getServiceWebSocketUrl('fileproc', WS_ENDPOINTS.fileproc.progress, { project_id: projectId });
    return url || fallbackUrl;
  } catch (error) {
    console.warn('[Service Discovery] 使用回退URL for FileProc WebSocket:', fallbackUrl);
    return fallbackUrl;
  }
}

/**
 * 获取Graph服务的图谱WebSocket URL
 */
export async function getGraphWebSocketUrl(projectId: string): Promise<string | null> {
  const fallbackUrl = `ws://localhost:8003/api/ws/graph/${projectId}`;
  
  try {
    const url = await getServiceWebSocketUrl('graph', WS_ENDPOINTS.graph.graph, { project_id: projectId });
    return url || fallbackUrl;
  } catch (error) {
    console.warn('[Service Discovery] 使用回退URL for Graph WebSocket:', fallbackUrl);
    return fallbackUrl;
  }
}

/**
 * 获取Monitoring服务的监控WebSocket URL
 */
export async function getMonitoringWebSocketUrl(type: 'admin' | 'project', projectId?: string): Promise<string | null> {
  if (type === 'admin') {
    const fallbackUrl = 'ws://localhost:8008/api/ws/monitoring/admin';
    
    try {
      const url = await getServiceWebSocketUrl('monitoring', WS_ENDPOINTS.monitoring.admin);
      return url || fallbackUrl;
    } catch (error) {
      console.warn('[Service Discovery] 使用回退URL for Monitoring Admin WebSocket:', fallbackUrl);
      return fallbackUrl;
    }
  } else {
    if (!projectId) {
      throw new Error('Project ID is required for project monitoring');
    }
    
    const fallbackUrl = `ws://localhost:8008/api/ws/monitoring/project/${projectId}`;
    
    try {
      const url = await getServiceWebSocketUrl('monitoring', WS_ENDPOINTS.monitoring.project, { project_id: projectId });
      return url || fallbackUrl;
    } catch (error) {
      console.warn('[Service Discovery] 使用回退URL for Monitoring Project WebSocket:', fallbackUrl);
      return fallbackUrl;
    }
  }
}